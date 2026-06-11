"""
Stage 6 — Dimension Aggregator.

Converts 107 neuron scores → per-dimension scores → per-pillar scores →
collaboration_quality_kappa (the non-compensatory composite).

Aggregation rule (SAF §3.6):
  Composite = min(pillar_scores) × product(gates)

NOT a mean across pillars. The minimum-across-pillars rule is the explicit
Skilled-Outsourcer punisher: a user strong on Create but hollow on Design
cannot average over the gap. A mean would obscure exactly the pattern
the instrument exists to detect.

Pillar score = weighted mean of its two dimension scores using DIMENSION_WEIGHTS.
Dimension score = unweighted mean of its neuron scores (equal-weight v1).

Gates (Tier 1):
  scorability_gate  — 1.0 if all dimensions have ≥τ non-zero neurons, else 0.7
  verification_gate — 1.0 if verification_ratio > 0.0, else 0.85
  state_validity_gate — 1.0 (CSPC stub; becomes live in Tier 2)

Reference: SAF_ARI_Final_Master_Compilation.md §3.6, brief Stage 6
"""

from __future__ import annotations

import math

# ── Constants ─────────────────────────────────────────────────────────────────

DIMENSION_WEIGHTS: dict[str, float] = {
    "AL": 1.0,
    "PR": 1.0,
    "EC": 1.5,   # highest weight — surrender / blind-trust detection
    "ES": 1.0,
    "CS": 1.5,   # highest weight — cognitive offloading detection
    "CD": 1.0,
    "AUI": 1.0,
    "CA": 1.0,
}

PILLARS: dict[str, list[str]] = {
    "Engage":  ["AL", "PR"],
    "Manage":  ["EC", "ES"],
    "Create":  ["CS", "CD"],
    "Design":  ["AUI", "CA"],
}

SCORABILITY_TAU = 1   # min non-zero neurons per dimension for scorable status

# Gate values (Tier 1)
_GATE_SCORABILITY_FAIL = 0.7
_GATE_VERIFICATION_FAIL = 0.85
_GATE_STATE_VALIDITY = 1.0   # CSPC stub


# ── Main aggregation function ─────────────────────────────────────────────────

def aggregate(
    neuron_scores: dict[str, float],
    verification_ratio: float | None = None,
) -> dict:
    """
    Aggregate 107 neuron scores into dimensions, pillars, gates, and composite.

    Args:
        neuron_scores:      Dict of neuron_id → float in [0.0, 1.0].
        verification_ratio: From CompositeMetrics; drives the verification gate.

    Returns:
        Dict with keys:
          dimension_scores          — raw unweighted per-dim means (for flag eval)
          pillar_scores             — weighted means (for composite)
          gates                     — individual gate values and rationale
          collaboration_quality_kappa — min(pillar) × product(gates)
    """
    dim_scores = _compute_dimension_scores(neuron_scores)
    pillar_scores = _compute_pillar_scores(dim_scores)
    gates = _compute_gates(dim_scores, verification_ratio)
    composite = _compute_composite(pillar_scores, gates)

    return {
        "dimension_scores": {d: round(v, 4) for d, v in dim_scores.items()},
        "pillar_scores": {p: round(v, 4) for p, v in pillar_scores.items()},
        "gates": gates,
        "collaboration_quality_kappa": round(composite, 4) if composite is not None else None,
    }


# ── Internal helpers ──────────────────────────────────────────────────────────

def _compute_dimension_scores(
    neuron_scores: dict[str, float],
) -> dict[str, float]:
    """
    Unweighted mean of neuron scores per dimension (equal-weight v1).
    Returns 0.0 for any dimension with no neurons present.
    """
    by_dim: dict[str, list[float]] = {d: [] for d in DIMENSION_WEIGHTS}
    for nid, score in neuron_scores.items():
        dim = nid.split("-")[0]
        if dim in by_dim:
            by_dim[dim].append(score)

    result: dict[str, float] = {}
    for dim in DIMENSION_WEIGHTS:
        scores = by_dim[dim]
        result[dim] = sum(scores) / len(scores) if scores else 0.0
    return result


def _compute_pillar_scores(
    dim_scores: dict[str, float],
) -> dict[str, float]:
    """
    Weighted mean of dimension scores within each pillar.
    Uses DIMENSION_WEIGHTS (EC and CS carry 1.5×).
    """
    pillar_scores: dict[str, float] = {}
    for pillar, dims in PILLARS.items():
        total = sum(dim_scores[d] * DIMENSION_WEIGHTS[d] for d in dims)
        weight_sum = sum(DIMENSION_WEIGHTS[d] for d in dims)
        pillar_scores[pillar] = total / weight_sum
    return pillar_scores


def _compute_gates(
    dim_scores: dict[str, float],
    verification_ratio: float | None,
) -> dict[str, float]:
    """Compute all Tier-1 gate values."""
    # Scorability gate: all dimensions must have ≥ τ non-zero neurons
    # (approximated here as score > 0.0 for each dimension; full τ check
    # requires raw neuron lists but we use the dimension mean as proxy)
    all_scorable = all(v > 0.0 for v in dim_scores.values())
    scorability = 1.0 if all_scorable else _GATE_SCORABILITY_FAIL

    # Verification gate
    vr = verification_ratio if verification_ratio is not None else 0.0
    verification = 1.0 if vr > 0.0 else _GATE_VERIFICATION_FAIL

    return {
        "scorability_gate": scorability,
        "verification_gate": verification,
        "state_validity_gate": _GATE_STATE_VALIDITY,  # CSPC stub
    }


def _compute_composite(
    pillar_scores: dict[str, float],
    gates: dict[str, float],
) -> float | None:
    """
    Composite = min(pillar_scores) × product(gates).

    Returns None only if pillar_scores is empty (should never happen
    with a valid 107-neuron input).
    """
    if not pillar_scores:
        return None
    pillar_min = min(pillar_scores.values())
    gate_product = math.prod(gates.values())
    return pillar_min * gate_product
