"""Unit tests for gates + soft non-compensatory composite. OWNER: Chief Engineer."""

from __future__ import annotations

import pytest

from contracts.schemas import (
    Censored,
    ConfidenceInterval,
    Dimension,
    DimensionScore,
    Rung,
    ScoreStatus,
    StateValidity,
)
from src.aggregate.gates import gate_dimension, scorability_gate, state_validity_gate
from src.aggregate.softmin import PILLARS, compute_composite

CLEAN = StateValidity()
COMPROMISED = StateValidity(state_compromised=True, m_t_collapse=True)


def _ok(dim: Dimension, value: float, n_eff: float = 5.0, width: float = 0.1) -> DimensionScore:
    return DimensionScore(
        dim=dim, status=ScoreStatus.OK, value=value,
        ci=ConfidenceInterval(low=max(0.0, value - width), high=min(1.0, value + width)),
        n_eff=n_eff, rung=Rung.MEASURABLE,
    )


def _absent(dim: Dimension, status: ScoreStatus = ScoreStatus.NOT_APPLICABLE) -> DimensionScore:
    return DimensionScore(dim=dim, status=status, rung=Rung.MEASURABLE)


def _saturated(dim: Dimension, bound: float = 0.95) -> DimensionScore:
    """A topped-out dimension: status MEASUREMENT_SATURATED, value None, a high
    censored bound (the form saturation.py emits for a ≥ tau strong score)."""
    return DimensionScore(
        dim=dim, status=ScoreStatus.MEASUREMENT_SATURATED, value=None,
        censored=Censored(direction="high", bound=bound), n_eff=6.0, rung=Rung.MEASURABLE,
    )


def _profile(value: float = 0.6, **overrides: DimensionScore) -> dict[Dimension, DimensionScore]:
    profile = {dim: _ok(dim, value) for dim in Dimension}
    profile.update(overrides)
    return profile


# ── gates ────────────────────────────────────────────────────────────────────


def test_n_eff_gate_demotes_undersampled_and_keeps_raw_counts():
    score = DimensionScore(
        dim=Dimension.EC, status=ScoreStatus.OK, value=0.7,
        ci=ConfidenceInterval(low=0.6, high=0.8), n_eff=0.5,
        raw_counts={"fired": 1, "opportunities": 1}, rung=Rung.MEASURABLE,
    )
    gated = gate_dimension(score, tau=1.0)
    assert gated.status == ScoreStatus.INSUFFICIENT_SAMPLE
    assert gated.value is None and gated.ci is None
    assert gated.raw_counts == {"fired": 1, "opportunities": 1}  # retained
    assert "n_eff" in (gated.status_reason or "")


def test_n_eff_gate_passes_sufficient_samples_and_non_ok():
    ok = _ok(Dimension.AL, 0.5, n_eff=3.0)
    assert gate_dimension(ok) == ok
    na = _absent(Dimension.ES)
    assert gate_dimension(na) == na


def test_scorability_gate_needs_four_valid_dims():
    profile = _profile()
    assert scorability_gate(profile) is True
    dims = list(Dimension)
    for dim in dims[:5]:  # leave only 3 OK
        profile[dim] = _absent(dim, ScoreStatus.INSUFFICIENT_SAMPLE)
    assert scorability_gate(profile) is False


def test_saturated_dims_count_toward_scorability():
    # a topped-out strong session: 5 dims saturate, 3 stay OK. Saturated dims
    # carry usable signal (a censored ceiling), so the gate must still pass —
    # collapsing the strongest sessions to INSUFFICIENT_SAMPLE was the bug.
    profile = _profile(0.9)
    dims = list(Dimension)
    for dim in dims[:5]:
        profile[dim] = _saturated(dim)
    assert scorability_gate(profile) is True


def test_strong_topped_out_session_keeps_its_composite():
    # the reported collapse: ≥95 across most dims drove the overall index to
    # "—" (INSUFFICIENT_SAMPLE). It must now produce a real, high composite.
    profile = _profile(0.92)
    dims = list(Dimension)
    for dim in dims[:5]:
        profile[dim] = _saturated(dim, bound=0.95)
    comp = compute_composite(profile, CLEAN)
    assert comp.status == ScoreStatus.OK
    assert comp.value is not None and comp.value >= 0.9
    assert comp.ci is not None  # the 3 remaining OK dims still supply a CI


