"""Bootstrap — ensure correct import paths for rpg-dm scripts.

Call this once at the top of any entry-point script:
    import scripts.bootstrap  # noqa: F401
Then import modules normally:
    from engine.game_engine import run_turn
    from tools.state_mgr import ...
"""
import os
import sys

# Resolve root = my-rpg/ regardless of CWD
_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # skills/rpg-dm/
PROJECT_ROOT = os.path.dirname(_HERE)  # my-rpg/

# Insert scripts dir so "from engine.xxx" and "from tools.xxx" resolve
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
