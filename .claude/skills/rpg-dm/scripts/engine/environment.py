"""Environment processing — delegates to trigger.apply().

Backward-compatible: returns same format as original process_environment().
"""

from typing import Any, Dict, List, Optional

from .trigger import apply as _trigger_apply


def process_environment(
    state: Dict[str, Any],
    action_type: str = "action",
    action_tags: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Process environment side effects.

    All logic delegated to trigger.apply(). Returns dict with:
        white_breath, events, danger, omen, encounter, deferred_encounter
    """
    return _trigger_apply(action_type, action_tags or [], state)
