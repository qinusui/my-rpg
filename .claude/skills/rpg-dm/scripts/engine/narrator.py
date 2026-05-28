from typing import Any, Dict, List, Optional

from .state import active_goal_progress, active_mark_labels, format_track, read_world_json


def _load_templates() -> Dict[str, Any]:
    try:
        return read_world_json("narrative_config.json").get("narrator_templates", {})
    except Exception:
        return {}


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
    t = _load_templates()
    lines: List[str] = []

    if judgment:
        outcome = judgment.get("outcome", "?")
        degree = judgment.get("degree", "?")
        frame = judgment.get("narrative_frame", "")
        roll = judgment.get("roll", "?")
        total = judgment.get("total", "?")
        dc_eff = judgment.get("dc_effective", "?")

        lines.append(t.get("judgment_header", "── 判定结论 ──"))

        if outcome in ("success", "strong_success", "critical_success"):
            line_tpl = t.get("success_line", "结果: {outcome}")
            lines.append(line_tpl.format(outcome=outcome, roll=roll, total=total, dc_eff=dc_eff))
            lines.append(t.get("narrative_frame_label", "叙事框架: {frame}").format(frame=frame))
            cost_hint = judgment.get("cost_hint")
            if cost_hint == "optional_minor":
                from .state import read_world_json as _rwj
                try:
                    sc = _rwj("narrative_config.json").get("judgment_frames", {}).get("success", {})
                    lines.append(sc.get("cost_hint_text", "微小代价方向: 选一个"))
                except Exception:
                    lines.append("微小代价方向: [时间流逝] [引起注意] [消耗额外资源] —— 选一个让世界保持真实")
        else:
            gap = judgment.get("gap", "?")
            line_tpl = t.get("failure_line", "结果: {degree}_{outcome}")
            lines.append(line_tpl.format(degree=degree, outcome=outcome, roll=roll, total=total, dc_eff=dc_eff, gap=gap))
            lines.append(t.get("narrative_frame_label", "叙事框架: {frame}").format(frame=frame))
            lines.append(t.get("dm_instruction_label", "DM指令: {instruction}").format(
                instruction=judgment.get("dm_instruction", "")))

            categories = judgment.get("consequence_categories", [])
            if categories:
                lines.append("")
                lines.append(t.get("cost_section_header", "可选代价:"))
                item_tpl = t.get("cost_item_format", "  · {category} —— {costs}")
                for cat in categories:
                    costs_str = " / ".join(cat.get("costs", []))
                    lines.append(item_tpl.format(category=cat["category"], costs=costs_str))

            forbidden = judgment.get("forbidden_phrases", [])
            if forbidden:
                lines.append("")
                lines.append(t.get("forbidden_label", "禁止句式: {phrases}").format(
                    phrases=", ".join(forbidden)))

        lines.append("")

    lines.append(t.get("player_action_label", "玩家行动: {action}").format(action=player_action))

    if env_events:
        lines.append(t.get("environment_header", "── 环境压力 ──"))
        for ev in env_events:
            lines.append(f"  {ev}")

    if dice_results and not judgment:
        lines.append(f"判定结果: {'; '.join(dice_results)}")

    if vow_status.get("active"):
        v_tpl = t.get("vow_status_format", "誓言状态: {goal} {current}/{max}")
        lines.append(v_tpl.format(goal=vow_status.get("goal"), current=vow_status.get("current"),
                                  max=vow_status.get("max")))

    if chronicle_hints:
        lines.append(t.get("chronicle_header", "── 历史回声 ──"))
        for hint in chronicle_hints:
            lines.append(f"  {hint}")

    if fallback_flags:
        lines.append("")
        lines.append(t.get("fallback_header", "── 引擎覆盖提示 ──"))
        item_tpl = t.get("fallback_item_format", "  [{type}] {detail}")
        sug_tpl = t.get("fallback_suggestion_format", "    → {suggestion}")
        for flag in fallback_flags:
            flag_type = flag.get("type", "?")
            detail = flag.get("detail", "")
            suggestion = flag.get("suggestion") or flag.get("action", "")
            lines.append(item_tpl.format(type=flag_type, detail=detail))
            if suggestion:
                lines.append(sug_tpl.format(suggestion=suggestion))

    lines.append("")
    if judgment and judgment.get("outcome") in ("failure", "critical_failure"):
        lines.append(t.get("failure_prompt", "请基于以上推进叙事。明确下一步可行动方向。"))
    else:
        lines.append(t.get("success_prompt", "请基于以上推进叙事，明确下一步可行动方向。"))

    lines.append("")
    lines.append(t.get("option_skeleton", "[选项骨架 — 必须填充]"))
    for opt in t.get("option_lines", ["1. ", "2. ", "3. "]):
        lines.append(opt)
    lines.append("")
    lines.append(t.get("option_footer", "每次 --action 返回后，DM 必须将上述骨架扩展为 AskUserQuestion。"))

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
