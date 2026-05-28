"""Pre-narrative guardrails — inject consistency warnings into the DM prompt.

Checks state integrity and known-NPC cognition before the AI writes narrative,
so contradictions are caught before they enter the canon.
"""
from typing import Any, Dict, List

from .state import format_track, read_world_json


def _threshold_flag_value(state: Dict[str, Any], track_name: str, threshold: int) -> bool:
    clocks = state.get("clocks", {})
    track = clocks.get(track_name, {})
    if not track:
        return False
    filled = int(track.get("filled", 0))
    direction = track.get("direction", "up")
    if direction == "down":
        return filled <= threshold
    return filled >= threshold


def _active_npc_cognition_warnings(state: Dict[str, Any], npcs_present: List[str]) -> List[str]:
    """Per-NPC: what they DON'T know, what they believe WRONG."""
    warnings: List[str] = []
    wc_npcs = {}
    try:
        from tools.world_db import _load_world_constants
        wc_npcs = _load_world_constants().get("npcs", {})
    except Exception:
        return warnings

    for npc_str in npcs_present:
        # npcs_present strings are like "name: knows: ... | believes_wrongly: ..."
        if ":" in npc_str:
            npc_name = npc_str.split(":", 1)[0].strip()
        else:
            npc_name = npc_str.strip()

        profile = wc_npcs.get(npc_name, {})
        if not profile:
            continue

        cognition = profile.get("cognition", {})
        unaware = cognition.get("unaware_of", [])
        wrong = cognition.get("believes_wrongly", [])

        cn_name = profile.get("name_cn", npc_name)
        if unaware:
            items = "、".join(unaware[:3])
            warnings.append(f"[认知防火墙] {cn_name} 不知道: {items}")
        if wrong:
            items = "、".join(wrong[:3])
            warnings.append(f"[认知防火墙] {cn_name} 误信: {items}")

    return warnings


def guardrails(
    state: Dict[str, Any],
    npcs_present: List[str],
    environment_result: Dict[str, Any],
) -> List[str]:
    """Return guardrail warnings to inject into the narrator_prompt."""
    warnings: List[str] = []

    # 1. Pending encounter — remind DM to use combat flow
    encounter = state.get("pending_encounter") or environment_result.get("encounter")
    if encounter:
        monster = encounter.get("monster", "未知") if isinstance(encounter, dict) else encounter
        warnings.append(f"[战斗] 遭遇待触发: {monster} — DM 必须在下次 --action 前调用 combat.py --init {monster}")

    # 2. Goal without oath — prompt the player
    goal = state.get("active_goal")
    if goal and isinstance(goal, dict) and not goal.get("oath", "") and not goal.get("completed") and not goal.get("failed"):
        warnings.append("[誓言] 当前目标缺少誓言措辞 — DM 应在合适时机提示玩家立誓 (--set_oath)")

    # 3. NPC cognition firewalls
    cognition_warnings = _active_npc_cognition_warnings(state, npcs_present)
    warnings.extend(cognition_warnings)

    # 4. Locked truths — don't contradict
    truths = state.get("world_truths", {})
    if truths:
        wc = read_world_json("world_constants.json")
        truth_labels = wc.get("truth_dimensions", {})
        known = ", ".join(f"{truth_labels.get(k, k)}={v}" for k, v in truths.items())
        warnings.append(f"[真相锁定] 以下维度已确定，禁止叙事中引入矛盾设定: {known}")

    # 5. Critical track states
    if _threshold_flag_value(state, "supply", 1):
        warnings.append("[危机] 补给即将耗尽 — 叙事中必须体现短缺和紧迫感")
    if _threshold_flag_value(state, "health", 1):
        warnings.append("[危机] 身体濒临极限 — 描述物理代价，降低行动成功率")
    if _threshold_flag_value(state, "spirit", 1):
        warnings.append("[危机] 清醒濒临崩解 — 叙事中插入感知扭曲/幻觉/记忆闪回")

    # 6. Active injury
    injury = state.get("injury")
    if injury:
        warnings.append(f"[伤残] 当前: {injury['type']} (DC+{injury['dc_penalty']}, 剩余{injury['ticks_remaining']}tick) — 叙事中体现此限制")

    # 7. Active marks should shape narrative
    marks = state.get("marks", [])
    if marks:
        names = ", ".join(f"{m['name']}(+{m['bonus']})" for m in marks[:3])
        warnings.append(f"[印记] 可用加成: {names} — 在叙事中提及印记的触发条件")

    return warnings


def validate_state_integrity(state: Dict[str, Any]) -> List[str]:
    """Post-hoc state integrity check. Returns error list (empty = clean)."""
    errors: List[str] = []

    location = state.get("current_location", "")
    if not location:
        errors.append("current_location 未设置")

    player_name = state.get("player_name", "")
    if not player_name or player_name in ("冒险者", "无名者", ""):
        errors.append("player_name 未设置 (仍为默认值)")

    # Check that active_goal has required fields
    goal = state.get("active_goal")
    if goal and isinstance(goal, dict):
        if not goal.get("goal"):
            errors.append("active_goal.goal 字段缺失")
        if goal.get("completed") and goal.get("failed"):
            errors.append("active_goal 同时标记为 completed 和 failed")

    # Known NPCs should exist in affinities
    known = state.get("known_npcs", [])
    affinities = state.get("affinities", {})
    unknown_affinity = set(known) - set(affinities.keys())
    if unknown_affinity:
        errors.append(f"known_npcs 中有 {len(unknown_affinity)} 人没有 affinities 记录")

    return errors
