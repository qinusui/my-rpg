"""Unified trigger — entry point for all per-turn side effects.

Usage (inside engine or CLI):
    result = trigger.apply(action_type, action_tags, state)

Orchestration order:
    1. Query gate — skip everything for query actions
    2. Background switching — location change → set; mood tags → mood; combat start/end
    3. Encounter resolution — danger tick + context-aware pool filtering + deferred release

All mutation goes through `state`. Results returned as dict compatible with
the original process_environment output format.
"""

import os
import random
from typing import Any, Dict, List, Optional

from .dice import roll_d20, roll_dice
from .state import read_world_json

# ─── Mood → bg scene mapping ─────────────────────────────────────────────

_MOOD_TO_SCENE: Dict[str, str] = {
    "social": "safe",
    "rest": "safe",
    "ritual": "tension",
}
_MOOD_KEYS: frozenset[str] = frozenset({"safe", "normal", "tension", "danger", "tragedy"})


def apply(
    action_type: str,
    action_tags: Optional[List[str]],
    state: Dict[str, Any],
) -> Dict[str, Any]:
    """Execute all trigger behaviors for one turn.

    Returns dict compatible with original process_environment format:
        white_breath, events, danger, omen, encounter, deferred_encounter
    """
    env_result: Dict[str, Any] = {
        "white_breath": _white_breath_level(state),
        "events": [],
        "danger": None,
        "encounter": None,
        "omen": None,
        "deferred_encounter": None,
    }

    # 1. Query gate — no side effects
    if action_type == "query":
        return env_result

    safe_tags = action_tags or []

    # 2. Background switching
    _switch_background(safe_tags, state)

    # 3. Encounter resolution
    encounter_info = _resolve_encounters(safe_tags, state)

    # Add to environment result
    if encounter_info:
        t = encounter_info.get("type")
        monster = encounter_info.get("monster")
        enc_payload = {"monster": monster} if monster else None

        if t == "new_encounter":
            env_result["encounter"] = enc_payload
            env_result["events"].append(f"遭遇触发: {monster}")
        elif t == "released_deferred":
            env_result["encounter"] = enc_payload
            env_result["events"].append(f"遭遇触发(挂起): {monster}")
        elif t == "deferred":
            env_result["deferred_encounter"] = enc_payload
            env_result["events"].append(
                f"遭遇挂起: {monster} (当前行动类型阻塞遭遇触发)"
            )

        danger = encounter_info.get("danger")
        if danger:
            env_result["danger"] = danger
        omen = encounter_info.get("omen")
        if omen:
            env_result["omen"] = omen

    # 4. Combat-specific environment event (15% chance)
    combat_state = state.get("combat_state")
    if combat_state:
        combat_event = _roll_combat_event(state)
        if combat_event:
            env_result["events"].append(
                f"环境事件: {combat_event['name']} - {combat_event['desc']}"
            )

    return env_result


# ─── Background Switching ────────────────────────────────────────────────


def _switch_background(action_tags: List[str], state: Dict[str, Any]):
    """Detect location/mood/combat changes and emit bg scene key.

    Uses sentinels in state (cleared after reading):
      __trigger_prev_loc — last known location for diff detection
      __bg_switch_target — computed target (caller reads, then clears)
    """
    prev_loc = state.pop("__trigger_prev_loc", None)
    cur_loc = state.get("current_location", "")
    combat_state = state.get("combat_state")

    target = None
    if combat_state is not None:
        target = f"combat_{combat_state.get('mode', 'battle')}"
    elif prev_loc is None or prev_loc != cur_loc:
        target = cur_loc
    elif action_tags:
        for tag in action_tags:
            if tag == "combat":
                break
            mood = _MOOD_TO_SCENE.get(tag) or (tag if tag in _MOOD_KEYS else None)
            if mood:
                target = f"mood_{mood}"
                break

    # Emit signal (caller must clear __bg_switch_target after processing)
    if target:
        state["__bg_switch_target"] = target

    # Save current location for next turn's comparison
    state["__trigger_prev_loc"] = cur_loc


# ─── Environment Helpers ─────────────────────────────────────────────────


def _white_breath_level(state: Dict[str, Any]) -> str:
    location = state.get("current_location", "")
    constants = read_world_json("world_constants.json")
    loc = constants.get("locations", {}).get(location, {})
    return loc.get("white_breath_level", "low")


def _roll_combat_event(state, rng=None):
    """15% chance of combat-specific environment event."""
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


# ─── Encounter Resolution ────────────────────────────────────────────────


