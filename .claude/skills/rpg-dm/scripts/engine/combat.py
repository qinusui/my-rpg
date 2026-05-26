import random
from typing import Any, Dict, List, Optional, Tuple

from .state import load_state, read_world_json, save_state


def _damage_attr() -> str:
    try:
        default_state = read_world_json("default_state.json")
        return default_state.get("combat_damage_attr", "constitution")
    except Exception:
        return "constitution"


def _apply_ticks_to_player(state: Dict[str, Any], ticks: int) -> int:
    if ticks <= 0:
        return 0
    attr_key = _damage_attr()
    clock = state.setdefault("clocks", {}).get(attr_key)
    if not clock:
        return 0
    clock["filled"] = min(clock["max"], clock["filled"] + ticks)
    return ticks


def _get_player_damage_track(state: Dict[str, Any]) -> Tuple[int, int]:
    attr_key = _damage_attr()
    clock = state.get("clocks", {}).get(attr_key, {})
    return int(clock.get("filled", 0)), int(clock.get("max", 8))


def _player_is_dead(state: Dict[str, Any]) -> bool:
    filled, max_value = _get_player_damage_track(state)
    return filled >= max_value


def _mk_override(options: List[str]) -> Dict[str, Any]:
    return {"available": True, "options": options, "requires_reason": True}


def _next_log_id(combat_state: Dict[str, Any]) -> int:
    return len(combat_state.get("combat_log", [])) + 1


