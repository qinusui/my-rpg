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

# Find project root by walking up until config.json is found
_ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT = _ROOT_DIR
while _ROOT != os.path.dirname(_ROOT):
    if os.path.isfile(os.path.join(_ROOT, "config.json")):
        break
    _ROOT = os.path.dirname(_ROOT)

STATE_FILE = os.path.join(_ROOT, "state.json")
PHASES_DIR = ".claude/skills/rpg-dm/phases/"


def load_state():
    """Load game state file."""
    if not os.path.exists(STATE_FILE):
        return {}
    with open(STATE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def detect_phases(state):
    """Determine which phase files are needed based on current state.

    Detection conditions mirror the old _determine_modules() logic but
    are now independent of engine output. Called after --action/--tick
    when the model needs to know which rule files to read.
    """
    modules = []

    player_name = state.get("player_name", "")
    if player_name in ("冒险者", "无名者", ""):
        modules.append("character_creation.md")

    pending_encounter = state.get("pending_encounter")
    if pending_encounter:
        modules.append("combat.md")

    if state.get("current_goal"):
        modules.append("goals.md")

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