def _resolve_encounters(
    action_tags: List[str],
    state: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Full encounter pipeline: defer resolve → danger tick → pool selection."""
    location = state.get("current_location", "")
    encounter_tables = read_world_json("encounter_tables.json")
    entry = encounter_tables.get(location) or encounter_tables.get("_default", {})

    danger_max = int(entry.get("danger_max", 0))
    if danger_max <= 0:
        # Still check for pending encounter release
        if state.get("__pending_encounter"):
            state["pending_encounter"] = state.pop("__pending_encounter")
            state.pop("deferred_encounter", None)
            location_dangers = state.get("location_dangers", {})
            location_dangers[location] = 0
            state["location_dangers"] = location_dangers
            return {"type": "released_deferred", "monster": state["pending_encounter"]["monster"]}
        return None

    # Step A: Release any previously deferred encounter
    resolved = _release_pending_deferred(state, entry, location)
    if resolved:
        location_dangers = state.get("location_dangers", {})
        location_dangers[location] = 0
        state["location_dangers"] = location_dangers
        return {
            "type": "released_deferred",
            "monster": resolved,
            "danger": {"current": 0, "max": danger_max},
            "omen": None,
        }

    # Step B: Apply danger tick
    return _apply_danger_tick(entry, action_tags, state, location)


def _release_pending_deferred(
    state: Dict[str, Any],
    entry: Dict[str, Any],
    location: str,
) -> Optional[str]:
    """Check if there's a deferred encounter that can now fire."""
    deferred = state.get("deferred_encounter")
    if not deferred:
        return None

    trigger_cfg = entry.get("trigger", {})
    blocked_by = trigger_cfg.get("blocked_by", [])
    # If "action" blocks, tick won't be blocked (only action type blocks)
    if "action" in blocked_by:
        return None

    state.pop("deferred_encounter", None)
    return deferred["monster"]


def _apply_danger_tick(
    entry: Dict[str, Any],
    action_tags: List[str],
    state: Dict[str, Any],
    location: str,
) -> Optional[Dict[str, Any]]:
    """Roll danger advancement, check luck, resolve omens, select encounter."""
    rng = random

    danger_max = int(entry.get("danger_max", 0))
    danger_tick = entry.get("danger_tick", "1d3")
    omens = entry.get("omens", {})
    raw_pool = entry.get("pool", [])
    trigger_cfg = entry.get("trigger", {})
    blocked_by = trigger_cfg.get("blocked_by", [])

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
        pool = _filter_pool(raw_pool, action_tags)
        total_weight = sum(e["weight"] for e in pool)
        pick = rng.randint(1, total_weight)
        acc = 0
        chosen = pool[-1]["id"]
        for parsed in pool:
            acc += parsed["weight"]
            if pick <= acc:
                chosen = parsed["id"]
                break

        encounter_payload = {
            "monster": chosen,
            "roll": advance,
            "turn": int(state.get("turn_count", 0)),
        }

        if "action" in blocked_by:
            deferred_encounter = encounter_payload
            state["deferred_encounter"] = encounter_payload
        else:
            encounter = encounter_payload
            new_danger = 0
            state.pop("deferred_encounter", None)
    elif new_danger >= danger_max:
        new_danger = 0

    location_dangers[location] = new_danger
    state["location_dangers"] = location_dangers

    return {
        "type": ("new_encounter" if encounter else "none"),
        "monster": encounter["monster"] if encounter else (
            deferred_encounter["monster"] if deferred_encounter else None
        ),
        "encounter": encounter,
        "deferred_encounter": deferred_encounter,
        "danger": {"current": new_danger, "max": danger_max, "advance": advance},
        "omen": omen,
        "catastrophe": catastrophe,
        "boon": boon,
    }


def _parse_pool_entry(entry) -> Dict[str, Any]:
    """兼容旧格式 [id, weight] 和新格式 {id, weight, tags}"""
    if isinstance(entry, list):
        return {"id": entry[0], "weight": entry[1], "tags": []}
    return {
        "id": entry.get("id", "unknown"),
        "weight": entry.get("weight", 1),
        "tags": entry.get("tags", []),
    }


def _filter_pool(
    raw_pool: List,
    action_tags: List[str],
) -> List[Dict[str, Any]]:
    """按当前行动标签过滤遭遇池。有匹配时只返回匹配项，无匹配时返回全池。"""
    if not action_tags or not raw_pool:
        return [_parse_pool_entry(e) for e in raw_pool]
    parsed = [_parse_pool_entry(e) for e in raw_pool]
    matching = [e for e in parsed if any(t in action_tags for t in e.get("tags", []))]
    return matching if matching else parsed
