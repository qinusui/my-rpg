import json
import os
import sys
import random
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from world_loader import world_file

STATE_FILE = "state.json"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORLD_CONSTANTS_FILE = world_file("world_constants.json")

# ── World data (loaded from active world JSON files) ─────────

with open(world_file("encounter_tables.json"), "r", encoding="utf-8") as _f:
    ENCOUNTER_TABLES = json.load(_f)

with open(world_file("threshold_rules.json"), "r", encoding="utf-8") as _f:
    THRESHOLD_RULES = json.load(_f)

with open(world_file("default_state.json"), "r", encoding="utf-8") as _f:
    DEFAULT_STATE = json.load(_f)


# ── migration ──────────────────────────────────────────────

def _migrate_inventory(items):
    if not items:
        return []
    if all(isinstance(it, dict) for it in items):
        return items
    counts = Counter(items)
    migrated = []
    for i, (name, qty) in enumerate(counts.items(), start=1):
        migrated.append({
            "id": f"item_{i:03d}",
            "name": name,
            "qty": qty,
            "tags": [],
        })
    return migrated


# ── persistence ────────────────────────────────────────────

def load_state():
    if not os.path.exists(STATE_FILE):
        return dict(DEFAULT_STATE)
    with open(STATE_FILE, "r", encoding="utf-8") as f:
        s = json.load(f)

    for k, v in DEFAULT_STATE.items():
        if k not in s:
            s[k] = dict(v) if isinstance(v, dict) else (v[:] if isinstance(v, list) else v)
    for k, v in DEFAULT_STATE["attributes"].items():
        if k not in s.get("attributes", {}):
            s["attributes"][k] = v

    s["inventory"] = _migrate_inventory(s.get("inventory", []))
    if "events" not in s:
        s["events"] = []
    if "dm_log" not in s:
        s["dm_log"] = []
    if "clocks" not in s:
        s["clocks"] = {}
    if "injury" not in s:
        s["injury"] = None
    if "known_fragments" not in s:
        s["known_fragments"] = []
    if "known_npcs" not in s:
        s["known_npcs"] = []
    if "revealed_lore" not in s:
        s["revealed_lore"] = []
    if "background" not in s:
        s["background"] = ""
    if "active_goal" not in s:
        s["active_goal"] = None
    if "completed_goals" not in s:
        s["completed_goals"] = []

    return s


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


# ── inventory helpers ──────────────────────────────────────

def _next_item_id(state):
    existing = [int(it["id"].split("_")[1]) for it in state["inventory"]]
    return f"item_{max(existing) + 1:03d}" if existing else "item_001"


def _find_by_id(state, item_id):
    for it in state["inventory"]:
        if it["id"] == item_id:
            return it
    return None


# ── threshold flags ────────────────────────────────────────

def compute_flags(attrs):
    """Return list of active threshold flags for current attributes."""
    flags = []
    for attr, op, threshold, flag in THRESHOLD_RULES:
        val = attrs.get(attr, 10)
        if op == ">=" and val >= threshold:
            flags.append(flag)
        elif op == "<=" and val <= threshold:
            flags.append(flag)
    return flags


# ── attribute modifier ─────────────────────────────────────

def _attr_modifier(val):
    return (val - 10) // 5


# ── encounter roll ─────────────────────────────────────────

def _roll_encounter(s):
    loc = s.get("current_location", "")
    entry = ENCOUNTER_TABLES.get(loc, ENCOUNTER_TABLES["_default"])
    dc = entry["dc"]
    pool = entry["pool"]
    roll = random.randint(1, 20)
    result = {"roll": roll}
    if roll == 1:
        result["catastrophe"] = True
    elif roll == 20:
        result["boon"] = True
    if roll < dc:
        return None, result
    # Weighted pick from pool
    total = sum(w for _, w in pool)
    pick = random.randint(1, total)
    acc = 0
    for name, w in pool:
        acc += w
        if pick <= acc:
            result["monster"] = name
            return name, result
    result["monster"] = pool[-1][0]
    return pool[-1][0], result


# ── view ───────────────────────────────────────────────────

