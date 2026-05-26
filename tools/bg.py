#!/usr/bin/env python3
"""Wrapper — delegates to relocated engine."""
import os
import sys
import subprocess

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SCRIPT_RELATIVE = ".claude/skills/rpg-dm/scripts/tools/bg.py"
_SCRIPT_PATH = os.path.join(_PROJECT_ROOT, _SCRIPT_RELATIVE)

if not os.path.exists(_SCRIPT_PATH):
    print(f"ERROR: {os.path.relpath(_SCRIPT_PATH, _PROJECT_ROOT)} not found", file=sys.stderr)
    sys.exit(1)

subprocess.run([sys.executable, _SCRIPT_RELATIVE] + sys.argv[1:], cwd=_PROJECT_ROOT)
