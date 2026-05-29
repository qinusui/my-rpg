"""Major Arcana tarot system — oracle/D20 alternative for faith-path players."""

import random
from typing import Any, Dict, List

TAROT_DECK: List[Dict[str, Any]] = [
    {"id": "fool", "name_cn": "愚者", "index": 0,
     "upright": {"tier": "partial", "hint": "天真启程，结果未定"},
     "reversed": {"tier": "failure", "hint": "鲁莽冒进，自食其果"}},
    {"id": "magician", "name_cn": "魔术师", "index": 1,
     "upright": {"tier": "success", "hint": "意志显化，技艺在手"},
     "reversed": {"tier": "failure", "hint": "技艺误用，弄巧成拙"}},
    {"id": "high_priestess", "name_cn": "女祭司", "index": 2,
     "upright": {"tier": "partial", "hint": "隐知待揭，静观其变"},
     "reversed": {"tier": "failure", "hint": "秘密封锁，真相拒绝显现"}},
    {"id": "empress", "name_cn": "女皇", "index": 3,
     "upright": {"tier": "success", "hint": "丰盛涌现，生机勃发"},
     "reversed": {"tier": "partial", "hint": "滋养受阻，生长停滞"}},
    {"id": "emperor", "name_cn": "皇帝", "index": 4,
     "upright": {"tier": "success", "hint": "秩序确立，权威显现"},
     "reversed": {"tier": "failure", "hint": "控制失效，秩序崩解"}},
    {"id": "hierophant", "name_cn": "教皇", "index": 5,
     "upright": {"tier": "partial", "hint": "传统引导，循规蹈矩"},
     "reversed": {"tier": "failure", "hint": "教条束缚，信仰成枷"}},
    {"id": "lovers", "name_cn": "恋人", "index": 6,
     "upright": {"tier": "success", "hint": "选择清明，心意坚定"},
     "reversed": {"tier": "failure", "hint": "背叛或错选，代价随之而来"}},
    {"id": "chariot", "name_cn": "战车", "index": 7,
     "upright": {"tier": "critical_success", "hint": "意志征服，势不可挡"},
     "reversed": {"tier": "failure", "hint": "失控冲撞，力量反噬"}},
    {"id": "strength", "name_cn": "力量", "index": 8,
     "upright": {"tier": "success", "hint": "柔韧制刚，内力外显"},
     "reversed": {"tier": "partial", "hint": "力量内耗，心志动摇"}},
    {"id": "hermit", "name_cn": "隐者", "index": 9,
     "upright": {"tier": "partial", "hint": "独行寻道，答案在内"},
     "reversed": {"tier": "failure", "hint": "孤立封闭，拒绝指引"}},
    {"id": "wheel_of_fortune", "name_cn": "命运之轮", "index": 10,
     "upright": {"tier": "critical_success", "hint": "命运转机，时机已到"},
     "reversed": {"tier": "failure", "hint": "厄运循环，时机错失"}},
    {"id": "justice", "name_cn": "正义", "index": 11,
     "upright": {"tier": "partial", "hint": "因果显现，公正裁量"},
     "reversed": {"tier": "failure", "hint": "不公裁决，因果扭曲"}},
    {"id": "hanged_man", "name_cn": "倒吊人", "index": 12,
     "upright": {"tier": "failure", "hint": "牺牲等待，以退为进"},
     "reversed": {"tier": "partial", "hint": "抗拒放手，悬而未决"}},
    {"id": "death", "name_cn": "死神", "index": 13,
     "upright": {"tier": "critical_failure", "hint": "终结降临，无可回避"},
     "reversed": {"tier": "failure", "hint": "拒绝转化，执念为牢"}},
    {"id": "temperance", "name_cn": "节制", "index": 14,
     "upright": {"tier": "partial", "hint": "调和流动，恰到好处"},
     "reversed": {"tier": "failure", "hint": "失衡极端，过犹不及"}},
    {"id": "devil", "name_cn": "恶魔", "index": 15,
     "upright": {"tier": "failure", "hint": "欲望枷锁，难以挣脱"},
     "reversed": {"tier": "partial", "hint": "枷锁松动，转机初现"}},
    {"id": "tower", "name_cn": "塔", "index": 16,
     "upright": {"tier": "critical_failure", "hint": "突然崩塌，地基尽毁"},
     "reversed": {"tier": "failure", "hint": "崩塌延迟，危机潜伏"}},
    {"id": "star", "name_cn": "星星", "index": 17,
     "upright": {"tier": "success", "hint": "希望重燃，黑暗过后"},
     "reversed": {"tier": "failure", "hint": "希望幻灭，星光熄灭"}},
    {"id": "moon", "name_cn": "月亮", "index": 18,
     "upright": {"tier": "failure", "hint": "幻觉迷途，真相遮蔽"},
     "reversed": {"tier": "partial", "hint": "幻觉消散，迷雾初退"}},
    {"id": "sun", "name_cn": "太阳", "index": 19,
     "upright": {"tier": "critical_success", "hint": "光明显现，万物清朗"},
     "reversed": {"tier": "success", "hint": "光明受遮，但终将透出"}},
    {"id": "judgement", "name_cn": "审判", "index": 20,
     "upright": {"tier": "partial", "hint": "清算时刻，过去归位"},
     "reversed": {"tier": "failure", "hint": "拒绝觉醒，审判延误"}},
    {"id": "world", "name_cn": "世界", "index": 21,
     "upright": {"tier": "critical_success", "hint": "圆满完成，周期终结"},
     "reversed": {"tier": "success", "hint": "完成受阻，终点将近"}},
]

