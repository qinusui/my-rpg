#!/usr/bin/env python3
"""
会话富化工具 —— 将每次游玩的叙事沉淀回世界观文件。

Usage:
  python tools/session_enrich.py --snapshot   Save session start snapshot (run once at game start)
  python tools/session_enrich.py --report      Show enrichment report with session diff
  python tools/session_enrich.py --export-session "name"   Export session as standalone JSON
"""

import json
import os
import sys
import argparse
import io
from datetime import datetime

# Fix Windows encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

WORLD_DIR = "rules"
STATE_FILE = "state.json"
SETTINGS_FILE = "rules/settings.json"

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_active_world():
    settings = load_json(SETTINGS_FILE)
    return settings["active_world"], os.path.join(WORLD_DIR, settings["active_world"])

def snapshot_path(world_dir):
    return os.path.join(world_dir, "_session_start.json")

# ── Snapshot Mode ─────────────────────────────────────────────

def cmd_snapshot(world_key, world_dir):
    """Save current state as session start baseline for later diff."""
    state = load_json(STATE_FILE)
    snap = {
        "snapshot_at": datetime.now().isoformat(),
        "turn": state["turn_count"],
        "player_name": state.get("player_name", "?"),
        "clues": state.get("clues", []),
        "history": state.get("history", []),
        "inventory_names": [i["name"] for i in state.get("inventory", [])],
    }
    # Also snapshot world_constants npc/location keys (they may be added this session)
    constants = load_world_file(world_dir, "world_constants.json")
    snap["npc_keys"] = sorted(constants.get("npcs", {}).keys())
    snap["location_keys"] = sorted(constants.get("locations", {}).keys())

    save_json(snapshot_path(world_dir), snap)
    print(json.dumps({
        "snapshot": "ok",
        "turn": state["turn_count"],
        "npcs": len(snap["npc_keys"]),
        "locations": len(snap["location_keys"]),
        "clues": len(snap["clues"]),
        "history": len(snap["history"]),
    }, ensure_ascii=False))


def compute_diff(world_dir, state):
    """Compare current state against session start snapshot. Returns None if no snapshot."""
    sp = snapshot_path(world_dir)
    if not os.path.exists(sp):
        return None
    snap = load_json(sp)
    constants = load_world_file(world_dir, "world_constants.json")

    old_clues = set(snap.get("clues", []))
    old_history = set(snap.get("history", []))
    old_inv = set(snap.get("inventory_names", []))
    old_npcs = set(snap.get("npc_keys", []))
    old_locs = set(snap.get("location_keys", []))

    cur_clues = state.get("clues", [])
    cur_history = state.get("history", [])
    cur_inv = [i["name"] for i in state.get("inventory", [])]
    cur_npcs = set(constants.get("npcs", {}).keys())
    cur_locs = set(constants.get("locations", {}).keys())

    return {
        "turns_elapsed": state["turn_count"] - snap["turn"],
        "new_clues": [c for c in cur_clues if c not in old_clues],
        "new_history": [h for h in cur_history if h not in old_history],
        "new_inventory": [n for n in cur_inv if n not in old_inv],
        "new_npcs": sorted(cur_npcs - old_npcs),
        "new_locations": sorted(cur_locs - old_locs),
    }

def load_world_file(world_dir, filename):
    path = os.path.join(world_dir, filename)
    if os.path.exists(path):
        return load_json(path)
    return {}

def load_world_md(world_dir, filename):
    path = os.path.join(world_dir, filename)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return ""

# ── Report Mode ──────────────────────────────────────────────

