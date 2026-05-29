import argparse
import json
import os
import sys
from typing import Any, Dict, List, Optional

from tools.world_loader import setup_windows_encoding
setup_windows_encoding()

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from engine.chronicle import get_location_hints
    from engine.dice import get_next_oracle, resolve_d20, roll_or_draw
    from engine.trigger import apply as _trigger_apply
    from engine.fallback import resolve_rule_gap
    from engine.judge import resolve_outcome
    from engine.narrator import build_narrator_output
    from engine.npc import npcs_present_with_cognition
    from engine.sentinel import guardrails
    from engine.state import (
        advance_turn,
        compute_flags,
        load_state,
        save_state,
    )
    from engine.tarot import build_tarot_dice_line
    from engine.vow import check_vow_status
else:
    from .chronicle import get_location_hints
    from .dice import get_next_oracle, resolve_d20, roll_or_draw
    from .trigger import apply as _trigger_apply
    from .fallback import resolve_rule_gap
    from .judge import resolve_outcome
    from .narrator import build_narrator_output
    from .npc import npcs_present_with_cognition
    from .sentinel import guardrails
    from .state import (
        advance_turn,
        compute_flags,
        load_state,
        save_state,
    )
    from .tarot import build_tarot_dice_line
    from .vow import check_vow_status


def _dice_result_line(result: Dict[str, Any]) -> str:
    roll = result.get("roll")
    total = result.get("total")
    parts = [f"D20={roll}", f"总值={total}"]

    attrs = result.get("attrs", [])
    if attrs:
        parts.append("属性=" + ",".join(f"{a['attr']}({a['mod']:+d})" for a in attrs))
    if result.get("situational"):
        parts.append(f"局势修正={result['situational']:+d}")
    if result.get("mark"):
        parts.append(f"印记={result['mark']['name']}({result['mark']['bonus']:+d})")

    return " | ".join(parts)


def _build_roll_display(dice_result: Dict[str, Any], dice_payload: Dict[str, Any]) -> List[str]:
    """Build display lines from roll_or_draw output."""
    method = dice_result.get("method", "dice")
    if method == "tarot":
        tarot_data = dice_result.get("_tarot") or dice_result
        return [build_tarot_dice_line(tarot_data)]
    dice_payload["d20"] = dice_result
    return [_dice_result_line(dice_result)]


def _determine_modules(state: Dict[str, Any], environment_result: Dict[str, Any]) -> List[str]:
    from tools.phase_detection import detect_phases

    modules = detect_phases(state)

    # combat detection: phase_detection only checks persisted state;
    # also trigger on real-time encounter from environment
    if environment_result.get("encounter") and "combat.md" not in modules:
        modules.append("combat.md")

    return modules


def _resolve_turn(
    state: Dict[str, Any],
    player_action: str,
    action_type: str = "action",
    attr: Optional[str] = None,
    situational_mod: int = 0,
    mark: Optional[str] = None,
    consume_oracle: bool = False,
    dc: int = 15,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Pure core: state dict in → result dict out. No filesystem I/O."""

    if action_type in {"action", "tick"}:
        advance_turn(state)

    action_tags = (metadata or {}).get("action_tags", [])
    environment_result = _trigger_apply(action_type, action_tags or [], state)

    dice_result_strings: List[str] = []
    dice_payload: Dict[str, Any] = {}
    fallback_flags: List[Dict[str, Any]] = []

    if action_type == "action":
        # roll_or_draw returns tarot-compatible structure when belief==faith,
        # or dice-compatible structure otherwise.
        is_faith = state.get("belief") == "faith"
        dice_result = roll_or_draw(
            state, attr=attr,
            situational_mod=situational_mod,
            mark=mark, dc=dc,
        )
        dice_result_strings.extend(_build_roll_display(dice_result, dice_payload))

        if is_faith:
            # Tarot provides judgment fields directly via _tarot sub-dict
            tarot_data = dice_result.get("_tarot", {})
            judgment = {k: v for k, v in tarot_data.items() if k not in ("_tarot",)}
        else:
            # Standard D20 — still needs judge.resolve_outcome()
            injury_penalty = 0
            injury = state.get("injury")
            if injury:
                injury_penalty = int(injury.get("dc_penalty", 0))
            judgment = resolve_outcome(
                dice_result["roll"], dice_result["total"],
                dc=dc, injury_penalty=injury_penalty,
            )

        gap_flag = resolve_rule_gap(attr, player_action) if not is_faith else None
        if gap_flag:
            fallback_flags.append(gap_flag)
    else:
        judgment = None

    next_oracle = get_next_oracle(state, consume=consume_oracle)
    environment_result["oracle_result"] = next_oracle.get("value")
    dice_result_strings.append(
        f"神谕={next_oracle.get('value')}({next_oracle.get('oracle')})"
        + ("[已消耗]" if next_oracle.get("consumed") else "[待消耗]")
    )

    if environment_result.get("encounter"):
        state["pending_encounter"] = environment_result["encounter"]

    flags = compute_flags(state.get("clocks", {}))
    vow_status = check_vow_status(state)
    chronicle_hints = get_location_hints(state.get("current_location", ""))
    npcs_present = npcs_present_with_cognition(state)
    guardrail_warnings = guardrails(state, npcs_present, environment_result)

    narrator_output = build_narrator_output(
        state=state,
        player_action=player_action,
        npcs_present=npcs_present,
        environment_result=environment_result,
        dice_result_strings=dice_result_strings,
        chronicle_hints=chronicle_hints,
        vow_status=vow_status,
        judgment=judgment,
        fallback_flags=fallback_flags if fallback_flags else None,
    )

    narrator_output["context"]["flags"] = flags
    narrator_output["context"]["guardrails"] = guardrail_warnings
    narrator_output["context"]["engine"] = {
        "turn_count": state.get("turn_count", 0),
        "action_type": action_type,
        "metadata": metadata or {},
        "dice_payload": dice_payload,
        "inject_modules": _determine_modules(state, environment_result),
        "phases_dir": ".claude/skills/rpg-dm/phases/",
    }

    return narrator_output


def run_turn(
    player_action: str,
    action_type: str = "action",
    attr: Optional[str] = None,
    situational_mod: int = 0,
    mark: Optional[str] = None,
    consume_oracle: bool = False,
    dc: int = 15,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    state = load_state()
    result = _resolve_turn(state, player_action, action_type, attr, situational_mod, mark, consume_oracle, dc, metadata)
    save_state(state)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Automated RPG game engine turn runner")
    parser.add_argument("--player_action", required=True, help="Player action text")
    parser.add_argument("--action_type", default="action", choices=["action", "tick", "query"])
    parser.add_argument("--attr", help="Attribute names separated by commas")
    parser.add_argument("--situational_mod", type=int, default=0)
    parser.add_argument("--mark", help="Mark name")
    parser.add_argument("--consume_oracle", action="store_true")
    parser.add_argument("--dc", type=int, default=15, help="Difficulty class (default 15)")
    parser.add_argument("--metadata", help="JSON metadata")
    args = parser.parse_args()

    metadata = {}
    if args.metadata:
        try:
            metadata = json.loads(args.metadata)
        except json.JSONDecodeError:
            metadata = {"raw": args.metadata}

    output = run_turn(
        player_action=args.player_action,
        action_type=args.action_type,
        attr=args.attr,
        situational_mod=args.situational_mod,
        mark=args.mark,
        consume_oracle=args.consume_oracle,
        dc=args.dc,
        metadata=metadata,
    )
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
