"""State rendering: view_state, inventory listing, title bar, location info, chronicle."""
import io
import json
import os
import random
import subprocess
import sys
from contextlib import redirect_stdout

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from world_loader import world_file
from state_core import (
    _find_by_id,
    _get_goal_definition,
    ROOT,
    BG_PY_PATH,
    get_active_world,
    get_default_state,
    get_encounter_tables,
)
from world_db import _load_world_constants
from engine.state import compute_flags, attr_modifier, read_world_json


def _emit_title_bar(s, suppress=False):
    if suppress:
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
    world_name = get_active_world()
    try:
        with open(os.path.join("rules", "settings.json"), "r", encoding="utf-8") as f:
            world_name = json.load(f)["worlds"][world_name].get("name_cn", world_name)
    except Exception:
        pass  # world name lookup is cosmetic; failure is harmless
    title = f"{name} | {loc} | 第{chapter}章"
    print(f"\033]0;{title}\007", end="")
    print(f"\033]2;{world_name} — {title}\007", end="")


def _chronicle_snippet():
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
    random.shuffle(entries)
    return entries[:1]


def _active_tensions(s):
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


def _print_location_info(loc_id):
    wc = _load_world_constants()
    locations = wc.get("locations", {})
    npcs = wc.get("npcs", {})
    result = {"location_set": loc_id}
    loc = locations.get(loc_id)
    if not loc:
        for key, val in locations.items():
            if loc_id in key or key in loc_id:
                loc = val
                result["location_set"] = key
                break
    if loc:
        result["location"] = {k: loc[k] for k in ("name_cn", "always", "sound", "mood") if k in loc}
    nearby = {}
    for npc_name, npc_data in npcs.items():
        npc_loc = npc_data.get("location", "")
        if npc_loc and (npc_loc in loc_id or loc_id in npc_loc):
            nearby[npc_name] = npc_data.get("name_cn", npc_name)
    if nearby:
        result["npcs_nearby"] = nearby
    print(json.dumps(result, ensure_ascii=False))


def _auto_bg_set(location_id):
    from bg_client import set_location
    set_location(location_id)


def _render_view_text(state):
    buf = io.StringIO()
    with redirect_stdout(buf):
        view_state(state, suppress_title=True)
    return buf.getvalue()


