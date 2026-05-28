import json
import os
import random
from typing import Any, Dict, Optional

from tools.world_loader import world_file

from .sentinel_keys import NEXT_ORACLE


def roll_d20(rng: Optional[random.Random] = None) -> int:
    roller = rng or random
    return roller.randint(1, 20)


def roll_d6(rng: Optional[random.Random] = None) -> int:
    roller = rng or random
    return roller.randint(1, 6)


def roll_dice(dice_str: str, rng: Optional[random.Random] = None) -> int:
    roller = rng or random
    if "d" not in str(dice_str):
        return int(dice_str)
    parts = str(dice_str).split("d")
    count = int(parts[0])
    sides = int(parts[1])
    return sum(roller.randint(1, sides) for _ in range(count))


def _oracle_table() -> Dict[str, Dict[str, str]]:
    oracle_path = world_file("oracle.json")
    if os.path.exists(oracle_path):
        with open(oracle_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "1": {"oracle": "不利", "desc": "对玩家不利"},
        "2": {"oracle": "代价", "desc": "成功但要付出代价"},
        "3": {"oracle": "复杂化", "desc": "情况变得复杂"},
        "4": {"oracle": "意外", "desc": "意外因素出现"},
        "5": {"oracle": "机会", "desc": "短暂的有利条件"},
        "6": {"oracle": "眷顾", "desc": "完全有利"},
    }


def generate_oracle(rng: Optional[random.Random] = None) -> Dict[str, Any]:
    value = roll_d6(rng)
    entry = _oracle_table().get(str(value), {"oracle": "?", "desc": "未知"})
    return {"value": value, "oracle": entry["oracle"], "desc": entry["desc"], "consumed": False}


def get_next_oracle(state: Dict[str, Any], consume: bool = False, rng: Optional[random.Random] = None) -> Dict[str, Any]:
    existing = state.get(NEXT_ORACLE)
    if existing and not existing.get("consumed", True):
        oracle = dict(existing)
    else:
        oracle = generate_oracle(rng)

    if consume:
        oracle["consumed"] = True

    state[NEXT_ORACLE] = oracle
    return oracle


def resolve_d20(total_mod: int = 0, rng: Optional[random.Random] = None) -> Dict[str, int]:
    roll = roll_d20(rng)
    return {"roll": roll, "total": roll + total_mod}
