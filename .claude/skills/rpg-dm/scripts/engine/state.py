import json
import os
import tempfile
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

from tools.world_loader import world_file

STATE_FILE = "state.json"


_json_cache: Dict[str, Dict[str, Any]] = {}


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

    defaults = get_default_state()
    for key, value in defaults.items():
        if key not in state:
            state[key] = _clone_default_value(value)

    state["inventory"] = migrate_inventory(state.get("inventory", []))

    for field, default_value in (
        ("events", []),
        ("dm_log", []),
        ("known_fragments", []),
        ("marks", []),
        ("known_npcs", []),
        ("revealed_lore", []),
        ("completed_goals", []),
        ("affinities", {}),
    ):
        if field not in state:
            state[field] = _clone_default_value(default_value)

    if "clocks" not in state:
        state["clocks"] = {}

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

    if "injury" not in state:
        state["injury"] = None
    if "background" not in state:
        state["background"] = ""
    if "active_goal" not in state:
        state["active_goal"] = None

    return state


def save_state(state: Dict[str, Any]) -> None:
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".json", prefix=".state_tmp_", dir=".")
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        if os.path.exists(STATE_FILE):
            bak_path = STATE_FILE + ".bak"
            if os.path.exists(bak_path):
                os.remove(bak_path)
            os.rename(STATE_FILE, bak_path)
        os.rename(tmp_path, STATE_FILE)
    except Exception:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise


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
