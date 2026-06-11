"""Tests for Stage 8 — formatter."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))

import pytest
from saf_chat_analyser.src.metrics.composite_metrics import CompositeMetrics
from saf_chat_analyser.src.output.formatter import format_output


def _neuron_scores() -> dict[str, float]:
    neurons = json.load(
        open(Path(__file__).parents[1] / "data" / "neurons_v6.json", encoding="utf-8")
    )
    return {nid: 0.5 for nid in neurons}


def _metrics() -> CompositeMetrics:
    return CompositeMetrics(
        attribution_gap=0.2,
        verification_ratio=0.3,
        generative_query_ratio=0.5,
        actualization_depth=0.5,
        iteration_depth=0.3,
        semantic_distance_delta=0.4,
        vr_first_half=0.3,
        vr_second_half=0.3,
        session_turns=10,
        a_turn_ratio=0.3,
        s_turn_ratio=0.7,
        phase_distribution={"engage": 0.2, "create": 0.4, "manage": 0.3, "design": 0.1},
    )


def _aggregation() -> dict:
    return {
        "dimension_scores": {d: 0.5 for d in ["AL", "PR", "EC", "ES", "CS", "CD", "AUI", "CA"]},
        "pillar_scores": {"Engage": 0.5, "Manage": 0.5, "Create": 0.5, "Design": 0.5},
        "gates": {"scorability_gate": 1.0, "verification_gate": 1.0, "state_validity_gate": 1.0},
        "collaboration_quality_kappa": 0.5,
    }


def _risk_flags() -> dict:
    return {
        "fluent_incompetence": False,
        "cognitive_debt_flag": False,
        "explanation_trap": False,
        "genuine_collab_quality": True,
    }


# ── Claims boundary ───────────────────────────────────────────────────────────

def test_claims_boundary_tier_is_1():
    out = format_output("sid", _neuron_scores(), _aggregation(), _metrics(), _risk_flags())
    assert out["claims_boundary"]["tier"] == 1


def test_claims_boundary_present():
    out = format_output("sid", _neuron_scores(), _aggregation(), _metrics(), _risk_flags())
    assert "claims_boundary" in out


# ── Forbidden field names ─────────────────────────────────────────────────────

def test_no_synergy_in_output_keys():
    out = format_output("sid", _neuron_scores(), _aggregation(), _metrics(), _risk_flags())

    def _all_keys(obj, path=""):
        if isinstance(obj, dict):
            for k, v in obj.items():
                yield k
                yield from _all_keys(v, f"{path}.{k}")

    for key in _all_keys(out):
        assert "synergy" not in key.lower(), f"Forbidden key found: {key}"


def test_g_synergy_absent():
    out = format_output("sid", _neuron_scores(), _aggregation(), _metrics(), _risk_flags())
    assert "g_synergy" not in out


# ── Headline metric ───────────────────────────────────────────────────────────

def test_collaboration_quality_kappa_present():
    out = format_output("sid", _neuron_scores(), _aggregation(), _metrics(), _risk_flags())
    assert "collaboration_quality_kappa" in out


def test_kappa_value_matches_aggregation():
    out = format_output("sid", _neuron_scores(), _aggregation(), _metrics(), _risk_flags())
    assert out["collaboration_quality_kappa"] == 0.5


# ── Dependency debt stub ──────────────────────────────────────────────────────

def test_dependency_debt_ewma_is_none():
    out = format_output("sid", _neuron_scores(), _aggregation(), _metrics(), _risk_flags())
    assert out["dependency_debt_ewma"] is None


# ── Token efficiency stubs ────────────────────────────────────────────────────

def test_token_efficiency_stubs_are_none():
    out = format_output("sid", _neuron_scores(), _aggregation(), _metrics(), _risk_flags())
    te = out["token_efficiency"]
    assert te["s_human_estimate"] is None
    assert te["redundancy_delta"] is None


# ── Output is JSON-serialisable ───────────────────────────────────────────────

def test_output_is_json_serialisable():
    out = format_output("sid", _neuron_scores(), _aggregation(), _metrics(), _risk_flags())
    serialised = json.dumps(out)
    parsed = json.loads(serialised)
    assert parsed["claims_boundary"]["tier"] == 1
