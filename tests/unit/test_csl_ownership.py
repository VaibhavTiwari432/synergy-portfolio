"""Phase 2.3 acceptance — ownership normalization + CSPC precision.

Acceptance (v3.2 §2.3): 7 results, each OK result with a CI; low n_eff →
INSUFFICIENT_SAMPLE; applicability never arose → NOT_APPLICABLE; never a bare
percentage without denominator + CI. Plus SPEC_ownership: CSPC enters as
precision only, saturated levels use MEASUREMENT_SATURATED with censored bounds,
no session scalar.
"""

from __future__ import annotations

from contracts.schemas import ScoreStatus, StateValidity, StateVector
from csl.crosswalk import ACF_LEVELS
from csl.ownership import (
    STATE_CONDITIONED_FLAG,
    UNCERTIFIED_FLAG,
    CSPCState,
    compute_ownership,
)
from csl.projection import LevelEvidence, NeuronEvidence


def _ne(neuron_id, value, n_eff, turns=()):
    return NeuronEvidence(
        neuron_id=neuron_id, dimension=neuron_id.split("-")[0],
        control_value=value, applicable=True,
        opportunities=int(n_eff), n_eff=float(n_eff),
        evidence_turns=tuple(turns), source="deterministic",
    )


def _level(level, status, control, firings, n_eff=None):
    return LevelEvidence(
        level=level, label=f"{level}-label", status=status,
        control_strength=control,
        n_eff=n_eff if n_eff is not None else sum(f.n_eff for f in firings),
        applicable_count=len(firings), firings=tuple(firings),
    )


def _empty_cspc():
    return CSPCState.from_state([], StateValidity())


def test_returns_exactly_seven_levels():
    human = {"C3": _level("C3", ScoreStatus.OK, 0.8, [_ne("EC-01", 0.8, 3, (1,))])}
    result = compute_ownership(human, {"C3": 0.2}, _empty_cspc())
    assert tuple(result) == ACF_LEVELS
    assert len(result) == 7


def test_ok_level_has_ci_and_complementary_shares():
    human = {"C3": _level("C3", ScoreStatus.OK, 0.8, [_ne("EC-01", 0.8, 3, (1,))])}
    result = compute_ownership(human, {"C3": 0.2}, _empty_cspc())["C3"]

    assert result.status == ScoreStatus.OK
    assert result.ci is not None                       # never a bare percentage
    assert result.human_pct is not None and result.ai_pct is not None
    assert abs((result.human_pct + result.ai_pct) - 1.0) < 1e-9   # level-local contrast
    assert result.human_pct == 0.8 and result.ai_pct == 0.2
    assert UNCERTIFIED_FLAG in result.flags            # DESIGNED until ICC


def test_missing_human_level_is_not_applicable_even_if_ai_displayed():
    # AI displayed something but the human side never arose -> no honest contrast,
    # never a fabricated AI-100%.
    result = compute_ownership({}, {"C5": 0.7}, _empty_cspc())["C5"]
    assert result.status == ScoreStatus.NOT_APPLICABLE
    assert result.human_pct is None and result.ai_pct is None
    assert result.ci is None


def test_insufficient_sample_propagates_and_low_n_eff_flags():
    human = {
        "C3": _level("C3", ScoreStatus.INSUFFICIENT_SAMPLE, None,
                     [_ne("EC-01", 0.5, 1, (1,))]),
    }
    r = compute_ownership(human, {"C3": 0.2}, _empty_cspc())["C3"]
    assert r.status == ScoreStatus.INSUFFICIENT_SAMPLE
    assert r.human_pct is None and r.ci is None

    # OK status but n_eff under the configured floor also -> INSUFFICIENT_SAMPLE
    human2 = {"C3": _level("C3", ScoreStatus.OK, 0.5, [_ne("EC-01", 0.5, 1, (1,))])}
    r2 = compute_ownership(human2, {"C3": 0.2}, _empty_cspc(), min_n_eff=2.0)["C3"]
    assert r2.status == ScoreStatus.INSUFFICIENT_SAMPLE


