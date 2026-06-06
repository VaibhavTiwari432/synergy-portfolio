"""
Stage 7 — Risk Flag Evaluator.

Evaluates three behavioural risk flags from raw dimension scores and
composite metrics. All threshold comparisons use RAW (unweighted) scores
so that the same threshold applies regardless of dimension weight.
"""

from __future__ import annotations

from collections import defaultdict

from chat_classifier.config import (
    FLAG_ATTRIBUTION_GAP_HIGH,
    FLAG_CS_LOW_THRESHOLD,
    FLAG_DEBT_MIN_TURNS,
    FLAG_DEBT_RATIO_MULTIPLIER,
    FLAG_EC_LOW_THRESHOLD,
    FLAG_PR_HIGH_THRESHOLD,
    FLAG_SYNERGY_CS_MIN,
    FLAG_SYNERGY_EC_MIN,
    FLAG_SYNERGY_GENERATIVE_MIN,
    FLAG_SYNERGY_VERIFY_MIN,
    FLAG_VERIFICATION_RATIO_LOW,
)
from chat_classifier.schemas import CompositeMetrics


def evaluate_flags(
    neuron_scores: dict[str, float],
    metrics: CompositeMetrics,
) -> dict[str, bool]:
    """
    Return the three risk flags.

    neuron_scores — raw [0, 1] scores for all 107 neurons (from JudgeOutput).
    metrics       — CompositeMetrics computed by Stage 4.
    """
    raw = _raw_dim_means(neuron_scores)

    fluent_incompetence = _fluent_incompetence(raw, metrics)
    cognitive_debt = _cognitive_debt(metrics)
    true_synergy = _true_synergy(raw, metrics, fluent_incompetence, cognitive_debt)

    return {
        "fluent_incompetence": fluent_incompetence,
        "cognitive_debt_accumulation": cognitive_debt,
        "true_synergy": true_synergy,
    }


# ── Internal helpers ──────────────────────────────────────────────────────────

def _raw_dim_means(neuron_scores: dict[str, float]) -> dict[str, float]:
    """Compute unweighted mean score per dimension from neuron_scores."""
    by_dim: dict[str, list[float]] = defaultdict(list)
    for nid, score in neuron_scores.items():
        dim = nid.split("-")[0]
        by_dim[dim].append(score)
    return {
        dim: sum(vals) / len(vals)
        for dim, vals in by_dim.items()
        if vals
    }


def _fluent_incompetence(
    raw: dict[str, float],
    metrics: CompositeMetrics,
) -> bool:
    pr = raw.get("PR", 0.0)
    ec = raw.get("EC", 0.0)
    cs = raw.get("CS", 0.0)
    vr = metrics.verification_ratio or 0.0
    ag = metrics.attribution_gap or 0.0

    return (
        pr > FLAG_PR_HIGH_THRESHOLD
        and ec < FLAG_EC_LOW_THRESHOLD
        and cs < FLAG_CS_LOW_THRESHOLD
        and vr < FLAG_VERIFICATION_RATIO_LOW
        and ag > FLAG_ATTRIBUTION_GAP_HIGH
    )


def _cognitive_debt(metrics: CompositeMetrics) -> bool:
    vr_first = metrics.verification_ratio_first_half
    vr_second = metrics.verification_ratio_second_half

    if vr_first is None or vr_second is None:
        return False
    if metrics.session_turns <= FLAG_DEBT_MIN_TURNS:
        return False

    return vr_first > vr_second * FLAG_DEBT_RATIO_MULTIPLIER


def _true_synergy(
    raw: dict[str, float],
    metrics: CompositeMetrics,
    fluent_incompetence: bool,
    cognitive_debt: bool,
) -> bool:
    if fluent_incompetence or cognitive_debt:
        return False

    ec = raw.get("EC", 0.0)
    cs = raw.get("CS", 0.0)
    vr = metrics.verification_ratio or 0.0
    gr = metrics.generative_query_ratio or 0.0

    return (
        ec > FLAG_SYNERGY_EC_MIN
        and cs > FLAG_SYNERGY_CS_MIN
        and vr > FLAG_SYNERGY_VERIFY_MIN
        and gr > FLAG_SYNERGY_GENERATIVE_MIN
    )
