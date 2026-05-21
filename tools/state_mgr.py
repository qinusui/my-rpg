import json
import os
import sys
import random
import tempfile
import shutil
from datetime import datetime
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from world_loader import world_file

STATE_FILE = "state.json"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORLD_CONSTANTS_FILE = world_file("world_constants.json")

# ── World data (loaded from active world JSON files) ─────────

# ── World data (lazy-loaded on first access) ──────────────────

_json_cache = {}

def _load_json_cached(file_key, world_filename):
    """Load a JSON file from the active world, caching the result in memory."""
    if file_key not in _json_cache:
        with open(world_file(world_filename), "r", encoding="utf-8") as f:
            _json_cache[file_key] = json.load(f)
    return _json_cache[file_key]


def get_encounter_tables():
    return _load_json_cached("encounter_tables", "encounter_tables.json")

# Flag to suppress terminal title-bar escapes during text capture.
_suppress_title_bar = False

def get_threshold_rules():
    return _load_json_cached("threshold_rules", "threshold_rules.json")

def get_default_state():
    return _load_json_cached("default_state", "default_state.json")

def get_character_options():
    return _load_json_cached("character_options", "character_options.json")


# ── migration ──────────────────────────────────────────────

def _migrate_inventory(items):
    if not items:
        return []
    if all(isinstance(it, dict) for it in items):
        return items
    counts = Counter(items)
    migrated = []
    for i, (name, qty) in enumerate(counts.items(), start=1):
        migrated.append({
            "id": f"item_{i:03d}",
            "name": name,
            "qty": qty,
            "tags": [],
        })
    return migrated


# ── persistence ────────────────────────────────────────────

def load_state():
    if not os.path.exists(STATE_FILE):
        return dict(get_default_state())
    with open(STATE_FILE, "r", encoding="utf-8") as f:
        s = json.load(f)

    # ── Migration: old numeric attributes → clock-based attributes ─
    if "attributes" in s and isinstance(s["attributes"], dict):
        old = s.pop("attributes")
        s.setdefault("clocks", {})
        # Only migrate if clock keys are missing (avoids overwriting existing clocks)
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
            if attr_name not in s["clocks"]:
                if attr_name == "constitution":
                    # Legacy: if old attributes had "health" key, use it for constitution mapping
                    if "health" in old:
                        src_val = old["health"]
                        filled = max(0, min(8, round((20 - src_val) / 20 * 8)))
                        if filled == 0 and src_val >= 18:
                            filled = 1
                    else:
                        filled = clock_def["filled"]
                elif attr_name in old:
                    # Only convert if the old attributes actually had this key
                    old_val = old[attr_name]
                    filled = max(0, min(clock_def["max"], round(old_val / 5)))
                else:
                    # No old value → use default
                    filled = clock_def["filled"]
                s["clocks"][attr_name] = {**clock_def, "filled": filled}

    for k, v in get_default_state().items():
        if k not in s:
            s[k] = dict(v) if isinstance(v, dict) else (v[:] if isinstance(v, list) else v)

    s["inventory"] = _migrate_inventory(s.get("inventory", []))
    if "events" not in s:
        s["events"] = []
    if "dm_log" not in s:
        s["dm_log"] = []
    if "clocks" not in s:
        s["clocks"] = {}
    # Ensure attribute clocks exist within clocks dict
    if "strength" not in s["clocks"]:
        s["clocks"]["strength"] = {"max": 6, "filled": 3, "label": "力量"}
    if "agility" not in s["clocks"]:
        s["clocks"]["agility"] = {"max": 6, "filled": 3, "label": "敏捷"}
    if "constitution" not in s["clocks"]:
        s["clocks"]["constitution"] = {"max": 8, "filled": 1, "label": "体质"}
    if "sanity" not in s["clocks"]:
        s["clocks"]["sanity"] = {"max": 6, "filled": 3, "label": "理智"}
    if "magic" not in s["clocks"]:
        s["clocks"]["magic"] = {"max": 6, "filled": 1, "label": "魔力"}
    if "wealth" not in s["clocks"]:
        s["clocks"]["wealth"] = {"max": 6, "filled": 3, "label": "财富"}
    if "reputation" not in s["clocks"]:
        s["clocks"]["reputation"] = {"max": 6, "filled": 3, "label": "声望"}
    if "injury" not in s:
        s["injury"] = None
    if "known_fragments" not in s:
        s["known_fragments"] = []
    if "known_npcs" not in s:
        s["known_npcs"] = []
    if "revealed_lore" not in s:
        s["revealed_lore"] = []
    if "background" not in s:
        s["background"] = ""
    if "active_goal" not in s:
        s["active_goal"] = None
    if "completed_goals" not in s:
        s["completed_goals"] = []
    if "affinities" not in s:
        s["affinities"] = {}

    return s


def save_state(state):
    """Atomic write with automatic backup. Never corrupts the save file."""
    # 1. Write to temp file first (atomic — won't corrupt original if interrupted)
    tmp_fd, tmp_path = tempfile.mkstemp(
        suffix=".json", prefix=".state_tmp_", dir="."
    )
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        # 2. Rotate: previous → .bak, temp → state.json
        if os.path.exists(STATE_FILE):
            bak_path = STATE_FILE + ".bak"
            if os.path.exists(bak_path):
                os.remove(bak_path)
            os.rename(STATE_FILE, bak_path)
        os.rename(tmp_path, STATE_FILE)
    except Exception:
        # Clean up temp file on failure
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise


# ── inventory helpers ──────────────────────────────────────

def _next_item_id(state):
    existing = [int(it["id"].split("_")[1]) for it in state["inventory"]]
    return f"item_{max(existing) + 1:03d}" if existing else "item_001"


def _find_by_id(state, item_id):
    for it in state["inventory"]:
        if it["id"] == item_id:
            return it
    return None


