"""World constants CRUD: NPC/location lookup, session overlay, add NPC."""
import json
import os
import sys
from typing import Any, Dict, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from world_loader import atomic_write, world_file

WORLD_CONSTANTS_FILE = world_file("world_constants.json")
SESSION_ENRICH_FILE = world_file("_session_enrich.json")

_wc_cache: Optional[Dict[str, Any]] = None


def _load_world_constants():
    """Return merged world_constants + session enrich overlay. Cached per process lifetime."""
    global _wc_cache
    if _wc_cache is not None:
        return _wc_cache
    base = {}
    if os.path.exists(WORLD_CONSTANTS_FILE):
        with open(WORLD_CONSTANTS_FILE, "r", encoding="utf-8") as f:
            base = json.load(f)
    session = {}
    if os.path.exists(SESSION_ENRICH_FILE):
        with open(SESSION_ENRICH_FILE, "r", encoding="utf-8") as f:
            session = json.load(f)
    merged = dict(base)
    for key in ("npcs", "locations"):
        if key in session:
            merged.setdefault(key, {}).update(session[key])
    _wc_cache = merged
    return _wc_cache


def _save_world_constants(data):
    """Persist world constants diff and invalidate cache."""
    global _wc_cache
    _wc_cache = None
    base = {}
    if os.path.exists(WORLD_CONSTANTS_FILE):
        with open(WORLD_CONSTANTS_FILE, "r", encoding="utf-8") as f:
            base = json.load(f)
    session = {}
    for key in ("npcs", "locations"):
        base_items = base.get(key, {})
        data_items = data.get(key, {})
        new_items = {k: v for k, v in data_items.items() if k not in base_items}
        if new_items:
            session[key] = new_items
    atomic_write(SESSION_ENRICH_FILE, lambda f: json.dump(session, f, ensure_ascii=False, indent=2), prefix=".session_tmp_")

    # Auto-sync Markdown codec
    try:
        from engine.world_codec import sync as _sync_md
        _sync_md()
    except Exception as e:
        print(f"[WARN] Markdown codec sync 失败: {e}", file=sys.stderr)


def lookup_npc(query):
    wc = _load_world_constants()
    query_lower = query.lower()
    results = []
    for key, profile in wc.get("npcs", {}).items():
        if query_lower in key.lower() or query_lower in profile.get("name_cn", "").lower():
            results.append({"key": key, **profile})
    if not results:
        from engine.fallback import resolve_missing_npc
        fb = resolve_missing_npc(query, "")
        hint = "NPC 未收录，请用 --add_npc 添加"
        if fb.get("flag"):
            hint = fb.get("action", hint)
        return {"found": False, "query": query, "hint": hint, "fallback": fb}
    return {"found": True, "results": results}


def lookup_location(query):
    wc = _load_world_constants()
    query_lower = query.lower()
    results = []
    for key, sensory in wc.get("locations", {}).items():
        if query_lower in key.lower() or query_lower in sensory.get("name_cn", "").lower():
            results.append({"key": key, **sensory})
    if not results:
        from engine.fallback import resolve_missing_location
        fb = resolve_missing_location(query)
        hint = "地点未收录"
        if fb.get("flag"):
            hint = fb.get("action", hint)
        return {"found": False, "query": query, "hint": hint, "fallback": fb}
    return {"found": True, "results": results}


def add_npc(key, traits, quirk, voice):
    wc = _load_world_constants()
    wc.setdefault("npcs", {})[key] = {
        "traits": [t.strip() for t in traits.split(",") if t.strip()],
        "quirk": quirk,
        "voice": voice,
    }
    _save_world_constants(wc)
    print(json.dumps({"added": key, "profile": wc["npcs"][key]}, ensure_ascii=False))
