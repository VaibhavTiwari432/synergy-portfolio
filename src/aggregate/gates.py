"""
src/aggregate/gates.py — n_eff, scorability, and state-validity gates.
OWNER: Chief Engineer. (Brief §3.7.)

CE resolution on the spec's "× validity gates" phrasing: a failed STATE gate
never scales the composite — that would be a score multiplier for state (non-
negotiable #2). Scorability gates the composite's EXISTENCE; state validity
sets the caveat flag (precision was already widened in the merge).
"""

from __future__ import annotations

from contracts.schemas import (
    Dimension,
    DimensionScore,
    ScoreStatus,
    StateValidity,
)

#: n_eff threshold τ (brief §3.7; config)
N_EFF_TAU = 1.0

#: scorability: at least this many of the 8 dimensions must carry usable signal
MIN_VALID_DIMS = 4

#: statuses that count toward scorability — a dimension contributes to the
#: composite if it is OK *or* MEASUREMENT_SATURATED. A saturated dimension is not
#: missing signal: it tops out the instrument with strong evidence (n_eff ≥
#: SATURATION_MIN_NEFF > N_EFF_TAU by construction, saturation.py §65-71) and
#: PARTICIPATES in the soft-min via its censored bound (softmin.py §90-102).
#: Excluding it would collapse the composite of the strongest sessions to
#: INSUFFICIENT_SAMPLE — the exact opposite of insufficient sample.
_SCORABLE_STATUSES = frozenset({ScoreStatus.OK, ScoreStatus.MEASUREMENT_SATURATED})


def gate_dimension(score: DimensionScore, tau: float = N_EFF_TAU) -> DimensionScore:
    """Demote an under-sampled OK score to INSUFFICIENT_SAMPLE.

    Raw counts are retained; no ratio is reported (absent ≠ zero). Non-OK
    statuses pass through untouched.
    """
    if score.status != ScoreStatus.OK or score.n_eff >= tau:
        return score
    return score.model_copy(
        update={
            "status": ScoreStatus.INSUFFICIENT_SAMPLE,
            "value": None,
            "ci": None,
            "status_reason": f"n_eff {score.n_eff:g} < tau {tau:g}",
        }
    )


def scorability_gate(profile: dict[Dimension, DimensionScore]) -> bool:
    """≥ MIN_VALID_DIMS dimensions carry usable signal — an OK score or a
    MEASUREMENT_SATURATED ceiling (see _SCORABLE_STATUSES)."""
    return sum(1 for s in profile.values() if s.status in _SCORABLE_STATUSES) >= MIN_VALID_DIMS


def state_validity_gate(validity: StateValidity) -> bool:
    """True when the state channel did not flag a compromised session."""
    return not validity.state_compromised
