import json
import os
from typing import Any, Dict, Optional

from tools.world_loader import world_file


def _get_goal_definition(goal_name: str) -> Optional[Dict[str, Any]]:
    goal_path = world_file("goal_definitions.json")
    if os.path.exists(goal_path):
        with open(goal_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if goal_name in data:
            return data[goal_name]

    character_options_path = world_file("character_options.json")
    if os.path.exists(character_options_path):
        with open(character_options_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("goals", {}).get(goal_name)

    return None


def check_vow_status(state: Dict[str, Any]) -> Dict[str, Any]:
    goal = state.get("active_goal")
    if not goal or isinstance(goal, str):
        return {"active": False}

    current = int(goal.get("clock_current", 0))
    max_value = int(goal.get("clock_max", 0))
    filled = current >= max_value

    return {
        "active": True,
        "goal": goal.get("goal", "未命名誓言"),
        "clock_name": goal.get("clock_name", "目标时钟"),
        "current": current,
        "max": max_value,
        "filled": filled,
        "trigger_hint": goal.get("clock_trigger", ""),
        "failed": bool(goal.get("failed", False)),
        "completed": bool(goal.get("completed", False)),
        "definition": _get_goal_definition(goal.get("goal", "")) or {},
    }
