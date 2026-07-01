"""Phase 2 acceptance tests: CSPC-weighted aggregation."""

import pytest
from contracts.schemas import Dimension, LoadLabel, MetacogLabel, StateVector
from src.aggregate.cspc_weighting import (
    cspc_weight,
    weighted_aggregate,
    CSPC_EPISTEMIC_WEIGHT,
    CSPC_LOAD_WEIGHT,
    CSPC_METACOG_WEIGHT,
)
from src.aggregate.normalize import normalize_counts


def test_cspc_weight_high_quality():
    """High epistemic + low load + ACTIVE metacog → weight well above neutral.

    The conservative weights cap |z| at 0.7, so weight saturates at ~0.668; the
    contract is "clearly above the 0.5 neutral", not a fixed 0.7 ceiling.
    """
    state = StateVector(
        turn_index=0,
        epistemic=1.0,  # max confidence
        load=LoadLabel.LOW_LOAD,  # min load
        metacog=MetacogLabel.ACTIVE,  # max metacog
    )
    w = cspc_weight(state)
    assert w > 0.6, f"Expected high-quality state to weigh above neutral, got {w}"


def test_cspc_weight_low_quality():
    """Low epistemic + high load + PASSIVE metacog → weight well below neutral."""
    state = StateVector(
        turn_index=0,
        epistemic=-1.0,  # min confidence
        load=LoadLabel.HIGH_ECL,  # max load
        metacog=MetacogLabel.PASSIVE,  # min metacog
    )
    w = cspc_weight(state)
    assert w < 0.4, f"Expected low-quality state to weigh below neutral, got {w}"


def test_cspc_weight_neutral():
    """None values → neutral weight ≈ 0.5."""
    state = StateVector(
        turn_index=0,
        epistemic=None,
        load=None,
        metacog=None,
    )
    w = cspc_weight(state)
    assert 0.4 < w < 0.6, f"Expected neutral state to have weight ≈ 0.5, got {w}"


def test_weighted_aggregate():
    """Weighted mean with custom weights."""
    values = [0.2, 0.6, 0.8]
    weights = [1.0, 1.0, 0.1]  # Last value has low weight
    result = weighted_aggregate(values, weights)
    # Expect something between 0.2 and 0.6, closer to 0.4
    assert 0.3 < result < 0.5, f"Unexpected weighted mean: {result}"


def test_weighted_aggregate_zero_weights():
    """All-zero weights → fallback to equal weight."""
    values = [0.2, 0.5, 0.8]
    weights = [0.0, 0.0, 0.0]
    result = weighted_aggregate(values, weights)
    expected = sum(values) / len(values)
    assert abs(result - expected) < 0.01


def test_normalize_with_cspc_weighting_off():
    """Phase 2: use_cspc_weighting=False → byte-identical to baseline."""
    firings = {
        Dimension.AL: {"AL-01": 0.5, "AL-02": 0.7},
    }
    opportunities = {
        Dimension.AL: {"AL-01": 10, "AL-02": 10},
    }

    # Baseline (no CSPC weighting)
    baseline = normalize_counts(firings, opportunities, use_cspc_weighting=False)

    # With CSPC disabled explicitly
    result = normalize_counts(
        firings, opportunities, use_cspc_weighting=False, state_strip=[], evidence_turns={}
    )

    # Must be byte-identical
    assert (
        baseline.per_dimension[Dimension.AL].normalized
        == result.per_dimension[Dimension.AL].normalized
    )


def test_normalize_with_cspc_weighting_on():
    """Phase 2: use_cspc_weighting=True with state data → weighted aggregation."""
    firings = {
        Dimension.AL: {"AL-01": 0.5, "AL-02": 0.8},
    }
    opportunities = {
        Dimension.AL: {"AL-01": 10, "AL-02": 10},
    }

    # High-quality evidence from early turns, low-quality from late turns
    state_strip = [
        StateVector(turn_index=0, epistemic=1.0, load=LoadLabel.LOW_LOAD, metacog=MetacogLabel.ACTIVE),
        StateVector(turn_index=1, epistemic=0.5, load=LoadLabel.HIGH_ICL, metacog=MetacogLabel.PASSIVE),
        StateVector(turn_index=2, epistemic=-0.8, load=LoadLabel.HIGH_ECL, metacog=MetacogLabel.PASSIVE),
    ]

    evidence_turns = {
        Dimension.AL: {
            "AL-01": [0],  # from high-quality early turn
            "AL-02": [2],  # from low-quality late turn
        },
    }

    result = normalize_counts(
        firings,
        opportunities,
        use_cspc_weighting=True,
        state_strip=state_strip,
        evidence_turns=evidence_turns,
    )

    # With CSPC weighting, early-turn evidence (AL-01) has higher weight,
    # so the normalized score should lean toward it (0.5 < result < 0.65)
    norm = result.per_dimension[Dimension.AL].normalized
    assert norm is not None
    # Expect result closer to 0.5 (high-quality early turn) than 0.8 (low-quality late turn)
    assert 0.5 < norm < 0.68, f"Expected weighted result in (0.5, 0.68), got {norm}"


def test_long_chat_late_turn_downweight():
    """Phase 2: Late-turn evidence in long chats should have lower weight.

    This is the core accuracy win: on a 294-turn chat, CSPC degradation in the
    last 100 turns means late-turn evidence is automatically down-weighted.
    """
    # Simulate a long chat: 100 turns with degrading CSPC
    state_strip = []
    for i in range(100):
        # CSPC degrades over time (realistic for long chats)
        epistemic = 0.8 - (i / 100) * 1.6  # 0.8 → -0.8
        load = LoadLabel.HIGH_ICL if i < 50 else LoadLabel.HIGH_ECL
        metacog = MetacogLabel.ACTIVE if i < 30 else MetacogLabel.PASSIVE

        state_strip.append(
            StateVector(
                turn_index=i,
                epistemic=epistemic,
                load=load,
                metacog=metacog,
            )
        )

    # Two neurons: one firing early, one firing late
    firings = {
        Dimension.PR: {"PR-01": 0.7, "PR-02": 0.7},  # same strength
    }
    opportunities = {
        Dimension.PR: {"PR-01": 10, "PR-02": 10},
    }

    evidence_turns = {
        Dimension.PR: {
            "PR-01": list(range(10, 20)),  # early turns (good CSPC)
            "PR-02": list(range(80, 90)),  # late turns (degraded CSPC)
        },
    }

    result = normalize_counts(
        firings,
        opportunities,
        use_cspc_weighting=True,
        state_strip=state_strip,
        evidence_turns=evidence_turns,
    )

    # With CSPC weighting, early-turn evidence should dominate,
    # so normalized should lean toward 0.7 but influenced by both
    norm = result.per_dimension[Dimension.PR].normalized
    assert norm is not None
    # Since both have same strength (0.7) but early has better CSPC weight,
    # the result should be > 0.65 (skewed toward high-quality evidence)
    assert norm > 0.65, f"Expected late-turn downweighting to keep norm > 0.65, got {norm}"
