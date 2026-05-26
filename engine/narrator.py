from typing import Any, Dict, List, Optional

from .state import active_goal_progress, active_mark_labels, format_track


def _format_dice_text(dice_strings: List[str]) -> str:
    if not dice_strings:
        return ""
    return "\n".join(f"  {s}" for s in dice_strings)


def build_narrator_prompt(
    player_action: str,
    env_events: List[str],
    dice_results: List[str],
    vow_status: Dict[str, Any],
    chronicle_hints: List[str],
    judgment: Optional[Dict[str, Any]] = None,
    fallback_flags: Optional[List[Dict[str, Any]]] = None,
) -> str:
    lines: List[str] = []

    # ── judgment block (auto mode) ──
    if judgment:
        outcome = judgment.get("outcome", "?")
        degree = judgment.get("degree", "?")
        frame = judgment.get("narrative_frame", "")
        roll = judgment.get("roll", "?")
        total = judgment.get("total", "?")
        dc_eff = judgment.get("dc_effective", "?")

        lines.append("── 判定结论 ──")

        if outcome in ("success", "strong_success", "critical_success"):
            lines.append(f"结果: {outcome} (掷骰{roll} + 修正 = {total} vs DC{dc_eff})")
            lines.append(f"叙事框架: {frame}")
            cost_hint = judgment.get("cost_hint")
            if cost_hint == "optional_minor":
                lines.append("微小代价方向: [时间流逝] [引起注意] [消耗额外资源] —— 选一个让世界保持真实")
        else:
            gap = judgment.get("gap", "?")
            lines.append(f"结果: {degree}_{outcome} (掷骰{roll} + 修正 = {total} vs DC{dc_eff}, 差距{gap})")
            lines.append(f"叙事框架: {frame}")
            lines.append(f"DM指令: {judgment.get('dm_instruction', '')}")

            categories = judgment.get("consequence_categories", [])
            if categories:
                lines.append("")
                lines.append("可选代价:")
                for cat in categories:
                    costs_str = " / ".join(cat.get("costs", []))
                    lines.append(f"  · {cat['category']} —— {costs_str}")

            forbidden = judgment.get("forbidden_phrases", [])
            if forbidden:
                lines.append("")
                lines.append(f"禁止句式: {', '.join(forbidden)}")

        lines.append("")

    # ── player action ──
    lines.append(f"玩家行动: {player_action}")

    # ── environment ──
    if env_events:
        lines.append("── 环境压力 ──")
        for ev in env_events:
            lines.append(f"  {ev}")

    # ── dice results (raw, only if no judgment or as supplement) ──
    if dice_results and not judgment:
        lines.append(f"判定结果: {'; '.join(dice_results)}")

    # ── vow ──
    if vow_status.get("active"):
        lines.append(f"誓言状态: {vow_status.get('goal')} {vow_status.get('current')}/{vow_status.get('max')}")

    # ── chronicle ──
    if chronicle_hints:
        lines.append("── 历史回声 ──")
        for hint in chronicle_hints:
            lines.append(f"  {hint}")

    # ── fallback flags ──
    if fallback_flags:
        lines.append("")
        lines.append("── 引擎覆盖提示 ──")
        for flag in fallback_flags:
            flag_type = flag.get("type", "?")
            detail = flag.get("detail", "")
            suggestion = flag.get("suggestion") or flag.get("action", "")
            lines.append(f"  [{flag_type}] {detail}")
            if suggestion:
                lines.append(f"    → {suggestion}")

    lines.append("")
    if judgment and judgment.get("outcome") in ("failure", "critical_failure"):
        lines.append("请基于以上推进叙事。失败不可软化——失败后的世界比失败前更有趣。明确下一步可行动方向。")
    else:
        lines.append("请基于以上推进叙事，明确下一步可行动方向。")

    lines.append("")
    lines.append("[选项骨架 — 必须填充]")
    lines.append("1. ")
    lines.append("2. ")
    lines.append("3. ")
    lines.append("")
    lines.append("每次 --action 返回后，DM 必须将上述骨架扩展为 AskUserQuestion。空白选项视为回合未完成。")

    return "\n".join(lines)


def build_narrator_output(
    state: Dict[str, Any],
    player_action: str,
    npcs_present: List[str],
    environment_result: Dict[str, Any],
    dice_result_strings: List[str],
    chronicle_hints: List[str],
    vow_status: Dict[str, Any],
    judgment: Optional[Dict[str, Any]] = None,
    fallback_flags: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    output: Dict[str, Any] = {
        "state_summary": {
            "location": state.get("current_location", "未知地点"),
            "health": format_track(state, "health"),
            "spirit": format_track(state, "spirit"),
            "supply": format_track(state, "supply"),
            "active_vows": active_goal_progress(state),
            "active_marks": active_mark_labels(state),
        },
        "context": {
            "npcs_present": npcs_present,
            "environment": {
                "white_breath": environment_result.get("white_breath", "low"),
                "oracle_result": environment_result.get("oracle_result"),
                "events": environment_result.get("events", []),
                "danger": environment_result.get("danger"),
                "encounter": environment_result.get("encounter"),
                "deferred_encounter": environment_result.get("deferred_encounter"),
            },
            "dice_results": dice_result_strings,
            "chronicle_hints": chronicle_hints,
        },
        "player_action": player_action,
    }

    if judgment:
        output["judgment"] = judgment
    if fallback_flags:
        output["fallback_flags"] = fallback_flags

    output["narrator_prompt"] = build_narrator_prompt(
        player_action=player_action,
        env_events=environment_result.get("events", []),
        dice_results=dice_result_strings,
        vow_status=vow_status,
        chronicle_hints=chronicle_hints,
        judgment=judgment,
        fallback_flags=fallback_flags,
    )

    return output