def report(world_key, world_dir):
    """Display all enrichable content from the current state."""
    state = load_json(STATE_FILE)
    constants = load_world_file(world_dir, "world_constants.json")
    bestiary = load_world_file(world_dir, "bestiary.json")
    items_db = load_world_file(world_dir, "items.json")

    print(f"\n{'═'*60}")
    print(f"  会话富化报告 — {world_key}")
    print(f"  玩家: {state.get('player_name', '?')} | 回合: {state['turn_count']} | 章节: {state.get('chapter', '?')}")
    print(f"{'═'*60}\n")

    # ── 1. NPCs ──
    known_npcs = set(constants.get("npcs", {}).keys())
    print("▸ NPC 人物谱")
    print(f"  当前已收录: {len(known_npcs)} 人")
    if known_npcs:
        for name in sorted(known_npcs):
            profile = constants["npcs"][name]
            print(f"    ◆ {name} — {profile.get('quirk', '?')[:40]}")
    print()

    # ── 2. Locations ──
    known_locs = set(constants.get("locations", {}).keys())
    current_loc = state.get("current_location", "?")
    print(f"▸ 地点图鉴")
    print(f"  已收录: {len(known_locs)} 处 | 当前位置: {current_loc}")
    if known_locs:
        for key in sorted(known_locs):
            loc = constants["locations"][key]
            print(f"    ◆ {key} → {loc.get('name_cn', key)}")
    print()

    # ── 3. Items ──
    inventory = state.get("inventory", [])
    legendary_items = [i for i in inventory if "legendary" in i.get("tags", [])]
    quest_items = [i for i in inventory if "quest" in i.get("tags", [])]
    weapon_items = [i for i in inventory if "weapon" in i.get("tags", [])]
    print(f"▸ 物品资产")
    print(f"  总数: {len(inventory)} 件 | 传说: {len(legendary_items)} | 任务: {len(quest_items)} | 武器: {len(weapon_items)}")
    if legendary_items:
        print("  【传说】")
        for i in legendary_items:
            print(f"    ★ {i['name']} ×{i.get('qty',1)}")
    if quest_items:
        print("  【任务】")
        for i in quest_items:
            print(f"    ◆ {i['name']} ×{i.get('qty',1)}  [{','.join(i.get('tags',[]))}]")
    print()

    # ── 4. Clues & World Knowledge ──
    clues = state.get("clues", [])
    print(f"▸ 世界知识 (线索)")
    print(f"  总计: {len(clues)} 条")
    # Show only the last 5 as "recent discoveries"
    if clues:
        print("  最近发现:")
        for clue in clues[-5:]:
            print(f"    ? {clue[:80]}{'...' if len(clue)>80 else ''}")
    print()

    # ── 5. History ──
    history = state.get("history", [])
    print(f"▸ 叙事历史")
    print(f"  总计: {len(history)} 条")
    if history:
        print("  最近章节:")
        for h in history[-3:]:
            print(f"    ~ {h[:80]}{'...' if len(h)>80 else ''}")
    print()

    # ── 6. DM Overrides ──
    dm_log = state.get("dm_log", [])
    print(f"▸ DM 裁定记录")
    print(f"  总计: {len(dm_log)} 条")
    if dm_log:
        for entry in dm_log:
            print(f"    ✎ 回合{entry.get('turn','?')}: {entry.get('action','?')} — {entry.get('reason','?')[:50]}")
    print()

    # ── 7. Monsters encountered ──
    print("▸ 怪物遭遇统计 (本次会话需DM自行对照bestiary)")
    bestiary_keys = set(bestiary.keys()) if isinstance(bestiary, dict) else set()
    if bestiary_keys:
        print(f"  已收录: {len(bestiary_keys)} 种")
        for key in sorted(bestiary_keys):
            entry = bestiary[key]
            name = entry.get("name_cn", key) if isinstance(entry, dict) else key
            print(f"    ◆ {key} → {name}")
    print()

    # ── Session Diff ──
    diff = compute_diff(world_dir, state)
    if diff:
        print(f"▸ 本次会话增量 (自回合 {state['turn_count'] - diff['turns_elapsed']} 至 {state['turn_count']})")
        changed = False
        if diff["new_npcs"]:
            changed = True
            print(f"  新增 NPC: {', '.join(diff['new_npcs'])}")
        if diff["new_locations"]:
            changed = True
            print(f"  新地点: {', '.join(diff['new_locations'])}")
        if diff["new_inventory"]:
            changed = True
            print(f"  新物品: {', '.join(diff['new_inventory'])}")
        if diff["new_clues"]:
            changed = True
            print(f"  新线索: {len(diff['new_clues'])} 条")
            for c in diff["new_clues"]:
                print(f"    + {c[:90]}{'...' if len(c)>90 else ''}")
        if diff["new_history"]:
            changed = True
            print(f"  新历史: {len(diff['new_history'])} 条")
        if not changed:
            print("  (本次会话无新增内容)")
        print()

    # ── Suggestions ──
    print(f"{'─'*60}")
    print("  需手动处理:")
    needs_manual = []
    # Check for unregistered items (from --apply logic)
    items_db = load_world_file(world_dir, "items.json")
    all_known_items = set()
    for cat in items_db.values():
        if isinstance(cat, dict):
            all_known_items.update(cat.keys())
    unregistered = []
    for item in inventory:
        if item["name"] not in all_known_items:
            unregistered.append(item["name"])
    if unregistered:
        needs_manual.append(f"⚠ 物品未收录于 items.json: {', '.join(unregistered)}")

    current_loc = state.get("current_location", "")
    if current_loc and current_loc not in constants.get("locations", {}):
        needs_manual.append(f"⚠ 当前位置 '{current_loc}' 未收录于地点图鉴")

    if not needs_manual:
        needs_manual.append("✓ 无待处理项——世界观已与游玩进度同步")
    for m in needs_manual:
        print(f"  {m}")

    # Write timestamp
    state["_last_enrichment"] = datetime.now().isoformat()
    state["_enrichment_turn"] = state["turn_count"]
    save_json(STATE_FILE, state)
    print()

