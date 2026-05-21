import json
import os
import random
import sys
import re
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from world_loader import world_file

STATE_FILE = "state.json"

# ── World data (loaded from active world JSON files) ─────────
with open(world_file("bestiary.json"), "r", encoding="utf-8") as _f:
    BESTIARY = json.load(_f)

with open(world_file("items.json"), "r", encoding="utf-8") as _f:
    _items = json.load(_f)
    WEAPON_TICKS = _items["weapons"]
    ARMOR_BONUSES = _items["armors"]

with open(world_file("environment_events.json"), "r", encoding="utf-8") as _f:
    _env = json.load(_f)
    ENVIRONMENT_EVENTS = {k: v for k, v in _env.items() if k != "_default"}
    DEFAULT_ENV_EVENTS = _env.get("_default", [])


# ── helpers ────────────────────────────────────────────────

def _load():
    with open(STATE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(s):
    """Atomic write with backup — never corrupts state.json."""
    tmp_fd, tmp_path = tempfile.mkstemp(
        suffix=".json", prefix=".state_tmp_", dir="."
    )
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            json.dump(s, f, ensure_ascii=False, indent=2)
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


# ── player (constitution clock) ────────────────────────────

def _apply_ticks_to_player(s, ticks):
    """Apply clock ticks to player constitution. Returns ticks applied."""
    if ticks <= 0:
        return 0
    con = s.setdefault("clocks", {}).get("constitution")
    if not con:
        return 0
    con["filled"] = min(con["max"], con["filled"] + ticks)
    return ticks


def _get_player_constitution(s):
    """Return (filled, max) for player constitution clock."""
    con = s.get("clocks", {}).get("constitution", {})
    return con.get("filled", 0), con.get("max", 8)


def _player_is_dead(s):
    """Check if player constitution clock is full."""
    filled, mx = _get_player_constitution(s)
    return filled >= mx


# ── enemy phase helpers ────────────────────────────────────

def _enemy_dead(e):
    """Check if enemy is dead (all phases completed)."""
    return e.get("current_phase", 0) >= len(e.get("phases", []))


def _enemy_phase_info(e):
    """Return current phase info dict for an enemy."""
    idx = e.get("current_phase", 0)
    phases = e.get("phases", [])
    if idx >= len(phases):
        return {"index": idx, "name": None, "filled": 0, "max": 0, "total_phases": len(phases)}
    return {
        "index": idx,
        "name": phases[idx]["name"],
        "filled": e.get("phase_filled", 0),
        "max": phases[idx]["max"],
        "total_phases": len(phases),
    }


def _sync_enemy_from_phase(e):
    """Sync enemy ac/ticks/bonus_ticks from current phase."""
    idx = e.get("current_phase", 0)
    phases = e.get("phases", [])
    if idx < len(phases):
        p = phases[idx]
        e["ac"] = p.get("ac", e.get("ac", 10))
        e["ticks"] = p.get("ticks", e.get("ticks", "1d2"))
        if "bonus_ticks" in p:
            e["bonus_ticks"] = p["bonus_ticks"]
        if "bonus_label" in p:
            e["bonus_label"] = p["bonus_label"]


def _apply_ticks_to_enemy(e, ticks):
    """Apply clock ticks to enemy's phase clocks.
    Handles phase transitions with overflow. Returns result dict."""
    if ticks <= 0:
        return {"ticks": 0, "phase_transition": None, "enemy_defeated": _enemy_dead(e),
                "current_phase": _enemy_phase_info(e)}

    phases = e.get("phases", [])
    transitions = []

    remaining = ticks
    while remaining > 0:
        idx = e.get("current_phase", 0)
        if idx >= len(phases):
            break

        phase = phases[idx]
        capacity = phase["max"] - e.get("phase_filled", 0)

        if remaining >= capacity:
            remaining -= capacity
            old_name = phase["name"]
            e["current_phase"] = idx + 1

            if e["current_phase"] >= len(phases):
                e["phase_filled"] = phase["max"]
                _sync_enemy_from_phase(e)
                transitions.append({
                    "from": old_name, "to": None, "enemy_defeated": True,
                })
                break
            else:
                new_phase = phases[e["current_phase"]]
                e["phase_filled"] = 0
                _sync_enemy_from_phase(e)
                transitions.append({
                    "from": old_name, "to": new_phase["name"],
                    "ac_was": phase.get("ac"), "ac_now": new_phase.get("ac"),
                    "behavior": new_phase.get("behavior", ""),
                    "attack": new_phase.get("attack", ""),
                    "enemy_defeated": False,
                })
        else:
            e["phase_filled"] = e.get("phase_filled", 0) + remaining
            remaining = 0

    return {
        "ticks": ticks,
        "phase_transition": transitions[-1] if transitions else None,
        "all_transitions": transitions if len(transitions) > 1 else None,
        "enemy_defeated": _enemy_dead(e),
        "current_phase": _enemy_phase_info(e),
    }


def _roll(dice_str):
    """Roll dice or return flat value. Supports '2d6', '1d8+2', or flat int/str like 1 or '2'."""
    if isinstance(dice_str, (int, float)):
        return int(dice_str), str(int(dice_str))
    s = str(dice_str)
    if s.lstrip('-').isdigit():
        return int(s), s
    m = re.match(r"(\d+)d(\d+)(?:([+-])(\d+))?$", s)
    if not m:
        return 0, "0"
    count, sides = int(m.group(1)), int(m.group(2))
    op, mod = m.group(3), int(m.group(4)) if m.group(4) else 0
    rolls = [random.randint(1, sides) for _ in range(count)]
    total = sum(rolls) + (mod if op == "+" else -mod if op == "-" else 0)
    detail = "+".join(str(r) for r in rolls)
    if mod:
        detail += f"{op}{mod}"
    return total, detail


def _get_player_ac(s):
    base = 12
    eq = s.get("equipped", {})
    armor_id = eq.get("armor") if eq else None
    if armor_id:
        for it in s.get("inventory", []):
            if it["id"] == armor_id:
                base += ARMOR_BONUSES.get(it["name"], 0)
                break
    return base


def _get_player_ticks(s):
    """Return tick dice string for player's equipped weapon."""
    eq = s.get("equipped", {})
    weapon_id = eq.get("weapon") if eq else None
    if weapon_id:
        for it in s.get("inventory", []):
            if it["id"] == weapon_id:
                w = WEAPON_TICKS.get(it["name"], {})
                if w:
                    return w.get("ticks", "1d2")
                break
    return "1d2"


def _mk_override(options):
    """Return the standard dm_override block."""
    return {"available": True, "options": options, "requires_reason": True}


def _next_log_id(cs):
    logs = cs.get("combat_log", [])
    return len(logs) + 1


# ── effect ticking ─────────────────────────────────────────

def _tick_effects(cs):
    """Tick all status effects on enemies and player. Return summary."""
    ticks = []
    expired = []

    # Tick enemy effects
    for eid, e in cs.get("enemies", {}).items():
        if _enemy_dead(e):
            continue
        for fx in e.get("effects", []):
            result = _tick_single_effect(fx, f"{e['name_cn']}({eid})")
            if result:
                if result.get("expired"):
                    expired.append({"target": eid, "effect": fx["name"]})
                else:
                    ticks.append(result)
        e["effects"] = [fx for fx in e.get("effects", []) if fx.get("turns", 1) > 0]

    # Tick player effects
    for fx in cs.get("player_effects", []):
        result = _tick_single_effect(fx, "玩家")
        if result:
            if result.get("expired"):
                expired.append({"target": "player", "effect": fx["name"]})
            else:
                ticks.append(result)
    cs["player_effects"] = [fx for fx in cs.get("player_effects", []) if fx.get("turns", 1) > 0]

    return ticks, expired


def _tick_single_effect(fx, label):
    ticks_str = fx.get("ticks", "0")
    ticks, _ = _roll(ticks_str) if ticks_str != "0" else (0, "0")
    fx["turns"] = fx.get("turns", 1) - 1
    expired = fx["turns"] <= 0
    return {
        "target": label,
        "effect": fx["name"],
        "ticks": ticks,
        "turns_left": fx["turns"],
        "expired": expired,
    }


# ── environment events ─────────────────────────────────────

def _roll_environment(s):
    """15% chance to trigger an environment event. Returns event or None."""
    if random.randint(1, 100) > 15:
        return None
    loc = s.get("current_location", "")
    for keyword, events in ENVIRONMENT_EVENTS.items():
        if keyword in loc:
            return random.choice(events)
    return random.choice(DEFAULT_ENV_EVENTS)


def trigger_env_event(event_key=None):
    """DM triggers an environment event. event_key=None → random from location table."""
    s = _load()
    cs = s.get("combat_state")
    if not cs:
        print(json.dumps({"error": "没有进行中的战斗"}, ensure_ascii=False))
        sys.exit(1)

    if event_key and event_key != "random":
        all_events = {name: (name, desc, spec) for name, desc, spec in DEFAULT_ENV_EVENTS}
        for events in ENVIRONMENT_EVENTS.values():
            for name, desc, spec in events:
                all_events[name] = (name, desc, spec)
        env_event = all_events.get(event_key)
        if not env_event:
            print(json.dumps({"error": f"未知环境事件: {event_key}，可用: {list(all_events.keys())}"}, ensure_ascii=False))
            sys.exit(1)
    else:
        env_event = _roll_environment(s)

    if env_event:
        name, desc, spec = env_event
        cs["environment"] = {"name": name, "desc": desc, "spec": spec}
    else:
        cs["environment"] = None

    log_entry = {
        "id": _next_log_id(cs), "turn": cs["turn"], "type": "env_event",
        "environment_event": {"name": name, "desc": desc} if env_event else None,
    }
    cs.setdefault("combat_log", []).append(log_entry)

    _save(s)
    print(json.dumps({
        "turn": cs["turn"],
        "environment_event": {"name": name, "desc": desc} if env_event else None,
        "dm_override": {"reason_required": True, "options": []},
    }, ensure_ascii=False))


# ── ops ────────────────────────────────────────────────────

def init_combat(monster_key, count=1):
    data = BESTIARY.get(monster_key)
    if not data:
        print(json.dumps({"error": f"未知怪物: {monster_key}"}, ensure_ascii=False))
        sys.exit(1)

    s = _load()
    phases = data["phases"]
    enemies = {}
    for i in range(1, count + 1):
        eid = f"{monster_key}_{i}"
        p0 = phases[0]
        enemies[eid] = {
            "name_cn": data["name_cn"],
            "key": monster_key,
            "phases": phases,
            "current_phase": 0,
            "phase_filled": 0,
            "ac": p0["ac"],
            "ticks": p0.get("ticks", data.get("ticks", "1d2")),
            "bonus_ticks": p0.get("bonus_ticks") or data.get("bonus_ticks"),
            "bonus_label": p0.get("bonus_label") or data.get("bonus_label"),
            "special": data.get("special", ""),
            "effects": [],
        }

    s["combat_state"] = {
        "enemies": enemies,
        "player_effects": [],
        "environment": None,
        "combat_log": [],
        "turn": 0,
    }
    _save(s)

    monster_list = []
    for eid, e in enemies.items():
        pi = _enemy_phase_info(e)
        monster_list.append({
            "id": eid, "name": e["name_cn"],
            "phase": f"{pi['name']} ({pi['filled']}/{pi['max']})",
            "phase_index": f"{pi['index'] + 1}/{pi['total_phases']}",
            "ac": e["ac"],
        })

    result = {
        "combat_started": True,
        "enemies": monster_list,
        "turn": 0,
        "dm_override": _mk_override(["advance_phase"]),
    }
    print(json.dumps(result, ensure_ascii=False))


def end_combat():
    s = _load()
    cs = s.get("combat_state")
    if not cs:
        print(json.dumps({"error": "没有进行中的战斗"}, ensure_ascii=False))
        sys.exit(1)

    defeated = []
    escaped = []
    for eid, e in cs.get("enemies", {}).items():
        if _enemy_dead(e):
            defeated.append(e["name_cn"])
        else:
            escaped.append(e["name_cn"])

    combat_log = cs.get("combat_log", [])

    s["combat_state"] = None
    _save(s)

    print(json.dumps({
        "combat_ended": True,
        "defeated": defeated,
        "escaped": escaped,
        "total_rounds": len([e for e in combat_log if e.get("type") == "round_event"]),
        "dm_override": _mk_override([]),
    }, ensure_ascii=False))


def round_event():
    s = _load()
    cs = s.get("combat_state")
    if not cs:
        print(json.dumps({"error": "没有进行中的战斗"}, ensure_ascii=False))
        sys.exit(1)

    # 1. Tick existing effects
    effect_ticks, expired = _tick_effects(cs)

    # 2. Apply tick damage from effects to enemies
    for t in effect_ticks:
        if t["ticks"] > 0:
            target_label = t["target"]
            for eid, e in cs["enemies"].items():
                if f"{e['name_cn']}({eid})" == target_label:
                    result = _apply_ticks_to_enemy(e, t["ticks"])
                    t["phase_result"] = result
                    break
            if "玩家" in target_label:
                _apply_ticks_to_player(s, t["ticks"])

    # 3. Remove dead enemies
    cs["enemies"] = {eid: e for eid, e in cs.get("enemies", {}).items() if not _enemy_dead(e)}

    cs["turn"] = cs.get("turn", 0) + 1

    # 4. Auto-roll environment event
    env_event = _roll_environment(s)
    env_data = {"name": env_event[0], "desc": env_event[1]} if env_event else None
    if env_event:
        name, desc, spec = env_event
        cs["environment"] = {"name": name, "desc": desc, "spec": spec}
    else:
        cs["environment"] = None

    # 5. Auto-execute enemy attacks (all surviving enemies)
    env_spec = env_event[2] if env_event else {}
    enemy_attacks = []
    for eid in list(cs.get("enemies", {}).keys()):
        if not _enemy_dead(cs["enemies"][eid]):
            atk_result = _monster_attack(s, cs, eid, "player", env_spec)
            enemy_attacks.append(atk_result)
            # Log each attack
            cs.setdefault("combat_log", []).append({
                "id": _next_log_id(cs), "turn": cs["turn"], "type": "attack",
                "attacker": eid, "target": "player",
                "ticks": atk_result.get("ticks", 0),
                "result": {k: v for k, v in atk_result.items() if k != "dm_override"},
            })

    # 6. Remove dead enemies (from attacks)
    cs["enemies"] = {eid: e for eid, e in cs.get("enemies", {}).items() if not _enemy_dead(e)}

    # 7. Log round event
    log_entry = {
        "id": _next_log_id(cs), "turn": cs["turn"], "type": "round_event",
        "effect_ticks": effect_ticks, "effects_expired": expired,
        "environment_event": env_data,
        "enemy_attacks": len(enemy_attacks),
    }
    cs.setdefault("combat_log", []).append(log_entry)

    # 8. Check combat end
    result = {
        "turn": cs["turn"],
        "effect_ticks": effect_ticks,
        "effects_expired": expired,
        "environment_event": env_data,
        "enemy_attacks": enemy_attacks,
        "dm_override": _mk_override([]),
    }
    if not cs["enemies"]:
        result["combat_over"] = True
        result["victory"] = True
        s["combat_state"] = None
    elif _player_is_dead(s):
        result["combat_over"] = True
        result["victory"] = False
        s["combat_state"] = None

    _save(s)
    print(json.dumps(result, ensure_ascii=False))


def resolve_action(attacker, target, action):
    s = _load()
    cs = s.get("combat_state")
    if not cs:
        print(json.dumps({"error": "没有进行中的战斗，请先 --init"}, ensure_ascii=False))
        sys.exit(1)

    if action != "attack":
        print(json.dumps({"error": f"未知行动: {action}"}, ensure_ascii=False))
        sys.exit(1)

    # Apply environment modifiers
    env = cs.get("environment") or {}
    env_spec = env.get("spec", {})

    if attacker == "player":
        result = _player_attack(s, cs, target, env_spec)
    elif attacker in cs.get("enemies", {}):
        result = _monster_attack(s, cs, attacker, target, env_spec)
    else:
        print(json.dumps({"error": f"未知攻击方: {attacker}"}, ensure_ascii=False))
        sys.exit(1)

    if "error" in result:
        print(json.dumps(result, ensure_ascii=False))
        sys.exit(1)

    cs["turn"] = cs.get("turn", 0) + 1

    # Remove dead enemies
    cs["enemies"] = {eid: e for eid, e in cs.get("enemies", {}).items() if not _enemy_dead(e)}

    # Log the action
    log_entry = {
        "id": _next_log_id(cs), "turn": cs["turn"], "type": "attack",
        "attacker": attacker, "target": target,
        "ticks": result.get("ticks", 0),
        "result": {k: v for k, v in result.items() if k != "dm_override"},
    }
    cs.setdefault("combat_log", []).append(log_entry)

    # Add dm_override to result
    result["dm_override"] = _mk_override(["modify_ticks", "add_effect"])

    # Check combat end
    if not cs["enemies"]:
        result["combat_over"] = True
        result["victory"] = True
        s["combat_state"] = None
    elif _player_is_dead(s):
        result["combat_over"] = True
        result["victory"] = False
        s["combat_state"] = None

    _save(s)
    print(json.dumps(result, ensure_ascii=False))


def apply_override(override_type, reason, value=None, target=None, monster=None, count=1):
    if not reason:
        print(json.dumps({"error": "--reason 是必填字段，覆盖操作必须提供理由"}, ensure_ascii=False))
        sys.exit(1)

    s = _load()
    cs = s.get("combat_state")
    if not cs:
        print(json.dumps({"error": "没有进行中的战斗"}, ensure_ascii=False))
        sys.exit(1)

    log = cs.get("combat_log", [])

    # Types that don't need a prior log entry
    standalone = {"advance_phase"}
    # Types that operate on the last log entry
    needs_log = {"modify_ticks", "add_effect", "undo_override"}

    if override_type in needs_log and not log:
        print(json.dumps({"error": "没有可覆盖的操作记录"}, ensure_ascii=False))
        sys.exit(1)

    last = log[-1] if log else None
    original = dict(last.get("result", {})) if last else {}
    old_ticks = last.get("ticks", 0) if last else 0

    # ── Reverse old ticks (for attack-based overrides) ──
    if override_type in {"modify_ticks", "add_effect"}:
        if old_ticks != 0:
            if last.get("attacker") == "player":
                target_id = last.get("target")
                if target_id in cs["enemies"]:
                    e = cs["enemies"][target_id]
                    # Restore phase from log
                    phase_before = last.get("result", {}).get("phase_before", {})
                    if phase_before:
                        e["current_phase"] = phase_before.get("index", 0)
                        e["phase_filled"] = phase_before.get("filled", 0)
                        _sync_enemy_from_phase(e)
            else:
                # Reverse player ticks
                con = s.setdefault("clocks", {}).get("constitution")
                if con:
                    con["filled"] = max(0, con["filled"] - abs(old_ticks))

    new_ticks = 0
    override_result = {}

    # ── Attack-based overrides ──────────────────────────────
    if override_type == "modify_ticks":
        if value is None:
            print(json.dumps({"error": "modify_ticks 需要 --value 参数"}, ensure_ascii=False))
            sys.exit(1)
        if last.get("attacker") == "player":
            target_id = last.get("target")
            if target_id in cs["enemies"]:
                phase_result = _apply_ticks_to_enemy(cs["enemies"][target_id], value)
            else:
                phase_result = None
        else:
            _apply_ticks_to_player(s, value)
            phase_result = None
        new_ticks = value
        override_result = {
            "hit": True, "ticks": value,
            "phase_result": phase_result,
            "detail": f"DM 覆盖: 钟格修改为 {value} 格",
        }

    elif override_type == "add_effect":
        target_id = last.get("target")
        if target_id and target_id in cs["enemies"]:
            cs["enemies"][target_id].setdefault("effects", []).append(
                {"name": f"dm_override_{_next_log_id(cs)}", "turns": 2, "ticks": "1d2"})
        new_ticks = old_ticks
        override_result = {"effect_added": True, "detail": "DM 覆盖: 添加额外效果"}

    # ── Phase overrides ────────────────────────────────────
    elif override_type == "advance_phase":
        if not target:
            print(json.dumps({"error": "advance_phase 需要 --target 参数（敌人 ID）"}, ensure_ascii=False))
            sys.exit(1)
        if target not in cs["enemies"]:
            print(json.dumps({"error": f"目标不存在: {target}"}, ensure_ascii=False))
            sys.exit(1)
        e = cs["enemies"][target]
        phases = e.get("phases", [])
        old_idx = e.get("current_phase", 0)
        if old_idx >= len(phases) - 1:
            # Already on last phase — kill the enemy
            e["current_phase"] = len(phases)
            e["phase_filled"] = phases[-1]["max"] if phases else 0
            _sync_enemy_from_phase(e)
            override_result = {
                "target": target, "enemy_defeated": True,
                "detail": f"DM 覆盖: {e['name_cn']}({target}) 直接击败（最后一阶段）",
            }
        else:
            old_name = phases[old_idx]["name"]
            e["current_phase"] = old_idx + 1
            e["phase_filled"] = 0
            _sync_enemy_from_phase(e)
            new_name = phases[e["current_phase"]]["name"]
            override_result = {
                "target": target,
                "from_phase": old_name, "to_phase": new_name,
                "ac_now": e["ac"],
                "behavior": phases[e["current_phase"]].get("behavior", ""),
                "detail": f"DM 覆盖: {e['name_cn']}({target}) 阶段推进: {old_name} → {new_name}",
            }

    # ── Undo override ───────────────────────────────────────
    elif override_type == "undo_override":
        last_override = None
        for entry in reversed(log):
            if entry.get("type") == "override":
                last_override = entry
                break
        if not last_override:
            print(json.dumps({"error": "没有可撤销的覆盖操作"}, ensure_ascii=False))
            sys.exit(1)
        ov_type = last_override.get("override_type", "")
        ov_original = last_override.get("original", {})
        ov_result = last_override.get("override", {})

        if ov_type == "modify_ticks":
            ov_ticks = ov_result.get("ticks", 0)
            if ov_ticks > 0:
                prev_idx = log.index(last_override) - 1
                if prev_idx >= 0:
                    prev_entry = log[prev_idx]
                    if prev_entry.get("attacker") == "player":
                        tid = prev_entry.get("target")
                        if tid in cs["enemies"]:
                            e = cs["enemies"][tid]
                            # Restore phase from original
                            phase_before = ov_original.get("phase_before", {})
                            if phase_before:
                                e["current_phase"] = phase_before.get("index", 0)
                                e["phase_filled"] = phase_before.get("filled", 0)
                                _sync_enemy_from_phase(e)
                    else:
                        con = s.setdefault("clocks", {}).get("constitution")
                        if con:
                            con["filled"] = max(0, con["filled"] - ov_ticks)
                # Re-apply original ticks
                orig_ticks = ov_original.get("ticks", 0)
                if orig_ticks > 0:
                    if prev_idx >= 0:
                        prev_entry = log[prev_idx]
                        if prev_entry.get("attacker") == "player":
                            tid = prev_entry.get("target")
                            if tid in cs["enemies"]:
                                _apply_ticks_to_enemy(cs["enemies"][tid], orig_ticks)
                        else:
                            _apply_ticks_to_player(s, orig_ticks)
            override_result = {"detail": f"DM 覆盖: 撤销 {ov_type}", "restored": ov_original}

        elif ov_type == "add_effect":
            prev_idx = log.index(last_override) - 1
            if prev_idx >= 0:
                tid = log[prev_idx].get("target")
                if tid and tid in cs["enemies"]:
                    effects = cs["enemies"][tid].get("effects", [])
                    cs["enemies"][tid]["effects"] = [fx for fx in effects if not fx["name"].startswith("dm_override_")]
            override_result = {"detail": "DM 覆盖: 撤销 add_effect"}

        elif ov_type == "advance_phase":
            from_phase = ov_result.get("from_phase")
            tid = ov_result.get("target")
            if from_phase and tid and tid in cs["enemies"]:
                e = cs["enemies"][tid]
                phases = e.get("phases", [])
                # Go back one phase
                e["current_phase"] = max(0, e.get("current_phase", 0) - 1)
                e["phase_filled"] = phases[e["current_phase"]]["max"] if e["current_phase"] < len(phases) else 0
                _sync_enemy_from_phase(e)
            override_result = {"detail": "DM 覆盖: 撤销 advance_phase"}

        else:
            print(json.dumps({"error": f"无法撤销类型: {ov_type}"}, ensure_ascii=False))
            sys.exit(1)

    else:
        print(json.dumps({"error": f"未知覆盖类型: {override_type}"}, ensure_ascii=False))
        sys.exit(1)

    # Remove dead enemies
    cs["enemies"] = {eid: e for eid, e in cs.get("enemies", {}).items() if not _enemy_dead(e)}

    # ── Log override to combat_log ──
    override_log = {
        "id": _next_log_id(cs), "turn": cs["turn"], "type": "override",
        "override_type": override_type,
        "reason": reason,
        "original": original,
        "override": override_result,
    }
    cs.setdefault("combat_log", []).append(override_log)

    # Log to dm_log (persistent)
    dm_entry = {
        "turn": s["turn_count"],
        "combat_turn": cs["turn"],
        "type": override_type,
        "reason": reason,
        "original": original,
        "override": override_result,
    }
    s.setdefault("dm_log", []).append(dm_entry)

    result = {
        "overridden": True,
        "type": override_type,
        "reason": reason,
        "original": original,
        "new_result": override_result,
        "dm_override": _mk_override(["undo_override"]),
    }

    if not cs["enemies"]:
        result["combat_over"] = True
        result["victory"] = True
        s["combat_state"] = None
    elif _player_is_dead(s):
        result["combat_over"] = True
        result["victory"] = False
        s["combat_state"] = None

    _save(s)
    print(json.dumps(result, ensure_ascii=False))


# ── attack resolution ──────────────────────────────────────

def _player_attack(s, cs, target_id, env_spec):
    target = cs["enemies"].get(target_id)
    if not target:
        return {"error": f"目标不存在: {target_id}"}

    # Check player effects
    player_fx = cs.get("player_effects", [])
    stunned = any(fx["name"] == "stunned" for fx in player_fx)
    blinded = any(fx["name"] == "blinded" for fx in player_fx)
    weakened = any(fx["name"] == "weakened" for fx in player_fx)

    phase_before = _enemy_phase_info(target)

    if stunned:
        return {
            "attacker": "player", "target": target_id,
            "hit": False, "roll": 0, "crit": False, "fumble": False,
            "ticks": 0,
            "target_phase": phase_before,
            "target_defeated": _enemy_dead(target),
            "detail": "玩家被眩晕，无法行动！",
            "suppressed_by": "stunned",
            "phase_before": phase_before,
        }

    roll = random.randint(1, 20)
    if blinded:
        roll -= 5
    if env_spec.get("type") == "modifier" and "hit_modifier" in env_spec:
        roll += env_spec["hit_modifier"]

    crit = (roll == 20)
    fumble = (roll == 1)

    if fumble:
        return {
            "attacker": "player", "target": target_id,
            "hit": False, "roll": 1, "crit": False, "fumble": True,
            "ticks": 0,
            "target_phase": phase_before,
            "target_defeated": _enemy_dead(target),
            "detail": "大失败 — 攻击落空",
            "phase_before": phase_before,
        }

    ticks_dice = _get_player_ticks(s)

    effective_ac = target["ac"]
    if env_spec.get("type") == "modifier" and "ac_modifier" in env_spec:
        effective_ac += env_spec["ac_modifier"]

    if crit:
        t1, det1 = _roll(ticks_dice)
        t2, det2 = _roll(ticks_dice)
        ticks = max(0, t1 + t2)
        if weakened:
            ticks = max(0, ticks - 1)
        detail_str = f"大成功! 掷骰 {roll} vs AC {effective_ac}, 钟格 {det1}+{det2}={ticks}格"
    elif roll >= effective_ac:
        ticks, tdetail = _roll(ticks_dice)
        if weakened:
            ticks = max(0, ticks - 1)
        detail_str = f"命中! 掷骰 {roll} vs AC {effective_ac}, 钟格 {tdetail}={ticks}格"
    else:
        ticks = 0
        detail_str = f"未命中! 掷骰 {roll} vs AC {effective_ac}"

    # Apply ticks through phase system
    phase_result = _apply_ticks_to_enemy(target, ticks) if ticks > 0 else None
    phase_after = _enemy_phase_info(target)

    if phase_result and phase_result.get("phase_transition"):
        pt = phase_result["phase_transition"]
        if pt.get("enemy_defeated"):
            detail_str += f" — {pt['from']} 已碎！目标倒下！"
        else:
            ac_info = f" (AC {pt.get('ac_was')}→{pt.get('ac_now')})" if pt.get('ac_was') != pt.get('ac_now') else ""
            detail_str += f" — {pt['from']} → {pt['to']}！{pt.get('behavior', '')}"
            if ac_info:
                detail_str += ac_info

    return {
        "attacker": "player", "target": target_id,
        "hit": ticks > 0,
        "roll": roll, "crit": crit, "fumble": False,
        "ticks": ticks,
        "target_phase": phase_after,
        "target_ac": effective_ac if effective_ac != target["ac"] else target["ac"],
        "target_defeated": _enemy_dead(target),
        "phase_transition": phase_result.get("phase_transition") if phase_result else None,
        "detail": detail_str,
        "phase_before": phase_before,
    }


def _monster_attack(s, cs, attacker_id, target_name, env_spec):
    attacker = cs["enemies"].get(attacker_id)
    if not attacker:
        return {"error": f"攻击方不存在: {attacker_id}"}

    # Check monster effects
    stunned = any(fx["name"] == "stunned" for fx in attacker.get("effects", []))
    weakened = any(fx["name"] == "weakened" for fx in attacker.get("effects", []))

    con_filled, con_max = _get_player_constitution(s)

    if stunned:
        return {
            "attacker": attacker_id, "target": "player",
            "hit": False, "roll": 0, "crit": False, "fumble": False,
            "ticks": 0,
            "target_constitution_filled": con_filled, "target_constitution_max": con_max,
            "detail": f"{attacker['name_cn']} 被眩晕，无法行动！",
            "suppressed_by": "stunned",
        }

    player_ac = _get_player_ac(s)
    if env_spec.get("type") == "modifier" and "ac_modifier" in env_spec:
        player_ac += env_spec["ac_modifier"]

    roll = random.randint(1, 20)
    if env_spec.get("type") == "modifier" and "hit_modifier" in env_spec:
        roll += env_spec["hit_modifier"]

    crit = (roll == 20)
    fumble = (roll == 1)

    if fumble:
        return {
            "attacker": attacker_id, "target": "player",
            "hit": False, "roll": 1, "crit": False, "fumble": True,
            "ticks": 0,
            "target_constitution_filled": con_filled, "target_constitution_max": con_max, "target_ac": player_ac,
            "detail": f"{attacker['name_cn']} 大失败 — 攻击落空",
        }

    if crit or roll >= player_ac:
        base_ticks, tdetail = _roll(attacker["ticks"])
        if weakened:
            base_ticks = max(0, base_ticks - 1)

        bonus_val = 0
        bonus_detail = ""
        bonus_ticks_dice = attacker.get("bonus_ticks")
        if bonus_ticks_dice:
            bonus_val, bd = _roll(bonus_ticks_dice)
            bonus_label = attacker.get("bonus_label", "额外")
            bonus_detail = f" + {bonus_label} {bd}"

        total_ticks = base_ticks + bonus_val
        detail_str = f"{'大成功! ' if crit else '命中! '}{attacker['name_cn']} 掷骰 {roll} vs AC {player_ac}, 钟格 {tdetail}{bonus_detail}={total_ticks}格"
    else:
        total_ticks = 0
        detail_str = f"未命中! {attacker['name_cn']} 掷骰 {roll} vs AC {player_ac}"

    _apply_ticks_to_player(s, total_ticks)
    con_filled, con_max = _get_player_constitution(s)

    return {
        "attacker": attacker_id, "target": "player",
        "hit": total_ticks > 0,
        "roll": roll, "crit": crit, "fumble": False,
        "ticks": total_ticks,
        "target_constitution_filled": con_filled,
        "target_constitution_max": con_max,
        "target_ac": player_ac,
        "detail": detail_str,
    }


# ── CLI ────────────────────────────────────────────────────

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

    if not os.path.exists(STATE_FILE):
        print(json.dumps({"error": "state.json 不存在，请先初始化"}, ensure_ascii=False))
        sys.exit(1)

    raw = sys.argv[1:]

    def _arg(name):
        try:
            i = raw.index(name)
            return raw[i + 1] if i + 1 < len(raw) else None
        except ValueError:
            return None

    if "--init" in raw:
        monster = _arg("--init")
        if not monster:
            print(json.dumps({"error": "--init 需要怪物名"}, ensure_ascii=False))
            sys.exit(1)
        count = int(_arg("--count") or "1")
        init_combat(monster, count)

    elif "--round_event" in raw:
        round_event()

    elif "--env_event" in raw:
        event_key = _arg("--env_event")
        trigger_env_event(event_key)

    elif "--override" in raw:
        override_type = _arg("--override")
        reason = _arg("--reason") or ""
        value = _arg("--value")
        target = _arg("--target")
        monster = _arg("--monster")
        count = int(_arg("--count") or "1")
        apply_override(override_type, reason,
                       int(value) if value else None,
                       target=target, monster=monster, count=count)

    elif "--end" in raw:
        end_combat()

    elif "--attacker" in raw and "--target" in raw and "--action" in raw:
        attacker = _arg("--attacker")
        target = _arg("--target")
        action = _arg("--action")
        if not all([attacker, target, action]):
            print(json.dumps({"error": "参数不完整"}, ensure_ascii=False))
            sys.exit(1)
        resolve_action(attacker, target, action)

    else:
        print(json.dumps({
            "error": "用法: combat.py --init | --round_event | --attacker X --target Y --action attack | --env_event <key|random> | --override | --end"
        }, ensure_ascii=False))
        sys.exit(1)