# Tier → effective DC margin equivalent for resolve_outcome compatibility.
# These margins produce outcomes with similar weight.
_TIER_MARGINS = {
    "critical_success": 15,
    "success": 3,
    "partial": 0,
    "failure": -5,
    "critical_failure": -15,
}

# Dark cards get slightly higher opacity for dramatic effect.
_DARK_CARD_OPACITY = {"death", "devil", "tower"}
_LIGHT_CARD_OPACITY = {"star", "world", "sun"}


def draw_tarot(rng: random.Random = None) -> Dict[str, Any]:
    """Draw one Major Arcana card. Returns structured result aligned with D20 output."""
    card = rng.choice(TAROT_DECK) if rng else random.choice(TAROT_DECK)
    is_reversed = (rng.random() < 0.5) if rng else (random.random() < 0.5)
    orientation = "reversed" if is_reversed else "upright"
    reading = card[orientation]

    return {
        "method": "tarot",
        "card_id": card["id"],
        "card_name": card["name_cn"],
        "card_index": card["index"],
        "reversed": is_reversed,
        "orientation": orientation,
        "tier": reading["tier"],
        "narrative_hint": reading["hint"],
        "bg_key": f"tarot_{card['id']}",
    }


def draw_tarot_with_judgment(
    state: Dict[str, Any], dc: int = 15,
    rng: random.Random = None,
) -> Dict[str, Any]:
    """Draw tarot + convert tier to judge-compatible resolution dict.

    Mirrors resolve_outcome() structure so narrator / consequences code
    can work unchanged regardless of whether D20 or tarot was used.
    """
    import os
    import sys

    # Lazy import to avoid circular deps — same pattern as judge.py uses
    _sys_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _sys_path not in sys.path:
        sys.path.insert(0, _sys_path)

    card = rng.choice(TAROT_DECK) if rng else random.choice(TAROT_DECK)
    is_reversed = (rng.random() < 0.5) if rng else (random.random() < 0.5)
    orientation = "reversed" if is_reversed else "upright"
    reading = card[orientation]

    margin = _TIER_MARGINS.get(reading["tier"], 0)
    effective_dc = dc  # tarot has no injury penalty — the card IS the verdict

    is_success = margin >= 0
    is_fail = margin < 0
    margin_abs = abs(margin)

    # Build a minimal judgment-like payload
    outcome_label = "strong_success" if margin >= 10 else "success" if is_success else "failure"
    degree_label = "exceptional" if margin >= 10 else "standard" if is_success else ("minor" if margin_abs <= 5 else "catastrophic") if is_fail else "minor"
    narrative_frame = reading["hint"]

    gap_flag = None  # tarot has no attribute-based rule gaps

    # Load consequence categories for dark tiers
    consequence_categories: List[Dict[str, Any]] = []
    if reading["tier"] == "critical_failure":
        try:
            from engine.state import read_world_json
            frames = read_world_json("narrative_config.json").get("judgment_frames", {})
            cf = frames.get("critical_failure", {})
            forbidden = cf.get("forbidden_phrases", [])
        except Exception:
            forbidden = []
    elif is_fail:
        consequence_categories = [{"category": "消耗", "costs": ["时间流失", "资源耗尽"]} ]
        forbidden = []
    else:
        forbidden = []

    return {
        "outcome": outcome_label,
        "degree": degree_label,
        "roll": None,  # tarot has no numeric roll
        "total": None,
        "dc_effective": effective_dc,
        "margin": margin,
        "gap": None,
        "narrative_frame": narrative_frame,
        "dm_instruction": "按照牌意推进叙事" if not is_fail else "选择一项代价执行",
        "forbidden_phrases": forbidden,
        # Extra context for narrator display (not consumed by judge)
        "_tarot": {
            "card_id": card["id"],
            "card_name": card["name_cn"],
            "card_index": card["index"],
            "reversed": is_reversed,
            "orientation": orientation,
            "tier": reading["tier"],
            "narrative_hint": reading["hint"],
            "bg_key": f"tarot_{card['id']}",
        },
    }


def build_tarot_dice_line(tarot_result: Dict[str, Any]) -> str:
    """Format a tarot draw into a line compatible with _dice_result_line style."""
    name = tarot_result["card_name"]
    orient = "逆位" if tarot_result.get("reversed") else "正位"
    card_id = tarot_result.get("card_id", "?")
    idx = tarot_result.get("card_index", "")
    label = f"{idx}{name}" if idx != "" else name
    parts = [f"[塔罗]{label}{orient}"]

    tier = tarot_result.get("tier", "?")
    parts.append(f"层级={tier}")

    hint = tarot_result.get("narrative_hint")
    if hint:
        parts.append(hint)

    return " · ".join(parts)


def tarot_opacity(card_id: str) -> float:
    """Default opacity per card mood — darker cards get higher opacity."""
    if card_id in _DARK_CARD_OPACITY:
        return 0.42
    if card_id in _LIGHT_CARD_OPACITY:
        return 0.28
    return 0.35
