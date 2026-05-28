import json
import os
from typing import Any, Dict, Optional

from tools.world_loader import atomic_write, world_file


def _session_enrich_path() -> str:
    return world_file("_session_enrich.json")


def _load_session_overlay() -> Dict[str, Any]:
    path = _session_enrich_path()
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_session_overlay(data: Dict[str, Any]) -> None:
    path = _session_enrich_path()
    atomic_write(path, lambda f: json.dump(data, f, ensure_ascii=False, indent=2), prefix=".session_tmp_")


def _generate_npc_stub(name: str, location: str) -> Dict[str, Any]:
    return {
        "name_cn": name,
        "location": location,
        "traits": [],
        "quirk": "",
        "voice": "",
        "cognition": {"knows": [], "believes_wrongly": [], "conceals": []},
        "_generated": True,
    }


def resolve_missing_npc(name: str, location: str = "") -> Dict[str, Any]:
    from tools.world_db import _load_world_constants
    merged = _load_world_constants()

    if name in merged.get("npcs", {}):
        return {"flag": False, "reason": f"NPC '{name}' 已存在"}

    overlay = _load_session_overlay()
    stub = _generate_npc_stub(name, location)
    overlay.setdefault("npcs", {})[name] = stub
    _save_session_overlay(overlay)

    return {
        "flag": True,
        "type": "missing_npc",
        "detail": name,
        "action": f"已生成空白 NPC stub（位置: {location or '未知'}）。DM 可在对话中逐步填充特征。",
    }


def _generate_location_stub(loc_id: str) -> Dict[str, Any]:
    return {
        "name_cn": loc_id,
        "always": "",
        "sound": "",
        "mood": "",
        "white_breath_level": "low",
        "_generated": True,
    }


def resolve_missing_location(loc_id: str) -> Dict[str, Any]:
    from tools.world_db import _load_world_constants
    merged = _load_world_constants()

    if loc_id in merged.get("locations", {}):
        return {"flag": False, "reason": f"地点 '{loc_id}' 已存在"}

    overlay = _load_session_overlay()
    stub = _generate_location_stub(loc_id)
    overlay.setdefault("locations", {})[loc_id] = stub
    _save_session_overlay(overlay)

    return {
        "flag": True,
        "type": "missing_location",
        "detail": loc_id,
        "action": f"已生成空白地点 stub。DM 应在首次访问时填充感官细节。",
    }


def resolve_rule_gap(attr: Optional[str], action_context: str = "") -> Optional[Dict[str, Any]]:
    if attr:
        return None

    return {
        "type": "rule_gap",
        "detail": action_context or "玩家行动未指定属性",
        "suggestion": "DM 自行决定适用属性及 DC，或降级为纯叙事（不掷骰）。",
    }
