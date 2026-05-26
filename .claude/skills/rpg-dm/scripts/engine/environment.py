import json
import random
from typing import Any, Dict, List, Optional

from .dice import roll_d20, roll_dice
from .state import read_world_json


def _white_breath_level(state: Dict[str, Any]) -> str:
    location = state.get("current_location", "")
    constants = read_world_json("world_constants.json")
    loc = constants.get("locations", {}).get(location, {})
    return loc.get("white_breath_level", "low")


def _combat_environment_event(state: Dict[str, Any], rng: Optional[random.Random] = None) -> Optional[Dict[str, str]]:
    combat_state = state.get("combat_state")
    if not combat_state:
        return None

    roller = rng or random
    if roller.randint(1, 100) > 15:
        return None

    event_table = read_world_json("environment_events.json")
    location = state.get("current_location", "")

    matched_events = None
    for keyword, events in event_table.items():
        if keyword == "_default":
            continue
        if keyword in location:
            matched_events = events
            break

    pool = matched_events or event_table.get("_default", [])
    if not pool:
        return None

    name, desc = roller.choice(pool)
    return {"name": name, "desc": desc}


def _parse_pool_entry(entry) -> Dict[str, Any]:
    """兼容旧格式 [id, weight] 和新格式 {id, weight, tags}"""
    if isinstance(entry, list):
        return {"id": entry[0], "weight": entry[1], "tags": []}
    return {
        "id": entry.get("id", "unknown"),
        "weight": entry.get("weight", 1),
        "tags": entry.get("tags", []),
    }


def _filter_pool_by_context(
    pool: List[Dict[str, Any]],
    action_tags: Optional[List[str]],
) -> List[Dict[str, Any]]:
    """按当前行动标签过滤遭遇池。有匹配时只返回匹配项，无匹配时返回全池。"""
    if not action_tags or not pool:
        return pool
    matching = [e for e in pool if any(t in action_tags for t in e.get("tags", []))]
    return matching if matching else pool


def tick_danger(
    state: Dict[str, Any],
    action_type: str = "action",
    action_tags: Optional[List[str]] = None,
    rng: Optional[random.Random] = None,
) -> Dict[str, Any]:
    encounter_tables = read_world_json("encounter_tables.json")
    location = state.get("current_location", "")
    entry = encounter_tables.get(location) or encounter_tables.get("_default", {})

    danger_max = int(entry.get("danger_max", 0))
    if danger_max <= 0:
        return {
            "danger": {"current": 0, "max": 0, "advance": 0},
            "omen": None,
            "encounter": None,
            "deferred_encounter": None,
            "catastrophe": False,
            "boon": False,
        }

    danger_tick = entry.get("danger_tick", "1d3")
    omens = entry.get("omens", {})
    raw_pool = entry.get("pool", [])
    trigger = entry.get("trigger", {})
    blocked_by = trigger.get("blocked_by", [])

    location_dangers = state.setdefault("location_dangers", {})
    current = int(location_dangers.get(location, 0))

    advance = roll_dice(danger_tick, rng)
    new_danger = min(current + advance, danger_max)

    catastrophe = False
    boon = False
    luck = roll_d20(rng)
    if luck == 1:
        catastrophe = True
        spike = max(2, danger_max // 3)
        new_danger = min(new_danger + spike, danger_max)
    elif luck == 20:
        boon = True
        new_danger = max(0, new_danger - 3)

    omen = None
    for threshold_str, omen_text in sorted(omens.items(), key=lambda x: int(x[0])):
        threshold = int(threshold_str)
        if current < threshold <= new_danger:
            omen = omen_text
            break

    encounter = None
    deferred_encounter = None

    if new_danger >= danger_max and raw_pool:
        pool = _filter_pool_by_context(
            [_parse_pool_entry(e) for e in raw_pool],
            action_tags,
        )
        total_weight = sum(e["weight"] for e in pool)
        pick = (rng or random).randint(1, total_weight)
        acc = 0
        chosen = pool[-1]["id"]
        for entry_parsed in pool:
            acc += entry_parsed["weight"]
            if pick <= acc:
                chosen = entry_parsed["id"]
                break

        encounter_payload = {
            "monster": chosen,
            "roll": advance,
            "turn": int(state.get("turn_count", 0)),
        }

        if action_type in blocked_by:
            deferred_encounter = encounter_payload
            state["deferred_encounter"] = encounter_payload
            encounter = None
        else:
            encounter = encounter_payload
            new_danger = 0
            state.pop("deferred_encounter", None)
    elif new_danger >= danger_max:
        new_danger = 0

    location_dangers[location] = new_danger
    state["location_dangers"] = location_dangers

    return {
        "danger": {"current": new_danger, "max": danger_max, "advance": advance},
        "omen": omen,
        "encounter": encounter,
        "deferred_encounter": deferred_encounter,
        "catastrophe": catastrophe,
        "boon": boon,
    }


def _resolve_deferred(state: Dict[str, Any], action_type: str) -> Optional[Dict[str, Any]]:
    """检查是否有挂起的遭遇，如果当前行动类型不再 blocked，则触发。"""
    deferred = state.get("deferred_encounter")
    if not deferred:
        return None

    encounter_tables = read_world_json("encounter_tables.json")
    location = state.get("current_location", "")
    entry = encounter_tables.get(location) or encounter_tables.get("_default", {})
    trigger = entry.get("trigger", {})
    blocked_by = trigger.get("blocked_by", [])

    if action_type in blocked_by:
        return None

    state.pop("deferred_encounter", None)
    location_dangers = state.get("location_dangers", {})
    location_dangers[location] = 0
    state["location_dangers"] = location_dangers
    return deferred


def process_environment(
    state: Dict[str, Any],
    action_type: str = "action",
    action_tags: Optional[List[str]] = None,
    rng: Optional[random.Random] = None,
) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "white_breath": _white_breath_level(state),
        "events": [],
        "danger": None,
        "encounter": None,
        "omen": None,
        "deferred_encounter": None,
    }

    if action_type in {"action", "tick"}:
        # 先检查是否有挂起的遭遇可以在本轮触发
        resolved_deferred = _resolve_deferred(state, action_type)
        if resolved_deferred:
            result["encounter"] = resolved_deferred
            result["events"].append(f"遭遇触发(挂起): {resolved_deferred['monster']}")

        danger_result = tick_danger(state, action_type=action_type, action_tags=action_tags, rng=rng)
        result["danger"] = danger_result["danger"]

        if danger_result["omen"]:
            result["omen"] = danger_result["omen"]
            result["events"].append(f"征兆: {danger_result['omen']}")
        if danger_result["catastrophe"]:
            result["events"].append("灾变: 风险陡增")
        if danger_result["boon"]:
            result["events"].append("转机: 风险暂缓")
        if danger_result["encounter"]:
            result["encounter"] = danger_result["encounter"]
            result["events"].append(f"遭遇触发: {danger_result['encounter']['monster']}")
        if danger_result["deferred_encounter"]:
            result["deferred_encounter"] = danger_result["deferred_encounter"]
            result["events"].append(
                f"遭遇挂起: {danger_result['deferred_encounter']['monster']} "
                f"(当前行动类型 [{action_type}] 阻塞遭遇触发)"
            )

    combat_event = _combat_environment_event(state, rng)
    if combat_event:
        result["events"].append(f"环境事件: {combat_event['name']} - {combat_event['desc']}")

    return result
