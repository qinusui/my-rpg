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


def _load_narrative_config() -> Dict[str, Any]:
    try:
        return read_world_json("narrative_config.json")
    except Exception:
        return {}


def resolve_outcome(
    roll: int,
    total: int,
    dc: int = 15,
    injury_penalty: int = 0,
) -> Dict[str, Any]:
    effective_dc = dc + injury_penalty
    frames = _load_narrative_config().get("judgment_frames", {})

    if roll == 1:
        cf = frames.get("critical_failure", {})
        return {
            "outcome": "critical_failure",
            "degree": "catastrophic",
            "roll": roll,
            "total": total,
            "dc_effective": effective_dc,
            "gap": None,
            "narrative_frame": cf.get("narrative_frame", "彻底的失败"),
            "forbidden_phrases": cf.get("forbidden_phrases", []),
        }

    if roll == 20:
        cs = frames.get("critical_success", {})
        return {
            "outcome": "critical_success",
            "degree": "exceptional",
            "roll": roll,
            "total": total,
            "dc_effective": effective_dc,
            "gap": None,
            "narrative_frame": cs.get("narrative_frame", "超乎预期的成功"),
            "forbidden_phrases": cs.get("forbidden_phrases", []),
        }

    margin = total - effective_dc

    if margin >= 0:
        if margin >= 5:
            ss = frames.get("strong_success", {})
            return {
                "outcome": "strong_success",
                "degree": "exceptional",
                "roll": roll,
                "total": total,
                "dc_effective": effective_dc,
                "margin": margin,
                "gap": None,
                "narrative_frame": ss.get("narrative_frame", "出色的成功"),
                "forbidden_phrases": ss.get("forbidden_phrases", []),
            }
        sc = frames.get("success", {})
        return {
            "outcome": "success",
            "degree": "standard",
            "roll": roll,
            "total": total,
            "dc_effective": effective_dc,
            "margin": margin,
            "gap": None,
            "narrative_frame": sc.get("narrative_frame", "行动达成目标"),
            "cost_hint": "optional_minor",
            "forbidden_phrases": sc.get("forbidden_phrases", []),
        }

    gap = abs(margin)
    fd = frames.get("failure_default", {})
    if gap <= 4:
        degree = "minor"
        fi = frames.get("failure_minor", {})
        frame = fi.get("narrative_frame", "轻微失败")
    elif gap <= 9:
        degree = "major"
        fi = frames.get("failure_major", {})
        frame = fi.get("narrative_frame", "实质失败")
    else:
        degree = "catastrophic"
        fi = frames.get("failure_catastrophic", {})
        frame = fi.get("narrative_frame", "致命失败")

    result: Dict[str, Any] = {
        "outcome": "failure",
        "degree": degree,
        "roll": roll,
        "total": total,
        "dc_effective": effective_dc,
        "gap": gap,
        "narrative_frame": frame,
        "dm_instruction": fi.get("dm_instruction", "选择一项代价执行"),
        "forbidden_phrases": fd.get("forbidden_phrases", []),
    }

    consequences = _load_consequences()
    if consequences and degree in consequences:
        result["consequence_categories"] = consequences[degree]

    return result