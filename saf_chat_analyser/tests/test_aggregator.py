"""Tests for Stage 6 — dimension_aggregator."""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))

import pytest
from saf_chat_analyser.src.aggregator.dimension_aggregator import (
    DIMENSION_WEIGHTS,
    PILLARS,
    aggregate,
    _compute_composite,
    _compute_dimension_scores,
    _compute_pillar_scores,
)

_NEURONS_PATH = Path(__file__).parents[1] / "data" / "neurons_v6.json"


def _stub_scores(value: float = 0.5) -> dict[str, float]:
    with open(_NEURONS_PATH, encoding="utf-8") as f:
        neurons = json.load(f)
    return {nid: value for nid in neurons}


# ── Neuron count gate ─────────────────────────────────────────────────────────

def test_neurons_v6_has_107_entries():
    with open(_NEURONS_PATH, encoding="utf-8") as f:
        neurons = json.load(f)
    assert len(neurons) == 107


# ── Aggregation rule: min × product(gates) ───────────────────────────────────

def test_composite_equals_min_times_gate_product():
    scores = _stub_scores(0.5)
    result = aggregate(scores, verification_ratio=0.3)
    pillar_min = min(result["pillar_scores"].values())
    gate_product = math.prod(result["gates"].values())
    expected = round(pillar_min * gate_product, 4)
    assert result["collaboration_quality_kappa"] == expected


def test_min_rule_fires_not_mean():
    # Skew one dimension very low to confirm min dominates
    scores = _stub_scores(0.8)
    # Force CD neurons to near-zero
    for nid in list(scores):
        if nid.startswith("CD-"):
            scores[nid] = 0.1
    result = aggregate(scores, verification_ratio=0.3)
    # Create pillar (CS+CD) must be the minimum
    pillar_min_name = min(result["pillar_scores"], key=lambda k: result["pillar_scores"][k])
    assert pillar_min_name == "Create"
    # kappa < mean of pillars (mean would hide the gap)
    mean_pillars = sum(result["pillar_scores"].values()) / len(result["pillar_scores"])
    assert result["collaboration_quality_kappa"] < mean_pillars


# ── Gate logic ────────────────────────────────────────────────────────────────

def test_verification_gate_is_085_when_vr_zero():
    scores = _stub_scores(0.5)
    result = aggregate(scores, verification_ratio=0.0)
    assert result["gates"]["verification_gate"] == 0.85


def test_verification_gate_is_1_when_vr_positive():
    scores = _stub_scores(0.5)
    result = aggregate(scores, verification_ratio=0.2)
    assert result["gates"]["verification_gate"] == 1.0


def test_scorability_gate_fails_when_dimension_zero():
    scores = _stub_scores(0.5)
    for nid in list(scores):
        if nid.startswith("AL-"):
            scores[nid] = 0.0
    result = aggregate(scores, verification_ratio=0.2)
    assert result["gates"]["scorability_gate"] == 0.7


def test_state_validity_gate_always_one():
    scores = _stub_scores(0.5)
    result = aggregate(scores, verification_ratio=0.3)
    assert result["gates"]["state_validity_gate"] == 1.0


# ── Output structure ──────────────────────────────────────────────────────────

def test_aggregate_returns_required_keys():
    scores = _stub_scores(0.5)
    result = aggregate(scores, verification_ratio=0.3)
    assert "dimension_scores" in result
    assert "pillar_scores" in result
    assert "gates" in result
    assert "collaboration_quality_kappa" in result


def test_dimension_scores_has_all_8_dims():
    scores = _stub_scores(0.5)
    result = aggregate(scores, verification_ratio=0.3)
    assert set(result["dimension_scores"].keys()) == set(DIMENSION_WEIGHTS.keys())


def test_pillar_scores_has_4_pillars():
    scores = _stub_scores(0.5)
    result = aggregate(scores, verification_ratio=0.3)
    assert set(result["pillar_scores"].keys()) == set(PILLARS.keys())


def test_kappa_in_unit_interval():
    scores = _stub_scores(0.6)
    result = aggregate(scores, verification_ratio=0.3)
    assert 0.0 <= result["collaboration_quality_kappa"] <= 1.0
