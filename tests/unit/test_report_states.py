"""Phase 0.3 — the four ScoreStatus states are never collapsed, and the new
MEASUREMENT_SATURATED censored-reporting state renders as "≥ X"/"≤ X" rather
than a point value (v3 §A3/V3, v3.2 §0.3). OWNER: Chief Engineer."""

from __future__ import annotations

import itertools

import pytest
from pydantic import ValidationError

from contracts.schemas import (
    Censored,
    Dimension,
    DimensionScore,
    Rung,
    ScoreStatus,
)
from src.claims.report import generate_report
from tests.unit.test_claims import _report_inputs


# ── schema: the censored bound is bound to the saturated state, one-to-one ──


def test_saturated_requires_censored_bound():
    with pytest.raises(ValidationError, match="requires a censored bound"):
        DimensionScore(
            dim=Dimension.EC, status=ScoreStatus.MEASUREMENT_SATURATED, rung=Rung.MEASURABLE
        )


def test_censored_bound_only_on_saturated():
    # reverse direction of the iff: a censored bound on ANY non-saturated status
    # is rejected — both the N/A case and (the silent-misrepresentation case) OK.
    with pytest.raises(ValidationError, match="only valid for MEASUREMENT_SATURATED"):
        DimensionScore(
            dim=Dimension.EC, status=ScoreStatus.NOT_APPLICABLE, rung=Rung.MEASURABLE,
            censored=Censored(direction="high", bound=0.95),
        )
    with pytest.raises(ValidationError, match="only valid for MEASUREMENT_SATURATED"):
        DimensionScore(
            dim=Dimension.EC, status=ScoreStatus.OK, value=0.5, rung=Rung.MEASURABLE,
            censored=Censored(direction="high", bound=0.95),
        )


def test_saturated_carries_no_point_value():
    # absent != zero, and saturated != max: the value stays None, the bound speaks.
    with pytest.raises(ValidationError, match="must not carry a value"):
        DimensionScore(
            dim=Dimension.EC, status=ScoreStatus.MEASUREMENT_SATURATED, value=1.0,
            rung=Rung.MEASURABLE, censored=Censored(direction="high", bound=0.95),
        )
    ok = DimensionScore(
        dim=Dimension.EC, status=ScoreStatus.MEASUREMENT_SATURATED, rung=Rung.MEASURABLE,
        censored=Censored(direction="high", bound=0.95),
    )
    assert ok.value is None and ok.censored.bound == 0.95


# ── report: the four states render as distinct, never-merged clauses ──


def _four_state_profile() -> dict[Dimension, DimensionScore]:
    profile = {
        dim: DimensionScore(dim=dim, status=ScoreStatus.OK, value=0.5, rung=Rung.MEASURABLE)
        for dim in Dimension
    }
    profile[Dimension.EC] = DimensionScore(
        dim=Dimension.EC, status=ScoreStatus.MEASUREMENT_SATURATED, rung=Rung.MEASURABLE,
        censored=Censored(direction="high", bound=0.95),
    )
    profile[Dimension.ES] = DimensionScore(
        dim=Dimension.ES, status=ScoreStatus.INSUFFICIENT_SAMPLE, rung=Rung.MEASURABLE,
    )
    profile[Dimension.CA] = DimensionScore(
        dim=Dimension.CA, status=ScoreStatus.NOT_APPLICABLE, rung=Rung.MEASURABLE,
    )
    return profile


def test_four_states_never_collapsed_in_report():
    inputs = _report_inputs()
    inputs["profile"] = _four_state_profile()
    report = generate_report(**inputs)
    line = " ".join(report.observed)

    # Each state has a distinct rendered marker. OK is counted; the three non-OK
    # states each name their dimensions under their own clause.
    markers = {
        ScoreStatus.OK: "scoreable evidence",
        ScoreStatus.MEASUREMENT_SATURATED: "instrument saturated",
        ScoreStatus.INSUFFICIENT_SAMPLE: "too few items to score",
        ScoreStatus.NOT_APPLICABLE: "no applicable evidence for",
    }
    # all four present (saturated also carries its censored "≥ 0.95"; the others
    # name their dimension)
    assert all(m in line for m in markers.values())
    assert "≥ 0.95" in line
    assert "ES" in line and "CA" in line

    # never-collapse: all six pairwise combinations of the four states render
    # to genuinely different markers — no two states share an output label.
    for a, b in itertools.combinations(markers.values(), 2):
        assert a != b
        assert a not in b and b not in a  # nor is one a substring of the other


def test_low_direction_saturation_renders_as_le():
    # a floor-saturated dimension must read "≤ X", not "≥ X" — high and low
    # saturation mean different things to a reader.
    inputs = _report_inputs()
    profile = {
        dim: DimensionScore(dim=dim, status=ScoreStatus.OK, value=0.5, rung=Rung.MEASURABLE)
        for dim in Dimension
    }
    profile[Dimension.EC] = DimensionScore(
        dim=Dimension.EC, status=ScoreStatus.MEASUREMENT_SATURATED, rung=Rung.MEASURABLE,
        censored=Censored(direction="low", bound=0.05),
    )
    inputs["profile"] = profile
    line = " ".join(generate_report(**inputs).observed)
    assert "≤ 0.05" in line and "≥" not in line
