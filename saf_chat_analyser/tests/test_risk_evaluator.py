"""Tests for Stage 7 — risk_evaluator."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))

from saf_chat_analyser.src.metrics.composite_metrics import CompositeMetrics
from saf_chat_analyser.src.flags.risk_evaluator import evaluate_flags


def _metrics(**overrides) -> CompositeMetrics:
    defaults = dict(
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
    defaults.update(overrides)
    return CompositeMetrics(**defaults)


def _neuron_scores(**dim_overrides) -> dict[str, float]:
    """Build stub neuron scores with 107 entries, overriding per-dim values."""
    import json
    from pathlib import Path as P
    neurons = json.load(open(P(__file__).parents[1] / "data" / "neurons_v6.json", encoding="utf-8"))
    scores = {nid: 0.5 for nid in neurons}
    for nid in neurons:
        dim = nid.split("-")[0]
        if dim in dim_overrides:
            scores[nid] = dim_overrides[dim]
    return scores


# ── Fluent incompetence ───────────────────────────────────────────────────────

def test_fluent_incompetence_fires():
    scores = _neuron_scores(PR=0.8, EC=0.3, CS=0.3)
    m = _metrics(verification_ratio=0.05, attribution_gap=0.7)
    flags = evaluate_flags(scores, m)
    assert flags["fluent_incompetence"] is True


def test_fluent_incompetence_does_not_fire_when_ec_high():
    scores = _neuron_scores(PR=0.8, EC=0.6, CS=0.3)
    m = _metrics(verification_ratio=0.05, attribution_gap=0.7)
    flags = evaluate_flags(scores, m)
    assert flags["fluent_incompetence"] is False


# ── Cognitive debt ────────────────────────────────────────────────────────────

def test_cognitive_debt_fires_on_long_surrender():
    scores = _neuron_scores()
    m = _metrics(
        session_turns=25,
        vr_first_half=0.5,
        vr_second_half=0.2,  # drops >40%
    )
    flags = evaluate_flags(scores, m)
    assert flags["cognitive_debt_flag"] is True


def test_cognitive_debt_does_not_fire_short_session():
    scores = _neuron_scores()
    m = _metrics(
        session_turns=15,
        vr_first_half=0.5,
        vr_second_half=0.2,
    )
    flags = evaluate_flags(scores, m)
    assert flags["cognitive_debt_flag"] is False


# ── Explanation trap ──────────────────────────────────────────────────────────

def test_explanation_trap_fires():
    scores = _neuron_scores()
    m = _metrics(
        phase_distribution={"engage": 0.6, "create": 0.2, "manage": 0.1, "design": 0.1},
        verification_ratio=0.05,
    )
    flags = evaluate_flags(scores, m)
    assert flags["explanation_trap"] is True


def test_explanation_trap_does_not_fire_when_vr_above_threshold():
    scores = _neuron_scores()
    m = _metrics(
        phase_distribution={"engage": 0.6, "create": 0.2, "manage": 0.1, "design": 0.1},
        verification_ratio=0.25,
    )
    flags = evaluate_flags(scores, m)
    assert flags["explanation_trap"] is False


def test_explanation_trap_does_not_fire_when_engage_low():
    scores = _neuron_scores()
    m = _metrics(
        phase_distribution={"engage": 0.3, "create": 0.3, "manage": 0.2, "design": 0.2},
        verification_ratio=0.05,
    )
    flags = evaluate_flags(scores, m)
    assert flags["explanation_trap"] is False


# ── Genuine collaboration quality ─────────────────────────────────────────────

def test_genuine_collab_quality_fires():
    scores = _neuron_scores(EC=0.7, CS=0.7)
    m = _metrics(
        verification_ratio=0.4,
        generative_query_ratio=0.5,
        phase_distribution={"engage": 0.2, "create": 0.4, "manage": 0.3, "design": 0.1},
    )
    flags = evaluate_flags(scores, m)
    assert flags["genuine_collab_quality"] is True


def test_genuine_collab_quality_blocked_by_fluent_incompetence():
    scores = _neuron_scores(PR=0.8, EC=0.3, CS=0.3)
    m = _metrics(
        verification_ratio=0.05, attribution_gap=0.7,
        generative_query_ratio=0.5,
    )
    flags = evaluate_flags(scores, m)
    assert flags["genuine_collab_quality"] is False


# ── Field names ───────────────────────────────────────────────────────────────

def test_no_synergy_in_flag_keys():
    scores = _neuron_scores()
    flags = evaluate_flags(scores, _metrics())
    for key in flags:
        assert "synergy" not in key.lower()


def test_genuine_collab_quality_key_not_true_synergy():
    scores = _neuron_scores()
    flags = evaluate_flags(scores, _metrics())
    assert "genuine_collab_quality" in flags
    assert "true_synergy" not in flags
    assert "g_synergy" not in flags
