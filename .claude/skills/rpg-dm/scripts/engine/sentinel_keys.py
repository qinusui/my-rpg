"""Sentinel key contracts — typed constants for state dict inter-module communication.

These underscore-prefixed keys on the mutable state dict serve as an implicit
event bus between modules. Each is documented with its producer, consumer(s),
and lifecycle (who writes, who reads, who clears).

Adding a new sentinel? Register it here first so the contract stays visible.
"""

# ── trigger.py → state_mgr.py ──────────────────────────────────────────
# Producer: trigger._switch_background() writes this when a bg change is needed.
# Consumer: state_mgr.py --action and --tick handlers read + pop + act on it.
# Lifecycle: set in trigger, popped by state_mgr (one-shot signal).
BG_SWITCH_TARGET = "__bg_switch_target"

# ── Internal to trigger.py ─────────────────────────────────────────────
# Producer/Consumer: trigger._switch_background() tracks previous location
# to detect location changes. Written at end of each call, popped at start.
TRIGGER_PREV_LOC = "__trigger_prev_loc"

# Producer: trigger._resolve_encounters() defers encounter release.
# Consumer: trigger._resolve_encounters() releases it on next trigger call.
PENDING_ENCOUNTER = "__pending_encounter"

# ── dice.py ↔ state_mgr.py ─────────────────────────────────────────────
# Producer: dice.get_next_oracle() generates oracle on creation.
# Consumer: game_engine._resolve_turn() reads it; state_mgr --consume_oracle marks consumed.
# Lifecycle: persists across turns until consumed, then regenerated.
NEXT_ORACLE = "_next_oracle"

# ── state_mgr.py internal ──────────────────────────────────────────────
# Producer: --complete_goal with world_mutation writes permanent flags.
# Consumer: any code checking world state (e.g. "safe_house" flag).
PERMANENT_FLAGS = "_permanent_flags"

# Producer: --flush_pending writes pre-rolled dice results.
# Consumer: state_mgr internal (bridge between pre-computation and action).
LAST_PRE_ROLL = "_last_pre_roll"

# ── All known sentinel keys (for validation / debugging) ────────────────
ALL_SENTINELS = frozenset({
    BG_SWITCH_TARGET,
    TRIGGER_PREV_LOC,
    PENDING_ENCOUNTER,
    NEXT_ORACLE,
    PERMANENT_FLAGS,
    LAST_PRE_ROLL,
})
