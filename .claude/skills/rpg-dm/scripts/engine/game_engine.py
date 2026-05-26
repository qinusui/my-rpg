import argparse
import json
import os
import sys
from typing import Any, Dict, List, Optional

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from engine.chronicle import get_location_hints
    from engine.dice import get_next_oracle, resolve_d20
    from engine.environment import process_environment
    from engine.fallback import resolve_rule_gap
    from engine.judge import resolve_outcome
    from engine.narrator import build_narrator_output
    from engine.npc import npcs_present_with_cognition
    from engine.state import (
        advance_turn,
        average_attr_modifier,
        compute_flags,
        load_state,
        mark_bonus,
        save_state,
    )
    from engine.vow import check_vow_status
else:
    from .chronicle import get_location_hints
    from .dice import get_next_oracle, resolve_d20
    from .environment import process_environment
    from .fallback import resolve_rule_gap
    from .judge import resolve_outcome
    from .narrator import build_narrator_output
    from .npc import npcs_present_with_cognition
    from .state import (
        advance_turn,
        average_attr_modifier,
        compute_flags,
        load_state,
        mark_bonus,
        save_state,
    )
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


def _determine_modules(state: Dict[str, Any], environment_result: Dict[str, Any]) -> List[str]:
    modules: List[str] = []

    player_name = state.get("player_name", "")
    if player_name in ("冒险者", "无名者", ""):
        modules.append("character_creation.md")

    pending_encounter = state.get("pending_encounter")
    if pending_encounter or environment_result.get("encounter"):
        modules.append("combat.md")

    if state.get("current_goal"):
        modules.append("goals.md")

    health = state.get("health")
    spirit = state.get("spirit")
    if isinstance(health, dict) and health.get("current", 0) >= health.get("max", 10):
        modules.append("endings.md")
    if isinstance(spirit, dict) and spirit.get("current", 0) <= 0:
        modules.append("endings.md")

    return list(dict.fromkeys(modules))


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

    if action_type in {"action", "tick"}:
        advance_turn(state)

    action_tags = (metadata or {}).get("action_tags", [])
    environment_result = process_environment(state, action_type=action_type, action_tags=action_tags)

    dice_result_strings: List[str] = []
    dice_payload: Dict[str, Any] = {}
    fallback_flags: List[Dict[str, Any]] = []

    if action_type == "action":
        attrs = [a.strip() for a in attr.split(",")] if attr else []
        attr_mod, attr_details = average_attr_modifier(state, attrs) if attrs else (0, [])
        bonus, mark_name = mark_bonus(state, mark)
        total_mod = int(attr_mod) + int(situational_mod) + int(bonus)

        d20_result = resolve_d20(total_mod=total_mod)
        d20_result["attrs"] = attr_details
        if situational_mod:
            d20_result["situational"] = situational_mod
        if mark_name:
            d20_result["mark"] = {"name": mark_name, "bonus": bonus}

        dice_payload["d20"] = d20_result
        dice_result_strings.append(_dice_result_line(d20_result))

        injury_penalty = 0
        injury = state.get("injury")
        if injury:
            injury_penalty = int(injury.get("dc_penalty", 0))
        judgment = resolve_outcome(
            d20_result["roll"], d20_result["total"],
            dc=dc, injury_penalty=injury_penalty,
        )

        gap_flag = resolve_rule_gap(attr, player_action)
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

    save_state(state)

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
    narrator_output["context"]["engine"] = {
        "turn_count": state.get("turn_count", 0),
        "action_type": action_type,
        "metadata": metadata or {},
        "dice_payload": dice_payload,
        "inject_modules": _determine_modules(state, environment_result),
        "phases_dir": ".claude/skills/rpg-dm/phases/",
    }

    return narrator_output


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
