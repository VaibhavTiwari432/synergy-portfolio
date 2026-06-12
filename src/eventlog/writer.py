"""
src/eventlog/writer.py — the ONLY mutation surface for the event log.
OWNER: Chief Engineer. Leaves never import this module (INTERFACES.md import rules).

The writer assigns ordinals itself — callers describe the event, the writer
places it. This is what makes ingestion idempotent: the same session +
the same detector outputs, replayed, produce an identical log.
"""

from __future__ import annotations

from typing import Any

from contracts.schemas import Actor, CanonicalSession, Event, EventType, Provenance
from src.eventlog.schema import EventLog


def new_log(session: CanonicalSession) -> EventLog:
    """Materialize the (initially empty) event log for a canonical session.

    Turns are not events; the log fills as detectors run. Creating the log
    from the session — and only from the session — is what guarantees nothing
    downstream reads raw source formats.
    """
    return EventLog(session.session_id)


def append_event(
    log: EventLog,
    *,
    event_type: EventType,
    actor: Actor,
    confidence: float,
    provenance: Provenance,
    turn_index: int | None = None,
    payload_ref: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> Event:
    """Append one event, assigning the next ordinal.

    Exactly one of turn_index / payload_ref identifies the evidence; passing
    turn_index builds the canonical "turn:N" reference.
    """
    if turn_index is not None and payload_ref is not None:
        raise ValueError("pass turn_index or payload_ref, not both")
    if turn_index is not None:
        payload_ref = f"turn:{turn_index}"
    event = Event(
        t=len(log),
        event_type=event_type,
        actor=actor,
        payload_ref=payload_ref,
        confidence=confidence,
        provenance=provenance,
        metadata=metadata or {},
    )
    log.append(event)
    return event


def append_neuron_firing(
    log: EventLog,
    *,
    neuron_id: str,
    strength: float,
    turn_index: int,
    provenance: Provenance,
    confidence: float = 1.0,
) -> Event:
    """Convenience writer for N-FIRE events (extractor / judge firings)."""
    return append_event(
        log,
        event_type=EventType.N_FIRE,
        actor=Actor.SYSTEM,
        confidence=confidence,
        provenance=provenance,
        turn_index=turn_index,
        metadata={"neuron_id": neuron_id, "strength": strength},
    )
