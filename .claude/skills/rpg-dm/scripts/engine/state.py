import json
import os
import sys
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

from tools.world_loader import atomic_write, world_file

STATE_FILE = "state.json"


_json_cache: Dict[str, Dict[str, Any]] = {}

# ═══════════════════════════════════════════════════════════════
# State dict key reference — every key in the state dict, grouped.
# This is documentation, not enforcement.  Keep in sync with
# default_state.json and sentinel_keys.py.
# ═══════════════════════════════════════════════════════════════
#
# ── Core identity ──
#   player_name    str         角色名
#   player_class   str         职业 (shattered_crown only)
#   player_race    str         种族 (shattered_crown only)
#   origin         str         起源 (cloud_chamber only)
#   scar           str         旧伤 (cloud_chamber character creation)
#   drive          str         执念 / 核心动机 (cloud_chamber character creation)
#   appearance     str         形貌描述 (cloud_chamber character creation)
#   background     str         背景描述
#   chapter        int         当前章节
#   turn_count     int         回合计数
#   tags           list[str]   全局标签 (e.g. "game_over_desolation")
#
# ── Clocks & tracks ──
#   clocks         dict[str, clock]  属性时钟 + 进度时钟
#     clock: {max, filled, label, direction?, modifier?}
#   attr_order     list[str]         属性时钟显示顺序 (world config)
#   track_order    list[str]         资源轨显示顺序 (world config)
#
# ── Inventory & equipment ──
#   inventory      list[item]   背包物品
#     item: {id, name, qty, tags}
#   equipped       dict         装备 {weapon, armor} (shattered_crown)
#
# ── Combat ──
#   combat_state           dict|null  {enemies, player_effects, environment,
#                                      combat_log, turn}
#   pending_encounter      dict|null  待处理的遭遇
#   deferred_encounter     dict|null  延迟遭遇 (runtime only)
#   combat_damage_attr     str        伤害关联属性 (world config)
#
# ── NPCs & affinities ──
#   known_npcs     list[str]              已结识 NPC key 列表
#   affinities     dict[str, affinity]    NPC 好感度
#     affinity: {level, milestones}
#   npc_moods      dict                   待 flush 的 NPC 心情 (runtime)
#
# ── Goals & marks ──
#   active_goal         dict|null  {goal, clock_current, clock_max, dc, oath, ...}
#   completed_goals     list[dict] 已完成/失败的目标历史
#   marks               list[dict] 印记 [{name, bonus, context}]
#
# ── World knowledge ──
#   clues              list[str]    线索列表
#   history            list[str]    叙事历史
#   revealed_lore      list[str]    已揭示的世界知识
#   known_fragments    list[int]    已知碎片编号
#   world_truths       dict         世界真相维度选择 (cloud_chamber)
#   future_seeds       list[dict]   未来叙事种子
#
# ── Location & danger ──
#   current_location   str              当前位置 key
#   location_dangers   dict[str, int]   各地图格危险值
#
# ── Scenes (cloud_chamber) ──
#   active_scene       dict|null  {name, location, started_at_turn, ...}
#   scene_history       list[dict] 已结束场景历史
#
# ── Misc ──
#   injury      dict|null  {type, ticks_remaining, dc_penalty}
#   dm_log      list[dict] DM 裁定记录
#   events      list       环境事件 (legacy, rarely used)
#   other_clocks dict      预留字段 (unused)
#
# ── Sentinel keys (underscore-prefixed, internal event bus) ──
#   __bg_switch_target   str   后台切换信号 (set by trigger, consumed by state_mgr)
#   __trigger_prev_loc   str   位置变更追踪 (internal to trigger)
#   __pending_encounter  dict  待处理遭遇队列 (trigger internal)
#   _next_oracle         dict  预生成的神谕值 {value, oracle, desc, consumed}
#   _permanent_flags     dict  永久标记 (跨会话持久)
#   _last_pre_roll       dict  最近一次掷骰缓存
#   _pending             dict  待 flush 的状态变更
#   _last_enrichment     str   上次富化时间戳 (ISO)
#   _enrichment_turn     int   上次富化时的回合数
#   queued_events        list  待 flush 的事件队列 (runtime)
#
# ── Legacy / migrated ──
#   attributes    dict  旧属性格式 → 加载时自动迁移到 clocks
#   current_goal  dict  旧目标格式 → 读取时兼容 active_goal
# ═══════════════════════════════════════════════════════════════


