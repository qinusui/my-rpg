"""Phase detection — determine which rule files are active based on game state.

This module consolidates all auto-detection logic previously scattered
across game_engine._determine_modules() and CLAUDE.md routing tables.

Usage:
    python .claude/skills/rpg-dm/scripts/tools/phase_detection.py detect
        Returns JSON of required phase files.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine.state import load_state

PHASES_DIR = ".claude/skills/rpg-dm/phases/"


def detect_phases(state):
    """Determine which phase files are needed based on current state.

    Detection conditions mirror the old _determine_modules() logic but
    are now independent of engine output. Called after --action/--tick
    when the model needs to know which rule files to read.
    """
    modules = []

    player_name = state.get("player_name", "")
    origin = state.get("origin", "")
    scar = state.get("scar", "")
    drive = state.get("drive", "")
    appearance = state.get("appearance", "")
    is_creating = (
        player_name in ("冒险者", "无名者", "")
        or not origin
        or not scar
        or not drive
        or not appearance
    )
    if is_creating:
        modules.append("character_creation.md")

    pending_encounter = state.get("pending_encounter")
    if pending_encounter:
        modules.append("combat.md")

    if state.get("current_goal"):
        modules.append("goals.md")

    # Oath selection: truths locked but no oath yet → DM must present oath choice
    world_truths = state.get("world_truths", {})
    has_locked_truth = isinstance(world_truths, dict) and len(world_truths) > 0
    active_goal = state.get("active_goal") or state.get("current_goal")
    oath_set = isinstance(active_goal, dict) and bool(active_goal.get("oath", ""))
    if has_locked_truth and (not active_goal or not oath_set):
        modules.append("oath_selection.md")

    health = state.get("health")
    spirit = state.get("spirit")
    if isinstance(health, dict) and health.get("current", 0) >= health.get("max", 10):
        modules.append("endings.md")
    if isinstance(spirit, dict) and spirit.get("current", 0) <= 0:
        modules.append("endings.md")

    return list(dict.fromkeys(modules))


def main():
    if len(sys.argv) < 2 or sys.argv[1] == "--help" or sys.argv[1] == "-h":
        print("用法: python scripts/tools/phase_detection.py detect")
        sys.exit(1)

    if sys.argv[1] == "detect":
        state = load_state()
        phases = detect_phases(state)
        result = {
            "phases_dir": PHASES_DIR,
            "active_phases": phases,
            "state_summary": {
                "player_name": state.get("player_name", ""),
                "location": state.get("current_location", ""),
                "has_pending_encounter": bool(state.get("pending_encounter")),
                "has_active_goal": bool(state.get("current_goal")),
            },
        }
        print(json.dumps(result, ensure_ascii=False))
    else:
        print(f"未知命令: {sys.argv[1]}")
        sys.exit(1)


if __name__ == "__main__":
    main()
