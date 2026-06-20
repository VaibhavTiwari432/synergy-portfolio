"""v3 P1 — instrument-saturation detection (ADR-0010). OWNER: Chief Engineer.

tau is a SCORE threshold on [0,1], not an item count (§0). Detection is a
conjunctive guard on score + n_eff + confidence + (absence of a) standing flag
(§2). The tau table (§1) is frozen and pinned here so it cannot drift silently.
"""

from __future__ import annotations

import pytest

from contracts.schemas import Censored, Dimension, ScoreStatus
from src.aggregate import saturation as sat
from src.aggregate.gates import N_EFF_TAU
from src.aggregate.saturation import (
    SATURATION_CONF_FLOOR,
    SATURATION_FLOOR_ENABLED,
    SATURATION_MIN_NEFF,
    TAU_CEILING,
    saturation_for,
)

# good = clears every clause except the score test
_GOOD_NEFF = SATURATION_MIN_NEFF + 1.0
_GOOD_CONF = 0.99


# ── §1 pin test: the frozen tau table, exactly ──────────────────────────────


def test_tau_ceiling_table_is_frozen_exactly():
    assert TAU_CEILING == {
        Dimension.AL: 0.95,
        Dimension.PR: 0.95,
        Dimension.EC: 0.97,
        Dimension.ES: 0.97,
        Dimension.CS: 0.93,
        Dimension.CD: 0.95,
        Dimension.AUI: 0.95,
        Dimension.CA: 0.95,
    }
    # every one of the 8 frozen dimensions carries a tau
    assert set(TAU_CEILING) == set(Dimension)


def test_min_neff_at_least_scorability_tau():
    # §6 Q2: a saturated dim must clear the n_eff gate by construction.
    assert SATURATION_MIN_NEFF >= N_EFF_TAU


# ── §0/§2 boundary: at tau → saturated, below → not (per dimension) ─────────


@pytest.mark.parametrize("dim", list(Dimension))
def test_at_tau_saturates_below_does_not(dim: Dimension):
    tau = TAU_CEILING[dim]

    at = saturation_for(dim, tau, _GOOD_NEFF, _GOOD_CONF, flags=[])
    assert at == Censored(direction="high", bound=tau)

    # one ulp-ish below the registered ceiling → not saturated
    below = saturation_for(dim, tau - 0.01, _GOOD_NEFF, _GOOD_CONF, flags=[])
    assert below is None

    # comfortably above the ceiling still reports the BOUND (tau), never the score
    above = saturation_for(dim, min(1.0, tau + 0.02), _GOOD_NEFF, _GOOD_CONF, flags=[])
    assert above is not None and above.bound == tau


# ── §2 conjunctive guard: each clause independently blocks ──────────────────


def test_low_n_eff_blocks_saturation():
    out = saturation_for(
        Dimension.CS, 0.99, SATURATION_MIN_NEFF - 0.5, _GOOD_CONF, flags=[]
    )
    assert out is None


def test_low_confidence_blocks_saturation():
    out = saturation_for(
        Dimension.CS, 0.99, _GOOD_NEFF, SATURATION_CONF_FLOOR - 0.01, flags=[]
    )
    assert out is None


def test_standing_flag_blocks_saturation():
    # any standing quality/calibration flag means a high score is not a trusted
    # ceiling — block. This is the mechanism by which EC never saturates today.
    out = saturation_for(
        Dimension.EC, 0.99, _GOOD_NEFF, _GOOD_CONF,
        flags=["ec_low_calibration_confidence"],
    )
    assert out is None


def test_none_score_never_saturates():
    assert saturation_for(Dimension.AL, None, _GOOD_NEFF, _GOOD_CONF, flags=[]) is None


# ── §3 floor detection is structurally present but operationally off ────────


def test_floor_detection_disabled_by_default():
    assert SATURATION_FLOOR_ENABLED is False
    # even a 0.0 score never produces a low-direction bound while the flag is off
    assert saturation_for(Dimension.AL, 0.0, _GOOD_NEFF, _GOOD_CONF, flags=[]) is None


# ── direction renders correctly (high → "≥ X") through the real renderer ────


def test_high_direction_renders_as_ge():
    from contracts.schemas import DimensionScore, Rung
    from src.claims.report import generate_report
    from tests.unit.test_claims import _report_inputs

    tau = TAU_CEILING[Dimension.CS]
    censored = saturation_for(Dimension.CS, 0.99, _GOOD_NEFF, _GOOD_CONF, flags=[])
    assert censored is not None and censored.direction == "high"

    profile = {
        d: DimensionScore(dim=d, status=ScoreStatus.OK, value=0.5, rung=Rung.MEASURABLE)
        for d in Dimension
    }
    profile[Dimension.CS] = DimensionScore(
        dim=Dimension.CS,
        status=ScoreStatus.MEASUREMENT_SATURATED,
        censored=censored,
        rung=Rung.MEASURABLE,
    )
    inputs = _report_inputs()
    inputs["profile"] = profile
    line = " ".join(generate_report(**inputs).observed)
    assert f"CS ≥ {tau:.2f}" in line and "instrument saturated" in line


# ── never-emit-before-frozen: empty constants ⇒ zero emissions ──────────────


def test_empty_tau_table_emits_nothing(monkeypatch):
    monkeypatch.setattr(sat, "TAU_CEILING", {})
    for dim in Dimension:
        # a maximal, fully-qualified score still produces no bound when no tau
        # is registered for the dimension.
        assert sat.saturation_for(dim, 1.0, _GOOD_NEFF, _GOOD_CONF, flags=[]) is None