def _lookup_item_effect(name):
    """Look up an item's effect from the active world's items.json. Returns effect text or None."""
    try:
        items_path = world_file("items.json")
        with open(items_path, "r", encoding="utf-8") as f:
            items = json.load(f)
        for category in ("quest_items", "legendary", "weapons", "armors"):
            entry = items.get(category, {}).get(name, {})
            if isinstance(entry, dict) and entry:
                return entry.get("effect") or entry.get("property")
        return None
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def _print_location_info(loc_id):
    """Print location sensory data + nearby NPCs for a location change."""
    wc = _load_world_constants()
    locations = wc.get("locations", {})
    npcs = wc.get("npcs", {})
    result = {"location_set": loc_id}
    # Exact match first, then fuzzy
    loc = locations.get(loc_id)
    if not loc:
        for key, val in locations.items():
            if loc_id in key or key in loc_id:
                loc = val
                result["location_set"] = key
                break
    if loc:
        result["location"] = {k: loc[k] for k in ("name_cn", "always", "sound", "mood") if k in loc}
    # Find NPCs associated with this location area
    nearby = {}
    for npc_name, npc_data in npcs.items():
        npc_loc = npc_data.get("location", "")
        if npc_loc and (npc_loc in loc_id or loc_id in npc_loc):
            nearby[npc_name] = npc_data.get("name_cn", npc_name)
    if nearby:
        result["npcs_nearby"] = nearby
    print(json.dumps(result, ensure_ascii=False))


# ── threshold flags ────────────────────────────────────────

def compute_flags(clocks):
    """Return list of active threshold flags for current attribute clocks."""
    flags = []
    for attr, op, threshold, flag in get_threshold_rules():
        clock = clocks.get(attr)
        if not clock:
            continue
        val = clock["filled"]
        if op == ">=" and val >= threshold:
            flags.append(flag)
        elif op == "<=" and val <= threshold:
            flags.append(flag)
    return flags


# ── attribute modifier ─────────────────────────────────────

def _attr_modifier(filled, max_val, attr_name=None, direction=None):
    """Compute D20 modifier from clock filled value. Midpoint = max/2.
    Direction 'down' means more filled = worse (inverted modifier).
    Default direction: 'up' for standard resource clocks, 'down' for constitution/sanity."""
    midpoint = max_val // 2
    mod = filled - midpoint
    # Determine direction: explicit > clock field > hardcoded list
    if direction is None:
        # Hardcoded defaults for standard attributes
        direction = "down" if attr_name in ("constitution", "sanity") else "up"
    if direction == "down":
        mod = -mod
    return mod


# ── goal helpers ────────────────────────────────────────────

def _get_goal_definition(goal_name):
    """Look up goal definition from character_options.json."""
    goals = get_character_options().get("goals", {})
    return goals.get(goal_name)


# ── chronicle ──────────────────────────────────────────────

def _chronicle_snippet():
    """Pick 1-2 random entries from world chronicle for DM to weave into opening."""
    chronicle_path = world_file("sessions/chronicle.json")
    if not os.path.exists(chronicle_path):
        return []
    try:
        with open(chronicle_path, "r", encoding="utf-8") as f:
            c = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return []
    entries = []
    if c.get("legends"):
        entries.append({"kind": "传说", "text": random.choice(c["legends"])})
    if c.get("relics"):
        entries.append({"kind": "遗迹", "text": random.choice(c["relics"])})
    # Only 1 entry total, legends prioritized then relics
    random.shuffle(entries)
    return entries[:1]


def _active_tensions(s):
    """Return tension info if player background is in tension with active goal."""
    bg = s.get("background", "")
    goal = s.get("active_goal")
    if not bg or not goal or isinstance(goal, str):
        return None
    goal_def = _get_goal_definition(goal.get("goal", ""))
    if not goal_def:
        return None
    tension_with = goal_def.get("tension_with", [])
    if bg in tension_with:
        return {
            "background": bg,
            "goal": goal["goal"],
            "tension_effect": goal_def.get("tension_effect", ""),
        }
    return None


# ── encounter / danger clock ───────────────────────────────

def _roll_dice(dice_str):
    """Parse dice notation like '1d3', '2d4'. Returns sum of rolls."""
    if "d" not in str(dice_str):
        return int(dice_str)
    parts = str(dice_str).split("d")
    count = int(parts[0])
    sides = int(parts[1])
    return sum(random.randint(1, sides) for _ in range(count))


