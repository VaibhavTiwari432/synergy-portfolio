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

Phase 2: CSPC-weighted aggregation (feature-flagged). When use_cspc_weighting=True
and state_strip is provided, neuron firings are weighted by evidence quality proxies
(epistemic, load, metacog) so late-turn noise in long chats is down-weighted.
Flag OFF: byte-identical to baseline. Flag ON: ratchet must pass + late-turn weights
demonstrably lower on long chats.
"""

from __future__ import annotations

from typing import Sequence

from contracts.schemas import (
    Dimension,
    DimensionNormalization,
    NormalizedScores,
    ScoreStatus,
    StateVector,
)


def normalize_counts(
    firings: dict[Dimension, dict[str, float]],
    opportunities: dict[Dimension, dict[str, int]],
    use_cspc_weighting: bool = False,
    state_strip: Sequence[StateVector] | None = None,
    evidence_turns: dict[Dimension, dict[str, list[int]]] | None = None,
) -> NormalizedScores:
    """Normalize neuron counts to per-dimension strength, optionally CSPC-weighted.

    Phase 2: When use_cspc_weighting=True and state_strip + evidence_turns provided,
    neuron values are weighted by CSPC quality (epistemic, load, metacog). Otherwise,
    equal-weight mean (byte-identical to baseline).

    Args:
        firings: dict[Dimension, dict[neuron_id, strength]]
        opportunities: dict[Dimension, dict[neuron_id, count]]
        use_cspc_weighting: Phase 2 feature flag. If False, behavior unchanged.
        state_strip: Sequence of StateVector (per-turn state). Required if use_cspc_weighting.
        evidence_turns: dict[Dimension, dict[neuron_id, list[turn_index]]]. Required if use_cspc_weighting.
    """
    from src.aggregate.cspc_weighting import cspc_weight, weighted_aggregate

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

        # Phase 2: optionally apply CSPC weighting to neuron values
        if (
            use_cspc_weighting
            and state_strip is not None
            and evidence_turns is not None
        ):
            dim_evidence = evidence_turns.get(dim, {})
            weights = []
            for nid in dim_opps:
                turn_indices = dim_evidence.get(nid, [])
                if not turn_indices:
                    # No evidence turns: neutral weight
                    weights.append(1.0)
                else:
                    # Weight this neuron by the quality of turns it came from
                    neuron_weights = [
                        cspc_weight(state_strip[ti])
                        for ti in turn_indices
                        if ti < len(state_strip)
                    ]
                    avg_weight = sum(neuron_weights) / len(neuron_weights) if neuron_weights else 1.0
                    weights.append(avg_weight)
            # Weighted mean using per-neuron quality weights
            normalized = weighted_aggregate(strengths, weights)
        else:
            # Phase 0/1: equal-weight mean (unchanged behavior)
            normalized = sum(strengths) / len(dim_opps)

        fired_weight = sum(strengths)
        per_dimension[dim] = DimensionNormalization(
            dim=dim,
            fired_weight=fired_weight,
            applicable_opportunities=sum(dim_opps.values()),
            normalized=normalized,
            status=ScoreStatus.OK,
        )

    return NormalizedScores(per_dimension=per_dimension)
