import json
import os
import random
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from world_loader import world_file

STATE_FILE = "state.json"

# ── World data (name mapping only — no numerical stats) ─────
with open(world_file("bestiary.json"), "r", encoding="utf-8") as _f:
    BESTIARY = json.load(_f)

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


# ── player (damage track — world-configurable) ────────────

def _damage_attr():
    """Return the attribute key that receives combat damage."""
    try:
        with open(world_file("default_state.json"), "r", encoding="utf-8") as f:
            ds = json.load(f)
        return ds.get("combat_damage_attr", "constitution")
    except Exception:
        return "constitution"

def _apply_ticks_to_player(s, ticks):
    """Apply clock ticks to player damage track. Returns ticks applied."""
    if ticks <= 0:
        return 0
    attr_key = _damage_attr()
    con = s.setdefault("clocks", {}).get(attr_key)
    if not con:
        return 0
    con["filled"] = min(con["max"], con["filled"] + ticks)
    return ticks


def _get_player_constitution(s):
    """Return (filled, max) for player damage track."""
    attr_key = _damage_attr()
    con = s.get("clocks", {}).get(attr_key, {})
    return con.get("filled", 0), con.get("max", 8)


def _player_is_dead(s):
    """Check if player damage track is full."""
    filled, mx = _get_player_constitution(s)
    return filled >= mx


def _mk_override(options):
    """Return the standard dm_override block."""
    return {"available": True, "options": options, "requires_reason": True}


def _next_log_id(cs):
    logs = cs.get("combat_log", [])
    return len(logs) + 1


# ── effect ticking ─────────────────────────────────────────

def _tick_effects(cs):
    """Tick all status effects on enemies and player. Return summary.
    Effects are purely narrative — DM decides mechanical impact."""
    ticks = []
    expired = []

    # Tick enemy effects
    for eid, e in cs.get("enemies", {}).items():
        if e.get("defeated"):
            continue
        for fx in e.get("effects", []):
            fx["turns"] = fx.get("turns", 1) - 1
            if fx["turns"] <= 0:
                expired.append({"target": eid, "effect": fx["name"]})
            else:
                ticks.append({
                    "target": f"{e['name']}({eid})",
                    "effect": fx["name"],
                    "turns_left": fx["turns"],
                })
        e["effects"] = [fx for fx in e.get("effects", []) if fx.get("turns", 1) > 0]

    # Tick player effects
    for fx in cs.get("player_effects", []):
        fx["turns"] = fx.get("turns", 1) - 1
        if fx["turns"] <= 0:
            expired.append({"target": "player", "effect": fx["name"]})
        else:
            ticks.append({
                "target": "玩家",
                "effect": fx["name"],
                "turns_left": fx["turns"],
            })
    cs["player_effects"] = [fx for fx in cs.get("player_effects", []) if fx.get("turns", 1) > 0]

    return ticks, expired


# ── environment events (narrative only) ────────────────────

def _roll_environment(s):
    """15% chance to trigger a narrative environment event. Returns event or None."""
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
        all_events = {}
        for events in ENVIRONMENT_EVENTS.values():
            for name, desc in events:
                all_events[name] = (name, desc)
        for name, desc in DEFAULT_ENV_EVENTS:
            all_events[name] = (name, desc)
        env_event = all_events.get(event_key)
        if not env_event:
            print(json.dumps({"error": f"未知环境事件: {event_key}，可用: {list(all_events.keys())}"}, ensure_ascii=False))
            sys.exit(1)
    else:
        env_event = _roll_environment(s)

    if env_event:
        name, desc = env_event
        cs["environment"] = {"name": name, "desc": desc}
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
        "dm_override": _mk_override([]),
    }, ensure_ascii=False))


# ── ops ────────────────────────────────────────────────────

