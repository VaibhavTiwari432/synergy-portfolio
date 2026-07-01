"""
src/merge/precision.py — THE precision-weighting merge. OWNER: Chief Engineer.
The only meeting point of the STATE and TRAIT channels (brief §1, §3.7).

The whole contract in one sentence: state conditions trait evidence
PRECISION (CI width) — never trait score VALUE (non-negotiable #2, R2).

Mechanics:
- a compromised state (M_t collapse) widens every dimension's CI by a base
  factor;
- the per-turn strip adds graded widening: the larger the share of human turns
  spent in high-extraneous-load / fatigued / surrendered state, the wider the
  CIs (evidence gathered in a degraded state is less precise evidence — it is
  not worse performance);
- score values, statuses, n_eff, evidence — everything else — pass through
  IDENTICALLY. The Gate-C audit test asserts value equality structurally.

Scores are never suppressed; confidence is suppressed and the caveat reported
(brief §3.5).
"""

from __future__ import annotations

from contracts.schemas import (
    ConfidenceInterval,
    Dimension,
    DimensionScore,
    LoadLabel,
    MetacogLabel,
    StateValidity,
    StateVector,
)

#: CI width multiplier when the session's state validity gate fails (M_t collapse)
COMPROMISED_WIDENING = 1.5

#: additional graded widening: factor 1.0 + DEGRADED_SHARE_GAIN × degraded_share
DEGRADED_SHARE_GAIN = 0.5

#: a turn counts as degraded evidence context under these labels
_DEGRADED_LOADS = {LoadLabel.HIGH_ECL, LoadLabel.FATIGUE}
_DEGRADED_METACOG = {MetacogLabel.SURRENDER}

#: flag attached to scores whose CI was state-conditioned
STATE_CONDITIONED_FLAG = "state_conditioned_precision"


def degraded_share(strip: list[StateVector]) -> float:
    """Share of ASSESSABLE turns whose state labels mark degraded evidence context.
    Turns with no labels (both load=None and metacog=None) contribute neither
    numerator nor denominator (absent ≠ degraded, non-negotiable #12)."""
    if not strip:
        return 0.0
    assessable = [v for v in strip if v.load is not None or v.metacog is not None]
    if not assessable:
        return 0.0
    degraded = sum(
        1
        for v in assessable
        if (v.load in _DEGRADED_LOADS) or (v.metacog in _DEGRADED_METACOG)
    )
    return degraded / len(assessable)


def turn_precision(
    load: LoadLabel | None,
    metacog: MetacogLabel | None,
    *,
    compromised: bool,
) -> tuple[float | None, list[str]]:
    """Per-turn evidence precision π_t and the cascade flags that reduced it.

    Single-turn analogue of `widening_factor`: π_t = 1 / w_t where w_t mirrors the
    session widening at one turn (degraded label → ×(1+gain); session M_t collapse
    → ×COMPROMISED). This is computed at score time so a chat's per-turn precision
    is recoverable after the transcript purges — precision is the ONLY meeting
    point of state and trait (TEAM.md §1), so it owns this definition.

    Returns (None, []) when the turn has no assessable state label at all — absent
    state is N/A, never full precision (non-negotiable #12). A turn that IS
    assessable but undegraded returns (1.0, []).
    """
    if load is None and metacog is None:
        return None, []
    flags: list[str] = []
    degraded = False
    if load in _DEGRADED_LOADS:
        degraded = True
        flags.append(load.value.lower())
    if metacog in _DEGRADED_METACOG:
        degraded = True
        flags.append(metacog.value.lower())  # "surrender"
    factor = 1.0 + DEGRADED_SHARE_GAIN * (1.0 if degraded else 0.0)
    if compromised:
        factor *= COMPROMISED_WIDENING
        if "surrender" not in flags:
            flags.append("session_m_t_collapse")
    return round(1.0 / factor, 6), flags


def _widen(ci: ConfidenceInterval, factor: float) -> ConfidenceInterval:
    """Widen symmetrically around the CI midpoint, clamped to [0, 1]."""
    mid = (ci.low + ci.high) / 2
    half = (ci.high - ci.low) / 2 * factor
    return ConfidenceInterval(low=max(0.0, mid - half), high=min(1.0, mid + half))


def widening_factor(state_validity: StateValidity, strip: list[StateVector]) -> float:
    factor = 1.0 + DEGRADED_SHARE_GAIN * degraded_share(strip)
    if state_validity.state_compromised:
        factor *= COMPROMISED_WIDENING
    return factor


def merge(
    trait_scores: dict[Dimension, DimensionScore],
    state_validity: StateValidity,
    state_strip: list[StateVector],
) -> dict[Dimension, DimensionScore]:
    """Condition trait evidence precision on state. Values NEVER change."""
    factor = widening_factor(state_validity, state_strip)
    if factor == 1.0:
        return dict(trait_scores)

    merged: dict[Dimension, DimensionScore] = {}
    for dim, score in trait_scores.items():
        if score.ci is None:
            merged[dim] = score  # nothing to widen; status/value untouched
            continue
        merged[dim] = score.model_copy(
            update={
                "ci": _widen(score.ci, factor),
                "flags": [*score.flags, STATE_CONDITIONED_FLAG],
            }
        )
    return merged