def _tick_danger(s):
    """Advance location danger clock. Handles luck, omens, and encounter triggers."""
    loc = s.get("current_location", "")
    entry = get_encounter_tables().get(loc, get_encounter_tables()["_default"])
    danger_max = entry["danger_max"]
    danger_tick = entry["danger_tick"]
    omens = entry.get("omens", {})
    pool = entry["pool"]

    dangers = s.get("location_dangers", {})
    current = dangers.get(loc, 0)

    result = {
        "danger": {"current": current, "max": danger_max},
        "omen": None,
        "monster": None,
        "catastrophe": False,
        "boon": False,
    }

    # Normal danger advance
    advance = _roll_dice(danger_tick)
    new_danger = min(current + advance, danger_max)

    # Luck roll (D20, independent of danger)
    luck = random.randint(1, 20)
    if luck == 1:
        result["catastrophe"] = True
        spike = max(2, danger_max // 3)
        new_danger = min(new_danger + spike, danger_max)
        result["danger"]["catastrophe_spike"] = spike
    elif luck == 20:
        result["boon"] = True
        new_danger = max(0, new_danger - 3)
        result["danger"]["boon_reduction"] = True

    result["danger"]["current"] = new_danger
    result["danger"]["advance"] = advance

    # Store
    dangers[loc] = new_danger
    s["location_dangers"] = dangers

    # Check omens crossed this tick (report first new one)
    sorted_omens = sorted(omens.items(), key=lambda x: int(x[0]))
    for threshold_str, omen_text in sorted_omens:
        threshold = int(threshold_str)
        if current < threshold <= new_danger:
            result["omen"] = omen_text
            break

    # Trigger encounter if danger is full
    if new_danger >= danger_max:
        total = sum(w for _, w in pool)
        pick = random.randint(1, total)
        acc = 0
        for name, w in pool:
            acc += w
            if pick <= acc:
                result["monster"] = name
                break
        if result["monster"] is None:
            result["monster"] = pool[-1][0]
        dangers[loc] = 0
        s["location_dangers"] = dangers

    return result


# ── view ───────────────────────────────────────────────────

def _emit_title_bar(s):
    """Print OSC escape sequence to set WT tab/window title. Reads config toggle."""
    if _suppress_title_bar:
        return
    config_path = os.path.join(ROOT, "config.json")
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        if not cfg.get("display", {}).get("title_bar", True):
            return
    except (FileNotFoundError, json.JSONDecodeError):
        pass

    name = s.get("player_name", "冒险者")
    loc = s.get("current_location", "???")
    chapter = s.get("chapter", 0)
    title = f"{name} | {loc} | 第{chapter}章"
    print(f"\033]0;{title}\007", end="")
    print(f"\033]2;破碎之冠 — {title}\007", end="")


def view_state(state=None):
    s = state if state is not None else load_state()
    _emit_title_bar(s)

    # Chronicle snippet —— 1 entry from world memory layer
    chronicle_entries = _chronicle_snippet()
    if chronicle_entries:
        print(f"\033[2m  ◈ {chronicle_entries[0]['kind']}: {chronicle_entries[0]['text']}\033[0m\n")

    attr_keys = ("strength", "agility", "constitution", "sanity", "magic", "wealth", "reputation")
    attr_clocks = {k: v for k, v in s.get("clocks", {}).items() if k in attr_keys}
    flags = compute_flags(attr_clocks)

    print(f"╔══ {s.get('player_name', '冒险者')} ══╗")
    print(f"种族: {s.get('player_race', '未知')}  职业: {s.get('player_class', '未知')}")
    print(f"位置: {s.get('current_location', '未知')}  章节: {s.get('chapter', 0)}")

    # Location danger clock
    dangers = s.get("location_dangers", {})
    loc = s.get("current_location", "")
    loc_danger = dangers.get(loc, 0)
    if loc_danger > 0:
        entry = get_encounter_tables().get(loc, get_encounter_tables().get("_default", {}))
        danger_max = entry.get("danger_max", 8)
        bar_filled = "█" * loc_danger
        bar_empty = "░" * (danger_max - loc_danger)
        print(f"危机感知: [{bar_filled}{bar_empty}] {loc_danger}/{danger_max}")

    print(f"--- 属性钟 ---")
    attr_order = ["strength", "agility", "constitution", "sanity", "magic", "wealth", "reputation"]
    attr_labels = {"strength": "力量", "agility": "敏捷", "constitution": "体质", "sanity": "理智", "magic": "魔力", "wealth": "财富", "reputation": "声望"}
    for key in attr_order:
        c = attr_clocks.get(key)
        if not c:
            continue
        filled, mx = c["filled"], c["max"]
        bar = "█" * filled + "░" * (mx - filled)
        mod = _attr_modifier(filled, mx, key, c.get("direction"))
        sign = "+" if mod >= 0 else ""
        label = c.get("label", attr_labels.get(key, key))
        print(f"  {label:8s} [{bar}] {filled}/{mx}  [{sign}{mod}]")

    # Custom attribute clocks (non-standard, non-progress)
    custom_attrs = {k: v for k, v in s.get("clocks", {}).items()
                    if k not in attr_keys and "current" not in v}
    if custom_attrs:
        print(f"--- 特殊属性 ---")
        for key, c in custom_attrs.items():
            filled, mx = c["filled"], c["max"]
            bar = "█" * filled + "░" * (mx - filled)
            mod = _attr_modifier(filled, mx, key, c.get("direction"))
            sign = "+" if mod >= 0 else ""
            label = c.get("label", key)
            direction = c.get("direction", "up")
            arrow = "↑" if direction == "up" else "↓"
            print(f"  {label:8s} [{bar}] {filled}/{mx}  [{sign}{mod}] {arrow}")

    injury = s.get("injury")
    if injury:
        print(f"--- ⚠ 伤残 ---")
        print(f"  类型: {injury['type']} | 剩余 {injury['ticks_remaining']} tick | 检定 DC +{injury['dc_penalty']}")

    if flags:
        print(f"--- 状态标志 ---")
        print(f"  {', '.join(flags)}")

    # Progress clocks (exclude attribute clocks which use "filled" not "current")
    progress_clocks = {k: v for k, v in s.get("clocks", {}).items()
                       if "current" in v}
    if progress_clocks:
        print(f"--- 进度钟 ({len(progress_clocks)}) ---")
        for name, c in progress_clocks.items():
            cur, mx = c["current"], c["max"]
            bar_filled = "█" * cur
            bar_empty = "░" * (mx - cur)
            warn = " ⚡满格将触发" if cur >= mx else ""
            print(f"  [{bar_filled}{bar_empty}] {cur}/{mx}  {name}{warn}")
            if cur >= mx and c.get("consequence"):
                print(f"    ↳ {c['consequence']}")

    pe = s.get("pending_encounter")
    if pe:
        print(f"--- ⚠ 待处理遭遇 ---")
        print(f"  {pe.get('monster', '未知')} (掷骰 {pe.get('roll', '?')})")

    eq = s.get("equipped", {})
    if eq.get("weapon") or eq.get("armor"):
        print(f"--- 装备 ---")
        if eq.get("weapon"):
            w = _find_by_id(s, eq["weapon"])
            print(f"  武器: {w['name'] if w else eq['weapon']}")
        if eq.get("armor"):
            a = _find_by_id(s, eq["armor"])
            print(f"  护甲: {a['name'] if a else eq['armor']}")

    inv = s.get("inventory", [])
    print(f"--- 物品 ({len(inv)} 种 / {sum(it['qty'] for it in inv)} 件) ---")
    for it in inv:
        tag_str = f"  [{', '.join(it['tags'])}]" if it["tags"] else ""
        print(f"  [{it['id']}] {it['name']} ×{it['qty']}{tag_str}")

    print(f"--- 线索 ({len(s.get('clues', []))}) ---")
    for clue in s.get("clues", []):
        print(f"  ? {clue}")

    known_frags = s.get("known_fragments", [])
    known_npcs = s.get("known_npcs", [])
    revealed = s.get("revealed_lore", [])
    if known_frags or known_npcs or revealed:
        print(f"--- 知识状态 ---")
        if known_frags:
            print(f"  已知碎片: 第{', '.join(str(f) for f in known_frags)}片")
        if known_npcs:
            print(f"  已知 NPC: {', '.join(known_npcs)}")
        if revealed:
            print(f"  已揭示文献: {', '.join(revealed)}")

    bg = s.get("background", "")
    goal = s.get("active_goal")
    if isinstance(goal, str):
        goal = None
    completed = s.get("completed_goals", [])
    if bg or goal or completed:
        print(f"--- 身份与目标 ---")
        if bg:
            print(f"  过往: {bg}")
        if goal:
            gclock = goal.get("clock_current", 0)
            gmax = goal.get("clock_max", 4)
            gfilled = "█" * gclock + "░" * (gmax - gclock)
            gfail = " ✗已失败" if goal.get("failed") else ""
            gdone = " ✓已完成" if goal.get("completed") else ""
            print(f"  目标: {goal['goal']}{gdone}{gfail}")
            print(f"  [{gfilled}] {goal.get('clock_name', '目标时钟')} [{gclock}/{gmax}]")
        if completed:
            summaries = []
            for g in completed:
                tag = "✗" if g.get("failed") else "✓"
                summaries.append(f"{tag}{g['goal']}")
            print(f"  已结束: {', '.join(summaries)}")

    tension = _active_tensions(s)
    if tension:
        print(f"--- ⚡ 过往张力 ---")
        print(f"  「{tension['background']}」×「{tension['goal']}」")
        print(f"  {tension['tension_effect']}")

    history = s.get("history", [])
    if history:
        print(f"--- 前情提要 ({len(history)} 条) ---")
        for h in history[-5:]:
            print(f"  ~ {h}")
    dm_log = s.get("dm_log", [])
    if dm_log:
        print(f"--- DM 覆盖记录 ({len(dm_log)} 条) ---")
        for entry in dm_log[-3:]:
            print(f"  ✎ 回合 {entry.get('turn','?')}: {entry.get('type','?')} — {entry.get('reason','无理由')}")

    affinities = s.get("affinities", {})
    if affinities:
        level_labels = {"hostile": "敌对", "wary": "戒备", "cold": "冷淡", "stranger": "陌生人", "acquaintance": "相识", "friend": "朋友", "close": "亲密", "intimate": "羁绊"}
        print(f"--- NPC 关系 ({len(affinities)} 人) ---")
        for name, a in affinities.items():
            level = a.get("level", "stranger")
            label = level_labels.get(level, level)
            ms_count = len(a.get("milestones", []))
            print(f"  {label}  {name}  [{ms_count} 个里程碑]")


def _render_view_text(state):
    """Return view_state() output as a plain string, without title-bar escapes."""
    import io
    global _suppress_title_bar
    buf = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = buf
    _suppress_title_bar = True
    try:
        view_state(state=state)
        return buf.getvalue()
    finally:
        sys.stdout = old_stdout
        _suppress_title_bar = False


def list_inventory(s, tag_filter=None):
    inv = s["inventory"]
    if tag_filter:
        inv = [it for it in inv if tag_filter in it.get("tags", [])]
    if not inv:
        print("(背包为空)")
        return
    for i, it in enumerate(inv, start=1):
        print(f"[{i}] {it['name']} ×{it['qty']}  ({it['id']})")


# ── World constants helpers ──────────────────────────────────

def _load_world_constants():
    if not os.path.exists(WORLD_CONSTANTS_FILE):
        return {"npcs": {}, "locations": {}}
    with open(WORLD_CONSTANTS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_world_constants(data):
    os.makedirs(os.path.dirname(WORLD_CONSTANTS_FILE), exist_ok=True)
    with open(WORLD_CONSTANTS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _lookup_npc(query):
    wc = _load_world_constants()
    query_lower = query.lower()
    results = []
    for key, profile in wc.get("npcs", {}).items():
        if query_lower in key.lower() or query_lower in profile.get("name_cn", "").lower():
            results.append({"key": key, **profile})
    if not results:
        return {"found": False, "query": query, "hint": "NPC 未收录，请用 --add_npc 添加"}
    return {"found": True, "results": results}


def _lookup_location(query):
    wc = _load_world_constants()
    query_lower = query.lower()
    results = []
    for key, sensory in wc.get("locations", {}).items():
        if query_lower in key.lower() or query_lower in sensory.get("name_cn", "").lower():
            results.append({"key": key, **sensory})
    if not results:
        return {"found": False, "query": query, "hint": "地点未收录"}
    return {"found": True, "results": results}


def _add_npc(key, traits, quirk, voice):
    wc = _load_world_constants()
    wc.setdefault("npcs", {})[key] = {
        "traits": [t.strip() for t in traits.split(",") if t.strip()],
        "quirk": quirk,
        "voice": voice,
    }
    _save_world_constants(wc)
    print(json.dumps({"added": key, "profile": wc["npcs"][key]}, ensure_ascii=False))


# ── CLI ────────────────────────────────────────────────────

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

    raw_args = sys.argv[1:]

    # --list_inventory handled before argparse (supports --tag)
    list_mode = "--list_inventory" in raw_args
    list_tag = None
    if list_mode:
        for i, a in enumerate(raw_args):
            if a == "--tag" and i + 1 < len(raw_args):
                list_tag = raw_args[i + 1]
                break
    if list_mode:
        s = load_state()
        list_inventory(s, tag_filter=list_tag)
        sys.exit(0)

    # --clear_encounter handled before argparse
    if "--clear_encounter" in raw_args:
        s = load_state()
        s["pending_encounter"] = None
        loc = s.get("current_location", "")
        dangers = s.get("location_dangers", {})
        dangers[loc] = 0
        s["location_dangers"] = dangers
        save_state(s)
        print(json.dumps({"cleared": True}, ensure_ascii=False))
        sys.exit(0)

    import argparse

    parser = argparse.ArgumentParser(description="RPG State Manager")
    parser.add_argument("--init", action="store_true", help="初始化 state.json")
    parser.add_argument("--view", action="store_true", help="查看当前状态")
    parser.add_argument("--tick", action="store_true", help="回合数 +1 (JSON 输出)")
    parser.add_argument("--with-view", action="store_true",
                        help="--tick 输出中附带格式化状态视图")
    parser.add_argument(
        "--update", nargs=2, metavar=("key", "val"), help="更新属性增量"
    )
    parser.add_argument(
        "--set", nargs=2, metavar=("key", "val"), help="设置非属性字段"
    )
    # Inventory
    parser.add_argument("--add_item", nargs="+", help="添加物品")
    parser.add_argument("--qty", type=int, default=1)
    parser.add_argument("--tags", help="标签逗号分隔")
    parser.add_argument("--use_item", help="消耗物品 (按 id)")
    parser.add_argument("--drop_item", help="丢弃物品 (按 id)")
    # Clues / history
    parser.add_argument("--add_clue", nargs="+", help="添加线索")
    parser.add_argument("--add_history", nargs="+", help="记录一条历史摘要")
    parser.add_argument("--d20", action="store_true", help="掷一个d20骰子")
    parser.add_argument("--attr", help="指定适用属性，多属性用逗号分隔取平均 (strength,agility)")
    parser.add_argument("--mod", type=int, default=0, help="DM 局势修正 (掷骰前宣告，装备/环境/优势)")
    # Future seeds
    parser.add_argument("--seed_branch", nargs="+", help="为分支选项预写叙事种子 (JSON 行)")
    parser.add_argument("--get_seed", type=int, help="提取指定分支的预写种子")
    # World constants
    parser.add_argument("--add_npc", help="添加NPC到世界常数库")
    parser.add_argument("--traits", help="NPC特征 (逗号分隔)")
    parser.add_argument("--quirk", help="NPC怪癖/口头禅")
    parser.add_argument("--voice", help="NPC声音描述")
    parser.add_argument("--lookup_npc", help="查询NPC特征 (模糊搜索)")
    parser.add_argument("--lookup_location", help="查询地点感官细节 (模糊搜索)")
    # Custom Attribute Clocks
    parser.add_argument("--create_attr", help="创建自定义属性钟（可用 --d20 检定）")
    parser.add_argument("--attr_max", type=int, default=6, help="属性钟满格值 (默认6)")
    parser.add_argument("--direction", choices=["up", "down"], default="up", help="方向: up=更多更强, down=更多更弱")
    # Progress Clocks
    parser.add_argument("--create_clock", help="创建一个进度钟")
    parser.add_argument("--clock_max", type=int, default=4, help="钟的满格值 (默认4)")
    parser.add_argument("--consequence", help="钟满格时的后果描述")
    parser.add_argument("--tick_clock", help="推进指定进度钟 1 格")
    parser.add_argument("--set_clock", nargs=2, metavar=("clock_name", "value"), help="直接设置钟的当前值")
    parser.add_argument("--reset_clock", help="重置指定钟到 0")
    # Injury
    parser.add_argument("--set_injury", help="设置伤残状态 (类型名)")
    parser.add_argument("--injury_ticks", type=int, default=5, help="伤残持续 tick 数")
    parser.add_argument("--injury_penalty", type=int, default=3, help="伤残 DC 惩罚")
    parser.add_argument("--heal", action="store_true", help="支付代价治愈伤残")
    # Knowledge firewall
    parser.add_argument("--learn_fragment", type=int, help="标记王冠碎片为已知 (1-8)")
    parser.add_argument("--learn_npc", help="标记NPC为已知 (NPC名称)")
    parser.add_argument("--reveal_lore", help="标记文献/真相为已揭示 (文献名)")
    # Goal system
    parser.add_argument("--set_background", help="设置角色过往")
    parser.add_argument("--set_goal", nargs="+", help="设置当前目标 (名称 + JSON属性)")
    parser.add_argument("--tick_goal_clock", action="store_true", help="推进目标时钟 1 格")
    parser.add_argument("--complete_goal", action="store_true", help="标记当前目标为已完成")
    parser.add_argument("--goal_location", help="完成守护目标时，被守护的地点 key")
    parser.add_argument("--goal_npc", help="完成寻找目标时，找到的 NPC 名称")
    parser.add_argument("--goal_lore", help="完成揭秘目标时，揭示的文献 key")
    parser.add_argument("--fail_goal", action="store_true", help="标记当前目标为已失败")
    # NPC Affinity / Relationships
    parser.add_argument("--affinity", nargs="*", help="查询或设置 NPC 关系 (name [level])。无参数列出全部，一个参数查询，两个参数设置")
    parser.add_argument("--milestone", help="关系升级时的里程碑描述（配合 --affinity set 使用）")
    # Pending state (pre-computation stash)
    parser.add_argument("--set_pending", nargs=2, metavar=("key", "value"),
                        help="写入暂存值到 _pending (JSON 字符串)")
    parser.add_argument("--flush_pending", action="store_true",
                        help="合并 _pending 到主状态并清空")
    args = parser.parse_args()

    if args.init:
        save_state(dict(get_default_state()))
        print("state.json 已初始化。")
        sys.exit(0)

    if args.view:
        view_state()
        sys.exit(0)

    if args.d20:
        roll = random.randint(1, 20)
        if args.attr or args.mod:
            s = load_state() if args.attr else None
            if args.attr and s:
                attr_names = [a.strip() for a in args.attr.split(",")]
                mod_sum = 0
                attr_details = []
                for name in attr_names:
                    clock = s.get("clocks", {}).get(name)
                    if clock:
                        filled, mx = clock["filled"], clock["max"]
                        m = _attr_modifier(filled, mx, name, clock.get("direction"))
                        mod_sum += m
                        attr_details.append({"attr": name, "filled": filled, "max": mx, "mod": m})
                if attr_details:
                    mod = mod_sum // len(attr_details)  # average, truncate toward zero
                else:
                    mod = 0
            else:
                mod = 0
                attr_details = []
            sit = args.mod
            result = {"roll": roll, "total": roll + mod + sit}
            if attr_details:
                result["attrs"] = attr_details
                result["modifier"] = mod
            if sit:
                result["situational"] = sit
            print(json.dumps(result, ensure_ascii=False))
        else:
            print(roll)
        sys.exit(0)

    if args.lookup_npc:
        print(json.dumps(_lookup_npc(args.lookup_npc), ensure_ascii=False))
        sys.exit(0)

    if args.lookup_location:
        print(json.dumps(_lookup_location(args.lookup_location), ensure_ascii=False))
        sys.exit(0)

    if args.add_npc:
        _add_npc(args.add_npc, args.traits or "", args.quirk or "", args.voice or "")
        sys.exit(0)

    if args.affinity is not None:
        s = load_state()
        s.setdefault("affinities", {})
        VALID_LEVELS = ["hostile", "wary", "cold", "stranger", "acquaintance", "friend", "close", "intimate"]

        if len(args.affinity) == 0:
            # List all affinities
            print(json.dumps({"affinities": s.get("affinities", {})}, ensure_ascii=False))
        elif len(args.affinity) == 1:
            # Query specific NPC
            name = args.affinity[0]
            entry = s["affinities"].get(name)
            if entry:
                print(json.dumps({"npc": name, **entry}, ensure_ascii=False))
            else:
                print(json.dumps({"npc": name, "level": "stranger", "milestones": []}, ensure_ascii=False))
        else:
            # Set affinity level
            name = args.affinity[0]
            level = args.affinity[1]
            if level not in VALID_LEVELS:
                print(json.dumps({"error": f"Invalid level '{level}'. Valid: {VALID_LEVELS}"}, ensure_ascii=False))
                sys.exit(1)
            entry = s["affinities"].get(name, {"level": "stranger", "milestones": []})
            old_level = entry.get("level", "stranger")
            entry["level"] = level
            if args.milestone:
                entry.setdefault("milestones", []).append(args.milestone)
            s["affinities"][name] = entry
            save_state(s)
            print(json.dumps({
                "affinity_set": name,
                "level": level,
                "previous_level": old_level,
                "milestones": entry.get("milestones", []),
            }, ensure_ascii=False))
        sys.exit(0)

    s = load_state()
    tick_result = None

    # ── --tick (core loop) ──
    if args.tick:
        s["turn_count"] = s.get("turn_count", 0) + 1

        result = {
            "encounter": None,
            "flags": compute_flags(s.get("clocks", {})),
        }

        if s.get("pending_encounter"):
            result["encounter_pending"] = s["pending_encounter"]
        else:
            danger_result = _tick_danger(s)
            result["danger"] = danger_result["danger"]
            if danger_result["omen"]:
                result["omen"] = danger_result["omen"]
            if danger_result["catastrophe"]:
                result["catastrophe"] = True
            if danger_result["boon"]:
                result["boon"] = True
            if danger_result["monster"]:
                s["pending_encounter"] = {
                    "monster": danger_result["monster"],
                    "roll": danger_result["danger"].get("advance", 0),
                    "turn": s["turn_count"]
                }
                result["encounter"] = s["pending_encounter"]

        # Goal clock status
        goal = s.get("active_goal")
        if goal and isinstance(goal, dict) and not goal.get("completed") and not goal.get("failed"):
            result["goal_clock"] = {
                "goal": goal["goal"],
                "clock_name": goal.get("clock_name", ""),
                "current": goal.get("clock_current", 0),
                "max": goal.get("clock_max", 4),
                "filled": goal.get("clock_current", 0) >= goal.get("clock_max", 4),
                "trigger_hint": goal.get("clock_trigger", ""),
            }

        # Active tension
        tension = _active_tensions(s)
        if tension:
            result["tension"] = tension

        # Check for filled progress clocks (skip attribute clocks)
        filled_clocks = []
        for name, c in s.get("clocks", {}).items():
            if "current" in c and c["current"] >= c["max"]:
                filled_clocks.append({"name": name, "consequence": c.get("consequence", "")})
        if filled_clocks:
            result["filled_clocks"] = filled_clocks

        # Injury tick-down
        injury = s.get("injury")
        if injury and injury.get("ticks_remaining", 0) > 0:
            injury["ticks_remaining"] -= 1
            if injury["ticks_remaining"] <= 0:
                s["injury"] = None
                result["injury_healed"] = True

        # Reminders for forgettable DM actions
        reminders = []
        if s.get("clues"):  # player has discovered things
            reminders.append("玩家本轮是否获知了新信息？→ --learn_fragment / --learn_npc / --reveal_lore")
        if s.get("affinities"):  # player has NPC relationships
            reminders.append("本轮互动是否改变了NPC关系？→ --affinity <name> <level>")
        if s.get("active_goal") and not s["active_goal"].get("completed") and not s["active_goal"].get("failed"):
            reminders.append("目标时钟是否应推进？→ --tick_goal_clock")
        if reminders:
            result["reminders"] = reminders

        tick_result = result

    changed = args.tick

    if args.update:
        k, v = args.update
        delta = int(v)
        attr_clock = s.setdefault("clocks", {}).get(k)
        if not attr_clock:
            # Auto-create attribute clock with defaults (max=6, filled=3, direction=up)
            s["clocks"][k] = {"max": 6, "filled": 3, "direction": "up", "label": k}
            attr_clock = s["clocks"][k]
        attr_clock["filled"] = max(0, min(attr_clock["max"], attr_clock["filled"] + delta))
        changed = True

    if args.set:
        k, v = args.set
        if k == "equipped_weapon":
            s.setdefault("equipped", {})["weapon"] = v if v != "None" else None
        elif k == "equipped_armor":
            s.setdefault("equipped", {})["armor"] = v if v != "None" else None
        elif k == "current_location":
            s["current_location"] = v
            _print_location_info(v)
        elif k in ("chapter", "turn_count"):
            s[k] = int(v)
        elif v in ("null", "None"):
            s[k] = None
        else:
            s[k] = v
        changed = True

    # ── Inventory ──

    if args.add_item:
        names = " ".join(args.add_item)
        for raw_name in names.replace("\n", ",").split(","):
            name = raw_name.strip()
            if not name:
                continue
            tag_list = [t.strip() for t in (args.tags or "").split(",") if t.strip()]
            existing = None
            for it in s["inventory"]:
                if it["name"] == name:
                    existing = it
                    break
            if existing:
                existing["qty"] += args.qty
                for t in tag_list:
                    if t not in existing["tags"]:
                        existing["tags"].append(t)
                print(json.dumps({"ok": True, "stacked": name, "id": existing["id"], "qty_now": existing["qty"]}, ensure_ascii=False))
            else:
                new_id = _next_item_id(s)
                s["inventory"].append({
                    "id": new_id,
                    "name": name,
                    "qty": args.qty,
                    "tags": tag_list,
                })
                print(json.dumps({"ok": True, "added": name, "id": new_id, "qty": args.qty, "tags": tag_list}, ensure_ascii=False))
        changed = True

    if args.use_item:
        it = _find_by_id(s, args.use_item)
        if not it:
            print(json.dumps({"error": f"物品 {args.use_item} 不存在"}, ensure_ascii=False))
            sys.exit(1)
        it["qty"] -= args.qty
        removed = False
        if it["qty"] <= 0:
            s["inventory"].remove(it)
            removed = True
        result = {"ok": True, "used": args.use_item, "item_name": it["name"],
                  "remaining_qty": 0 if removed else it["qty"],
                  "effect": _lookup_item_effect(it["name"])}
        print(json.dumps(result, ensure_ascii=False))
        changed = True

    if args.drop_item:
        it = _find_by_id(s, args.drop_item)
        if not it:
            print(f"错误: 物品 {args.drop_item} 不存在", file=sys.stderr)
            sys.exit(1)
        it["qty"] -= args.qty
        if it["qty"] <= 0:
            s["inventory"].remove(it)
        changed = True

    # ── Custom Attribute Clocks ──

    if args.create_attr:
        name = args.create_attr
        s.setdefault("clocks", {})[name] = {
            "filled": args.attr_max // 2,  # start at midpoint
            "max": args.attr_max,
            "direction": args.direction,
            "label": name,
        }
        print(json.dumps({
            "attr_created": name,
            "max": args.attr_max,
            "filled": args.attr_max // 2,
            "direction": args.direction,
        }, ensure_ascii=False))
        changed = True

    # ── Progress Clocks ──

    if args.create_clock:
        name = args.create_clock
        s.setdefault("clocks", {})[name] = {
            "current": 0,
            "max": args.clock_max,
            "consequence": args.consequence or "",
        }
        print(json.dumps({
            "clock_created": name,
            "current": 0,
            "max": args.clock_max,
            "consequence": args.consequence or "",
        }, ensure_ascii=False))
        changed = True

    if args.tick_clock:
        name = args.tick_clock
        if name not in s.get("clocks", {}):
            print(json.dumps({"error": f"进度钟 '{name}' 不存在"}, ensure_ascii=False))
            sys.exit(1)
        c = s["clocks"][name]
        c["current"] += 1
        result = {
            "clock_ticked": name,
            "current": c["current"],
            "max": c["max"],
            "filled": c["current"] >= c["max"],
        }
        if result["filled"] and c.get("consequence"):
            result["consequence_triggered"] = c["consequence"]
        print(json.dumps(result, ensure_ascii=False))
        changed = True

    if args.set_clock:
        name, val = args.set_clock
        if name not in s.get("clocks", {}):
            print(json.dumps({"error": f"进度钟 '{name}' 不存在"}, ensure_ascii=False))
            sys.exit(1)
        s["clocks"][name]["current"] = int(val)
        c = s["clocks"][name]
        print(json.dumps({
            "clock_set": name,
            "current": c["current"],
            "max": c["max"],
            "filled": c["current"] >= c["max"],
        }, ensure_ascii=False))
        changed = True

    if args.reset_clock:
        name = args.reset_clock
        if name not in s.get("clocks", {}):
            print(json.dumps({"error": f"进度钟 '{name}' 不存在"}, ensure_ascii=False))
            sys.exit(1)
        s["clocks"][name]["current"] = 0
        print(json.dumps({"clock_reset": name, "current": 0}, ensure_ascii=False))
        changed = True

    # ── Injury ──

    if args.set_injury:
        s["injury"] = {
            "type": args.set_injury,
            "ticks_remaining": args.injury_ticks,
            "dc_penalty": args.injury_penalty,
        }
        print(json.dumps({"injury_set": s["injury"]}, ensure_ascii=False))
        changed = True

    if args.heal:
        if s.get("injury"):
            old = s["injury"]["type"]
            s["injury"] = None
            print(json.dumps({"healed": True, "was": old}, ensure_ascii=False))
            changed = True
        else:
            print(json.dumps({"healed": False, "reason": "当前无伤残"}, ensure_ascii=False))

    # ── Knowledge firewall ──

    if args.learn_fragment is not None:
        idx = args.learn_fragment
        if idx < 1 or idx > 8:
            print(json.dumps({"error": f"碎片索引 {idx} 越界 (1-8)"}, ensure_ascii=False))
            sys.exit(1)
        known = s.setdefault("known_fragments", [])
        if idx not in known:
            known.append(idx)
            known.sort()
        print(json.dumps({"learned_fragment": idx, "known_fragments": known}, ensure_ascii=False))
        changed = True

    if args.learn_npc:
        name = args.learn_npc
        known = s.setdefault("known_npcs", [])
        if name not in known:
            known.append(name)
        print(json.dumps({"learned_npc": name, "known_npcs": known}, ensure_ascii=False))
        changed = True

    if args.reveal_lore:
        key = args.reveal_lore
        known = s.setdefault("revealed_lore", [])
        if key not in known:
            known.append(key)
        print(json.dumps({"revealed_lore": key, "revealed_lore_all": known}, ensure_ascii=False))
        changed = True

    # ── Goal system ──

    if args.set_background:
        s["background"] = args.set_background
        print(json.dumps({"background_set": args.set_background}, ensure_ascii=False))
        changed = True

    if args.set_goal:
        goal_name_parts = []
        props_json = None
        for part in args.set_goal:
            if part.startswith("{"):
                props_json = part
                break
            goal_name_parts.append(part)
        goal_name = " ".join(goal_name_parts)
        props = {"clock_name": "目标时钟", "clock_max": 4, "clock_trigger": ""}
        if props_json:
            try:
                props.update(json.loads(props_json))
            except json.JSONDecodeError:
                pass
        s["active_goal"] = {
            "goal": goal_name,
            "clock_current": 0,
            "clock_max": props.get("clock_max", 4),
            "clock_name": props.get("clock_name", "目标时钟"),
            "clock_trigger": props.get("clock_trigger", ""),
            "failed": False,
            "completed": False,
        }
        print(json.dumps({"goal_set": s["active_goal"]}, ensure_ascii=False))
        changed = True

    if args.tick_goal_clock:
        goal = s.get("active_goal")
        if not goal:
            print(json.dumps({"error": "当前没有激活的目标"}, ensure_ascii=False))
        else:
            goal["clock_current"] = goal.get("clock_current", 0) + 1
            result = {
                "goal_clock_ticked": goal["goal"],
                "current": goal["clock_current"],
                "max": goal["clock_max"],
                "filled": goal["clock_current"] >= goal["clock_max"],
            }
            if result["filled"]:
                result["warning"] = "目标时钟满格——DM 必须判定失败条件是否已叙事物化"
            print(json.dumps(result, ensure_ascii=False))
            changed = True

    if args.complete_goal:
        goal = s.get("active_goal")
        if not goal:
            print(json.dumps({"error": "当前没有激活的目标"}, ensure_ascii=False))
        else:
            goal["completed"] = True
            s.setdefault("completed_goals", []).append({
                "goal": goal["goal"],
                "failed": False,
                "completed": True,
            })

            # Apply world mutation from goal definition
            goal_def = _get_goal_definition(goal.get("goal", ""))
            mutation = goal_def.get("world_mutation") if goal_def else None
            mutation_result = None

            if mutation:
                mtype = mutation.get("type", "")
                if mtype == "flag":
                    s.setdefault("_permanent_flags", {})[mutation["key"]] = True
                    mutation_result = {"flag_set": mutation["key"], "description": mutation["description"]}

                elif mtype == "safe_house":
                    loc_key = args.goal_location or s.get("current_location", "")
                    wc = _load_world_constants()
                    if loc_key in wc.get("locations", {}):
                        wc["locations"][loc_key]["safe_house"] = True
                    else:
                        wc.setdefault("locations", {})[loc_key] = {
                            "name_cn": loc_key,
                            "safe_house": True,
                            "always": "",
                            "sound": "",
                            "mood": "",
                        }
                    _save_world_constants(wc)
                    s.setdefault("_permanent_flags", {})["safe_house"] = loc_key
                    mutation_result = {"safe_house": loc_key, "description": mutation["description"]}

                elif mtype == "npc_known":
                    npc_name = args.goal_npc or ""
                    if npc_name:
                        known = s.setdefault("known_npcs", [])
                        if npc_name not in known:
                            known.append(npc_name)
                        mutation_result = {"npc_known": npc_name, "description": mutation["description"]}
                    else:
                        mutation_result = {"npc_known": "待 DM 通过 --goal_npc 指定", "description": mutation["description"]}

                elif mtype == "lore":
                    lore_key = args.goal_lore or ""
                    if lore_key:
                        revealed = s.setdefault("revealed_lore", [])
                        if lore_key not in revealed:
                            revealed.append(lore_key)
                        mutation_result = {"lore_revealed": lore_key, "description": mutation["description"]}
                    else:
                        mutation_result = {"lore_revealed": "待 DM 通过 --goal_lore 指定", "description": mutation["description"]}

            result_out = {
                "goal_completed": goal["goal"],
                "suggestion": "DM 使用 character_options.json 的 goal_completion_branch 展示分叉选项",
            }
            if mutation_result:
                result_out["world_mutation"] = mutation_result
            print(json.dumps(result_out, ensure_ascii=False))
            changed = True

    if args.fail_goal:
        goal = s.get("active_goal")
        if not goal:
            print(json.dumps({"error": "当前没有激活的目标"}, ensure_ascii=False))
        else:
            goal["failed"] = True
            s.setdefault("completed_goals", []).append({
                "goal": goal["goal"],
                "failed": True,
                "completed": False,
            })
            print(json.dumps({
                "goal_failed": goal["goal"],
                "reminder": "DM 禁止软化失败。空白的目标栏是叙事的一部分——玩家可随时选择新目标。",
            }, ensure_ascii=False))
            changed = True

    # ── Pending state (pre-computation stash) ──

    if args.set_pending:
        key, value = args.set_pending
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            parsed = value
        s.setdefault("_pending", {})[key] = parsed
        print(json.dumps({"pending_set": key}, ensure_ascii=False))
        changed = True

    if args.flush_pending:
        pending = s.pop("_pending", {})
        if pending.get("npc_mood"):
            s.setdefault("npc_moods", {}).update(pending["npc_mood"])
        if pending.get("queued_event"):
            s.setdefault("queued_events", []).append(pending["queued_event"])
        if pending.get("pre_rolled"):
            s["_last_pre_roll"] = pending["pre_rolled"]
        print(json.dumps({"flushed": pending}, ensure_ascii=False))
        changed = True

    # ── Clues / History ──

    if args.add_clue:
        for clue in args.add_clue:
            s["clues"].append(clue)
        print(json.dumps({"ok": True, "clue_added": len(args.add_clue)}, ensure_ascii=False))
        changed = True

    if args.add_history:
        for h in args.add_history:
            s["history"].append(h)
        print(json.dumps({"ok": True, "history_added": len(args.add_history)}, ensure_ascii=False))
        changed = True

    # ── Future seeds ──

    if args.seed_branch:
        seeds = []
        for raw in args.seed_branch:
            try:
                seeds.append(json.loads(raw))
            except json.JSONDecodeError:
                print(f"错误: 无效 JSON: {raw}", file=sys.stderr)
                sys.exit(1)
        s["future_seeds"] = seeds
        changed = True

    if args.get_seed is not None:
        idx = args.get_seed
        seeds = s.get("future_seeds", [])
        if 0 <= idx < len(seeds):
            seed = seeds[idx]
            print(json.dumps(seed, ensure_ascii=False))
            # Remove consumed seed
            seeds.pop(idx)
            s["future_seeds"] = seeds
            changed = True
            save_state(s)
            sys.exit(0)
        else:
            print(json.dumps({"error": f"种子索引 {idx} 越界，共 {len(seeds)} 个种子"}, ensure_ascii=False))
            sys.exit(1)

    save_state(s)
    if tick_result:
        if args.with_view:
            tick_result["view"] = _render_view_text(s)
        print(json.dumps(tick_result, ensure_ascii=False))