def read_world_json(filename: str) -> Dict[str, Any]:
    if filename not in _json_cache:
        with open(world_file(filename), "r", encoding="utf-8") as f:
            _json_cache[filename] = json.load(f)
    return _json_cache[filename]


def get_default_state() -> Dict[str, Any]:
    return read_world_json("default_state.json")


def get_threshold_rules() -> List[List[Any]]:
    return read_world_json("threshold_rules.json")


def get_track(state: Dict[str, Any], name: str) -> Tuple[int, int]:
    track = state.get("clocks", {}).get(name, {})
    return int(track.get("filled", 0)), int(track.get("max", 0))


def format_track(state: Dict[str, Any], name: str) -> str:
    filled, max_value = get_track(state, name)
    return f"{filled}/{max_value}"


def migrate_inventory(items: List[Any]) -> List[Dict[str, Any]]:
    if not items:
        return []
    if all(isinstance(it, dict) for it in items):
        return items
    counts = Counter(items)
    migrated = []
    for i, (name, qty) in enumerate(counts.items(), start=1):
        migrated.append({"id": f"item_{i:03d}", "name": name, "qty": qty, "tags": []})
    return migrated


def _clone_default_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _clone_default_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_clone_default_value(v) for v in value]
    return value


def load_state() -> Dict[str, Any]:
    if not os.path.exists(STATE_FILE):
        return dict(get_default_state())

    with open(STATE_FILE, "r", encoding="utf-8") as f:
        state = json.load(f)

    # ── Legacy migration: old numeric attributes → clock-based attributes ──
    if "attributes" in state and isinstance(state["attributes"], dict):
        old = state.pop("attributes")
        state.setdefault("clocks", {})
        attr_clock_defaults = {
            "strength":     {"max": 6, "filled": 3, "label": "力量"},
            "agility":      {"max": 6, "filled": 3, "label": "敏捷"},
            "constitution": {"max": 8, "filled": 1, "label": "体质"},
            "sanity":       {"max": 6, "filled": 3, "label": "理智"},
            "magic":        {"max": 6, "filled": 1, "label": "魔力"},
            "wealth":       {"max": 6, "filled": 3, "label": "财富"},
            "reputation":   {"max": 6, "filled": 3, "label": "声望"},
        }
        for attr_name, clock_def in attr_clock_defaults.items():
            if attr_name not in state["clocks"]:
                if attr_name == "constitution":
                    if "health" in old:
                        src_val = old["health"]
                        filled = max(0, min(8, round((20 - src_val) / 20 * 8)))
                        if filled == 0 and src_val >= 18:
                            filled = 1
                    else:
                        filled = clock_def["filled"]
                elif attr_name in old:
                    old_val = old[attr_name]
                    filled = max(0, min(clock_def["max"], round(old_val / 5)))
                else:
                    filled = clock_def["filled"]
                state["clocks"][attr_name] = {**clock_def, "filled": filled}

    # ── Fill missing fields from defaults ──
    defaults = get_default_state()
    for key, value in defaults.items():
        if key not in state:
            state[key] = _clone_default_value(value)

    state["inventory"] = migrate_inventory(state.get("inventory", []))

    for field, default_value in (
        ("events", []),
        ("dm_log", []),
        ("clocks", {}),
        ("known_fragments", []),
        ("marks", []),
        ("known_npcs", []),
        ("revealed_lore", []),
        ("completed_goals", []),
        ("affinities", {}),
        ("injury", None),
        ("background", ""),
        ("active_goal", None),
        ("active_scene", None),
        ("scene_history", []),
    ):
        if field not in state:
            state[field] = _clone_default_value(default_value)

    # Ensure attribute and track clocks exist from defaults
    default_clocks = defaults.get("clocks", {})
    attr_order = defaults.get("attr_order", list(default_clocks.keys()))
    track_order = defaults.get("track_order", [])
    for key in attr_order + track_order:
        if key not in state["clocks"] and key in default_clocks:
            state["clocks"][key] = dict(default_clocks[key])
        elif key in state["clocks"] and key in default_clocks:
            for field in ("direction", "modifier"):
                if field not in state["clocks"][key] and field in default_clocks[key]:
                    state["clocks"][key][field] = default_clocks[key][field]

    if "game_over_desolation" in state.get("tags", []):
        print("检测到上一局角色已崩解，自动载入默认状态。", file=sys.stderr)
        return dict(get_default_state())

    return state