# ── Apply Mode ──────────────────────────────────────────────

def apply_enrichments(world_key, world_dir):
    """Deprecated — use --report instead (it now writes timestamp and checks items)."""
    print("  (--apply 已合并入 --report，直接调用 report)")
    report(world_key, world_dir)

# ── Archive Mode ──────────────────────────────────────────────

def cmd_archive(world_key, world_dir):
    """Cap clues at 20 + scars, history at 8. Overflow → _archive.json."""
    state = load_json(STATE_FILE)
    clues = state.get("clues", [])
    history = state.get("history", [])

    # Clues: keep 【伤疤】 permanently, last 20 of the rest
    scars = [c for c in clues if "【伤疤】" in c]
    rest = [c for c in clues if c not in scars]
    kept_clues = scars + rest[-20:]
    archived_clues = [c for c in clues if c not in kept_clues]

    # History: keep last 8
    kept_history = history[-8:] if len(history) > 8 else history[:]
    archived_history = history[:-8] if len(history) > 8 else []

    if not archived_clues and not archived_history:
        print(json.dumps({"archive": "nothing_to_archive"}, ensure_ascii=False))
        return

    archive_path = os.path.join(world_dir, "_archive.json")
    archive = load_json(archive_path) if os.path.exists(archive_path) else {}
    archive.setdefault("clues", [])
    archive.setdefault("history", [])
    archive["clues"].extend(archived_clues)
    archive["history"].extend(archived_history)
    archive["_last_archive"] = datetime.now().isoformat()
    save_json(archive_path, archive)

    state["clues"] = kept_clues
    state["history"] = kept_history
    save_json(STATE_FILE, state)

    print(json.dumps({
        "archive": "ok",
        "clues_archived": len(archived_clues),
        "clues_kept": len(kept_clues),
        "history_archived": len(archived_history),
        "history_kept": len(kept_history),
    }, ensure_ascii=False))


# ── Session Export Mode ─────────────────────────────────────

def export_session(world_key, world_dir, name):
    """Export current session narrative as standalone JSON/MD summary."""
    state = load_json(STATE_FILE)

    export = {
        "session_name": name,
        "world": world_key,
        "exported_at": datetime.now().isoformat(),
        "player_name": state.get("player_name", "?"),
        "player_class": state.get("player_class", "?"),
        "player_race": state.get("player_race", "?"),
        "turn_range": f"会话结束时回合 {state['turn_count']}",
        "chapter": state.get("chapter", "?"),
        "current_location": state.get("current_location", ""),
        "attributes": state.get("attributes", {}),
        "flags_active": state.get("flags", []),
        "inventory_count": len(state.get("inventory", [])),
        "inventory_highlights": [
            {"name": i["name"], "tags": i.get("tags", [])}
            for i in state.get("inventory", [])
            if any(t in i.get("tags", []) for t in ["legendary", "quest", "crown_shard"])
        ],
        "recent_history": state.get("history", [])[-5:] if state.get("history") else [],
        "recent_clues": state.get("clues", [])[-5:] if state.get("clues") else [],
        "dm_overrides": state.get("dm_log", []),
        "narrative_summary": (
            f"玩家{state.get('player_name','?')}在{state.get('current_location','?')}"
            f"结束了本次会话。回合{state['turn_count']}，章节{state.get('chapter','?')}。"
        )
    }

    out_path = f"rules/{world_key}/sessions/{name}.json"
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    save_json(out_path, export)
    print(f"\n  会话已导出: {out_path}")
    print(f"  摘要: {export['narrative_summary']}")

# ── Chronicle Mode ──────────────────────────────────────────

