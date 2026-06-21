"""
src/eventlog/queries.py — the ONLY read surface for leaf modules.
OWNER: Chief Engineer.

Pure functions over an EventLog (or a plain event sequence). Leaves receive
events through these helpers; they never touch EventLog internals or the writer.
"""

from __future__ import annotations

from collections import Counter
from typing import Iterable

from contracts.event_taxonomy import TRIGGER_EVENTS
from contracts.schemas import Event, EventType

EventSource = "EventLog | Sequence[Event]"  # documentation alias


def _events(source: Iterable[Event]) -> tuple[Event, ...]:
    return tuple(source)


def all_events(source: Iterable[Event]) -> tuple[Event, ...]:
    """Every event, in log order."""
    return _events(source)


def by_type(source: Iterable[Event], event_type: EventType) -> tuple[Event, ...]:
    return tuple(e for e in source if e.event_type == event_type)


def trigger_events(source: Iterable[Event]) -> tuple[Event, ...]:
    """The six reaction-window-opening events, in order (N-FIRE excluded)."""
    return tuple(e for e in source if e.event_type in TRIGGER_EVENTS)


def neuron_firings(source: Iterable[Event]) -> tuple[Event, ...]:
    return by_type(source, EventType.N_FIRE)


def count_by_type(source: Iterable[Event]) -> dict[EventType, int]:
    counts: Counter[EventType] = Counter(e.event_type for e in source)
    return dict(counts)


def turn_of(event: Event) -> int | None:
    """Parse the turn index out of a canonical 'turn:N[...]' payload_ref."""
    ref = event.payload_ref
    if ref is None or not ref.startswith("turn:"):
        return None
    head = ref[len("turn:"):].split("#", 1)[0]
    try:
        return int(head)
    except ValueError:
        return None


def events_for_turn(source: Iterable[Event], turn_index: int) -> tuple[Event, ...]:
    return tuple(e for e in source if turn_of(e) == turn_index)


def events_after_turn(source: Iterable[Event], turn_index: int) -> tuple[Event, ...]:
    """Events whose evidence turn is strictly after turn_index (window scans)."""
    return tuple(
        e for e in source if (t := turn_of(e)) is not None and t > turn_index
    )
