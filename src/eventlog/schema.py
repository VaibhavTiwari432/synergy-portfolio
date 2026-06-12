"""
src/eventlog/schema.py — the universal event log container. OWNER: Chief Engineer.

Append-only, ordered, provenance-tagged (spec §5.9a). The log holds ONLY the
frozen taxonomy (contracts.event_taxonomy.ALL_EVENT_TYPES). Transcript turns are
NOT events — they live in CanonicalSession; events reference them via
payload_ref ("turn:N"). Order carries what rates destroy: t is the dense
ordinal append position, enforced here.
"""

from __future__ import annotations

from typing import Iterator

from contracts.event_taxonomy import ALL_EVENT_TYPES
from contracts.schemas import Event


class AppendOnlyViolation(Exception):
    """Raised on any attempt to break the append-only / dense-ordering invariant."""


class EventLog:
    """In-memory event log for one session.

    Invariants (enforced, property-tested):
      - append-only: no removal, no replacement, no reordering API exists
      - dense ordinal time: events[i].t == i for all i
      - taxonomy-closed: only the 7 frozen event types are accepted
    """

    __slots__ = ("_session_id", "_events")

    def __init__(self, session_id: str) -> None:
        self._session_id = session_id
        self._events: list[Event] = []

    @property
    def session_id(self) -> str:
        return self._session_id

    @property
    def events(self) -> tuple[Event, ...]:
        """Immutable view. Leaves read via eventlog.queries, never this class."""
        return tuple(self._events)

    def append(self, event: Event) -> int:
        """Append one event. event.t must equal the next ordinal position.

        Returns the assigned ordinal. Raises AppendOnlyViolation otherwise —
        a writer must never renumber an event silently.
        """
        if event.event_type not in ALL_EVENT_TYPES:
            raise AppendOnlyViolation(
                f"event_type {event.event_type!r} is outside the frozen taxonomy"
            )
        expected = len(self._events)
        if event.t != expected:
            raise AppendOnlyViolation(
                f"append-only ordering violated: expected t={expected}, got t={event.t}"
            )
        self._events.append(event)
        return event.t

    def __len__(self) -> int:
        return len(self._events)

    def __iter__(self) -> Iterator[Event]:
        return iter(self.events)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, EventLog):
            return NotImplemented
        return self._session_id == other._session_id and self._events == other._events

    def __repr__(self) -> str:  # pragma: no cover
        return f"EventLog(session_id={self._session_id!r}, n={len(self._events)})"
