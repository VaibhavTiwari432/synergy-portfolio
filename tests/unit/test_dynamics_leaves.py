"""Unit tests for transitions (5 frozen metrics) + regime overlay (leaves)."""

from __future__ import annotations

import pytest

from contracts.event_taxonomy import MIN_EVENTS_PER_CELL
from contracts.schemas import (
    Actor,
    Event,
    EventType,
    IntentTag,
    Provenance,
    RegimeLabel,
    TurnTags,
)
from src.dynamics.overlay import regime_overlay
from src.dynamics.transitions import compute_transitions


def _event(t: int, event_type: EventType, turn_index: int) -> Event:
    return Event(t=t, event_type=event_type, actor=Actor.SYSTEM, confidence=0.9,
                 provenance=Provenance.DISPLAYED, payload_ref=f"turn:{turn_index}")


def _tags(mapping: dict[int, list[IntentTag]]) -> list[TurnTags]:
    return [TurnTags(turn_index=i, tags=tags) for i, tags in sorted(mapping.items())]


# ── transitions ──────────────────────────────────────────────────────────────


def test_verify_after_error_gated_below_min_events():
    events = [_event(0, EventType.E_ERR, 0)]
    tags = _tags({0: [], 2: [IntentTag.VERIFY]})
    tm = compute_transitions(events, tags)
    assert tm.verify_after_error_rate.value is None
    assert tm.verify_after_error_rate.n_events == 1


def test_verify_after_error_rate_when_gate_passes():
    events = [_event(i, EventType.E_ERR, 4 * i) for i in range(MIN_EVENTS_PER_CELL)]
    tag_map: dict[int, list[IntentTag]] = {}
    for i in range(MIN_EVENTS_PER_CELL):
        tag_map[4 * i] = []
        tag_map[4 * i + 2] = [IntentTag.VERIFY] if i < 2 else [IntentTag.ACCEPT_FLAT]
    tm = compute_transitions(events, _tags(tag_map))
    assert tm.verify_after_error_rate.n_events == MIN_EVENTS_PER_CELL
    assert tm.verify_after_error_rate.value == pytest.approx(2 / 3)


def test_constraint_before_generation():
    tags = _tags({
        0: [IntentTag.SCAFFOLD],                      # constraints set up…
        2: [IntentTag.DELEGATE],                      # …then generation: constrained
        4: [IntentTag.DELEGATE],                      # bare generation
        6: [IntentTag.DELEGATE, IntentTag.SCAFFOLD],  # same-turn constraint
    })
    tm = compute_transitions([], tags)
    assert tm.constraint_before_generation_rate.n_events == 3
    assert tm.constraint_before_generation_rate.value == pytest.approx(2 / 3)


def test_prediction_before_answer_is_permanently_gated_at_tier1():
    tm = compute_transitions([], _tags({0: [IntentTag.EXTRACT]}))
    assert tm.prediction_before_answer_rate.value is None
    assert tm.prediction_before_answer_rate.n_events == 0


def test_accept_run_max_and_mean():
    tags = _tags({
        0: [IntentTag.EXTRACT],
        2: [IntentTag.ACCEPT_FLAT],
        4: [IntentTag.ACCEPT_FLAT],
        6: [IntentTag.ACCEPT_FLAT],
        8: [IntentTag.VERIFY],
        10: [IntentTag.ACCEPT_FLAT],
    })
    tm = compute_transitions([], tags)
    assert tm.accept_run_max == 3
    assert tm.accept_run_mean == pytest.approx(2.0)  # runs: 3 and 1


def test_accept_run_none_without_human_turns():
    tm = compute_transitions([], [])
    assert tm.accept_run_max is None and tm.accept_run_mean is None


def test_revision_after_output_rate():
    tags = _tags({
        0: [IntentTag.DELEGATE],
        2: [IntentTag.OVERRIDE],
        4: [IntentTag.ACCEPT_FLAT],
        6: [IntentTag.OVERRIDE],
    })
    tm = compute_transitions([], tags)
    assert tm.revision_after_output_rate.n_events == 3  # turns after the first
    assert tm.revision_after_output_rate.value == pytest.approx(2 / 3)


def test_no_latent_variables_in_transitions():
    import inspect
    import io
    import tokenize

    import src.dynamics.transitions as module

    source = inspect.getsource(module)
    names = {
        tok.string.lower()
        for tok in tokenize.generate_tokens(io.StringIO(source).readline)
        if tok.type == tokenize.NAME
    }
    for forbidden in ("latent", "hidden", "hgf", "kalman"):
        assert forbidden not in names


# ── overlay ──────────────────────────────────────────────────────────────────


def test_overlay_rules_and_occupancy():
    tags = _tags({
        0: [IntentTag.SCAFFOLD],       # generative
        2: [IntentTag.VERIFY],         # verification
        4: [IntentTag.EXTRACT],        # extractive
        6: [IntentTag.ACCEPT_FLAT],    # accept run (with next)
        8: [IntentTag.ACCEPT_FLAT],
        10: [],                        # drift
    })
    result = regime_overlay([], tags)
    assert result.strip == [
        RegimeLabel.GENERATIVE, RegimeLabel.VERIFICATION, RegimeLabel.EXTRACTIVE,
        RegimeLabel.ACCEPT_RUN, RegimeLabel.ACCEPT_RUN, RegimeLabel.DRIFT,
    ]
    assert sum(result.occupancy.values()) == pytest.approx(1.0)
    assert result.occupancy[RegimeLabel.ACCEPT_RUN] == pytest.approx(2 / 6)
    assert result.run_lengths[RegimeLabel.ACCEPT_RUN] == [2]


def test_lone_accept_flat_is_extractive_not_accept_run():
    tags = _tags({0: [IntentTag.EXTRACT], 2: [IntentTag.ACCEPT_FLAT], 4: [IntentTag.VERIFY]})
    result = regime_overlay([], tags)
    assert result.strip[1] == RegimeLabel.EXTRACTIVE
    assert RegimeLabel.ACCEPT_RUN not in result.strip


def test_overlay_empty_session():
    result = regime_overlay([], [])
    assert result.strip == [] and result.occupancy == {}


def test_overlay_emits_only_regime_labels_and_never_the_cspc_word():
    import inspect

    import src.dynamics.overlay as module

    # the file itself must not contain the CSPC construct's name at all —
    # this is the CI grep made local (non-negotiable #5)
    assert "surrender" not in inspect.getsource(module).lower()

    tags = _tags({0: [IntentTag.ACCEPT_FLAT], 2: [IntentTag.ACCEPT_FLAT],
                  4: [IntentTag.ACCEPT_FLAT], 6: [IntentTag.ACCEPT_FLAT]})
    result = regime_overlay([], tags)
    assert all(isinstance(label, RegimeLabel) for label in result.strip)
    assert result.strip == [RegimeLabel.ACCEPT_RUN] * 4
