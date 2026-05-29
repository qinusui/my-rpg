import json
import os
import sys
import random
import subprocess

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from world_loader import world_file

from state_core import (
    STATE_FILE,
    OPTIONS_LOCK,
    ROOT,
    BG_PY_PATH,
    get_active_world,
    get_default_state,
    get_encounter_tables,
    get_threshold_rules,
    get_character_options,
    _find_by_id,
    _get_goal_definition,
)

if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from engine.state import compute_flags, attr_modifier, migrate_inventory, load_state, save_state
from engine.dice import generate_oracle
from engine.sentinel_keys import BG_SWITCH_TARGET
from world_db import lookup_npc, lookup_location, add_npc, _load_world_constants, _save_world_constants
from view import view_state, _render_view_text, list_inventory, _print_location_info, _auto_bg_set
from config_loader import load_config as _load_cfg, save_config as _save_cfg


def _flush_bg_switch():
    """Pop and dispatch any pending background switch from state."""
    from bg_client import dispatch_from_target

    st = load_state()
    bg_target = st.pop(BG_SWITCH_TARGET, None)
    if bg_target:
        dispatch_from_target(bg_target)


def _parse_env_events(engine_output, result):
    """Parse encounter/omen events from engine output into result dict (mutated in place)."""
    env_events = engine_output.get("context", {}).get("environment", {}).get("events", [])
    turn = engine_output.get("context", {}).get("engine", {}).get("turn_count", 0)
    for event in env_events:
        if event.startswith("遭遇触发:"):
            monster = event.split(":", 1)[1].strip()
            result["encounter"] = {"monster": monster, "turn": turn}
        if event.startswith("征兆:"):
            result["omen"] = event.split(":", 1)[1].strip()


def _build_turn_output(engine_output, include_view=False):
    """Build common turn output dict from engine_output."""
    ctx = engine_output.get("context", {})
    env = ctx.get("environment", {})
    result = {
        "encounter": None,
        "omen": None,
        "danger": env.get("danger"),
        "deferred_encounter": env.get("deferred_encounter"),
        "flags": ctx.get("flags", []),
        "next_oracle": {
            "value": env.get("oracle_result"),
            "consumed": False,
        },
        "engine_narrator_context": engine_output,
    }
    if include_view:
        result["turn"] = ctx.get("engine", {}).get("turn_count", 0)
        result["view"] = _render_view_text(load_state())
    return result


# ── inventory helpers ──────────────────────────────────────

def _next_item_id(state):
    existing = [int(it["id"].split("_")[1]) for it in state["inventory"]]
    return f"item_{max(existing) + 1:03d}" if existing else "item_001"


def _lookup_item_effect(name):
    """Look up an item's effect from the active world's items.json. Returns effect text or None."""
    try:
        items_path = world_file("items.json")
        with open(items_path, "r", encoding="utf-8") as f:
            items = json.load(f)
        for category in ("quest_items", "legendary"):
            entry = items.get(category, {}).get(name, {})
            if isinstance(entry, dict) and entry:
                return entry.get("effect") or entry.get("property")
        return None
    except (FileNotFoundError, json.JSONDecodeError):
        return None


# ── Origin essential registration (NPCs, affinity, inventory) ────────


def _get_origin_essentials(origin_key):
    """返回起源绑定的人物、物品和初始位置。从世界常量读取。"""
    wc = _load_world_constants()
    mapping = wc.get("origin_essentials", {})
    return mapping.get(origin_key, {"npcs": [], "inventory_keys": [], "initial_location": None})


def _register_origin_essentials(state, origin_key):
    """当选定起源后，自动注册 NPC、建立亲和度、添加初始物品。不覆盖已有数据。"""
    essentials = _get_origin_essentials(origin_key)
    if not essentials:
        return

    known_npcs = state.setdefault("known_npcs", [])
    affinities = state.setdefault("affinities", {})
    inventory = state.setdefault("inventory", [])

    registered = []
    for npc_key in essentials.get("npcs", []):
        if npc_key not in known_npcs:
            known_npcs.append(npc_key)
            if npc_key not in affinities:
                affinities[npc_key] = {"level": "close", "milestones": [f"origin:{origin_key}"]}
            registered.append(npc_key)

    # Process inventory keys from origin essentials
    for item_key in essentials.get("inventory_keys", []):
        item_name = item_key
        try:
            items_path = world_file("items.json")
            with open(items_path, "r", encoding="utf-8") as f:
                items_db = json.load(f)
            item_def = items_db.get(item_key, {})
            item_name = item_def.get("name", item_key)
        except (FileNotFoundError, json.JSONDecodeError):
            pass
        existing = next((it for it in inventory if it["name"] == item_name), None)
        if existing:
            existing["qty"] += 1
        else:
            new_id = _next_item_id(state)
            inventory.append({
                "id": new_id,
                "name": item_name,
                "qty": 1,
                "tags": [item_key],
            })

    # Set initial location if provided
    if essentials.get("initial_location"):
        old_loc = state.get("current_location")
        state["current_location"] = essentials["initial_location"]
        if old_loc and old_loc != essentials["initial_location"]:
            print(f"[origin:{origin_key}] 初始位置已设置: {old_loc} → {essentials['initial_location']}")

    if registered:
        print(f"[origin:{origin_key}] 自动注册人物: {', '.join(registered)}")
    changed = True


