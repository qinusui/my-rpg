import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import combat as combat_engine


def _emit(result):
    print(json.dumps(result, ensure_ascii=False))


def _exit_for_result(result):
    if isinstance(result, dict) and "error" in result:
        _emit(result)
        sys.exit(1)
    _emit(result)
    sys.exit(0)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

    raw = sys.argv[1:]

    def _arg(name):
        try:
            i = raw.index(name)
            return raw[i + 1] if i + 1 < len(raw) else None
        except ValueError:
            return None

    if "--init" in raw:
        monster = _arg("--init")
        if not monster:
            _emit({"error": "--init 需要怪物名"})
            sys.exit(1)
        count = int(_arg("--count") or "1")
        _exit_for_result(combat_engine.init_combat(monster, count))

    elif "--round_event" in raw:
        _exit_for_result(combat_engine.round_event())

    elif "--env_event" in raw:
        event_key = _arg("--env_event")
        _exit_for_result(combat_engine.trigger_env_event(event_key))

    elif "--tick_constitution" in raw:
        amount = _arg("--tick_constitution")
        if amount is None:
            _emit({"error": "--tick_constitution 需要数值"})
            sys.exit(1)
        _exit_for_result(combat_engine.tick_constitution(int(amount)))

    elif "--override" in raw:
        override_type = _arg("--override")
        reason = _arg("--reason") or ""
        value = _arg("--value")
        target = _arg("--target")
        _exit_for_result(
            combat_engine.apply_override(
                override_type=override_type,
                reason=reason,
                value=int(value) if value else None,
                target=target,
            )
        )

    elif "--end" in raw:
        _exit_for_result(combat_engine.end_combat())

    else:
        _emit(
            {
                "error": "用法: combat.py --init | --round_event | --env_event | --tick_constitution | --override | --end"
            }
        )
        sys.exit(1)
