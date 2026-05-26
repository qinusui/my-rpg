"""Path setup for rpg-dm scripts package.

This module ensures the project root and scripts/ are on sys.path
so that 'engine' and 'tools' packages resolve correctly regardless
of how the script was invoked.

Call this once in any top-level entry script:
    import scripts.pathutils  # noqa: F401
Then use normal imports:
    from engine.game_engine import run_turn
"""
import os
import sys

# Resolve: this file lives in my-rpg/.claude/skills/rpg-dm/scripts/
_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPTS_DIR)  # my-rpg/

# Add scripts dir so 'from engine.xxx' resolves (engine/tools live alongside)
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

# Cache for repeated access
PROJECT_ROOT = _PROJECT_ROOT