def view_state():
    s = load_state()
    attrs = s.get("attributes", {})
    flags = compute_flags(attrs)

    print(f"╔══ {s.get('player_name', '冒险者')} ══╗")
    print(f"种族: {s.get('player_race', '未知')}  职业: {s.get('player_class', '未知')}")
    print(f"位置: {s.get('current_location', '未知')}  章节: {s.get('chapter', 0)}")
    print(f"--- 属性 ---")
    for k, v in attrs.items():
        bar = "█" * (v // 2) + "░" * (10 - v // 2)
        mod = _attr_modifier(v)
        sign = "+" if mod >= 0 else ""
        print(f"  {k:12s} {v:3d}  {bar}  [{sign}{mod}]")

    injury = s.get("injury")
    if injury:
        print(f"--- ⚠ 伤残 ---")
        print(f"  类型: {injury['type']} | 剩余 {injury['ticks_remaining']} tick | 检定 DC +{injury['dc_penalty']}")

    if flags:
        print(f"--- 状态标志 ---")
        print(f"  {', '.join(flags)}")

    clocks = s.get("clocks", {})
    if clocks:
        print(f"--- 进度钟 ({len(clocks)}) ---")
        for name, c in clocks.items():
            cur, mx = c["current"], c["max"]
            filled = "█" * cur
            empty = "░" * (mx - cur)
            warn = " ⚡满格将触发" if cur >= mx else ""
            print(f"  [{filled}{empty}] {cur}/{mx}  {name}{warn}")
            if cur >= mx and c.get("consequence"):
                print(f"    ↳ {c['consequence']}")

    pe = s.get("pending_encounter")
    if pe:
        print(f"--- ⚠ 待处理遭遇 ---")
        print(f"  {pe.get('monster', '未知')} (掷骰 {pe.get('roll', '?')})")

    eq = s.get("equipped", {})
    if eq.get("weapon") or eq.get("armor"):
        print(f"--- 装备 ---")
        if eq.get("weapon"):
            w = _find_by_id(s, eq["weapon"])
            print(f"  武器: {w['name'] if w else eq['weapon']}")
        if eq.get("armor"):
            a = _find_by_id(s, eq["armor"])
            print(f"  护甲: {a['name'] if a else eq['armor']}")

    inv = s.get("inventory", [])
    print(f"--- 物品 ({len(inv)} 种 / {sum(it['qty'] for it in inv)} 件) ---")
    for it in inv:
        tag_str = f"  [{', '.join(it['tags'])}]" if it["tags"] else ""
        print(f"  [{it['id']}] {it['name']} ×{it['qty']}{tag_str}")

    print(f"--- 线索 ({len(s.get('clues', []))}) ---")
    for clue in s.get("clues", []):
        print(f"  ? {clue}")

    known_frags = s.get("known_fragments", [])
    known_npcs = s.get("known_npcs", [])
    revealed = s.get("revealed_lore", [])
    if known_frags or known_npcs or revealed:
        print(f"--- 知识状态 ---")
        if known_frags:
            print(f"  已知碎片: 第{', '.join(str(f) for f in known_frags)}片")
        if known_npcs:
            print(f"  已知 NPC: {', '.join(known_npcs)}")
        if revealed:
            print(f"  已揭示文献: {', '.join(revealed)}")

    bg = s.get("background", "")
    goal = s.get("active_goal")
    if isinstance(goal, str):
        goal = None
    completed = s.get("completed_goals", [])
    if bg or goal or completed:
        print(f"--- 身份与目标 ---")
        if bg:
            print(f"  过往: {bg}")
        if goal:
            gclock = goal.get("clock_current", 0)
            gmax = goal.get("clock_max", 4)
            gfilled = "█" * gclock + "░" * (gmax - gclock)
            gfail = " ✗已失败" if goal.get("failed") else ""
            gdone = " ✓已完成" if goal.get("completed") else ""
            print(f"  目标: {goal['goal']}{gdone}{gfail}")
            print(f"  [{gfilled}] {goal.get('clock_name', '目标时钟')} [{gclock}/{gmax}]")
        if completed:
            summaries = []
            for g in completed:
                tag = "✗" if g.get("failed") else "✓"
                summaries.append(f"{tag}{g['goal']}")
            print(f"  已结束: {', '.join(summaries)}")

    history = s.get("history", [])
    if history:
        print(f"--- 前情提要 ({len(history)} 条) ---")
        for h in history[-5:]:
            print(f"  ~ {h}")
    dm_log = s.get("dm_log", [])
    if dm_log:
        print(f"--- DM 覆盖记录 ({len(dm_log)} 条) ---")
        for entry in dm_log[-3:]:
            print(f"  ✎ 回合 {entry.get('turn','?')}: {entry.get('type','?')} — {entry.get('reason','无理由')}")


def list_inventory(s, tag_filter=None):
    inv = s["inventory"]
    if tag_filter:
        inv = [it for it in inv if tag_filter in it.get("tags", [])]
    if not inv:
        print("(背包为空)")
        return
    for i, it in enumerate(inv, start=1):
        print(f"[{i}] {it['name']} ×{it['qty']}  ({it['id']})")


# ── World constants helpers ──────────────────────────────────

def _load_world_constants():
    if not os.path.exists(WORLD_CONSTANTS_FILE):
        return {"npcs": {}, "locations": {}}
    with open(WORLD_CONSTANTS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_world_constants(data):
    os.makedirs(os.path.dirname(WORLD_CONSTANTS_FILE), exist_ok=True)
    with open(WORLD_CONSTANTS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _lookup_npc(query):
    wc = _load_world_constants()
    query_lower = query.lower()
    results = []
    for key, profile in wc.get("npcs", {}).items():
        if query_lower in key.lower() or query_lower in profile.get("name_cn", "").lower():
            results.append({"key": key, **profile})
    if not results:
        return {"found": False, "query": query, "hint": "NPC 未收录，请用 --add_npc 添加"}
    return {"found": True, "results": results}


def _lookup_location(query):
    wc = _load_world_constants()
    query_lower = query.lower()
    results = []
    for key, sensory in wc.get("locations", {}).items():
        if query_lower in key.lower() or query_lower in sensory.get("name_cn", "").lower():
            results.append({"key": key, **sensory})
    if not results:
        return {"found": False, "query": query, "hint": "地点未收录"}
    return {"found": True, "results": results}


def _add_npc(key, traits, quirk, voice):
    wc = _load_world_constants()
    wc.setdefault("npcs", {})[key] = {
        "traits": [t.strip() for t in traits.split(",") if t.strip()],
        "quirk": quirk,
        "voice": voice,
    }
    _save_world_constants(wc)
    print(json.dumps({"added": key, "profile": wc["npcs"][key]}, ensure_ascii=False))


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
        save_state(s)
        print(json.dumps({"cleared": True}, ensure_ascii=False))
        sys.exit(0)

    import argparse

    parser = argparse.ArgumentParser(description="RPG State Manager")
    parser.add_argument("--init", action="store_true", help="初始化 state.json")
    parser.add_argument("--view", action="store_true", help="查看当前状态")
    parser.add_argument("--tick", action="store_true", help="回合数 +1 (JSON 输出)")
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
    parser.add_argument("--attr", help="指定适用属性 (health/sanity/magic/reputation/wealth)")
    parser.add_argument("--mod", type=int, default=0, help="DM 局势修正 (掷骰前宣告，装备/环境/优势)")
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
    parser.add_argument("--fail_goal", action="store_true", help="标记当前目标为已失败")
    # Pending state (pre-computation stash)
    parser.add_argument("--set_pending", nargs=2, metavar=("key", "value"),
                        help="写入暂存值到 _pending (JSON 字符串)")
    parser.add_argument("--flush_pending", action="store_true",
                        help="合并 _pending 到主状态并清空")
    args = parser.parse_args()

    if args.init:
        save_state(dict(DEFAULT_STATE))
        print("state.json 已初始化。")
        sys.exit(0)

    if args.view:
        view_state()
        sys.exit(0)

    if args.d20:
        roll = random.randint(1, 20)
        if args.attr or args.mod:
            s = load_state() if args.attr else None
            val = s["attributes"].get(args.attr, 10) if args.attr else None
            mod = _attr_modifier(val) if args.attr else 0
            sit = args.mod
            result = {"roll": roll, "total": roll + mod + sit}
            if args.attr:
                result["attr"] = args.attr
                result["attr_value"] = val
                result["modifier"] = mod
            if sit:
                result["situational"] = sit
            print(json.dumps(result, ensure_ascii=False))
        else:
            print(roll)
        sys.exit(0)

    if args.lookup_npc:
        print(json.dumps(_lookup_npc(args.lookup_npc), ensure_ascii=False))
        sys.exit(0)

    if args.lookup_location:
        print(json.dumps(_lookup_location(args.lookup_location), ensure_ascii=False))
        sys.exit(0)

    if args.add_npc:
        _add_npc(args.add_npc, args.traits or "", args.quirk or "", args.voice or "")
        sys.exit(0)

    s = load_state()
    tick_result = None

    # ── --tick (core loop) ──
    if args.tick:
        s["turn_count"] = s.get("turn_count", 0) + 1

        result = {
            "encounter": None,
            "flags": compute_flags(s["attributes"]),
        }

        if s.get("pending_encounter"):
            result["encounter_pending"] = s["pending_encounter"]
        else:
            monster, roll_info = _roll_encounter(s)
            if roll_info.get("catastrophe"):
                result["catastrophe"] = True
            if roll_info.get("boon"):
                result["boon"] = True
            if monster:
                s["pending_encounter"] = {"monster": monster, "roll": roll_info["roll"], "turn": s["turn_count"]}
                result["encounter"] = s["pending_encounter"]

        # Check for filled clocks
        filled_clocks = []
        for name, c in s.get("clocks", {}).items():
            if c["current"] >= c["max"]:
                filled_clocks.append({"name": name, "consequence": c.get("consequence", "")})
        if filled_clocks:
            result["filled_clocks"] = filled_clocks

        # Injury tick-down
        injury = s.get("injury")
        if injury and injury.get("ticks_remaining", 0) > 0:
            injury["ticks_remaining"] -= 1
            if injury["ticks_remaining"] <= 0:
                s["injury"] = None
                result["injury_healed"] = True

        tick_result = result

    changed = args.tick

    if args.update:
        k, v = args.update
        s["attributes"][k] = s["attributes"].get(k, 10) + int(v)
        changed = True

    if args.set:
        k, v = args.set
        if k == "equipped_weapon":
            s.setdefault("equipped", {})["weapon"] = v if v != "None" else None
        elif k == "equipped_armor":
            s.setdefault("equipped", {})["armor"] = v if v != "None" else None
        elif k == "current_location":
            s["current_location"] = v
        elif k in ("chapter", "turn_count"):
            s[k] = int(v)
        elif v in ("null", "None"):
            s[k] = None
        else:
            s[k] = v
        changed = True

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
            else:
                s["inventory"].append({
                    "id": _next_item_id(s),
                    "name": name,
                    "qty": args.qty,
                    "tags": tag_list,
                })
        changed = True

    if args.use_item:
        it = _find_by_id(s, args.use_item)
        if not it:
            print(f"错误: 物品 {args.use_item} 不存在", file=sys.stderr)
            sys.exit(1)
        it["qty"] -= args.qty
        if it["qty"] <= 0:
            s["inventory"].remove(it)
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
            print(json.dumps({"error": f"进度钟 '{name}' 不存在"}, ensure_ascii=False))
            sys.exit(1)
        s["clocks"][name]["current"] = int(val)
        c = s["clocks"][name]
        print(json.dumps({
            "clock_set": name,
            "current": c["current"],
            "max": c["max"],
            "filled": c["current"] >= c["max"],
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
        props = {"clock_name": "目标时钟", "clock_max": 4, "clock_trigger": ""}
        if props_json:
            try:
                props.update(json.loads(props_json))
            except json.JSONDecodeError:
                pass
        s["active_goal"] = {
            "goal": goal_name,
            "clock_current": 0,
            "clock_max": props.get("clock_max", 4),
            "clock_name": props.get("clock_name", "目标时钟"),
            "clock_trigger": props.get("clock_trigger", ""),
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
            print(json.dumps({
                "goal_completed": goal["goal"],
                "suggestion": "DM 使用 character_options.json 的 goal_completion_branch 展示分叉选项",
            }, ensure_ascii=False))
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
        changed = True

    if args.add_history:
        for h in args.add_history:
            s["history"].append(h)
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
        print(json.dumps(tick_result, ensure_ascii=False))