def save_state(state: Dict[str, Any]) -> None:
    atomic_write(STATE_FILE, lambda f: json.dump(state, f, ensure_ascii=False, indent=2), prefix=".state_tmp_")


def compute_flags(clocks: Dict[str, Dict[str, Any]]) -> List[str]:
    flags = []
    for attr, op, threshold, flag in get_threshold_rules():
        clock = clocks.get(attr)
        if not clock:
            continue
        value = clock.get("filled", 0)
        if op == ">=" and value >= threshold:
            flags.append(flag)
        elif op == "<=" and value <= threshold:
            flags.append(flag)
    return flags


def attr_modifier(clock: Dict[str, Any]) -> int:
    filled = int(clock.get("filled", 0))
    max_value = int(clock.get("max", 0))
    raw_mod = clock.get("modifier") == "raw"
    if raw_mod:
        mod = filled
    else:
        midpoint = max_value // 2
        mod = filled - midpoint
    if clock.get("direction", "up") == "down":
        mod = -mod
    return mod


def average_attr_modifier(state: Dict[str, Any], attrs: List[str]) -> Tuple[int, List[Dict[str, Any]]]:
    details: List[Dict[str, Any]] = []
    mod_sum = 0
    for name in attrs:
        clock = state.get("clocks", {}).get(name)
        if not clock:
            continue
        mod = attr_modifier(clock)
        mod_sum += mod
        details.append(
            {
                "attr": name,
                "filled": int(clock.get("filled", 0)),
                "max": int(clock.get("max", 0)),
                "mod": mod,
            }
        )
    if not details:
        return 0, []
    return int(mod_sum / len(details)), details


def advance_turn(state: Dict[str, Any]) -> None:
    state["turn_count"] = int(state.get("turn_count", 0)) + 1


def mark_bonus(state: Dict[str, Any], mark_name: Optional[str]) -> Tuple[int, Optional[str]]:
    if not mark_name:
        return 0, None
    for mark in state.get("marks", []):
        if mark.get("name") == mark_name:
            return int(mark.get("bonus", 0)), mark_name
    return 0, None


def active_goal_progress(state: Dict[str, Any]) -> List[str]:
    goal = state.get("active_goal")
    if not goal or isinstance(goal, str):
        return []
    goal_name = goal.get("goal", "未命名誓言")
    current = int(goal.get("clock_current", 0))
    max_value = int(goal.get("clock_max", 0))
    return [f"{goal_name} ({current}/{max_value})"]


def active_mark_labels(state: Dict[str, Any]) -> List[str]:
    labels = []
    for mark in state.get("marks", []):
        name = mark.get("name")
        bonus = mark.get("bonus")
        if name is not None and bonus is not None:
            labels.append(f"{name}(+{bonus})")
    return labels