def view_state(state, suppress_title=False):
    s = state
    _emit_title_bar(s, suppress=suppress_title)

    chronicle_entries = _chronicle_snippet()
    if chronicle_entries:
        print(f"\033[2m  ◈ {chronicle_entries[0]['kind']}: {chronicle_entries[0]['text']}\033[0m\n")

    attr_order = get_default_state().get("attr_order", ["strength", "agility", "constitution", "sanity", "magic", "wealth", "reputation"])
    attr_clocks = {k: v for k, v in s.get("clocks", {}).items() if k in attr_order}
    flags = compute_flags(s.get("clocks", {}))

    print(f"╔══ {s.get('player_name', '冒险者')} ══╗")
    print(f"种族: {s.get('player_race', '未知')}  职业: {s.get('player_class', '未知')}")
    origin = s.get("origin", "")
    if origin:
        print(f"出身: {origin}")
    print(f"位置: {s.get('current_location', '未知')}  章节: {s.get('chapter', 0)}  回合: {s.get('turn_count', 0)}")

    active_scene = s.get("active_scene")
    if active_scene:
        scene_name = active_scene.get("name", "?")
        scene_loc = active_scene.get("location", s.get("current_location", ""))
        started = active_scene.get("started_at_turn", 0)
        current = s.get("turn_count", 0)
        print(f"场景: {scene_name}  ({scene_loc})  [{current - started} turns]")

    truths = s.get("world_truths", {})
    if truths:
        print(f"--- 世界观认知 ---")
        wc = read_world_json("world_constants.json")
        truth_labels = wc.get("truth_dimensions", {})
        for dim, choice in truths.items():
            label = truth_labels.get(dim, dim)
            print(f"  {label}: {choice}")

    dangers = s.get("location_dangers", {})
    loc = s.get("current_location", "")
    loc_danger = dangers.get(loc, 0)
    if loc_danger > 0:
        tables = get_encounter_tables()
        entry = tables.get(loc, tables.get("_default", {}))
        danger_max = entry.get("danger_max", 8)
        bar_filled = "█" * loc_danger
        bar_empty = "░" * (danger_max - loc_danger)
        print(f"危机感知: [{bar_filled}{bar_empty}] {loc_danger}/{danger_max}")

    print(f"--- 属性 ---")
    for key in attr_order:
        c = attr_clocks.get(key)
        if not c:
            continue
        filled, mx = c["filled"], c["max"]
        bar = "█" * filled + "░" * (mx - filled)
        mod = attr_modifier(c)
        sign = "+" if mod >= 0 else ""
        label = c.get("label", key)
        direction = c.get("direction", "up")
        arrow = "↑" if direction == "up" else "↓"
        print(f"  {label:8s} [{bar}] {filled}/{mx}  [{sign}{mod}] {arrow}")

    track_order = get_default_state().get("track_order", [])
    track_clocks = {k: v for k, v in s.get("clocks", {}).items() if k in track_order}
    if track_clocks:
        print(f"--- 轨道 ---")
        for key in track_order:
            c = track_clocks.get(key)
            if not c:
                continue
            filled, mx = c["filled"], c["max"]
            bar = "█" * filled + "░" * (mx - filled)
            mod = attr_modifier(c)
            sign = "+" if mod >= 0 else ""
            label = c.get("label", key)
            direction = c.get("direction", "up")
            arrow = "↑" if direction == "up" else "↓"
            print(f"  {label:8s} [{bar}] {filled}/{mx}  [{sign}{mod}] {arrow}")

    custom_attrs = {k: v for k, v in s.get("clocks", {}).items()
                    if k not in attr_order and k not in track_order and "current" not in v}
    if custom_attrs:
        print(f"--- 特殊属性 ---")
        for key, c in custom_attrs.items():
            filled, mx = c["filled"], c["max"]
            bar = "█" * filled + "░" * (mx - filled)
            mod = attr_modifier(c)
            sign = "+" if mod >= 0 else ""
            label = c.get("label", key)
            direction = c.get("direction", "up")
            arrow = "↑" if direction == "up" else "↓"
            print(f"  {label:8s} [{bar}] {filled}/{mx}  [{sign}{mod}] {arrow}")

    marks = s.get("marks", [])
    if marks:
        print(f"--- 印记 ---")
        for mk in marks:
            print(f"  {mk['name']}  +{mk['bonus']}  ({mk['context']})")

    injury = s.get("injury")
    if injury:
        print(f"--- ⚠ 伤残 ---")
        print(f"  类型: {injury['type']} | 剩余 {injury['ticks_remaining']} tick | 检定 DC +{injury['dc_penalty']}")

    if flags:
        print(f"--- 状态标志 ---")
        print(f"  {', '.join(flags)}")

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

    scenes = s.get("scene_history", [])
    if scenes:
        print(f"--- 场景历史 ({len(scenes)} 场) ---")
        for sc in scenes[-8:]:
            name = sc.get("name", "?")
            turns = ""
            started = sc.get("started_at_turn")
            ended = sc.get("ended_at_turn")
            if started is not None and ended is not None:
                turns = f" [{ended - started}t]"
            summary = sc.get("summary", "")
            if summary:
                print(f"  {name}{turns} — {summary}")
            else:
                print(f"  {name}{turns}")


def list_inventory(s, tag_filter=None):
    inv = s["inventory"]
    if tag_filter:
        inv = [it for it in inv if tag_filter in it.get("tags", [])]
    if not inv:
        print("(背包为空)")
        return
    for i, it in enumerate(inv, start=1):
        print(f"[{i}] {it['name']} ×{it['qty']}  ({it['id']})")
