"""Unit tests for E→R reaction signatures + reliability map scaffold.
OWNER: Chief Engineer."""

from __future__ import annotations

import pytest

from contracts.event_taxonomy import MIN_EVENTS_PER_CELL
from contracts.schemas import (
    Actor,
    CellGatedProb,
    Event,
    EventType,
    IntentTag,
    PartnerModel,
    Provenance,
    ResponseClass,
    TransitionMetrics,
    TurnTags,
)
from src.dynamics.reactions import classify_response, compute_reactions
from src.dynamics.reliability_map import ReliabilityMap


def _event(t: int, event_type: EventType, turn_index: int) -> Event:
    return Event(
        t=t, event_type=event_type, actor=Actor.SYSTEM, confidence=0.9,
        provenance=Provenance.DISPLAYED, payload_ref=f"turn:{turn_index}",
    )


def _tags(mapping: dict[int, list[IntentTag]]) -> list[TurnTags]:
    return [TurnTags(turn_index=i, tags=tags) for i, tags in sorted(mapping.items())]


def _metrics() -> TransitionMetrics:
    gated = CellGatedProb()
    return TransitionMetrics(
        verify_after_error_rate=gated, constraint_before_generation_rate=gated,
        prediction_before_answer_rate=gated, revision_after_output_rate=gated,
    )


def test_classify_response_priority():
    assert classify_response(frozenset({IntentTag.VERIFY, IntentTag.EXTRACT})) \
        == ResponseClass.VERIFY_CHALLENGE
    assert classify_response(frozenset({IntentTag.ACCEPT_FLAT})) == ResponseClass.ACCEPT_FLAT
    assert classify_response(frozenset()) is None


def test_sparse_cells_are_gated_na():
    # one friction event only — below MIN_EVENTS_PER_CELL
    events = [_event(0, EventType.E_FRICTION, 0)]
    tags = _tags({0: [], 2: [IntentTag.VERIFY]})
    result = compute_reactions(events, tags, _metrics())
    assert result.ftm.p_verify.value is None        # never a prob from 1 event
    assert result.ftm.p_verify.n_events == 1


def test_pooled_probabilities_when_gate_passes():
    # MIN_EVENTS_PER_CELL friction events, all answered with VERIFY
    events = [_event(i, EventType.E_FRICTION, 2 * i) for i in range(MIN_EVENTS_PER_CELL)]
    tag_map: dict[int, list[IntentTag]] = {}
    for i in range(MIN_EVENTS_PER_CELL):
        tag_map[2 * i] = []                       # the turn the event points at
        tag_map[2 * i + 2] = [IntentTag.VERIFY]   # hmm: next human turn
    # ensure a final response turn exists for the last event
    tag_map[2 * MIN_EVENTS_PER_CELL] = [IntentTag.VERIFY]
    result = compute_reactions(events, _tags(tag_map), _metrics())

    p_verify = result.ftm.p_verify
    assert p_verify.n_events == MIN_EVENTS_PER_CELL
    assert p_verify.value is not None
    # pooling: dominant but pulled toward uniform, never 1.0
    assert 0.4 < p_verify.value < 1.0
    # distribution over classes sums to 1
    row = result.pi[EventType.E_FRICTION]
    assert sum(c.value for c in row.values()) == pytest.approx(1.0)


def test_events_without_classifiable_response_are_not_observations():
    events = [_event(i, EventType.E_ERR, 2 * i) for i in range(4)]
    tags = _tags({i: [] for i in range(0, 12, 2)})  # nothing tagged → no responses
    result = compute_reactions(events, tags, _metrics())
    assert all(c.value is None for c in result.pi[EventType.E_ERR].values())
    assert result.pi[EventType.E_ERR][ResponseClass.VERIFY_CHALLENGE].n_events == 0


def test_no_latent_variables_in_module():
    """No-latent-variable audit: scans code IDENTIFIERS (not docs/comments,
    which legitimately explain the rule)."""
    import inspect
    import io
    import tokenize

    import src.dynamics.reactions as module

    source = inspect.getsource(module)
    names = {
        tok.string.lower()
        for tok in tokenize.generate_tokens(io.StringIO(source).readline)
        if tok.type == tokenize.NAME
    }
    for forbidden in ("latent", "hidden", "hgf", "kalman", "posterior_state"):
        assert forbidden not in names


# ── reliability map scaffold ─────────────────────────────────────────────────


def test_reliability_map_empty_lookup_is_none_not_a_default():
    rmap = ReliabilityMap()
    pm = PartnerModel(family="openai", model_id="gpt-x", era_key="2026-01")
    assert rmap.lookup(pm, "code") is None
    assert rmap.back_test("code") is None


def test_reliability_map_records_and_averages_outcomes():
    rmap = ReliabilityMap()
    pm = PartnerModel(family="openai", model_id="gpt-x", era_key="2026-01")
    rmap.record_outcome(pm, "code", verified_sound=True)
    rmap.record_outcome(pm, "code", verified_sound=True)
    rmap.record_outcome(pm, "code", verified_sound=False)
    entry = rmap.lookup(pm, "code")
    assert entry.n_verified == 3
    assert entry.reliability == pytest.approx(2 / 3)
    assert rmap.back_test("code") == {"2026-01": pytest.approx(2 / 3)}
