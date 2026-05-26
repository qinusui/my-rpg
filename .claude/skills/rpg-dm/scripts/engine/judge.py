import json
import os
import sys
from typing import Any, Dict, List, Optional

from .state import read_world_json


def _load_consequences() -> Dict[str, Any]:
    try:
        return read_world_json("consequences.json")
    except Exception as e:
        print(f"[WARN] 无法加载 consequences.json: {e}", file=sys.stderr)
        return {}


def resolve_outcome(
    roll: int,
    total: int,
    dc: int = 15,
    injury_penalty: int = 0,
) -> Dict[str, Any]:
    effective_dc = dc + injury_penalty

    if roll == 1:
        return {
            "outcome": "critical_failure",
            "degree": "catastrophic",
            "roll": roll,
            "total": total,
            "dc_effective": effective_dc,
            "gap": None,
            "narrative_frame": "彻底的失败——局势不可逆恶化，世界线分叉",
            "forbidden_phrases": ["虽然失败了但是", "侥幸的是", "幸好", "意外地"],
        }

    if roll == 20:
        return {
            "outcome": "critical_success",
            "degree": "exceptional",
            "roll": roll,
            "total": total,
            "dc_effective": effective_dc,
            "gap": None,
            "narrative_frame": "超乎预期的成功——不仅达成目标，还有额外收获",
            "forbidden_phrases": [],
        }

    margin = total - effective_dc

    if margin >= 0:
        if margin >= 5:
            return {
                "outcome": "strong_success",
                "degree": "exceptional",
                "roll": roll,
                "total": total,
                "dc_effective": effective_dc,
                "margin": margin,
                "gap": None,
                "narrative_frame": "出色的成功——行动达成目标，且没有实质代价",
                "forbidden_phrases": [],
            }
        return {
            "outcome": "success",
            "degree": "standard",
            "roll": roll,
            "total": total,
            "dc_effective": effective_dc,
            "margin": margin,
            "gap": None,
            "narrative_frame": "行动达成目标，但过程有摩擦——给一个微小代价让世界保持真实",
            "cost_hint": "optional_minor",
            "forbidden_phrases": [],
        }

    gap = abs(margin)
    if gap <= 4:
        degree = "minor"
        frame = "轻微失败——可恢复，但留下痕迹"
    elif gap <= 9:
        degree = "major"
        frame = "实质失败——局势显著恶化，不可通过简单休整恢复"
    else:
        degree = "catastrophic"
        frame = "致命失败——不可逆恶化，世界永久改变"

    result: Dict[str, Any] = {
        "outcome": "failure",
        "degree": degree,
        "roll": roll,
        "total": total,
        "dc_effective": effective_dc,
        "gap": gap,
        "narrative_frame": frame,
        "dm_instruction": "选择一项代价执行 → state_mgr.py 更新状态 → 叙事体现具体后果",
        "forbidden_phrases": ["虽然失败了但是", "侥幸的是", "幸好", "意外地"],
    }

    consequences = _load_consequences()
    if consequences and degree in consequences:
        result["consequence_categories"] = consequences[degree]

    return result