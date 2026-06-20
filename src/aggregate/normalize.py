"""
src/aggregate/normalize.py — count normalization (INTERFACES.md §1.4).
Leaf module: imports ONLY from contracts/. Pure function; no I/O.

Per neuron the extractors already report strength = fired ÷ applicable
opportunities. Per dimension this module aggregates by the MEAN strength over
neurons that had opportunities — the mean (not the sum) is what standardizes
across neuron counts, so CA's 17 neurons get no structural edge over AUI's 12
(brief §3.7).

A neuron with opportunities but no firing entry contributes 0.0 — that is a
measured zero (the opportunity existed, the behavior provably did not occur),
not an absence. A dimension with no opportunities at all → NOT_APPLICABLE,
normalized=None (absent ≠ zero, non-negotiable #12).
"""

from __future__ import annotations

from contracts.schemas import (
    Dimension,
    DimensionNormalization,
    NormalizedScores,
    ScoreStatus,
)


def normalize_counts(
    firings: dict[Dimension, dict[str, float]],
    opportunities: dict[Dimension, dict[str, int]],
) -> NormalizedScores:
    per_dimension: dict[Dimension, DimensionNormalization] = {}

    for dim in Dimension:
        dim_opps = {
            nid: count for nid, count in opportunities.get(dim, {}).items() if count > 0
        }
        dim_firings = firings.get(dim, {})

        if not dim_opps:
            per_dimension[dim] = DimensionNormalization(
                dim=dim,
                fired_weight=0.0,
                applicable_opportunities=0,
                normalized=None,
                status=ScoreStatus.NOT_APPLICABLE,
            )
            continue

        strengths = [
            min(1.0, max(0.0, dim_firings.get(nid, 0.0))) for nid in dim_opps
        ]
        fired_weight = sum(strengths)
        per_dimension[dim] = DimensionNormalization(
            dim=dim,
            fired_weight=fired_weight,
            applicable_opportunities=sum(dim_opps.values()),
            normalized=fired_weight / len(dim_opps),
            status=ScoreStatus.OK,
        )

    return NormalizedScores(per_dimension=per_dimension)
