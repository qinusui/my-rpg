import json
from typing import Any, Dict, List

from tools.world_db import _load_world_constants as load_world_constants


def _relation_level(state: Dict[str, Any], npc_name: str) -> str:
    affinity = state.get("affinities", {}).get(npc_name, {})
    return affinity.get("level", "stranger")


def _visible_cognition(cognition: Dict[str, Any], relation_level: str) -> Dict[str, List[str]]:
    knows = cognition.get("knows", []) or []
    wrongly = cognition.get("believes_wrongly", []) or []
    conceals = cognition.get("conceals", []) or []

    if relation_level in {"friend", "close", "intimate"}:
        conceals_visible = conceals[:1]
    else:
        conceals_visible = []

    return {
        "knows_visible": knows[:2],
        "believes_wrongly_visible": wrongly[:1],
        "conceals_visible": conceals_visible,
    }


def npcs_present_with_cognition(state: Dict[str, Any]) -> List[str]:
    constants = load_world_constants()
    location = state.get("current_location", "")
    results: List[str] = []

    for npc_key, npc_data in constants.get("npcs", {}).items():
        npc_location = npc_data.get("location", "")
        if npc_location and location not in npc_location and npc_location not in location:
            continue

        relation = _relation_level(state, npc_key)
        visible = _visible_cognition(npc_data.get("cognition", {}), relation)

        parts = []
        if visible["knows_visible"]:
            parts.append(f"知道: {'; '.join(visible['knows_visible'])}")
        if visible["believes_wrongly_visible"]:
            parts.append(f"误信: {'; '.join(visible['believes_wrongly_visible'])}")
        if visible["conceals_visible"]:
            parts.append(f"隐瞒: {'; '.join(visible['conceals_visible'])}")

        summary = " | ".join(parts) if parts else "暂无可见认知"
        display_name = npc_data.get("name_cn", npc_key)
        results.append(f"{display_name}: {summary}")

    return results