CHRONICLE_FILE_TEMPLATE = "rules/{world}/sessions/chronicle.json"


def _chronicle_path(world_dir):
    return os.path.join(world_dir, "sessions", "chronicle.json")


def _load_chronicle(world_dir):
    cp = _chronicle_path(world_dir)
    if os.path.exists(cp):
        return load_json(cp)
    return {"legends": [], "relics": [], "endings": []}


def _save_chronicle(world_dir, data):
    cp = _chronicle_path(world_dir)
    os.makedirs(os.path.dirname(cp), exist_ok=True)
    save_json(cp, data)


def cmd_chronicle(action, world_key, world_dir, text=None, ending_type=None):
    """Add to or view the world chronicle —— cross-session memory layer."""
    chronicle = _load_chronicle(world_dir)

    if action == "add_legend":
        chronicle.setdefault("legends", []).append(text)
        _save_chronicle(world_dir, chronicle)
        print(json.dumps({"chronicle": "legend_added", "text": text, "total": len(chronicle["legends"])}, ensure_ascii=False))

    elif action == "add_relic":
        chronicle.setdefault("relics", []).append(text)
        _save_chronicle(world_dir, chronicle)
        print(json.dumps({"chronicle": "relic_added", "text": text, "total": len(chronicle["relics"])}, ensure_ascii=False))

    elif action == "add_ending":
        chronicle.setdefault("endings", []).append({"type": ending_type or "unknown", "note": text})
        _save_chronicle(world_dir, chronicle)
        print(json.dumps({"chronicle": "ending_added", "type": ending_type, "text": text, "total": len(chronicle["endings"])}, ensure_ascii=False))

    elif action == "view":
        import random
        entries = []
        if chronicle.get("legends"):
            entries.append({"kind": "传说", "text": random.choice(chronicle["legends"])})
        if chronicle.get("relics"):
            entries.append({"kind": "遗迹", "text": random.choice(chronicle["relics"])})
        # Endings: show last 2, only type + note
        if chronicle.get("endings"):
            for e in chronicle["endings"][-2:]:
                entries.append({"kind": f"结局({e.get('type','?')})", "text": e["note"]})
        print(json.dumps({"chronicle": entries, "total_legends": len(chronicle.get("legends", [])),
                          "total_relics": len(chronicle.get("relics", [])),
                          "total_endings": len(chronicle.get("endings", []))}, ensure_ascii=False))

    else:
        print(json.dumps({"error": f"未知 chronicle 操作: {action}，可用: add_legend, add_relic, add_ending, view"}, ensure_ascii=False))
        sys.exit(1)


# ── Main ────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="会话富化——将游玩叙事沉淀回世界观")
    parser.add_argument("--snapshot", action="store_true", help="保存会话开始快照（每轮游戏开始时执行一次）")
    parser.add_argument("--report", action="store_true", help="查看富化报告与本次会话增量")
    parser.add_argument("--apply", action="store_true", help="(已弃用) 等同于 --report")
    parser.add_argument("--archive", action="store_true", help="归档旧线索/历史（保留最近+伤疤，其余移入 _archive.json）")
    parser.add_argument("--export-session", type=str, metavar="NAME", help="导出当前会话为独立文件")
    parser.add_argument("--world", type=str, help="指定世界观 (默认使用当前活跃世界观)")
    parser.add_argument("--chronicle", nargs="+", metavar=("action", "text"), help="世界知识层: add_legend | add_relic | add_ending | view")

    args = parser.parse_args()
    world_key, world_dir = get_active_world()

    if args.snapshot:
        cmd_snapshot(world_key, world_dir)

    if args.archive:
        cmd_archive(world_key, world_dir)

    if args.report or args.apply or (not args.snapshot and not args.archive and not args.export_session and not args.chronicle):
        report(world_key, world_dir)

    if args.export_session:
        export_session(world_key, world_dir, args.export_session)

    if args.chronicle:
        action = args.chronicle[0]
        text = " ".join(args.chronicle[1:]) if len(args.chronicle) > 1 else None
        ending_type = None
        if action == "add_ending" and text:
            parts = text.split(" ", 1)
            if parts[0] in ("victory", "defeat", "tragedy", "和解", "牺牲"):
                ending_type = parts[0]
                text = parts[1] if len(parts) > 1 else ""
        cmd_chronicle(action, world_key, world_dir, text=text, ending_type=ending_type)

if __name__ == "__main__":
    main()
