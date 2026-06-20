"""
contracts/event_taxonomy.py — FROZEN. OWNER: Chief Engineer. v1.0.0

The six trigger events (spec §5.9b) plus N-FIRE. This taxonomy is frozen:
adding an event type is a contract change (CE-only, version bump, juniors re-read).
"""

from __future__ import annotations

from contracts.schemas import EventType

#: The six trigger events — the only events that open a reaction window.
TRIGGER_EVENTS: frozenset[EventType] = frozenset({
    EventType.E_ERR,
    EventType.E_CONTRA,
    EventType.E_CONFUSE,
    EventType.E_FRICTION,
    EventType.E_CORRECT,
    EventType.E_OVERREACH,
})

#: Neuron firings — logged for order preservation; never a reaction trigger.
NEURON_FIRING: EventType = EventType.N_FIRE

#: Everything a writer may append.
ALL_EVENT_TYPES: frozenset[EventType] = TRIGGER_EVENTS | {NEURON_FIRING}

#: Reaction window: classify the first substantive human response within
#: this many human turns after a trigger event (spec §5.9c).
REACTION_WINDOW_K: int = 3

#: Per-cell gate: an (event, response) probability is N/A unless the event
#: occurred at least this many times (spec §5.9c; brief §3.8).
MIN_EVENTS_PER_CELL: int = 3

__all__ = [
    "TRIGGER_EVENTS",
    "NEURON_FIRING",
    "ALL_EVENT_TYPES",
    "REACTION_WINDOW_K",
    "MIN_EVENTS_PER_CELL",
]