# ── CLI ────────────────────────────────────────────────────

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

    raw_args = sys.argv[1:]

    # --list_inventory handled before argparse (supports --tag)
    list_mode = "--list_inventory" in raw_args
    list_tag = None
    if list_mode:
        for i, a in enumerate(raw_args):
            if a == "--tag" and i + 1 < len(raw_args):
                list_tag = raw_args[i + 1]
                break
    if list_mode:
        s = load_state()
        list_inventory(s, tag_filter=list_tag)
        sys.exit(0)

    # --clear_encounter handled before argparse
    if "--clear_encounter" in raw_args:
        s = load_state()
        s["pending_encounter"] = None
        loc = s.get("current_location", "")
        dangers = s.get("location_dangers", {})
        dangers[loc] = 0
        s["location_dangers"] = dangers
        save_state(s)
        print(json.dumps({"cleared": True}, ensure_ascii=False))
        sys.exit(0)

    import argparse

    parser = argparse.ArgumentParser(description="RPG State Manager")
    parser.add_argument("--init", action="store_true", help="初始化 state.json")
    parser.add_argument("--view", action="store_true", help="查看当前状态")
    parser.add_argument("--action", action="store_true", help="玩家行动：d20+回合推进+状态视图 (合并 --d20 + --tick --with-view)")
    parser.add_argument("--resolve_options", action="store_true", help="解除选项锁：确认选项已呈现并已被玩家选择，允许下一次 --action")
    parser.add_argument("--tick", action="store_true", help="回合数 +1 (JSON 输出)")
    parser.add_argument("--with-view", action="store_true",
                        help="--tick 输出中附带格式化状态视图")
    parser.add_argument(
        "--update", nargs=2, metavar=("key", "val"), help="更新属性增量"
    )
    parser.add_argument(
        "--set", nargs=2, metavar=("key", "val"), help="设置非属性字段"
    )
    # Inventory
    parser.add_argument("--add_item", nargs="+", help="添加物品")
    parser.add_argument("--qty", type=int, default=1)
    parser.add_argument("--tags", help="标签逗号分隔")
    parser.add_argument("--use_item", help="消耗物品 (按 id)")
    parser.add_argument("--drop_item", help="丢弃物品 (按 id)")
    # Clues / history
    parser.add_argument("--add_clue", nargs="+", help="添加线索")
    parser.add_argument("--add_history", nargs="+", help="记录一条历史摘要")
    parser.add_argument("--d20", action="store_true", help="掷一个d20骰子")
    parser.add_argument("--attr", help="指定适用属性，多属性用逗号分隔取平均 (strength,agility)")
    parser.add_argument("--mod", type=int, default=0, help="DM 局势修正 (掷骰前宣告，装备/环境/优势)")
    parser.add_argument("--dc", type=int, default=15, help="难度等级 DC (10=简单, 15=中等, 20=困难)")
    parser.add_argument("--reason", help="DM 干预理由（配合 --set/--update 使用，写入 dm_log）")
    parser.add_argument("--mark", help="指定适用的印记名称，引擎自动查找加值")
    parser.add_argument("--action-tags", nargs="+", help="行动上下文标签，用于遭遇池过滤 (social/combat/patrol/ritual/rest)")
    # Tarot / faith
    parser.add_argument("--belief", choices=["faith", "none"], help="信仰路线：切换 D20/Tarot 判定系统")
    parser.add_argument("--set-belief", metavar="VALUE", choices=["faith", "none"],
                        help="设置信仰状态（faith=tarot, none=d20）")
    # Phase detection
    parser.add_argument("--detect-phase", action="store_true", help="检测当前活跃阶段文件（用于非 --action 场景，如初始化后）")
    # Marks
    parser.add_argument("--add_mark", help="添加印记")
    parser.add_argument("--mark_bonus", type=int, choices=[1, 2], help="印记加值 (+1 或 +2)")
    parser.add_argument("--mark_context", help="印记适用场景描述")
    # Future seeds
    parser.add_argument("--seed_branch", nargs="+", help="为分支选项预写叙事种子 (JSON 行)")
    parser.add_argument("--get_seed", type=int, help="提取指定分支的预写种子")
    # World constants
    parser.add_argument("--add_npc", help="添加NPC到世界常数库")
    parser.add_argument("--traits", help="NPC特征 (逗号分隔)")
    parser.add_argument("--quirk", help="NPC怪癖/口头禅")
    parser.add_argument("--voice", help="NPC声音描述")
    parser.add_argument("--lookup_npc", help="查询NPC特征 (模糊搜索)")
    parser.add_argument("--lookup_location", help="查询地点感官细节 (模糊搜索)")
    # Custom Attribute Clocks
    parser.add_argument("--create_attr", help="创建自定义属性钟（可用 --d20 检定）")
    parser.add_argument("--attr_max", type=int, default=6, help="属性钟满格值 (默认6)")
    parser.add_argument("--direction", choices=["up", "down"], default="up", help="方向: up=更多更强, down=更多更弱")
    # Progress Clocks
    parser.add_argument("--create_clock", help="创建一个进度钟")
    parser.add_argument("--clock_max", type=int, default=4, help="钟的满格值 (默认4)")
    parser.add_argument("--consequence", help="钟满格时的后果描述")
    parser.add_argument("--tick_clock", help="推进指定进度钟 1 格")
    parser.add_argument("--set_clock", nargs=2, metavar=("clock_name", "value"), help="直接设置钟的当前值")
    parser.add_argument("--reset_clock", help="重置指定钟到 0")
    # Injury
    parser.add_argument("--set_injury", help="设置伤残状态 (类型名)")
    parser.add_argument("--injury_ticks", type=int, default=5, help="伤残持续 tick 数")
    parser.add_argument("--injury_penalty", type=int, default=3, help="伤残 DC 惩罚")
    parser.add_argument("--heal", action="store_true", help="支付代价治愈伤残")
    # Knowledge firewall
    parser.add_argument("--learn_fragment", type=int, help="标记王冠碎片为已知 (1-8)")
    parser.add_argument("--learn_npc", help="标记NPC为已知 (NPC名称)")
    parser.add_argument("--reveal_lore", help="标记文献/真相为已揭示 (文献名)")
    # Goal system
    parser.add_argument("--set_background", help="设置角色过往")
    parser.add_argument("--set_goal", nargs="+", help="设置当前目标 (名称 + JSON属性)")
    parser.add_argument("--tick_goal_clock", action="store_true", help="推进目标时钟 1 格")
    parser.add_argument("--complete_goal", action="store_true", help="标记当前目标为已完成")
    parser.add_argument("--goal_location", help="完成守护目标时，被守护的地点 key")
    parser.add_argument("--goal_npc", help="完成寻找目标时，找到的 NPC 名称")
    parser.add_argument("--goal_lore", help="完成揭秘目标时，揭示的文献 key")
    parser.add_argument("--fail_goal", action="store_true", help="标记当前目标为已失败")
    parser.add_argument("--finale_goal", action="store_true", help="终结行动：掷 1d6+进度 vs DC，尝试完成目标")
    parser.add_argument("--set_oath", type=str, help="为目标写入誓言措辞（玩家的原话）")
    parser.add_argument("--oracle", action="store_true", help="神谕骰：掷 1d6，返回世界专属诠释")
    parser.add_argument("--consume_oracle", action="store_true", help="标记 next_oracle 已消耗，下次 tick 生成新神谕")
    parser.add_argument("--face_desolation", action="store_true", help="Face Desolation 判定：spirit 满格时的终结掷骰")
    parser.add_argument("--set_truth", nargs=2, metavar=("dimension", "choice"),
                        help="设置 world_truths 维度 (如: brewer_understanding B)")
    # NPC Affinity / Relationships
    parser.add_argument("--affinity", nargs="*", help="查询或设置 NPC 关系 (name [level])。无参数列出全部，一个参数查询，两个参数设置")
    parser.add_argument("--milestone", help="关系升级时的里程碑描述（配合 --affinity set 使用）")
    # World Markdown codec
    parser.add_argument("--sync_world_md", action="store_true", help="同步 world_constants.json → world_constants.md")
    # Scene management (inspired by SoloGM chapter/scene hierarchy)
    parser.add_argument("--scene_begin", help="开始新场景 (场景名称)")
    parser.add_argument("--scene_location", help="场景位置 (配合 --scene_begin)")
    parser.add_argument("--scene_end", action="store_true", help="结束当前场景并归档")
    parser.add_argument("--scene_summary", help="场景摘要 (配合 --scene_end)")
    parser.add_argument("--list_scenes", action="store_true", help="列出场景历史")
    # Pending state (pre-computation stash)
    parser.add_argument("--set_pending", nargs=2, metavar=("key", "value"),
                        help="写入暂存值到 _pending (JSON 字符串)")
    parser.add_argument("--flush_pending", action="store_true",
                        help="合并 _pending 到主状态并清空")
    args = parser.parse_args()

    if args.init:
        save_state(dict(get_default_state()))
        print("state.json 已初始化。")
        sys.exit(0)

    if args.view:
        view_state(load_state())
        sys.exit(0)

    if args.list_scenes:
        s = load_state()
        scenes = s.get("scene_history", [])
        active = s.get("active_scene")
        output = {"scene_history": scenes, "total": len(scenes), "active_scene": active}
        print(json.dumps(output, ensure_ascii=False, indent=2))
        sys.exit(0)

    if args.sync_world_md:
        from engine.world_codec import sync as sync_world_md
        result = sync_world_md()
        print(json.dumps(result, ensure_ascii=False))
        sys.exit(0)

    if args.d20:
        roll = random.randint(1, 20)
        if args.attr or args.mod:
            s = load_state() if args.attr else None
            if args.attr and s:
                attr_names = [a.strip() for a in args.attr.split(",")]
                mod_sum = 0
                attr_details = []
                for name in attr_names:
                    clock = s.get("clocks", {}).get(name)
                    if clock:
                        filled, mx = clock["filled"], clock["max"]
                        m = attr_modifier(clock)
                        mod_sum += m
                        attr_details.append({"attr": name, "filled": filled, "max": mx, "mod": m})
                if attr_details:
                    mod = mod_sum // len(attr_details)  # average, truncate toward zero
                else:
                    mod = 0
            else:
                mod = 0
                attr_details = []
            sit = args.mod
            mark_bonus = 0
            mark_name = None
            if args.mark and s:
                for mk in s.get("marks", []):
                    if mk["name"] == args.mark:
                        mark_bonus = mk.get("bonus", 0)
                        mark_name = mk["name"]
                        break
            result = {"roll": roll, "total": roll + mod + sit + mark_bonus}
            if attr_details:
                result["attrs"] = attr_details
                result["modifier"] = mod
            if sit:
                result["situational"] = sit
            if mark_name:
                result["mark"] = {"name": mark_name, "bonus": mark_bonus}
            print(json.dumps(result, ensure_ascii=False))
        else:
            print(roll)
        sys.exit(0)

    if args.set_belief is not None:
        cfg = _load_cfg(force_reload=True)
        old = cfg.get("belief", "none")
        cfg["belief"] = args.set_belief
        _save_cfg(cfg)
        msg = f"信仰路线已切换: tarot (判定系统 = 塔罗)" if args.set_belief == "faith" else "信仰已移除: 恢复 D20 判定"
        print(json.dumps({"belief_set": args.set_belief, "previous": old, "hint": msg}, ensure_ascii=False))
        sys.exit(0)

    if args.action:
        # Apply inline --belief flag (writes to config.json for persistence)
        if args.belief is not None:
            cfg = _load_cfg(force_reload=True)
            old = cfg.get("belief", "none")
            cfg["belief"] = args.belief
            _save_cfg(cfg)
            if args.belief != old:
                print(f"[belief] {old} → {args.belief}", file=sys.stderr)

        # 选项锁：防止连续两次 --action 之间跳过选项
        lock_path = os.path.join(ROOT, OPTIONS_LOCK)
        if os.path.exists(lock_path):
            print(json.dumps({
                "error": "options_lock_active",
                "message": "上轮选项尚未解决。必须先呈现 AskUserQuestion 并等待玩家选择，然后执行 --resolve_options 解锁。",
                "fix": "python .claude/skills/rpg-dm/scripts/tools/state_mgr.py --resolve_options"
            }, ensure_ascii=False))
            sys.exit(1)

        from engine.game_engine import run_turn

        engine_output = run_turn(
            player_action="state_mgr_action",
            action_type="action",
            attr=args.attr,
            situational_mod=args.mod,
            mark=args.mark,
            consume_oracle=False,
            dc=args.dc,
            metadata={"source": ".claude/skills/rpg-dm/scripts/tools/state_mgr.py", "action_tags": args.action_tags or []},
        )

        bridge = _build_turn_output(engine_output, include_view=True)
        _parse_env_events(engine_output, bridge)
        _flush_bg_switch()

        # 写入选项锁，强制 DM 在下一次 --action 前必须呈现选项
        os.makedirs(os.path.dirname(lock_path), exist_ok=True)
        with open(lock_path, "w") as f:
            f.write("1")

        print(json.dumps(bridge, ensure_ascii=False))
        sys.exit(0)

    if args.detect_phase:
        from tools.phase_detection import detect_phases, load_state as pd_load_state

        state = pd_load_state()
        phases = detect_phases(state)
        result = {
            "phases_dir": ".claude/skills/rpg-dm/phases/",
            "active_phases": phases,
            "state_summary": {
                "player_name": state.get("player_name", ""),
                "location": state.get("current_location", ""),
                "has_pending_encounter": bool(state.get("pending_encounter")),
                "has_active_goal": bool(state.get("current_goal")),
            },
        }
        print(json.dumps(result, ensure_ascii=False))
        sys.exit(0)

    if args.resolve_options:
        lock_path = os.path.join(ROOT, OPTIONS_LOCK)
        if os.path.exists(lock_path):
            os.remove(lock_path)
        print(json.dumps({"ok": True, "action": "options_resolved", "message": "锁已解除，可执行下一次 --action"}, ensure_ascii=False))
        sys.exit(0)

    if args.lookup_npc:
        print(json.dumps(lookup_npc(args.lookup_npc), ensure_ascii=False))
        sys.exit(0)

    if args.lookup_location:
        print(json.dumps(lookup_location(args.lookup_location), ensure_ascii=False))
        sys.exit(0)

    if args.add_npc:
        add_npc(args.add_npc, args.traits or "", args.quirk or "", args.voice or "")
        sys.exit(0)

    if args.affinity is not None:
        s = load_state()
        s.setdefault("affinities", {})
        VALID_LEVELS = ["hostile", "wary", "cold", "stranger", "acquaintance", "friend", "close", "intimate"]

        if len(args.affinity) == 0:
            # List all affinities
            print(json.dumps({"affinities": s.get("affinities", {})}, ensure_ascii=False))
        elif len(args.affinity) == 1:
            # Query specific NPC
            name = args.affinity[0]
            entry = s["affinities"].get(name)
            if entry:
                print(json.dumps({"npc": name, **entry}, ensure_ascii=False))
            else:
                print(json.dumps({"npc": name, "level": "stranger", "milestones": []}, ensure_ascii=False))
        else:
            # Set affinity level
            name = args.affinity[0]
            level = args.affinity[1]
            if level not in VALID_LEVELS:
                print(json.dumps({"error": f"Invalid level '{level}'. Valid: {VALID_LEVELS}"}, ensure_ascii=False))
                sys.exit(1)
            entry = s["affinities"].get(name, {"level": "stranger", "milestones": []})
            old_level = entry.get("level", "stranger")
            entry["level"] = level
            if args.milestone:
                entry.setdefault("milestones", []).append(args.milestone)
            s["affinities"][name] = entry
            save_state(s)
            print(json.dumps({
                "affinity_set": name,
                "level": level,
                "previous_level": old_level,
                "milestones": entry.get("milestones", []),
            }, ensure_ascii=False))
        sys.exit(0)

    s = load_state()
    tick_result = None

    # ── --tick (core loop) ──
    if args.tick:
        from engine.game_engine import run_turn

        engine_output = run_turn(
            player_action="state_mgr_tick",
            action_type="tick",
            consume_oracle=False,
            metadata={"source": ".claude/skills/rpg-dm/scripts/tools/state_mgr.py"},
        )

        tick_result = _build_turn_output(engine_output)
        _parse_env_events(engine_output, tick_result)
        _flush_bg_switch()

    changed = args.tick

    if args.update:
        k, v = args.update
        delta = int(v)
        attr_clock = s.setdefault("clocks", {}).get(k)
        if not attr_clock:
            # Auto-create attribute clock with defaults (max=6, filled=3, direction=up)
            s["clocks"][k] = {"max": 6, "filled": 3, "direction": "up", "label": k}
            attr_clock = s["clocks"][k]
        attr_clock["filled"] = max(0, min(attr_clock["max"], attr_clock["filled"] + delta))
        changed = True
        if args.reason:
            s.setdefault("dm_log", []).append({
                "turn": s.get("turn_count", 0),
                "type": "override_update",
                "key": k,
                "delta": delta,
                "reason": args.reason,
            })

    if args.set:
        k, v = args.set
        handled = False
        if k == "equipped_weapon":
            s.setdefault("equipped", {})["weapon"] = v if v != "None" else None
        elif k == "equipped_armor":
            s.setdefault("equipped", {})["armor"] = v if v != "None" else None
        elif k == "current_location":
            s["current_location"] = v
            _print_location_info(v)
            _auto_bg_set(v)
        elif k in ("chapter", "turn_count"):
            s[k] = int(v)
        elif k == "origin":
            _register_origin_essentials(s, v)
            s[k] = v
            changed = True
            if args.reason:
                s.setdefault("dm_log", []).append({
                    "turn": s.get("turn_count", 0),
                    "type": "override_set",
                    "key": k,
                    "value": v,
                    "reason": args.reason,
                })
            handled = True
        if not handled:
            if v in ("null", "None"):
                s[k] = None
            else:
                s[k] = v
            changed = True
            if args.reason:
                s.setdefault("dm_log", []).append({
                "turn": s.get("turn_count", 0),
                "type": "override_set",
                "key": k,
                "value": v,
                "reason": args.reason,
            })

    # ── Inventory ──

    if args.add_item:
        names = " ".join(args.add_item)
        for raw_name in names.replace("\n", ",").split(","):
            name = raw_name.strip()
            if not name:
                continue
            tag_list = [t.strip() for t in (args.tags or "").split(",") if t.strip()]
            existing = None
            for it in s["inventory"]:
                if it["name"] == name:
                    existing = it
                    break
            if existing:
                existing["qty"] += args.qty
                for t in tag_list:
                    if t not in existing["tags"]:
                        existing["tags"].append(t)
                print(json.dumps({"ok": True, "stacked": name, "id": existing["id"], "qty_now": existing["qty"]}, ensure_ascii=False))
            else:
                new_id = _next_item_id(s)
                s["inventory"].append({
                    "id": new_id,
                    "name": name,
                    "qty": args.qty,
                    "tags": tag_list,
                })
                print(json.dumps({"ok": True, "added": name, "id": new_id, "qty": args.qty, "tags": tag_list}, ensure_ascii=False))
        changed = True

    if args.use_item:
        it = _find_by_id(s, args.use_item)
        if not it:
            print(json.dumps({"error": f"物品 {args.use_item} 不存在"}, ensure_ascii=False))
            sys.exit(1)
        it["qty"] -= args.qty
        removed = False
        if it["qty"] <= 0:
            s["inventory"].remove(it)
            removed = True
        result = {"ok": True, "used": args.use_item, "item_name": it["name"],
                  "remaining_qty": 0 if removed else it["qty"],
                  "effect": _lookup_item_effect(it["name"])}
        print(json.dumps(result, ensure_ascii=False))
        changed = True

    if args.drop_item:
        it = _find_by_id(s, args.drop_item)
        if not it:
            print(f"错误: 物品 {args.drop_item} 不存在", file=sys.stderr)
            sys.exit(1)
        it["qty"] -= args.qty
        if it["qty"] <= 0:
            s["inventory"].remove(it)
        changed = True

    # ── Custom Attribute Clocks ──

    if args.create_attr:
        name = args.create_attr
        s.setdefault("clocks", {})[name] = {
            "filled": args.attr_max // 2,  # start at midpoint
            "max": args.attr_max,
            "direction": args.direction,
            "label": name,
        }
        print(json.dumps({
            "attr_created": name,
            "max": args.attr_max,
            "filled": args.attr_max // 2,
            "direction": args.direction,
        }, ensure_ascii=False))
        changed = True

    # ── Progress Clocks ──

    if args.create_clock:
        name = args.create_clock
        s.setdefault("clocks", {})[name] = {
            "current": 0,
            "max": args.clock_max,
            "consequence": args.consequence or "",
        }
        print(json.dumps({
            "clock_created": name,
            "current": 0,
            "max": args.clock_max,
            "consequence": args.consequence or "",
        }, ensure_ascii=False))
        changed = True

    if args.tick_clock:
        name = args.tick_clock
        if name not in s.get("clocks", {}):
            print(json.dumps({"error": f"进度钟 '{name}' 不存在"}, ensure_ascii=False))
            sys.exit(1)
        c = s["clocks"][name]
        c["current"] += 1
        result = {
            "clock_ticked": name,
            "current": c["current"],
            "max": c["max"],
            "filled": c["current"] >= c["max"],
        }
        if result["filled"] and c.get("consequence"):
            result["consequence_triggered"] = c["consequence"]
        print(json.dumps(result, ensure_ascii=False))
        changed = True

    if args.set_clock:
        name, val = args.set_clock
        if name not in s.get("clocks", {}):
            print(json.dumps({"error": f"钟 '{name}' 不存在"}, ensure_ascii=False))
            sys.exit(1)
        c = s["clocks"][name]
        if "filled" in c:
            c["filled"] = int(val)
            cur = c["filled"]
        else:
            c["current"] = int(val)
            cur = c["current"]
        print(json.dumps({
            "clock_set": name,
            "value": cur,
            "max": c["max"],
            "is_full": cur >= c["max"],
        }, ensure_ascii=False))
        changed = True

    if args.reset_clock:
        name = args.reset_clock
        if name not in s.get("clocks", {}):
            print(json.dumps({"error": f"进度钟 '{name}' 不存在"}, ensure_ascii=False))
            sys.exit(1)
        s["clocks"][name]["current"] = 0
        print(json.dumps({"clock_reset": name, "current": 0}, ensure_ascii=False))
        changed = True

    # ── Injury ──

    if args.set_injury:
        s["injury"] = {
            "type": args.set_injury,
            "ticks_remaining": args.injury_ticks,
            "dc_penalty": args.injury_penalty,
        }
        print(json.dumps({"injury_set": s["injury"]}, ensure_ascii=False))
        changed = True

    if args.heal:
        if s.get("injury"):
            old = s["injury"]["type"]
            s["injury"] = None
            print(json.dumps({"healed": True, "was": old}, ensure_ascii=False))
            changed = True
        else:
            print(json.dumps({"healed": False, "reason": "当前无伤残"}, ensure_ascii=False))

    # ── Knowledge firewall ──

    if args.learn_fragment is not None:
        idx = args.learn_fragment
        if idx < 1 or idx > 8:
            print(json.dumps({"error": f"碎片索引 {idx} 越界 (1-8)"}, ensure_ascii=False))
            sys.exit(1)
        known = s.setdefault("known_fragments", [])
        if idx not in known:
            known.append(idx)
            known.sort()
        print(json.dumps({"learned_fragment": idx, "known_fragments": known}, ensure_ascii=False))
        changed = True

    if args.learn_npc:
        name = args.learn_npc
        known = s.setdefault("known_npcs", [])
        if name not in known:
            known.append(name)
        print(json.dumps({"learned_npc": name, "known_npcs": known}, ensure_ascii=False))
        changed = True

    if args.reveal_lore:
        key = args.reveal_lore
        known = s.setdefault("revealed_lore", [])
        if key not in known:
            known.append(key)
        print(json.dumps({"revealed_lore": key, "revealed_lore_all": known}, ensure_ascii=False))
        changed = True

    # ── Goal system ──

    if args.set_background:
        s["background"] = args.set_background
        print(json.dumps({"background_set": args.set_background}, ensure_ascii=False))
        changed = True

    if args.set_goal:
        goal_name_parts = []
        props_json = None
        for part in args.set_goal:
            if part.startswith("{"):
                props_json = part
                break
            goal_name_parts.append(part)
        goal_name = " ".join(goal_name_parts)
        # Defaults from goal definition if available
        goal_def = _get_goal_definition(goal_name)
        def_props = {
            "clock_name": goal_def.get("clock_name", "目标时钟") if goal_def else "目标时钟",
            "clock_max": goal_def.get("clock_max", 4) if goal_def else 4,
            "clock_trigger": goal_def.get("clock_trigger", "") if goal_def else "",
            "dc": goal_def.get("dc", 7) if goal_def else 7,
        }
        if props_json:
            try:
                def_props.update(json.loads(props_json))
            except json.JSONDecodeError:
                pass
        s["active_goal"] = {
            "goal": goal_name,
            "clock_current": 0,
            "clock_max": def_props["clock_max"],
            "clock_name": def_props["clock_name"],
            "clock_trigger": def_props["clock_trigger"],
            "dc": def_props["dc"],
            "oath": def_props.get("oath", ""),
            "failed": False,
            "completed": False,
        }
        print(json.dumps({"goal_set": s["active_goal"]}, ensure_ascii=False))
        changed = True

    if args.tick_goal_clock:
        goal = s.get("active_goal")
        if not goal:
            print(json.dumps({"error": "当前没有激活的目标"}, ensure_ascii=False))
        else:
            goal["clock_current"] = goal.get("clock_current", 0) + 1
            result = {
                "goal_clock_ticked": goal["goal"],
                "current": goal["clock_current"],
                "max": goal["clock_max"],
                "filled": goal["clock_current"] >= goal["clock_max"],
            }
            if result["filled"]:
                result["warning"] = "目标时钟满格——DM 必须判定失败条件是否已叙事物化"
            print(json.dumps(result, ensure_ascii=False))
            changed = True

    if args.complete_goal:
        goal = s.get("active_goal")
        if not goal:
            print(json.dumps({"error": "当前没有激活的目标"}, ensure_ascii=False))
        else:
            goal["completed"] = True
            s.setdefault("completed_goals", []).append({
                "goal": goal["goal"],
                "failed": False,
                "completed": True,
            })

            # Apply world mutation from goal definition
            goal_def = _get_goal_definition(goal.get("goal", ""))
            mutation = goal_def.get("world_mutation") if goal_def else None
            mutation_result = None

            if mutation:
                mtype = mutation.get("type", "")
                if mtype == "flag":
                    s.setdefault("_permanent_flags", {})[mutation["key"]] = True
                    mutation_result = {"flag_set": mutation["key"], "description": mutation["description"]}

                elif mtype == "safe_house":
                    loc_key = args.goal_location or s.get("current_location", "")
                    wc = _load_world_constants()
                    if loc_key in wc.get("locations", {}):
                        wc["locations"][loc_key]["safe_house"] = True
                    else:
                        wc.setdefault("locations", {})[loc_key] = {
                            "name_cn": loc_key,
                            "safe_house": True,
                            "always": "",
                            "sound": "",
                            "mood": "",
                        }
                    _save_world_constants(wc)
                    s.setdefault("_permanent_flags", {})["safe_house"] = loc_key
                    mutation_result = {"safe_house": loc_key, "description": mutation["description"]}

                elif mtype == "npc_known":
                    npc_name = args.goal_npc or ""
                    if npc_name:
                        known = s.setdefault("known_npcs", [])
                        if npc_name not in known:
                            known.append(npc_name)
                        mutation_result = {"npc_known": npc_name, "description": mutation["description"]}
                    else:
                        mutation_result = {"npc_known": "待 DM 通过 --goal_npc 指定", "description": mutation["description"]}

                elif mtype == "lore":
                    lore_key = args.goal_lore or ""
                    if lore_key:
                        revealed = s.setdefault("revealed_lore", [])
                        if lore_key not in revealed:
                            revealed.append(lore_key)
                        mutation_result = {"lore_revealed": lore_key, "description": mutation["description"]}
                    else:
                        mutation_result = {"lore_revealed": "待 DM 通过 --goal_lore 指定", "description": mutation["description"]}

            result_out = {
                "goal_completed": goal["goal"],
                "suggestion": "DM 使用 character_options.json 的 goal_completion_branch 展示分叉选项",
            }
            if mutation_result:
                result_out["world_mutation"] = mutation_result
            print(json.dumps(result_out, ensure_ascii=False))
            changed = True

    if args.fail_goal:
        goal = s.get("active_goal")
        if not goal:
            print(json.dumps({"error": "当前没有激活的目标"}, ensure_ascii=False))
        else:
            goal["failed"] = True
            s.setdefault("completed_goals", []).append({
                "goal": goal["goal"],
                "failed": True,
                "completed": False,
            })
            print(json.dumps({
                "goal_failed": goal["goal"],
                "reminder": "DM 禁止软化失败。空白的目标栏是叙事的一部分——玩家可随时选择新目标。",
            }, ensure_ascii=False))
            changed = True

    if args.finale_goal:
        goal = s.get("active_goal")
        if not goal or goal.get("completed") or goal.get("failed"):
            print(json.dumps({"error": "当前没有激活的目标"}, ensure_ascii=False))
        else:
            import random
            dc = goal.get("dc", 7)
            filled = goal.get("clock_current", 0)
            roll = random.randint(1, 6)
            total = roll + filled
            if total >= dc + 3:
                result = "strong_success"
                desc = f"强成功——目标达成，额外收获 (掷骰{roll} + 进度{filled} = {total} ≥ DC{dc}+3)"
            elif total >= dc:
                result = "weak_success"
                desc = f"弱成功——目标达成，但有代价 (掷骰{roll} + 进度{filled} = {total} ≥ DC{dc})"
            else:
                result = "failure"
                desc = f"失败——进度倒退，情况恶化 (掷骰{roll} + 进度{filled} = {total} < DC{dc})"
                goal["clock_current"] = max(0, goal.get("clock_current", 0) - 1)
            out = {
                "finale_roll": roll,
                "progress": filled,
                "total": total,
                "dc": dc,
                "result": result,
                "description": desc,
            }
            if result in ("strong_success", "weak_success"):
                goal["completed"] = True
                s.setdefault("completed_goals", []).append({
                    "goal": goal["goal"],
                    "failed": False,
                    "completed": True,
                    "finale_result": result,
                })
                out["goal_completed"] = True
                out["follow_up"] = "DM 调用 --complete_goal 执行世界突变"
            elif result == "failure":
                out["clock_reduced"] = goal["clock_current"]
                out["reminder"] = "DM 叙述灾难后果，目标仍在——玩家可在未来再次尝试终结"
            print(json.dumps(out, ensure_ascii=False))
            changed = True

    if args.set_oath:
        goal = s.get("active_goal")
        if not goal or goal.get("completed") or goal.get("failed"):
            print(json.dumps({"error": "当前没有激活的目标"}, ensure_ascii=False))
        else:
            goal["oath"] = args.set_oath
            print(json.dumps({"oath_set": args.set_oath, "goal": goal["goal"]}, ensure_ascii=False))
            changed = True

    if args.oracle:
        oracle = generate_oracle()
        print(json.dumps({
            "oracle_roll": oracle["value"],
            "oracle": oracle["oracle"],
            "desc": oracle["desc"],
        }, ensure_ascii=False))

    if args.consume_oracle:
        no = s.get("_next_oracle")
        if no:
            no["consumed"] = True
            s["_next_oracle"] = no
            save_state(s)
            print(json.dumps({"next_oracle_consumed": True, "was": no["value"]}, ensure_ascii=False))
        else:
            print(json.dumps({"error": "没有待消耗的 next_oracle"}, ensure_ascii=False))

    if args.face_desolation:
        import random
        spirit = s.get("clocks", {}).get("spirit", {})
        if not spirit:
            print(json.dumps({"error": "当前世界没有 spirit 轨道"}, ensure_ascii=False))
        else:
            roll = random.randint(1, 6)
            # DC 7 — same scale as personal oath
            if roll >= 6:
                outcome = "strong_success"
                spirit["filled"] = max(0, spirit.get("filled", 0) - 2)
                desc = f"在边缘找到了支撑——spirit 恢复 2 (掷骰 {roll} ≥ 6)"
            elif roll >= 3:
                outcome = "weak_success"
                spirit["filled"] = max(0, spirit.get("filled", 0) - 1)
                desc = f"撑过去了，但留下永久标签 (掷骰 {roll} ≥ 3)"
                s.setdefault("tags", []).append("desolation_scarred")
            else:
                outcome = "failure"
                desc = f"精神永久性崩解——游戏结束 (掷骰 {roll} < 3)"
                s.setdefault("tags", []).append("game_over_desolation")
                # Determine broken state by location (from world data)
                loc = s.get("current_location", "")
                wc = _load_world_constants()
                state_map = wc.get("desolation_state_map", {})
                broken_state = list(state_map.values())[0] if state_map else "?"
                for loc_key, st in state_map.items():
                    if loc_key in loc:
                        broken_state = st
                        break
                broken_info = {
                    "name": s.get("player_name", "?"),
                    "origin": s.get("origin", "?"),
                    "location": loc,
                    "state": broken_state,
                    "fragment_prompt": "DM 根据玩家最后处境写一句感官碎片",
                }
            out = {
                "face_desolation_roll": roll,
                "outcome": outcome,
                "description": desc,
                "spirit_current": spirit.get("filled", "?"),
            }
            if outcome == "failure":
                out["broken"] = broken_info
                out["follow_up"] = "python tools/session_enrich.py --chronicle add_broken '<JSON>'  # DM 填充 fragment 后执行"
            print(json.dumps(out, ensure_ascii=False))
            changed = True

    if args.set_truth:
        dim, choice = args.set_truth
        s.setdefault("world_truths", {})[dim] = choice
        print(json.dumps({"truth_set": {dim: choice}, "world_truths": s["world_truths"]}, ensure_ascii=False))
        changed = True

    # ── Pending state (pre-computation stash) ──

    if args.set_pending:
        key, value = args.set_pending
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            parsed = value
        s.setdefault("_pending", {})[key] = parsed
        print(json.dumps({"pending_set": key}, ensure_ascii=False))
        changed = True

    if args.flush_pending:
        pending = s.pop("_pending", {})
        if pending.get("npc_mood"):
            s.setdefault("npc_moods", {}).update(pending["npc_mood"])
        if pending.get("queued_event"):
            s.setdefault("queued_events", []).append(pending["queued_event"])
        if pending.get("pre_rolled"):
            s["_last_pre_roll"] = pending["pre_rolled"]
        print(json.dumps({"flushed": pending}, ensure_ascii=False))
        changed = True

    # ── Clues / History ──

    if args.add_clue:
        for clue in args.add_clue:
            s["clues"].append(clue)
        print(json.dumps({"ok": True, "clue_added": len(args.add_clue)}, ensure_ascii=False))
        changed = True

    if args.add_history:
        for h in args.add_history:
            s["history"].append(h)
        print(json.dumps({"ok": True, "history_added": len(args.add_history)}, ensure_ascii=False))
        changed = True

    # ── Scene management ──

    if args.scene_begin:
        if s.get("active_scene"):
            # Auto-archive current scene
            current = s["active_scene"]
            current["ended_at_turn"] = s.get("turn_count", 0)
            s.setdefault("scene_history", []).append(current)
            print(json.dumps({"scene_archived": current.get("name"), "reason": "new_scene_begin"}, ensure_ascii=False))

        s["active_scene"] = {
            "name": args.scene_begin,
            "location": args.scene_location or s.get("current_location", ""),
            "started_at_turn": s.get("turn_count", 0),
            "started_at_chapter": s.get("chapter", 0),
        }
        print(json.dumps({"scene_began": s["active_scene"]}, ensure_ascii=False))
        changed = True

    if args.scene_end:
        active = s.get("active_scene")
        if not active:
            print(json.dumps({"error": "没有活跃的场景可以结束"}, ensure_ascii=False))
        else:
            active["ended_at_turn"] = s.get("turn_count", 0)
            if args.scene_summary:
                active["summary"] = args.scene_summary
            s.setdefault("scene_history", []).append(active)
            s["active_scene"] = None
            print(json.dumps({"scene_ended": active["name"], "total_scenes": len(s["scene_history"])}, ensure_ascii=False))
            changed = True

    if args.add_mark:
        s.setdefault("marks", [])
        if not args.mark_bonus or not args.mark_context:
            print(json.dumps({"error": "--add_mark 需要同时指定 --mark_bonus (+1/+2) 和 --mark_context \"适用场景\""}, ensure_ascii=False))
            sys.exit(1)
        s["marks"].append({
            "name": args.add_mark,
            "bonus": args.mark_bonus,
            "context": args.mark_context
        })
        print(json.dumps({"mark_added": args.add_mark, "bonus": args.mark_bonus, "context": args.mark_context}, ensure_ascii=False))
        changed = True

    # ── Future seeds ──

    if args.seed_branch:
        seeds = []
        for raw in args.seed_branch:
            try:
                seeds.append(json.loads(raw))
            except json.JSONDecodeError:
                print(f"错误: 无效 JSON: {raw}", file=sys.stderr)
                sys.exit(1)
        s["future_seeds"] = seeds
        changed = True

    if args.get_seed is not None:
        idx = args.get_seed
        seeds = s.get("future_seeds", [])
        if 0 <= idx < len(seeds):
            seed = seeds[idx]
            print(json.dumps(seed, ensure_ascii=False))
            # Remove consumed seed
            seeds.pop(idx)
            s["future_seeds"] = seeds
            changed = True
            save_state(s)
            sys.exit(0)
        else:
            print(json.dumps({"error": f"种子索引 {idx} 越界，共 {len(seeds)} 个种子"}, ensure_ascii=False))
            sys.exit(1)

    save_state(s)
    if tick_result:
        if args.with_view:
            tick_result["view"] = _render_view_text(s)
        print(json.dumps(tick_result, ensure_ascii=False))
