"""Shared state infrastructure: constants, caching, item helpers, goal lookup.
Imported by state_mgr.py and view.py — no circular dependencies."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from world_loader import world_file, get_active_world

STATE_FILE = "state.json"
OPTIONS_LOCK = "rules/_state/options.lock"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BG_PY_PATH = os.path.join(ROOT, "scripts", "tools", "bg.py")

def _load_json_cached(world_filename):
    from engine.state import read_world_json
    return read_world_json(world_filename)


def get_encounter_tables():
    return _load_json_cached("encounter_tables.json")


def get_threshold_rules():
    return _load_json_cached("threshold_rules.json")


def get_default_state():
    return _load_json_cached("default_state.json")


def get_character_options():
    return _load_json_cached("character_options.json")


def _find_by_id(state, item_id):
    for it in state["inventory"]:
        if it["id"] == item_id:
            return it
    return None


def _get_goal_definition(goal_name):
    gd_path = world_file("goal_definitions.json")
    if os.path.exists(gd_path):
        with open(gd_path, "r", encoding="utf-8") as f:
            gd = json.load(f)
        if goal_name in gd:
            return gd[goal_name]
    co_path = world_file("character_options.json")
    if os.path.exists(co_path):
        with open(co_path, "r", encoding="utf-8") as f:
            co = json.load(f)
        return co.get("goals", {}).get(goal_name)
    return None