def test_zero_denominator_is_insufficient_not_fifty_fifty():
    # level arose (human OK) but neither side displayed anything resolvable.
    human = {"C3": _level("C3", ScoreStatus.OK, 0.0, [_ne("EC-01", 0.0, 3, (1,))])}
    r = compute_ownership(human, {"C3": 0.0}, _empty_cspc())["C3"]
    assert r.status == ScoreStatus.INSUFFICIENT_SAMPLE
    assert r.human_pct is None


def test_cspc_precision_attenuates_via_pi_s():
    # contributing turn has degraded per-turn precision 0.5 -> pi_s(level) == 0.5.
    firing = _ne("EC-01", 1.0, 2, turns=(2,))
    human = {"C3": _level("C3", ScoreStatus.OK, 1.0, [firing])}
    strip = [StateVector(turn_index=2, precision=0.5)]
    cspc = CSPCState.from_state(strip, StateValidity())

    r = compute_ownership(human, {"C3": 0.0}, cspc)["C3"]
    assert r.pi_s == 0.5
    # human owns it all (AI displayed nothing) but precision is recorded
    assert r.human_pct == 1.0 and r.ai_pct == 0.0


def test_compromised_state_widens_ci_and_flags():
    firings = [_ne("EC-01", 1.0, 3, (1,)), _ne("EC-06", 0.0, 1, (1,))]
    human = {"C3": _level("C3", ScoreStatus.OK, 0.75, firings)}
    ai = {"C3": 0.25}

    calm = compute_ownership(human, ai, CSPCState.from_state([], StateValidity()))["C3"]
    compromised = compute_ownership(
        human, ai,
        CSPCState.from_state([], StateValidity(state_compromised=True)),
    )["C3"]

    assert STATE_CONDITIONED_FLAG not in calm.flags
    assert STATE_CONDITIONED_FLAG in compromised.flags
    assert compromised.ci.width >= calm.ci.width


def test_saturated_level_reports_censored_high_bound():
    # all applicable human evidence at the top bound -> MEASUREMENT_SATURATED.
    firings = [_ne("EC-01", 1.0, 2, (1,)), _ne("EC-06", 1.0, 2, (2,))]
    human = {"C3": _level("C3", ScoreStatus.OK, 1.0, firings)}
    r = compute_ownership(human, {"C3": 0.0}, _empty_cspc())["C3"]

    assert r.status == ScoreStatus.MEASUREMENT_SATURATED
    assert r.censored is not None and r.censored.direction == "high"
    assert r.human_pct is None and r.ci is None


def test_bootstrap_ci_has_width_with_varied_firings():
    firings = [_ne("EC-01", 1.0, 3, (1,)), _ne("EC-06", 0.0, 1, (1,))]
    human = {"C3": _level("C3", ScoreStatus.OK, 0.75, firings)}
    r = compute_ownership(human, {"C3": 0.25}, _empty_cspc())["C3"]
    assert r.ci.width > 0.0
    assert r.ci.low <= r.human_pct <= r.ci.high


def test_deterministic_across_calls():
    firings = [_ne("EC-01", 1.0, 3, (1,)), _ne("EC-06", 0.2, 2, (2,))]
    human = {"C3": _level("C3", ScoreStatus.OK, 0.68, firings)}
    a = compute_ownership(human, {"C3": 0.3}, _empty_cspc())["C3"]
    b = compute_ownership(human, {"C3": 0.3}, _empty_cspc())["C3"]
    assert a == b


def test_no_session_scalar_emitted():
    human = {"C3": _level("C3", ScoreStatus.OK, 0.8, [_ne("EC-01", 0.8, 3, (1,))])}
    result = compute_ownership(human, {"C3": 0.2}, _empty_cspc())
    assert set(result) == set(ACF_LEVELS)
    assert "session" not in result and "overall" not in result
