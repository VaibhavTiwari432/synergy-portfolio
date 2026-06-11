"""
Stage 7 — Risk Flag Evaluator.

Four flags, all derived from raw (unweighted) dimension means + composite metrics.
Raw scores are used so thresholds apply uniformly regardless of dimension weight.

Flags (from SAF_ARI_Final_Master_Compilation.md §1.3, §3.6, §7.3, brief Stage 7):

  fluent_incompetence   — Sophisticated-seeming AI use with no underlying competence
                          (Ayodele et al.): high PR fluency + low EC + low CS + low VR + high AG

  cognitive_debt_flag   — Within-session surrender proxy: verification rate drops >40%
                          in second half of a long session (not proven debt — stub only;
                          EWMA longitudinal tracker is a Phase 2 feature)

  explanation_trap      — Explanation-without-verification → negative synergy
                          (Berger et al. 2025): user spends >50% of session in ENGAGE
                          phase but never verifies (VR < 0.10)

  genuine_collab_quality — Positive signal: no active pathology flags + strong EC + CS
                          + verification + generativity. Field name is
                          'genuine_collab_quality', NOT 'synergy' (forbidden at Tier 1).

Forbidden field name: 'true_synergy' or 'g_synergy' — Tier 1 cannot claim synergy.
"""

from __future__ import annotations

from saf_chat_analyser.src.metrics.composite_metrics import CompositeMetrics

# ── Thresholds (from brief, verbatim) ─────────────────────────────────────────

_PR_HIGH = 0.65
_EC_LOW = 0.40
_CS_LOW = 0.40
_VR_LOW = 0.15
_AG_HIGH = 0.60

_DEBT_VR_RATIO = 1.4
_DEBT_MIN_TURNS = 20

_TRAP_ENGAGE_THRESHOLD = 0.5
_TRAP_VR_THRESHOLD = 0.10

_QUALITY_EC_MIN = 0.55
_QUALITY_CS_MIN = 0.55
_QUALITY_VR_MIN = 0.30
_QUALITY_GR_MIN = 0.45


# ── Main evaluator ────────────────────────────────────────────────────────────

def evaluate_flags(
    neuron_scores: dict[str, float],
    metrics: CompositeMetrics,
) -> dict[str, bool]:
    """
    Evaluate all four Tier-1 risk flags.

    Args:
        neuron_scores: raw [0,1] scores for all 107 neurons.
        metrics:       CompositeMetrics from Stage 4.

    Returns:
        Dict with keys:
          fluent_incompetence
          cognitive_debt_flag
          explanation_trap
          genuine_collab_quality
    """
    raw = _raw_dim_means(neuron_scores)

    fi = _fluent_incompetence(raw, metrics)
    cd = _cognitive_debt(metrics)
    et = _explanation_trap(metrics)
    gc = _genuine_collab_quality(raw, metrics, fi, cd)

    return {
        "fluent_incompetence": fi,
        "cognitive_debt_flag": cd,
        "explanation_trap": et,
        "genuine_collab_quality": gc,
    }


# ── Internal helpers ──────────────────────────────────────────────────────────

def _raw_dim_means(neuron_scores: dict[str, float]) -> dict[str, float]:
    """Unweighted per-dimension means from neuron scores (for flag thresholds)."""
    by_dim: dict[str, list[float]] = {}
    for nid, score in neuron_scores.items():
        dim = nid.split("-")[0]
        by_dim.setdefault(dim, []).append(score)
    return {
        dim: sum(vals) / len(vals)
        for dim, vals in by_dim.items()
        if vals
    }


def _fluent_incompetence(raw: dict[str, float], metrics: CompositeMetrics) -> bool:
    """
    Sophisticated-seeming AI use with no underlying competence.
    Triggered when: PR fluency high + EC low + CS low + low verification + high attribution gap.
    """
    return (
        raw.get("PR", 0.0) > _PR_HIGH
        and raw.get("EC", 0.0) < _EC_LOW
        and raw.get("CS", 0.0) < _CS_LOW
        and (metrics.verification_ratio or 0.0) < _VR_LOW
        and (metrics.attribution_gap or 0.0) > _AG_HIGH
    )


def _cognitive_debt(metrics: CompositeMetrics) -> bool:
    """
    Within-session surrender proxy: verification drops >40% second half.
    EWMA longitudinal tracker (Phase 2) is stubbed at None.
    Only fires for sessions > 20 turns.
    """
    vr_first = metrics.vr_first_half
    vr_second = metrics.vr_second_half
    if vr_first is None or vr_second is None:
        return False
    if metrics.session_turns <= _DEBT_MIN_TURNS:
        return False
    return vr_first > vr_second * _DEBT_VR_RATIO


def _explanation_trap(metrics: CompositeMetrics) -> bool:
    """
    Explanation-without-verification → negative synergy (Berger et al. 2025).
    User spends >50% in ENGAGE phase but never actually verifies.
    """
    engage_frac = metrics.phase_distribution.get("engage", 0.0)
    vr = metrics.verification_ratio or 0.0
    return engage_frac > _TRAP_ENGAGE_THRESHOLD and vr < _TRAP_VR_THRESHOLD


def _genuine_collab_quality(
    raw: dict[str, float],
    metrics: CompositeMetrics,
    fluent_incompetence: bool,
    cognitive_debt: bool,
) -> bool:
    """
    Positive signal: no active pathology + strong EC + CS + verification + generativity.
    Field name is 'genuine_collab_quality' — NEVER 'synergy' at Tier 1.
    """
    if fluent_incompetence or cognitive_debt:
        return False
    return (
        raw.get("EC", 0.0) > _QUALITY_EC_MIN
        and raw.get("CS", 0.0) > _QUALITY_CS_MIN
        and (metrics.verification_ratio or 0.0) > _QUALITY_VR_MIN
        and (metrics.generative_query_ratio or 0.0) > _QUALITY_GR_MIN
    )
