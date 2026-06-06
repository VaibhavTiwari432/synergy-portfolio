"""
Stage 6 — Dimension Aggregator.

Converts a flat dict of 107 neuron scores into:
  - Per-dimension weighted means
  - Per-pillar means
  - g_synergy: coverage-weighted mean across scorable dimensions

Scorability gate: a dimension needs >= SCORABILITY_TAU non-zero neurons
to produce a score. Dimensions that don't pass return None — they are
excluded from g_synergy rather than dragging it toward zero.
"""

from __future__ import annotations

from chat_classifier.config import (
    DIMENSIONS,
    DIMENSION_WEIGHTS,
    PILLAR_MAP,
    SCORABILITY_TAU,
)
from chat_classifier.schemas import SynergyReport


def aggregate(
    neuron_scores: dict[str, float],
    synergy_report: SynergyReport,
) -> SynergyReport:
    """
    Populate dimension_scores, pillar_scores, and synergy_score_kappa
    on an existing SynergyReport (mutates and returns it).
    """
    dim_scores = _compute_dimension_scores(neuron_scores)
    pillar_scores = _compute_pillar_scores(dim_scores)
    g_synergy = _compute_g_synergy(dim_scores)

    synergy_report.dimension_scores = dim_scores
    synergy_report.pillar_scores = pillar_scores
    synergy_report.synergy_score_kappa = g_synergy

    return synergy_report


def _compute_dimension_scores(
    neuron_scores: dict[str, float],
) -> dict[str, float | None]:
    """
    For each dimension, compute the weighted mean of its neurons.
    Returns None if fewer than SCORABILITY_TAU neurons are non-zero.
    """
    by_dim: dict[str, list[float]] = {d: [] for d in DIMENSIONS}

    for neuron_id, score in neuron_scores.items():
        dim = neuron_id.split("-")[0]
        if dim in by_dim:
            by_dim[dim].append(score)

    result: dict[str, float | None] = {}
    for dim in DIMENSIONS:
        scores = by_dim[dim]
        nonzero = [s for s in scores if s > 0.0]
        if len(nonzero) < SCORABILITY_TAU:
            result[dim] = None
            continue
        raw_mean = sum(scores) / len(scores)
        result[dim] = round(raw_mean * DIMENSION_WEIGHTS[dim], 4)

    return result


def _compute_pillar_scores(
    dim_scores: dict[str, float | None],
) -> dict[str, float | None]:
    """
    Average the scorable dimensions within each pillar.
    Returns None for a pillar if all its dimensions are None.
    """
    pillar_scores: dict[str, float | None] = {}
    for pillar, dims in PILLAR_MAP.items():
        scorable = [dim_scores[d] for d in dims if dim_scores.get(d) is not None]
        if not scorable:
            pillar_scores[pillar] = None
        else:
            pillar_scores[pillar] = round(sum(scorable) / len(scorable), 4)
    return pillar_scores


def _compute_g_synergy(
    dim_scores: dict[str, float | None],
) -> float | None:
    """
    Coverage-weighted mean of all scorable dimensions.
    Weights already baked into dim_scores (EC and CS carry 1.5x).
    Returns None if no dimensions are scorable.
    """
    scorable = [(d, s) for d, s in dim_scores.items() if s is not None]
    if not scorable:
        return None
    total = sum(s for _, s in scorable)
    # Normalise by the sum of weights for scorable dims only
    weight_sum = sum(DIMENSION_WEIGHTS[d] for d, _ in scorable)
    raw_weighted = total / weight_sum
    return round(raw_weighted, 4)
