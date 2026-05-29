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


def resolve_d20(total_mod: int = 0, rng: Optional[random.Random] = None) -> Dict[str, Any]:
    roll = roll_d20(rng)
    return {"roll": roll, "total": roll + total_mod, "method": "dice"}


def roll_or_draw(
    state: Dict[str, Any],
    attr: Optional[str] = None,
    situational_mod: int = 0,
    mark: Optional[str] = None,
    dc: int = 15,
    rng: Optional[random.Random] = None,
) -> Dict[str, Any]:
    """Route between D20 and tarot based on state.belief."""
    from .state import average_attr_modifier, mark_bonus as _mark_bonus

    belief = state.get("belief", "none")
    if belief == "faith":
        from .tarot import draw_tarot, build_tarot_dice_line, draw_tarot_with_judgment

        tarot_result = draw_tarot(rng=rng)
        judgment = draw_tarot_with_judgment(state, dc=dc, rng=rng)

        result = dict(tarot_result)
        # Also attach judgment-compatible fields so engine code works unchanged
        for key in ("outcome", "degree", "margin", "narrative_frame",
                     "dm_instruction", "forbidden_phrases"):
            result[key] = judgment.get(key)
        result["_tarot"] = judgment.get("_tarot")
        return result
    else:
        attrs = [a.strip() for a in attr.split(",")] if attr else []
        attr_mod, attr_details = average_attr_modifier(state, attrs) if attrs else (0, [])
        bonus, mark_name = _mark_bonus(state, mark)
        total_mod = int(attr_mod) + int(situational_mod) + int(bonus)

        d20_result = resolve_d20(total_mod=total_mod, rng=rng)
        d20_result["attrs"] = attr_details
        if situational_mod:
            d20_result["situational"] = situational_mod
        if mark_name:
            d20_result["mark"] = {"name": mark_name, "bonus": bonus}
        return d20_result