def test_state_validity_gate():
    assert state_validity_gate(CLEAN) is True
    assert state_validity_gate(COMPROMISED) is False


# ── composite ────────────────────────────────────────────────────────────────


def test_uniform_profile_composite_near_value_with_ci():
    comp = compute_composite(_profile(0.6), CLEAN)
    assert comp.status == ScoreStatus.OK
    assert comp.value == pytest.approx(0.6, abs=1e-6)
    assert comp.ci is not None and comp.ci.low < comp.value < comp.ci.high
    assert comp.gates_passed == {"scorability": True, "state_validity": True, "fluent_incompetence": True}
    assert comp.state_compromised_caveat is False


def test_hollow_pillar_cannot_be_averaged_away():
    # both manage-pillar dims hollow → soft-min drags composite well below the
    # arithmetic mean of the pillar values
    profile = _profile(0.8, **{
        Dimension.EC: _ok(Dimension.EC, 0.05),
        Dimension.ES: _ok(Dimension.ES, 0.05),
    })
    comp = compute_composite(profile, CLEAN)
    pillar_values = [0.8, 0.05, 0.8, 0.8]
    arithmetic = sum(pillar_values) / 4
    assert comp.value < arithmetic - 0.2
    assert comp.value < 0.2  # dominated by the hollow pillar


def test_one_insufficient_dimension_does_not_erase_the_rest():
    profile = _profile(0.6, **{Dimension.ES: _absent(Dimension.ES)})
    comp = compute_composite(profile, CLEAN)
    assert comp.status == ScoreStatus.OK
    # manage pillar rests on EC alone; all pillar values still 0.6
    assert comp.value == pytest.approx(0.6, abs=1e-6)


def test_scorability_failure_yields_no_bare_value():
    profile = {dim: _absent(dim, ScoreStatus.INSUFFICIENT_SAMPLE) for dim in Dimension}
    for dim in (Dimension.AL, Dimension.PR, Dimension.EC):
        profile[dim] = _ok(dim, 0.7)
    comp = compute_composite(profile, CLEAN)
    assert comp.status == ScoreStatus.INSUFFICIENT_SAMPLE
    assert comp.value is None and comp.ci is None
    assert comp.gates_passed["scorability"] is False


def test_state_gate_failure_caveats_but_never_scales():
    clean = compute_composite(_profile(0.6), CLEAN)
    compromised = compute_composite(_profile(0.6), COMPROMISED)
    assert compromised.value == clean.value  # no multiplier (#2)
    assert compromised.state_compromised_caveat is True
    assert compromised.gates_passed["state_validity"] is False


def test_ec_cs_weighting_inside_pillars():
    # EC (1.5×) low vs ES (1.0×) low must differ within the manage pillar
    low_ec = compute_composite(_profile(0.8, **{Dimension.EC: _ok(Dimension.EC, 0.2)}), CLEAN)
    low_es = compute_composite(_profile(0.8, **{Dimension.ES: _ok(Dimension.ES, 0.2)}), CLEAN)
    assert low_ec.value < low_es.value  # the weighted dim hurts more


def test_pillar_map_covers_all_eight_dimensions_once():
    seen = [d for dims in PILLARS.values() for d in dims]
    assert sorted(d.value for d in seen) == sorted(d.value for d in Dimension)


def test_within_pillar_non_compensation_d1():
    """D1: a hollow dim cannot hide behind a strong pillar-mate (within-pillar power mean)."""
    # create pillar: CD=0.55, CS=0.92 (CS is 1.5× weighted)
    profile = _profile(0.92)
    profile[Dimension.CD] = _ok(Dimension.CD, 0.55)
    comp = compute_composite(profile, CLEAN)
    assert comp.value is not None
    # old arithmetic within-pillar gave ~0.875; power-mean-within gives ~0.848 — material drop
    assert comp.value <= 0.86
