"""Property tests for the event log (brief §5 Stage 1 CE: ordered, append-only).
OWNER: Chief Engineer."""

from __future__ import annotations

import random

import pytest

from contracts.schemas import (
    Actor,
    CanonicalSession,
    Event,
    EventType,
    PartnerModel,
    Provenance,
    Turn,
)
from src.eventlog import queries
from src.eventlog.schema import AppendOnlyViolation, EventLog
from src.eventlog.writer import append_event, append_neuron_firing, new_log

SEED = 20260612


def _session(n_turns: int = 6) -> CanonicalSession:
    turns = [
        Turn(index=i, role="human" if i % 2 == 0 else "ai", text=f"turn {i}")
        for i in range(n_turns)
    ]
    return CanonicalSession(
        session_id="prop-1",
        source="plaintext",
        partner_model=PartnerModel(family="openai"),
        turns=turns,
    )


def _random_appends(log: EventLog, n: int, seed: int = SEED) -> None:
    rng = random.Random(seed)
    types = [t for t in EventType]
    for _ in range(n):
        append_event(
            log,
            event_type=rng.choice(types),
            actor=rng.choice(list(Actor)),
            confidence=rng.random(),
            provenance=rng.choice(list(Provenance)),
            turn_index=rng.randrange(0, 6),
        )


# ── Ordering preserved ───────────────────────────────────────────────────────


def test_ordinals_are_dense_and_ordered_after_many_appends():
    log = new_log(_session())
    _random_appends(log, 200)
    assert [e.t for e in log.events] == list(range(200))


def test_append_rejects_wrong_ordinal():
    log = new_log(_session())
    good = Event(t=0, event_type=EventType.E_ERR, actor=Actor.SYSTEM,
                 confidence=1.0, provenance=Provenance.DISPLAYED)
    log.append(good)
    for bad_t in (0, 2, 5):
        bad = Event(t=bad_t, event_type=EventType.E_ERR, actor=Actor.SYSTEM,
                    confidence=1.0, provenance=Provenance.DISPLAYED)
        with pytest.raises(AppendOnlyViolation):
            log.append(bad)
    assert len(log) == 1  # nothing slipped in


# ── Append-only invariant ────────────────────────────────────────────────────


def test_no_mutation_surface_exists():
    log = new_log(_session())
    _random_appends(log, 10)
    for forbidden in ("remove", "pop", "clear", "insert", "replace", "delete", "sort"):
        assert not hasattr(log, forbidden)


def test_events_view_is_immutable():
    log = new_log(_session())
    _random_appends(log, 5)
    view = log.events
    assert isinstance(view, tuple)
    # tampering with the returned view must not affect the log
    view2 = log.events
    assert view == view2 and len(log) == 5
    # Event records themselves are frozen pydantic models
    with pytest.raises(Exception):
        log.events[0].confidence = 0.0  # type: ignore[misc]


# ── Idempotent ingestion ─────────────────────────────────────────────────────


def test_same_session_same_detections_produce_identical_logs():
    a, b = new_log(_session()), new_log(_session())
    _random_appends(a, 50, seed=SEED)
    _random_appends(b, 50, seed=SEED)
    assert a == b
    assert a.events == b.events


def test_new_log_is_empty_and_bound_to_session():
    log = new_log(_session())
    assert len(log) == 0
    assert log.session_id == "prop-1"


# ── Queries (the leaf read surface) ──────────────────────────────────────────


def test_queries_partition_trigger_vs_nfire():
    log = new_log(_session())
    _random_appends(log, 100)
    append_neuron_firing(log, neuron_id="EC-01", strength=0.7, turn_index=2,
                         provenance=Provenance.DISPLAYED)
    trig = queries.trigger_events(log)
    fires = queries.neuron_firings(log)
    assert len(trig) + len(fires) == len(log)
    assert all(e.event_type != EventType.N_FIRE for e in trig)
    assert all(e.event_type == EventType.N_FIRE for e in fires)


def test_turn_of_parses_canonical_refs():
    log = new_log(_session())
    e = append_event(log, event_type=EventType.E_FRICTION, actor=Actor.SYSTEM,
                     confidence=0.8, provenance=Provenance.IMPLIED, turn_index=4)
    assert queries.turn_of(e) == 4
    assert queries.events_for_turn(log, 4) == (e,)
    assert queries.events_for_turn(log, 3) == ()
    assert queries.events_after_turn(log, 3) == (e,)
    assert queries.events_after_turn(log, 4) == ()


def test_count_by_type_sums_to_len():
    log = new_log(_session())
    _random_appends(log, 64)
    counts = queries.count_by_type(log)
    assert sum(counts.values()) == 64
