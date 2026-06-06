"""
Tests for aggregator/dimension_aggregator.py — Stage 6 acceptance criteria.

Uses synthetic neuron score dicts (no LLM call needed) to assert:
  - Correct dimension means
  - EC × 1.5 and CS × 1.5 weighting applied
  - Scorability gate: dimensions with all-zero neurons return None
  - g_synergy is the coverage-weighted mean of scorable dimensions
  - Pillar scores average their member dimensions
"""

from __future__ import annotations

import pytest

from chat_classifier.aggregator.dimension_aggregator import (
    aggregate,
    _compute_dimension_scores,
    _compute_g_synergy,
    _compute_pillar_scores,
)
from chat_classifier.config import DIMENSION_WEIGHTS, PILLAR_MAP
from chat_classifier.schemas import SynergyReport


# ── Helpers ───────────────────────────────────────────────────────────────────

def _report() -> SynergyReport:
    return SynergyReport(session_id="test-0", transcript_turns=10)


def _neurons(dim: str, scores: list[float]) -> dict[str, float]:
    """Build a neuron dict for one dimension with the given per-neuron scores."""
    return {f"{dim}-{i+1:02d}": s for i, s in enumerate(scores)}


def _uniform(dims: dict[str, float], n_per_dim: int = 3) -> dict[str, float]:
    """Build neurons for multiple dims, each neuron at the given mean value."""
    out: dict[str, float] = {}
    for dim, val in dims.items():
        out.update(_neurons(dim, [val] * n_per_dim))
    return out


# ── Dimension mean ────────────────────────────────────────────────────────────

class TestDimensionMean:
    def test_uniform_al_scores(self):
        neurons = _neurons("AL", [0.6, 0.4, 0.8])
        result = _compute_dimension_scores(neurons)
        expected = (0.6 + 0.4 + 0.8) / 3 * DIMENSION_WEIGHTS["AL"]
        assert result["AL"] == pytest.approx(expected, abs=0.001)

    def test_unscored_dims_are_none(self):
        # Only AL neurons present — every other dim should be None
        neurons = _neurons("AL", [0.5, 0.5, 0.5])
        result = _compute_dimension_scores(neurons)
        for dim in ["PR", "EC", "ES", "CS", "CD", "AUI", "CA"]:
            assert result[dim] is None

    def test_all_dims_present_when_populated(self):
        neurons = _uniform({"AL": 0.5, "PR": 0.5, "EC": 0.5, "ES": 0.5,
                            "CS": 0.5, "CD": 0.5, "AUI": 0.5, "CA": 0.5})
        result = _compute_dimension_scores(neurons)
        assert all(v is not None for v in result.values())


# ── EC and CS weighting (1.5×) ────────────────────────────────────────────────

class TestDimensionWeighting:
    def test_ec_weighted_1_5x(self):
        neurons = _neurons("EC", [0.6, 0.6, 0.6])
        result = _compute_dimension_scores(neurons)
        assert result["EC"] == pytest.approx(0.6 * 1.5, abs=0.001)

    def test_cs_weighted_1_5x(self):
        neurons = _neurons("CS", [0.4, 0.4, 0.4])
        result = _compute_dimension_scores(neurons)
        assert result["CS"] == pytest.approx(0.4 * 1.5, abs=0.001)

    def test_al_weighted_1_0x(self):
        neurons = _neurons("AL", [0.5, 0.5, 0.5])
        result = _compute_dimension_scores(neurons)
        assert result["AL"] == pytest.approx(0.5 * 1.0, abs=0.001)

    def test_ec_score_higher_than_al_for_equal_raw(self):
        neurons = {**_neurons("EC", [0.5, 0.5]), **_neurons("AL", [0.5, 0.5])}
        result = _compute_dimension_scores(neurons)
        assert result["EC"] > result["AL"]


# ── Scorability gate (τ = 1) ──────────────────────────────────────────────────

class TestScorabilityGate:
    def test_all_zero_neurons_returns_none(self):
        neurons = _neurons("EC", [0.0, 0.0, 0.0])
        result = _compute_dimension_scores(neurons)
        assert result["EC"] is None

    def test_single_nonzero_neuron_passes_gate(self):
        neurons = _neurons("EC", [0.05, 0.0, 0.0])
        result = _compute_dimension_scores(neurons)
        assert result["EC"] is not None

    def test_all_nonzero_passes_gate(self):
        neurons = _neurons("AL", [0.3, 0.6, 0.9])
        result = _compute_dimension_scores(neurons)
        assert result["AL"] is not None

    def test_gate_does_not_cross_contaminate_dims(self):
        # AL passes, EC fails — they should not interfere
        neurons = {**_neurons("AL", [0.5, 0.5]), **_neurons("EC", [0.0, 0.0])}
        result = _compute_dimension_scores(neurons)
        assert result["AL"] is not None
        assert result["EC"] is None


