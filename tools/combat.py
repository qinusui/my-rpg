import json
import os
import random
import sys
import re

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from world_loader import world_file

STATE_FILE = "state.json"

# ── World data (loaded from active world JSON files) ─────────
with open(world_file("bestiary.json"), "r", encoding="utf-8") as _f:
    BESTIARY = json.load(_f)

with open(world_file("items.json"), "r", encoding="utf-8") as _f:
    _items = json.load(_f)
    WEAPON_BONUSES = _items["weapons"]
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
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(s, f, ensure_ascii=False, indent=2)


def _roll(dice_str):
    m = re.match(r"(\d+)d(\d+)(?:([+-])(\d+))?$", dice_str)
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


def _get_player_damage(s):
    dice, bonus = "1d6", 0
    eq = s.get("equipped", {})
    weapon_id = eq.get("weapon") if eq else None
    if weapon_id:
        for it in s.get("inventory", []):
            if it["id"] == weapon_id:
                w = WEAPON_BONUSES.get(it["name"], {})
                dice = w.get("dice", "1d6") if w else "1d6"
                bonus = w.get("bonus", 0) if w else 0
                break
    return dice, bonus


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
    dmg_str = fx.get("damage", "0")
    damage, _ = _roll(dmg_str) if dmg_str != "0" else (0, "0")
    fx["turns"] = fx.get("turns", 1) - 1
    expired = fx["turns"] <= 0
    return {
        "target": label,
        "effect": fx["name"],
        "damage": damage,
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
    enemies = {}
    for i in range(1, count + 1):
        hp = random.randint(data["hp_min"], data["hp_max"])
        enemies[f"{monster_key}_{i}"] = {
            "name_cn": data["name_cn"],
            "key": monster_key,
            "hp": hp,
            "max_hp": hp,
            "ac": data["ac"],
            "damage": data["damage"],
            "special": data["special"],
            "bonus_damage": data.get("bonus_damage"),
            "bonus_label": data.get("bonus_label"),
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

    monster_list = [
        {"id": eid, "name": e["name_cn"], "hp": e["hp"], "ac": e["ac"]}
        for eid, e in enemies.items()
    ]
    result = {
        "combat_started": True,
        "enemies": monster_list,
        "turn": 0,
        "dm_override": _mk_override(["modify_hp", "add_enemy", "remove_enemy"]),
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
        if e["hp"] <= 0:
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
    ticks, expired = _tick_effects(cs)

    # 2. Apply tick damage to enemies
    for t in ticks:
        if t["damage"] > 0:
            target_label = t["target"]
            for eid, e in cs["enemies"].items():
                if f"{e['name_cn']}({eid})" == target_label:
                    e["hp"] -= t["damage"]
                    if e["hp"] < 0:
                        e["hp"] = 0
                    break
            if "玩家" in target_label:
                s["attributes"]["health"] -= t["damage"]
                if s["attributes"]["health"] < 0:
                    s["attributes"]["health"] = 0

    # 3. Remove dead enemies
    cs["enemies"] = {eid: e for eid, e in cs.get("enemies", {}).items() if e["hp"] > 0}

    cs["turn"] = cs.get("turn", 0) + 1

    # 4. Log round event
    log_entry = {
        "id": _next_log_id(cs), "turn": cs["turn"], "type": "round_event",
        "effect_ticks": ticks, "effects_expired": expired,
        "environment_event": None,
    }
    cs.setdefault("combat_log", []).append(log_entry)

    # 5. Check combat end
    result = {
        "turn": cs["turn"],
        "effect_ticks": ticks,
        "effects_expired": expired,
        "environment_event": None,
        "dm_override": _mk_override([]),
    }
    if not cs["enemies"]:
        result["combat_over"] = True
        result["victory"] = True
        s["combat_state"] = None
    elif s["attributes"]["health"] <= 0:
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
    cs["enemies"] = {eid: e for eid, e in cs.get("enemies", {}).items() if e["hp"] > 0}

    # Log the action
    log_entry = {
        "id": _next_log_id(cs), "turn": cs["turn"], "type": "attack",
        "attacker": attacker, "target": target,
        "hp_delta": -result.get("damage", 0) if result.get("hit") else 0,
        "result": {k: v for k, v in result.items() if k != "dm_override"},
    }
    cs.setdefault("combat_log", []).append(log_entry)

    # Add dm_override to result
    result["dm_override"] = _mk_override(["force_hit", "force_miss", "modify_damage", "add_effect"])

    # Check combat end
    if not cs["enemies"]:
        result["combat_over"] = True
        result["victory"] = True
        s["combat_state"] = None
    elif s["attributes"]["health"] <= 0:
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
    standalone = {"modify_hp", "add_enemy", "remove_enemy"}
    # Types that operate on the last log entry
    needs_log = {"force_hit", "force_miss", "modify_damage", "add_effect", "undo_override"}

    if override_type in needs_log and not log:
        print(json.dumps({"error": "没有可覆盖的操作记录"}, ensure_ascii=False))
        sys.exit(1)

    last = log[-1] if log else None
    original = dict(last.get("result", {})) if last else {}
    hp_delta = last.get("hp_delta", 0) if last else 0

    # ── Reverse old hp_delta (for attack-based overrides) ──
    if override_type in {"force_hit", "force_miss", "modify_damage", "add_effect"}:
        if hp_delta != 0:
            if last.get("attacker") == "player":
                target_id = last.get("target")
                if target_id in cs["enemies"]:
                    cs["enemies"][target_id]["hp"] -= hp_delta
            else:
                s["attributes"]["health"] -= hp_delta
                if s["attributes"]["health"] < 0:
                    s["attributes"]["health"] = 0

    new_hp_delta = 0
    override_result = {}

    # ── Attack-based overrides (existing) ────────────────────
    if override_type == "force_hit":
        if last.get("attacker") == "player":
            dice, bonus = _get_player_damage(s)
            damage, ddetail = _roll(dice)
            damage += bonus
            target_id = last.get("target")
            if target_id in cs["enemies"]:
                cs["enemies"][target_id]["hp"] -= damage
                if cs["enemies"][target_id]["hp"] < 0:
                    cs["enemies"][target_id]["hp"] = 0
            new_hp_delta = -damage
            override_result = {"hit": True, "damage": damage, "detail": f"DM 覆盖: 强制命中, 伤害 {damage}"}
        else:
            monster = cs["enemies"].get(last.get("attacker"), {})
            damage, ddetail = _roll(monster.get("damage", "1d4"))
            s["attributes"]["health"] -= damage
            if s["attributes"]["health"] < 0:
                s["attributes"]["health"] = 0
            new_hp_delta = -damage
            override_result = {"hit": True, "damage": damage, "detail": f"DM 覆盖: 强制命中, 伤害 {damage}"}

    elif override_type == "force_miss":
        new_hp_delta = 0
        override_result = {"hit": False, "damage": 0, "detail": "DM 覆盖: 强制未命中"}

    elif override_type == "modify_damage":
        if value is None:
            print(json.dumps({"error": "modify_damage 需要 --value 参数"}, ensure_ascii=False))
            sys.exit(1)
        if last.get("attacker") == "player":
            target_id = last.get("target")
            if target_id in cs["enemies"]:
                cs["enemies"][target_id]["hp"] -= value
                if cs["enemies"][target_id]["hp"] < 0:
                    cs["enemies"][target_id]["hp"] = 0
        else:
            s["attributes"]["health"] -= value
            if s["attributes"]["health"] < 0:
                s["attributes"]["health"] = 0
        new_hp_delta = -value
        override_result = {"hit": True, "damage": value, "detail": f"DM 覆盖: 伤害修改为 {value}"}

    elif override_type == "add_effect":
        target_id = last.get("target")
        if target_id and target_id in cs["enemies"]:
            cs["enemies"][target_id].setdefault("effects", []).append(
                {"name": f"dm_override_{_next_log_id(cs)}", "turns": 2, "damage": "1d4"})
        new_hp_delta = hp_delta
        override_result = {"effect_added": True, "detail": "DM 覆盖: 添加额外效果"}

    # ── Combat-state overrides ────────────────────────────────
    elif override_type == "modify_hp":
        if not target:
            print(json.dumps({"error": "modify_hp 需要 --target 参数（敌人 ID）"}, ensure_ascii=False))
            sys.exit(1)
        if value is None:
            print(json.dumps({"error": "modify_hp 需要 --value 参数（新 HP 值）"}, ensure_ascii=False))
            sys.exit(1)
        if target not in cs["enemies"]:
            print(json.dumps({"error": f"目标不存在: {target}"}, ensure_ascii=False))
            sys.exit(1)
        old_hp = cs["enemies"][target]["hp"]
        cs["enemies"][target]["hp"] = max(0, min(value, cs["enemies"][target]["max_hp"]))
        override_result = {
            "target": target, "old_hp": old_hp, "new_hp": cs["enemies"][target]["hp"],
            "detail": f"DM 覆盖: {cs['enemies'][target]['name_cn']}({target}) HP {old_hp} → {cs['enemies'][target]['hp']}",
        }

    elif override_type == "add_enemy":
        if not monster:
            print(json.dumps({"error": "add_enemy 需要 --monster 参数（怪物 key）"}, ensure_ascii=False))
            sys.exit(1)
        data = BESTIARY.get(monster)
        if not data:
            print(json.dumps({"error": f"未知怪物: {monster}"}, ensure_ascii=False))
            sys.exit(1)
        new_enemies = {}
        for i in range(1, count + 1):
            eid = f"{monster}_{_next_log_id(cs) + i}"
            hp = random.randint(data["hp_min"], data["hp_max"])
            new_enemies[eid] = {
                "name_cn": data["name_cn"], "key": monster,
                "hp": hp, "max_hp": hp, "ac": data["ac"],
                "damage": data["damage"], "special": data["special"], "effects": [],
            }
        cs["enemies"].update(new_enemies)
        override_result = {
            "added": list(new_enemies.keys()),
            "detail": f"DM 覆盖: 新增 {count} 只 {data['name_cn']} ({', '.join(new_enemies.keys())})",
        }

    elif override_type == "remove_enemy":
        if not target:
            print(json.dumps({"error": "remove_enemy 需要 --target 参数（敌人 ID）"}, ensure_ascii=False))
            sys.exit(1)
        if target not in cs["enemies"]:
            print(json.dumps({"error": f"目标不存在: {target}"}, ensure_ascii=False))
            sys.exit(1)
        removed = cs["enemies"].pop(target)
        override_result = {
            "removed": target,
            "detail": f"DM 覆盖: 移除 {removed['name_cn']}({target})",
        }

    # ── Undo override ─────────────────────────────────────────
    elif override_type == "undo_override":
        # Find the last override entry
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

        if ov_type in {"force_hit", "force_miss", "modify_damage"}:
            # Reverse the override's hp changes
            ov_dmg = ov_result.get("damage", 0)
            if ov_dmg > 0:
                # Check who was the attacker in the prior attack log
                prev_idx = log.index(last_override) - 1
                if prev_idx >= 0:
                    prev_entry = log[prev_idx]
                    if prev_entry.get("attacker") == "player":
                        tid = prev_entry.get("target")
                        if tid in cs["enemies"]:
                            cs["enemies"][tid]["hp"] += ov_dmg
                            cs["enemies"][tid]["hp"] = min(cs["enemies"][tid]["hp"], cs["enemies"][tid]["max_hp"])
                    else:
                        s["attributes"]["health"] += ov_dmg
                # Re-apply original damage if any
                orig_dmg = ov_original.get("damage", 0)
                if orig_dmg > 0:
                    if prev_idx >= 0:
                        prev_entry = log[prev_idx]
                        if prev_entry.get("attacker") == "player":
                            tid = prev_entry.get("target")
                            if tid in cs["enemies"]:
                                cs["enemies"][tid]["hp"] -= orig_dmg
                                if cs["enemies"][tid]["hp"] < 0:
                                    cs["enemies"][tid]["hp"] = 0
                        else:
                            s["attributes"]["health"] -= orig_dmg
                            if s["attributes"]["health"] < 0:
                                s["attributes"]["health"] = 0
            override_result = {"detail": f"DM 覆盖: 撤销 {ov_type}", "restored": ov_original}

        elif ov_type == "add_effect":
            # Remove the last dm_override effect from the target
            # Find which enemy got the effect by looking at the original attack's target
            prev_idx = log.index(last_override) - 1
            if prev_idx >= 0:
                tid = log[prev_idx].get("target")
                if tid and tid in cs["enemies"]:
                    effects = cs["enemies"][tid].get("effects", [])
                    cs["enemies"][tid]["effects"] = [fx for fx in effects if not fx["name"].startswith("dm_override_")]
            override_result = {"detail": "DM 覆盖: 撤销 add_effect"}

        elif ov_type == "modify_hp":
            old_hp = ov_result.get("old_hp")
            tid = ov_result.get("target")
            if old_hp is not None and tid and tid in cs["enemies"]:
                cs["enemies"][tid]["hp"] = old_hp
            override_result = {"detail": "DM 覆盖: 撤销 modify_hp"}

        elif ov_type == "add_enemy":
            for eid in ov_result.get("added", []):
                cs["enemies"].pop(eid, None)
            override_result = {"detail": "DM 覆盖: 撤销 add_enemy"}

        elif ov_type == "remove_enemy":
            # Can't fully restore without bestiary data, log as partial
            override_result = {"detail": "DM 覆盖: 撤销 remove_enemy（敌人数据已丢失，请用 add_enemy 手动恢复）"}

        else:
            print(json.dumps({"error": f"无法撤销类型: {ov_type}"}, ensure_ascii=False))
            sys.exit(1)

    else:
        print(json.dumps({"error": f"未知覆盖类型: {override_type}"}, ensure_ascii=False))
        sys.exit(1)

    # Remove dead enemies
    cs["enemies"] = {eid: e for eid, e in cs.get("enemies", {}).items() if e["hp"] > 0}

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
    elif s["attributes"]["health"] <= 0:
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

    if stunned:
        return {
            "attacker": "player", "target": target_id,
            "hit": False, "roll": 0, "crit": False, "fumble": False,
            "damage": 0, "target_hp": target["hp"], "target_ac": target["ac"],
            "target_alive": target["hp"] > 0,
            "detail": "玩家被眩晕，无法行动！",
            "suppressed_by": "stunned",
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
            "damage": 0, "target_hp": target["hp"], "target_ac": target["ac"],
            "target_alive": target["hp"] > 0,
            "detail": "大失败 — 攻击落空",
        }

    dice, bonus = _get_player_damage(s)
    if weakened:
        bonus -= 2

    effective_ac = target["ac"]
    if env_spec.get("type") == "modifier" and "ac_modifier" in env_spec:
        effective_ac += env_spec["ac_modifier"]

    if crit:
        d1, det1 = _roll(dice)
        d2, det2 = _roll(dice)
        damage = max(0, d1 + d2 + bonus)
        detail_str = f"大成功! 掷骰 {roll} vs AC {effective_ac}, 伤害 {det1}+{det2}+{bonus}={damage}"
    elif roll >= effective_ac:
        damage, ddetail = _roll(dice)
        damage = max(0, damage + bonus)
        detail_str = f"命中! 掷骰 {roll} vs AC {effective_ac}, 伤害 {ddetail}+{bonus}={damage}"
    else:
        damage = 0
        detail_str = f"未命中! 掷骰 {roll} vs AC {effective_ac}"

    target["hp"] -= damage
    if target["hp"] < 0:
        target["hp"] = 0

    return {
        "attacker": "player", "target": target_id,
        "hit": damage > 0,
        "roll": roll, "crit": crit, "fumble": False,
        "damage": damage,
        "target_hp": target["hp"],
        "target_max_hp": target["max_hp"],
        "target_ac": effective_ac if effective_ac != target["ac"] else target["ac"],
        "target_alive": target["hp"] > 0,
        "detail": detail_str,
    }


def _monster_attack(s, cs, attacker_id, target_name, env_spec):
    attacker = cs["enemies"].get(attacker_id)
    if not attacker:
        return {"error": f"攻击方不存在: {attacker_id}"}

    # Check monster effects
    stunned = any(fx["name"] == "stunned" for fx in attacker.get("effects", []))
    weakened = any(fx["name"] == "weakened" for fx in attacker.get("effects", []))

    if stunned:
        return {
            "attacker": attacker_id, "target": "player",
            "hit": False, "roll": 0, "crit": False, "fumble": False,
            "damage": 0, "target_health": s["attributes"]["health"],
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
            "target_health": s["attributes"]["health"], "target_ac": player_ac,
            "detail": f"{attacker['name_cn']} 大失败 — 攻击落空",
        }

    if crit or roll >= player_ac:
        base_damage, ddetail = _roll(attacker["damage"])
        if weakened:
            base_damage = max(0, base_damage - 2)

        bonus = 0
        bonus_detail = ""
        bonus_dice = attacker.get("bonus_damage")
        if bonus_dice:
            bonus, bd = _roll(bonus_dice)
            bonus_label = attacker.get("bonus_label", "额外")
            bonus_detail = f" + {bonus_label} {bd}"

        total_damage = base_damage + bonus
        detail_str = f"{'大成功! ' if crit else '命中! '}{attacker['name_cn']} 掷骰 {roll} vs AC {player_ac}, 伤害 {ddetail}{bonus_detail}={total_damage}"
    else:
        total_damage = 0
        detail_str = f"未命中! {attacker['name_cn']} 掷骰 {roll} vs AC {player_ac}"

    s["attributes"]["health"] -= total_damage
    if s["attributes"]["health"] < 0:
        s["attributes"]["health"] = 0

    return {
        "attacker": attacker_id, "target": "player",
        "hit": total_damage > 0,
        "roll": roll, "crit": crit, "fumble": False,
        "damage": total_damage,
        "target_health": s["attributes"]["health"],
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