def _tick_effects(combat_state: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    ticks: List[Dict[str, Any]] = []
    expired: List[Dict[str, Any]] = []

    for enemy_id, enemy in combat_state.get("enemies", {}).items():
        if enemy.get("defeated"):
            continue
        for effect in enemy.get("effects", []):
            effect["turns"] = effect.get("turns", 1) - 1
            if effect["turns"] <= 0:
                expired.append({"target": enemy_id, "effect": effect["name"]})
            else:
                ticks.append(
                    {
                        "target": f"{enemy['name']}({enemy_id})",
                        "effect": effect["name"],
                        "turns_left": effect["turns"],
                    }
                )
        enemy["effects"] = [effect for effect in enemy.get("effects", []) if effect.get("turns", 1) > 0]

    for effect in combat_state.get("player_effects", []):
        effect["turns"] = effect.get("turns", 1) - 1
        if effect["turns"] <= 0:
            expired.append({"target": "player", "effect": effect["name"]})
        else:
            ticks.append({"target": "玩家", "effect": effect["name"], "turns_left": effect["turns"]})
    combat_state["player_effects"] = [effect for effect in combat_state.get("player_effects", []) if effect.get("turns", 1) > 0]

    return ticks, expired


def _roll_environment(state: Dict[str, Any]) -> Optional[Tuple[str, str]]:
    if random.randint(1, 100) > 15:
        return None
    location = state.get("current_location", "")
    event_table = read_world_json("environment_events.json")
    for keyword, events in event_table.items():
        if keyword == "_default":
            continue
        if keyword in location and events:
            return random.choice(events)
    defaults = event_table.get("_default", [])
    if not defaults:
        return None
    return random.choice(defaults)


def init_combat(monster_key: str, count: int = 1) -> Dict[str, Any]:
    state = load_state()
    bestiary = read_world_json("bestiary.json")

    name_cn = monster_key
    if monster_key in bestiary:
        name_cn = bestiary[monster_key].get("name_cn", monster_key)

    enemies = {}
    for i in range(1, count + 1):
        enemy_id = f"{monster_key}_{i}"
        enemies[enemy_id] = {"name": name_cn, "key": monster_key, "defeated": False, "effects": []}

    state["combat_state"] = {
        "enemies": enemies,
        "player_effects": [],
        "environment": None,
        "combat_log": [],
        "turn": 0,
    }
    save_state(state)

    return {
        "combat_started": True,
        "enemies": [{"id": enemy_id, "name": enemy["name"]} for enemy_id, enemy in enemies.items()],
        "turn": 0,
        "dm_override": _mk_override(["advance_phase"]),
    }


def end_combat() -> Dict[str, Any]:
    state = load_state()
    combat_state = state.get("combat_state")
    if not combat_state:
        return {"error": "没有进行中的战斗"}

    defeated = []
    escaped = []
    for _, enemy in combat_state.get("enemies", {}).items():
        if enemy.get("defeated"):
            defeated.append(enemy["name"])
        else:
            escaped.append(enemy["name"])

    total_rounds = len([entry for entry in combat_state.get("combat_log", []) if entry.get("type") == "round_event"])

    state["combat_state"] = None
    save_state(state)

    return {
        "combat_ended": True,
        "defeated": defeated,
        "escaped": escaped,
        "total_rounds": total_rounds,
        "dm_override": _mk_override([]),
    }


def round_event() -> Dict[str, Any]:
    state = load_state()
    combat_state = state.get("combat_state")
    if not combat_state:
        return {"error": "没有进行中的战斗"}

    effect_ticks, effects_expired = _tick_effects(combat_state)
    combat_state["turn"] = combat_state.get("turn", 0) + 1

    env_event = _roll_environment(state)
    env_data = {"name": env_event[0], "desc": env_event[1]} if env_event else None
    combat_state["environment"] = env_data

    combat_state.setdefault("combat_log", []).append(
        {
            "id": _next_log_id(combat_state),
            "turn": combat_state["turn"],
            "type": "round_event",
            "effect_ticks": effect_ticks,
            "effects_expired": effects_expired,
            "environment_event": env_data,
        }
    )

    damage_attr = _damage_attr()
    filled, max_value = _get_player_damage_track(state)

    result: Dict[str, Any] = {
        "turn": combat_state["turn"],
        "effect_ticks": effect_ticks,
        "effects_expired": effects_expired,
        "environment_event": env_data,
        "damage_track": {"attr": damage_attr, "filled": filled, "max": max_value},
        "dm_override": _mk_override([]),
    }

    if _player_is_dead(state):
        result["combat_over"] = True
        result["victory"] = False
        state["combat_state"] = None

    save_state(state)
    return result


def trigger_env_event(event_key: Optional[str] = None) -> Dict[str, Any]:
    state = load_state()
    combat_state = state.get("combat_state")
    if not combat_state:
        return {"error": "没有进行中的战斗"}

    env_event = None
    if event_key and event_key != "random":
        table = read_world_json("environment_events.json")
        all_events = {}
        for events in table.values():
            for name, desc in events:
                all_events[name] = (name, desc)
        env_event = all_events.get(event_key)
        if not env_event:
            return {"error": f"未知环境事件: {event_key}"}
    else:
        env_event = _roll_environment(state)

    if env_event:
        name, desc = env_event
        combat_state["environment"] = {"name": name, "desc": desc}
    else:
        combat_state["environment"] = None

    env_payload = {"name": name, "desc": desc} if env_event else None

    combat_state.setdefault("combat_log", []).append(
        {
            "id": _next_log_id(combat_state),
            "turn": combat_state["turn"],
            "type": "env_event",
            "environment_event": env_payload,
        }
    )

    save_state(state)
    return {
        "turn": combat_state["turn"],
        "environment_event": env_payload,
        "dm_override": _mk_override([]),
    }


def tick_constitution(amount: int) -> Dict[str, Any]:
    state = load_state()
    combat_state = state.get("combat_state")
    if not combat_state:
        return {"error": "没有进行中的战斗"}

    _apply_ticks_to_player(state, amount)
    filled, max_value = _get_player_damage_track(state)
    damage_attr = _damage_attr()

    result: Dict[str, Any] = {
        "tick_applied": amount,
        "damage_track": damage_attr,
        "filled": filled,
        "max": max_value,
    }

    if _player_is_dead(state):
        result["combat_over"] = True
        result["victory"] = False
        state["combat_state"] = None

    save_state(state)
    return result


def apply_override(override_type: str, reason: str, value: Optional[int] = None, target: Optional[str] = None) -> Dict[str, Any]:
    if not reason:
        return {"error": "--reason 是必填字段，覆盖操作必须提供理由"}

    state = load_state()
    combat_state = state.get("combat_state")
    if not combat_state:
        return {"error": "没有进行中的战斗"}

    override_result: Dict[str, Any] = {}

    if override_type == "advance_phase":
        if not target:
            return {"error": "advance_phase 需要 --target 参数（敌人 ID）"}
        if target not in combat_state["enemies"]:
            return {"error": f"目标不存在: {target}"}
        enemy = combat_state["enemies"][target]
        old_phase = enemy.get("phase", 1)
        enemy["phase"] = old_phase + 1
        override_result = {
            "target": target,
            "from_phase": old_phase,
            "to_phase": enemy["phase"],
            "detail": f"DM 覆盖: {enemy['name']}({target}) 阶段推进: {old_phase} → {enemy['phase']}",
        }

    elif override_type == "add_effect":
        if not target:
            return {"error": "add_effect 需要 --target 参数"}
        if target == "player":
            combat_state.setdefault("player_effects", []).append({"name": f"dm_override_{_next_log_id(combat_state)}", "turns": 2})
        elif target in combat_state["enemies"]:
            combat_state["enemies"][target].setdefault("effects", []).append(
                {"name": f"dm_override_{_next_log_id(combat_state)}", "turns": 2}
            )
        else:
            return {"error": f"目标不存在: {target}"}
        override_result = {"effect_added": True, "target": target, "detail": "DM 覆盖: 添加效果"}

    elif override_type == "defeat_enemy":
        if not target:
            return {"error": "defeat_enemy 需要 --target 参数"}
        if target not in combat_state["enemies"]:
            return {"error": f"目标不存在: {target}"}
        combat_state["enemies"][target]["defeated"] = True
        override_result = {
            "target": target,
            "enemy_defeated": True,
            "detail": f"DM 覆盖: {combat_state['enemies'][target]['name']}({target}) 被击败",
        }

    elif override_type == "undo_override":
        last_override = None
        for entry in reversed(combat_state.get("combat_log", [])):
            if entry.get("type") == "override":
                last_override = entry
                break
        if not last_override:
            return {"error": "没有可撤销的覆盖操作"}

        ov_type = last_override.get("override_type", "")
        ov_result = last_override.get("override", {})

        if ov_type == "defeat_enemy":
            target_id = ov_result.get("target")
            if target_id and target_id in combat_state["enemies"]:
                combat_state["enemies"][target_id]["defeated"] = False
            override_result = {"detail": "DM 覆盖: 撤销 defeat_enemy"}

        elif ov_type == "advance_phase":
            target_id = ov_result.get("target")
            if target_id and target_id in combat_state["enemies"]:
                combat_state["enemies"][target_id]["phase"] = max(1, combat_state["enemies"][target_id].get("phase", 1) - 1)
            override_result = {"detail": "DM 覆盖: 撤销 advance_phase"}

        elif ov_type == "add_effect":
            target_id = ov_result.get("target")
            if target_id == "player":
                combat_state["player_effects"] = [
                    fx for fx in combat_state.get("player_effects", []) if not fx["name"].startswith("dm_override_")
                ]
            elif target_id in combat_state["enemies"]:
                combat_state["enemies"][target_id]["effects"] = [
                    fx
                    for fx in combat_state["enemies"][target_id].get("effects", [])
                    if not fx["name"].startswith("dm_override_")
                ]
            override_result = {"detail": "DM 覆盖: 撤销 add_effect"}
        else:
            return {"error": f"无法撤销类型: {ov_type}"}

    else:
        return {"error": f"未知覆盖类型: {override_type}"}

    combat_state["enemies"] = {
        enemy_id: enemy for enemy_id, enemy in combat_state.get("enemies", {}).items() if not enemy.get("defeated")
    }

    combat_state.setdefault("combat_log", []).append(
        {
            "id": _next_log_id(combat_state),
            "turn": combat_state["turn"],
            "type": "override",
            "override_type": override_type,
            "reason": reason,
            "override": override_result,
        }
    )

    state.setdefault("dm_log", []).append(
        {
            "turn": state.get("turn_count", 0),
            "combat_turn": combat_state["turn"],
            "type": override_type,
            "reason": reason,
            "override": override_result,
        }
    )

    result: Dict[str, Any] = {
        "overridden": True,
        "type": override_type,
        "reason": reason,
        "new_result": override_result,
        "dm_override": _mk_override(["undo_override"]),
    }

    if not combat_state["enemies"]:
        result["combat_over"] = True
        result["victory"] = True
        state["combat_state"] = None
    elif _player_is_dead(state):
        result["combat_over"] = True
        result["victory"] = False
        state["combat_state"] = None

    save_state(state)
    return result
