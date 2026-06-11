"""
Stage 8 — Output Formatter.

Assembles all pipeline outputs into the canonical Tier-1 JSON document.
Every output includes claims_boundary — non-negotiable.

Field name rules (enforced):
  - 'collaboration_quality_kappa' is the headline metric
  - NEVER 'synergy_score', 'g_synergy', or any field containing 'synergy'
  - dependency_debt_ewma is always None at Tier 1 (Phase 2 feature)
  - s_human_estimate and redundancy_delta are always None at Tier 1

Reference: SAF_ARI_Final_Master_Compilation.md §9.1, §9.4, brief Stage 8
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from saf_chat_analyser.src.metrics.composite_metrics import CompositeMetrics

# ── Tier-1 claims boundary (immutable) ───────────────────────────────────────

_CLAIMS_BOUNDARY = {
    "tier": 1,
    "permitted": "single-conversation collaboration-process quality (8 ARI dims)",
    "forbidden": [
        "synergy",
        "cognitive_debt_proven",
        "sustainability",
        "true_kappa_uplift",
        "solo_theta_baseline",
    ],
}

_DEPENDENCY_DEBT_NOTE = (
    "Longitudinal EWMA requires cross-session persistence layer (Phase 2)"
)

_TOKEN_EFFICIENCY_STATUS = (
    "HYPOTHESIS — requires autonomous-stretch baseline (§5.3.1)"
)


# ── Main formatter ────────────────────────────────────────────────────────────

def format_output(
    session_id: str,
    neuron_scores: dict[str, float],
    aggregation: dict[str, Any],
    metrics: CompositeMetrics,
    risk_flags: dict[str, bool],
) -> dict[str, Any]:
    """
    Assemble the canonical Tier-1 output document.

    Args:
        session_id:    Unique identifier for this session.
        neuron_scores: 107 validated float scores from the judge.
        aggregation:   Output from Stage 6 (dimension_scores, pillar_scores,
                       gates, collaboration_quality_kappa).
        metrics:       CompositeMetrics from Stage 4.
        risk_flags:    Output from Stage 7.

    Returns:
        Dict conforming to the Tier-1 output schema.
        Always contains claims_boundary with tier=1.
    """
    output: dict[str, Any] = {
        "session_id": session_id,
        "tier": 1,
        "claims_boundary": _CLAIMS_BOUNDARY,
        "neuron_scores": {k: round(v, 4) for k, v in neuron_scores.items()},
        "dimension_scores": aggregation["dimension_scores"],
        "pillar_scores": aggregation["pillar_scores"],
        "collaboration_quality_kappa": aggregation["collaboration_quality_kappa"],
        "composite_metrics": _format_metrics(metrics),
        "risk_flags": risk_flags,
        "token_efficiency": _format_token_efficiency(metrics),
        "dependency_debt_ewma": None,
        "dependency_debt_note": _DEPENDENCY_DEBT_NOTE,
    }

    # Enforce forbidden field names — belt-and-suspenders
    _assert_no_forbidden_keys(output)

    return output


# ── Internal helpers ──────────────────────────────────────────────────────────

def _format_metrics(m: CompositeMetrics) -> dict[str, Any]:
    return {
        "attribution_gap": _r(m.attribution_gap),
        "verification_ratio": _r(m.verification_ratio),
        "generative_query_ratio": _r(m.generative_query_ratio),
        "actualization_depth": _r(m.actualization_depth),
        "iteration_depth": _r(m.iteration_depth),
        "semantic_distance_delta": _r(m.semantic_distance_delta),
        "vr_first_half": _r(m.vr_first_half),
        "vr_second_half": _r(m.vr_second_half),
        "a_turn_ratio": round(m.a_turn_ratio, 4),
        "s_turn_ratio": round(m.s_turn_ratio, 4),
        "session_turns": m.session_turns,
        "phase_distribution": {k: round(v, 4) for k, v in m.phase_distribution.items()},
    }


def _format_token_efficiency(m: CompositeMetrics) -> dict[str, Any]:
    return {
        "a_turn_ratio": round(m.a_turn_ratio, 4),
        "s_turn_ratio": round(m.s_turn_ratio, 4),
        "s_human_estimate": None,
        "redundancy_delta": None,
        "status": _TOKEN_EFFICIENCY_STATUS,
    }


def _r(v: float | None, precision: int = 4) -> float | None:
    return round(v, precision) if v is not None else None


def _assert_no_forbidden_keys(obj: dict, path: str = "") -> None:
    """Recursively check that no field name contains 'synergy'."""
    for key in obj:
        full_key = f"{path}.{key}" if path else key
        assert "synergy" not in key.lower(), (
            f"Forbidden field name containing 'synergy' found at {full_key}. "
            "Tier 1 may not claim synergy."
        )
        if isinstance(obj[key], dict):
            _assert_no_forbidden_keys(obj[key], full_key)
