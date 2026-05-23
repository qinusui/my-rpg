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


def tick_danger(state: Dict[str, Any], rng: Optional[random.Random] = None) -> Dict[str, Any]:
    encounter_tables = read_world_json("encounter_tables.json")
    location = state.get("current_location", "")
    entry = encounter_tables.get(location) or encounter_tables.get("_default", {})

    danger_max = int(entry.get("danger_max", 0))
    if danger_max <= 0:
        return {
            "danger": {"current": 0, "max": 0, "advance": 0},
            "omen": None,
            "encounter": None,
            "catastrophe": False,
            "boon": False,
        }

    danger_tick = entry.get("danger_tick", "1d3")
    omens = entry.get("omens", {})
    pool = entry.get("pool", [])

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
    if new_danger >= danger_max and pool:
        total_weight = sum(weight for _, weight in pool)
        pick = (rng or random).randint(1, total_weight)
        acc = 0
        chosen = pool[-1][0]
        for monster, weight in pool:
            acc += weight
            if pick <= acc:
                chosen = monster
                break
        encounter = {"monster": chosen, "roll": advance, "turn": int(state.get("turn_count", 0))}
        new_danger = 0

    location_dangers[location] = new_danger
    state["location_dangers"] = location_dangers

    return {
        "danger": {"current": new_danger, "max": danger_max, "advance": advance},
        "omen": omen,
        "encounter": encounter,
        "catastrophe": catastrophe,
        "boon": boon,
    }


def process_environment(state: Dict[str, Any], action_type: str, rng: Optional[random.Random] = None) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "white_breath": _white_breath_level(state),
        "events": [],
        "danger": None,
        "encounter": None,
        "omen": None,
    }

    if action_type in {"action", "tick"}:
        danger_result = tick_danger(state, rng)
        result["danger"] = danger_result["danger"]
        result["encounter"] = danger_result["encounter"]
        result["omen"] = danger_result["omen"]

        if danger_result["omen"]:
            result["events"].append(f"征兆: {danger_result['omen']}")
        if danger_result["catastrophe"]:
            result["events"].append("灾变: 风险陡增")
        if danger_result["boon"]:
            result["events"].append("转机: 风险暂缓")
        if danger_result["encounter"]:
            result["events"].append(f"遭遇触发: {danger_result['encounter']['monster']}")

    combat_event = _combat_environment_event(state, rng)
    if combat_event:
        result["events"].append(f"环境事件: {combat_event['name']} - {combat_event['desc']}")

    return result