# ── g_synergy ─────────────────────────────────────────────────────────────────

class TestGSynergy:
    def test_no_scorable_dims_returns_none(self):
        dim_scores = {d: None for d in ["AL", "PR", "EC", "ES", "CS", "CD", "AUI", "CA"]}
        assert _compute_g_synergy(dim_scores) is None

    def test_single_scorable_dim(self):
        dim_scores = {"AL": 0.5, "PR": None, "EC": None, "ES": None,
                      "CS": None, "CD": None, "AUI": None, "CA": None}
        # g_synergy = 0.5 / 1.0 weight = 0.5
        assert _compute_g_synergy(dim_scores) == pytest.approx(0.5, abs=0.001)

    def test_ec_and_cs_weighted_in_g_synergy(self):
        # EC=0.6 (weight 1.5) + CS=0.6 (weight 1.5), total weight = 3.0
        # g = (0.6 * 1.5 + 0.6 * 1.5) already baked into dim_scores
        # Wait: dim_scores already has weights baked in, so:
        # EC dim_score = 0.6 * 1.5 = 0.9, CS dim_score = 0.6 * 1.5 = 0.9
        # g = (0.9 + 0.9) / (1.5 + 1.5) = 1.8 / 3.0 = 0.6
        neurons = {**_neurons("EC", [0.6, 0.6]), **_neurons("CS", [0.6, 0.6])}
        dim_scores = _compute_dimension_scores(neurons)
        g = _compute_g_synergy(dim_scores)
        assert g == pytest.approx(0.6, abs=0.001)

    def test_g_synergy_excludes_none_dims(self):
        # AL=0.5, EC=None — only AL contributes
        dim_scores = {"AL": 0.5, "PR": None, "EC": None, "ES": None,
                      "CS": None, "CD": None, "AUI": None, "CA": None}
        g = _compute_g_synergy(dim_scores)
        assert g == pytest.approx(0.5, abs=0.001)


# ── Pillar scores ─────────────────────────────────────────────────────────────

class TestPillarScores:
    def test_engage_pillar_averages_al_pr(self):
        dim_scores = {"AL": 0.4, "PR": 0.6, "EC": None, "ES": None,
                      "CS": None, "CD": None, "AUI": None, "CA": None}
        pillars = _compute_pillar_scores(dim_scores)
        assert pillars["Engage"] == pytest.approx(0.5, abs=0.001)

    def test_pillar_none_when_all_dims_none(self):
        dim_scores = {d: None for d in ["AL", "PR", "EC", "ES", "CS", "CD", "AUI", "CA"]}
        pillars = _compute_pillar_scores(dim_scores)
        assert all(v is None for v in pillars.values())

    def test_partial_pillar_excludes_none_dims(self):
        # Manage pillar = EC + ES. EC=None, ES=0.8 → pillar=0.8
        dim_scores = {"AL": None, "PR": None, "EC": None, "ES": 0.8,
                      "CS": None, "CD": None, "AUI": None, "CA": None}
        pillars = _compute_pillar_scores(dim_scores)
        assert pillars["Manage"] == pytest.approx(0.8, abs=0.001)

    def test_all_four_pillars_present(self):
        dim_scores = {d: None for d in ["AL", "PR", "EC", "ES", "CS", "CD", "AUI", "CA"]}
        pillars = _compute_pillar_scores(dim_scores)
        assert set(pillars.keys()) == {"Engage", "Manage", "Create", "Design"}


# ── Full aggregate() round-trip ───────────────────────────────────────────────

class TestAggregateRoundTrip:
    def test_aggregate_populates_report_fields(self):
        neurons = _uniform({"AL": 0.5, "PR": 0.4, "EC": 0.6, "ES": 0.3,
                            "CS": 0.5, "CD": 0.4, "AUI": 0.6, "CA": 0.5})
        report = aggregate(neurons, _report())
        assert len(report.dimension_scores) == 8
        assert len(report.pillar_scores) == 4
        assert report.synergy_score_kappa is not None

    def test_aggregate_ec_score_reflects_1_5_weight(self):
        neurons = _uniform({"EC": 0.4})
        report = aggregate(neurons, _report())
        assert report.dimension_scores["EC"] == pytest.approx(0.4 * 1.5, abs=0.001)

    def test_aggregate_all_zero_ec_gives_none(self):
        neurons = _uniform({"AL": 0.5, "EC": 0.0})
        report = aggregate(neurons, _report())
        assert report.dimension_scores["EC"] is None