def init_combat(monster_key, count=1):
    """Start combat tracking. monster_key is looked up in bestiary.json for display name."""
    name_cn = monster_key
    if monster_key in BESTIARY:
        name_cn = BESTIARY[monster_key].get("name_cn", monster_key)

    s = _load()
    enemies = {}
    for i in range(1, count + 1):
        eid = f"{monster_key}_{i}"
        enemies[eid] = {
            "name": name_cn,
            "key": monster_key,
            "defeated": False,
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

    monster_list = [{"id": eid, "name": e["name"]} for eid, e in enemies.items()]

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
        if e.get("defeated"):
            defeated.append(e["name"])
        else:
            escaped.append(e["name"])

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
    """Advance turn: tick effects, roll environment event (narrative). No auto-attacks."""
    s = _load()
    cs = s.get("combat_state")
    if not cs:
        print(json.dumps({"error": "没有进行中的战斗"}, ensure_ascii=False))
        sys.exit(1)

    # 1. Tick existing effects (narrative only — no numerical damage)
    effect_ticks, expired = _tick_effects(cs)

    cs["turn"] = cs.get("turn", 0) + 1

    # 2. Auto-roll environment event (15%, narrative only)
    env_event = _roll_environment(s)
    env_data = {"name": env_event[0], "desc": env_event[1]} if env_event else None
    if env_event:
        name, desc = env_event
        cs["environment"] = {"name": name, "desc": desc}
    else:
        cs["environment"] = None

    # 3. Log round event
    log_entry = {
        "id": _next_log_id(cs), "turn": cs["turn"], "type": "round_event",
        "effect_ticks": effect_ticks, "effects_expired": expired,
        "environment_event": env_data,
    }
    cs.setdefault("combat_log", []).append(log_entry)

    # 4. Check combat end
    dmg_attr = _damage_attr()
    con_filled, con_max = _get_player_constitution(s)
    result = {
        "turn": cs["turn"],
        "effect_ticks": effect_ticks,
        "effects_expired": expired,
        "environment_event": env_data,
        "damage_track": {"attr": dmg_attr, "filled": con_filled, "max": con_max},
        "dm_override": _mk_override([]),
    }
    if _player_is_dead(s):
        result["combat_over"] = True
        result["victory"] = False
        s["combat_state"] = None

    _save(s)
    print(json.dumps(result, ensure_ascii=False))


def tick_constitution(amount):
    """Apply ticks to player constitution clock. Positive = damage."""
    s = _load()
    cs = s.get("combat_state")
    if not cs:
        print(json.dumps({"error": "没有进行中的战斗"}, ensure_ascii=False))
        sys.exit(1)

    _apply_ticks_to_player(s, amount)
    con_filled, con_max = _get_player_constitution(s)
    dmg_attr = _damage_attr()

    result = {
        "tick_applied": amount,
        "damage_track": dmg_attr,
        "filled": con_filled,
        "max": con_max,
    }

    if _player_is_dead(s):
        result["combat_over"] = True
        result["victory"] = False
        s["combat_state"] = None

    _save(s)
    print(json.dumps(result, ensure_ascii=False))


def apply_override(override_type, reason, value=None, target=None):
    if not reason:
        print(json.dumps({"error": "--reason 是必填字段，覆盖操作必须提供理由"}, ensure_ascii=False))
        sys.exit(1)

    s = _load()
    cs = s.get("combat_state")
    if not cs:
        print(json.dumps({"error": "没有进行中的战斗"}, ensure_ascii=False))
        sys.exit(1)

    override_result = {}

    if override_type == "advance_phase":
        if not target:
            print(json.dumps({"error": "advance_phase 需要 --target 参数（敌人 ID）"}, ensure_ascii=False))
            sys.exit(1)
        if target not in cs["enemies"]:
            print(json.dumps({"error": f"目标不存在: {target}"}, ensure_ascii=False))
            sys.exit(1)
        e = cs["enemies"][target]
        old_phase = e.get("phase", 1)
        e["phase"] = old_phase + 1
        override_result = {
            "target": target,
            "from_phase": old_phase,
            "to_phase": e["phase"],
            "detail": f"DM 覆盖: {e['name']}({target}) 阶段推进: {old_phase} → {e['phase']}",
        }

    elif override_type == "add_effect":
        if not target:
            print(json.dumps({"error": "add_effect 需要 --target 参数"}, ensure_ascii=False))
            sys.exit(1)
        if target == "player":
            cs.setdefault("player_effects", []).append(
                {"name": f"dm_override_{_next_log_id(cs)}", "turns": 2})
        elif target in cs["enemies"]:
            cs["enemies"][target].setdefault("effects", []).append(
                {"name": f"dm_override_{_next_log_id(cs)}", "turns": 2})
        else:
            print(json.dumps({"error": f"目标不存在: {target}"}, ensure_ascii=False))
            sys.exit(1)
        override_result = {"effect_added": True, "target": target, "detail": "DM 覆盖: 添加效果"}

    elif override_type == "defeat_enemy":
        if not target:
            print(json.dumps({"error": "defeat_enemy 需要 --target 参数"}, ensure_ascii=False))
            sys.exit(1)
        if target not in cs["enemies"]:
            print(json.dumps({"error": f"目标不存在: {target}"}, ensure_ascii=False))
            sys.exit(1)
        cs["enemies"][target]["defeated"] = True
        override_result = {
            "target": target,
            "enemy_defeated": True,
            "detail": f"DM 覆盖: {cs['enemies'][target]['name']}({target}) 被击败",
        }

    elif override_type == "undo_override":
        last_override = None
        for entry in reversed(cs.get("combat_log", [])):
            if entry.get("type") == "override":
                last_override = entry
                break
        if not last_override:
            print(json.dumps({"error": "没有可撤销的覆盖操作"}, ensure_ascii=False))
            sys.exit(1)
        ov_type = last_override.get("override_type", "")
        ov_result = last_override.get("override", {})

        if ov_type == "defeat_enemy":
            tid = ov_result.get("target")
            if tid and tid in cs["enemies"]:
                cs["enemies"][tid]["defeated"] = False
            override_result = {"detail": "DM 覆盖: 撤销 defeat_enemy"}

        elif ov_type == "advance_phase":
            tid = ov_result.get("target")
            if tid and tid in cs["enemies"]:
                cs["enemies"][tid]["phase"] = max(1, cs["enemies"][tid].get("phase", 1) - 1)
            override_result = {"detail": "DM 覆盖: 撤销 advance_phase"}

        elif ov_type == "add_effect":
            tid = last_override.get("override", {}).get("target")
            if tid:
                if tid == "player":
                    cs["player_effects"] = [fx for fx in cs.get("player_effects", [])
                                            if not fx["name"].startswith("dm_override_")]
                elif tid in cs["enemies"]:
                    cs["enemies"][tid]["effects"] = [fx for fx in cs["enemies"][tid].get("effects", [])
                                                     if not fx["name"].startswith("dm_override_")]
            override_result = {"detail": "DM 覆盖: 撤销 add_effect"}

        else:
            print(json.dumps({"error": f"无法撤销类型: {ov_type}"}, ensure_ascii=False))
            sys.exit(1)

    else:
        print(json.dumps({"error": f"未知覆盖类型: {override_type}"}, ensure_ascii=False))
        sys.exit(1)

    # Remove defeated enemies
    cs["enemies"] = {eid: e for eid, e in cs.get("enemies", {}).items() if not e.get("defeated")}

    # Log override
    override_log = {
        "id": _next_log_id(cs), "turn": cs["turn"], "type": "override",
        "override_type": override_type,
        "reason": reason,
        "override": override_result,
    }
    cs.setdefault("combat_log", []).append(override_log)

    # Log to dm_log (persistent)
    dm_entry = {
        "turn": s["turn_count"],
        "combat_turn": cs["turn"],
        "type": override_type,
        "reason": reason,
        "override": override_result,
    }
    s.setdefault("dm_log", []).append(dm_entry)

    result = {
        "overridden": True,
        "type": override_type,
        "reason": reason,
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

    elif "--tick_constitution" in raw:
        amount = _arg("--tick_constitution")
        if amount is None:
            print(json.dumps({"error": "--tick_constitution 需要数值"}, ensure_ascii=False))
            sys.exit(1)
        tick_constitution(int(amount))

    elif "--override" in raw:
        override_type = _arg("--override")
        reason = _arg("--reason") or ""
        value = _arg("--value")
        target = _arg("--target")
        apply_override(override_type, reason,
                       value=int(value) if value else None,
                       target=target)

    elif "--end" in raw:
        end_combat()

    else:
        print(json.dumps({
            "error": "用法: combat.py --init | --round_event | --env_event | --tick_constitution | --override | --end"
        }, ensure_ascii=False))
        sys.exit(1)
