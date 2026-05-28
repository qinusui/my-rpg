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
from .sentinel_keys import BG_SWITCH_TARGET, PENDING_ENCOUNTER, TRIGGER_PREV_LOC
from .state import read_world_json


def _load_trigger_config() -> Dict[str, Any]:
    try:
        return read_world_json("narrative_config.json")
    except Exception:
        return {}


def _mood_to_scene() -> Dict[str, str]:
    return _load_trigger_config().get("mood_to_scene", {
        "social": "safe", "rest": "safe", "ritual": "tension",
    })


def _mood_keys() -> frozenset:
    keys = _load_trigger_config().get("mood_keys", ["safe", "normal", "tension", "danger", "tragedy"])
    return frozenset(keys)


def _trigger_templates() -> Dict[str, str]:
    return _load_trigger_config().get("trigger_templates", {})


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

        tt = _trigger_templates()
        if t == "new_encounter":
            env_result["encounter"] = enc_payload
            env_result["events"].append(
                tt.get("encounter_event_new", "遭遇触发: {monster}").format(monster=monster))
        elif t == "released_deferred":
            env_result["encounter"] = enc_payload
            env_result["events"].append(
                tt.get("encounter_event_released", "遭遇触发(挂起): {monster}").format(monster=monster))
        elif t == "deferred":
            env_result["deferred_encounter"] = enc_payload
            env_result["events"].append(
                tt.get("encounter_event_deferred", "遭遇挂起: {monster}").format(monster=monster))

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
            ce_tpl = _trigger_templates().get("combat_event_format", "环境事件: {name} - {desc}")
            env_result["events"].append(
                ce_tpl.format(name=combat_event["name"], desc=combat_event["desc"]))

    return env_result


# ─── Background Switching ────────────────────────────────────────────────


def _switch_background(action_tags: List[str], state: Dict[str, Any]):
    """Detect location/mood/combat changes and emit bg scene key.

    Uses sentinels in state (cleared after reading):
      __trigger_prev_loc — last known location for diff detection
      __bg_switch_target — computed target (caller reads, then clears)
    """
    prev_loc = state.pop(TRIGGER_PREV_LOC, None)
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
            mood = _mood_to_scene().get(tag) or (tag if tag in _mood_keys() else None)
            if mood:
                target = f"mood_{mood}"
                break

    # Emit signal (caller must clear __bg_switch_target after processing)
    if target:
        state[BG_SWITCH_TARGET] = target

    # Save current location for next turn's comparison
    state[TRIGGER_PREV_LOC] = cur_loc


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
        if state.get(PENDING_ENCOUNTER):
            state["pending_encounter"] = state.pop(PENDING_ENCOUNTER)
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


def _advance_danger(current: int, danger_max: int, danger_tick: str) -> tuple:
    """Pure: roll danger tick + luck check. Returns (new_danger, advance, catastrophe, boon)."""
    advance = roll_dice(danger_tick, random)
    new_danger = min(current + advance, danger_max)

    catastrophe = False
    boon = False
    luck = roll_d20(random)
    if luck == 1:
        catastrophe = True
        spike = max(2, danger_max // 3)
        new_danger = min(new_danger + spike, danger_max)
    elif luck == 20:
        boon = True
        new_danger = max(0, new_danger - 3)

    return new_danger, advance, catastrophe, boon


def _detect_omen(current: int, new_danger: int, omens: Dict[str, str]) -> Optional[str]:
    """Pure: check for threshold crossings. Returns omen text or None."""
    for threshold_str, omen_text in sorted(omens.items(), key=lambda x: int(x[0])):
        threshold = int(threshold_str)
        if current < threshold <= new_danger:
            return omen_text
    return None


def _select_encounter(
    raw_pool: List, action_tags: List[str], blocked_by: List[str],
    turn_count: int, advance: int,
) -> Dict[str, Any]:
    """Pure: filter pool, weighted random selection. Returns encounter dict."""
    pool = _filter_pool(raw_pool, action_tags)
    total_weight = sum(e["weight"] for e in pool)
    if total_weight == 0:
        return {"encounter": None, "deferred": None, "new_danger_override": 0}

    pick = random.randint(1, total_weight)
    acc = 0
    chosen = pool[-1]["id"]
    for parsed in pool:
        acc += parsed["weight"]
        if pick <= acc:
            chosen = parsed["id"]
            break

    payload = {"monster": chosen, "roll": advance, "turn": turn_count}

    if "action" in blocked_by:
        return {"encounter": None, "deferred": payload, "new_danger_override": None}
    return {"encounter": payload, "deferred": None, "new_danger_override": 0}


def _apply_danger_tick(
    entry: Dict[str, Any],
    action_tags: List[str],
    state: Dict[str, Any],
    location: str,
) -> Optional[Dict[str, Any]]:
    """Orchestrate danger advancement → omen detection → encounter selection."""
    danger_max = int(entry.get("danger_max", 0))
    danger_tick = entry.get("danger_tick", "1d3")
    omens = entry.get("omens", {})
    raw_pool = entry.get("pool", [])
    blocked_by = entry.get("trigger", {}).get("blocked_by", [])

    location_dangers = state.setdefault("location_dangers", {})
    current = int(location_dangers.get(location, 0))

    new_danger, advance, catastrophe, boon = _advance_danger(current, danger_max, danger_tick)
    omen = _detect_omen(current, new_danger, omens)

    encounter = None
    deferred_encounter = None

    if new_danger >= danger_max and raw_pool:
        sel = _select_encounter(raw_pool, action_tags, blocked_by,
                                int(state.get("turn_count", 0)), advance)
        override = sel.get("new_danger_override")
        if override is not None:
            new_danger = override
        encounter = sel.get("encounter")
        deferred_encounter = sel.get("deferred")

        if deferred_encounter:
            state["deferred_encounter"] = deferred_encounter
        elif encounter:
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
