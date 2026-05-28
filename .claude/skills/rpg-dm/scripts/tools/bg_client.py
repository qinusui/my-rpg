"""Unified bg.py subprocess client — single module for background switching.

All bg.py invocations (set, mood, combat, reset) go through this module.
Callers import the specific function they need instead of constructing
subprocess.run([sys.executable, bg_path, ...]) inline.
"""
import json
import os
import subprocess
import sys

_BG_PY_PATH = os.path.join(os.path.dirname(__file__), "bg.py")


def _run_bg(flags, timeout=15):
    """Execute bg.py with given flags. Returns (success, result_dict_or_error_str)."""
    try:
        r = subprocess.run(
            [sys.executable, _BG_PY_PATH] + flags,
            capture_output=True, text=True, timeout=timeout,
        )
        if r.stdout.strip():
            try:
                return True, json.loads(r.stdout)
            except json.JSONDecodeError:
                return True, r.stdout.strip()
        return True, {}
    except Exception as e:
        return False, str(e)


def set_location(location_id):
    """Switch background to match a location."""
    _run_bg(["--set", location_id])


def set_mood(mood):
    """Switch background mood (no fade)."""
    _run_bg(["--mood", mood, "--no-fade"], timeout=5)


def set_combat(mode, monster=None):
    """Switch to combat background."""
    flags = ["--combat", mode]
    if monster:
        flags.extend(["--monster", monster])
    _run_bg(flags)


def reset():
    """Reset background to default. Returns (ok, result_or_error)."""
    return _run_bg(["--reset"], timeout=10)


def dispatch_from_target(bg_target):
    """Parse sentinel bg_target value and dispatch to the right function.

    Handles the prefixed format from trigger.py signals:
      mood_X   → set_mood(X)
      combat_X → set_combat(X)
      other    → set_location(other)
    """
    if bg_target.startswith("mood_"):
        set_mood(bg_target[5:])
    elif bg_target.startswith("combat_"):
        set_combat(bg_target[len("combat_"):])
    else:
        set_location(bg_target)
