"""
src/claims/footer.py — the never-collapsible epistemic footer + four-state labels.
OWNER: Chief Engineer. (Brief §P6; spec V3/G8.)

This module is the single home for the two pieces of P6 user-facing copy that
passed human review (DISCREPANCY note / sign-off 2026-06-19):

1. `epistemic_footer(tier)` — the always-visible, never-collapsible note shown on
   EVERY view. It is a required field on each view model, so a view cannot be
   rendered without it (structural never-collapse).
2. `FOUR_STATE_LABELS` — the four DISTINCT labels for the never-collapse rule. A
   genuine low score, INSUFFICIENT_SAMPLE, NOT_APPLICABLE (STRUCTURAL_NA), and
   MEASUREMENT_SATURATED must never be merged into a single "focus area" bucket
   (spec §P6). The labels are distinct and non-substringable; a test enforces it.
3. `PORTFOLIO_ACKNOWLEDGEMENT` — the one-time statement gating the Portfolio view
   (personal baseline only, never population rank).

All copy here is forbidden-word clean for every tier (no synergy/surrender/
dependent stems) and lives at the MEASURABLE rung.
"""

from __future__ import annotations

from contracts.schemas import ScoreStatus, Tier

#: Display band for the "low" label ONLY — NOT a calibrated cut. It exists solely
#: to keep a low *measured* score from being collapsed into the three absent/
#: saturated states (never-collapse). The score value itself is always shown too.
LOW_SCORE_MAX = 0.34

#: The four never-collapse labels (spec §P6). Keys: the sentinel "low" for a
#: genuine low OK score, plus the three non-OK ScoreStatus values.
FOUR_STATE_LABELS: dict[str, str] = {
    "low": "Measured — low this session",
    ScoreStatus.INSUFFICIENT_SAMPLE.value: "Not enough evidence to score",
    ScoreStatus.NOT_APPLICABLE.value: "Didn't come up this session",
    ScoreStatus.MEASUREMENT_SATURATED.value: "Above the instrument's range (≥ bound)",
}


def four_state_label(status: ScoreStatus, value: float | None = None) -> str | None:
    """The never-collapse label for a dimension, or None for a normal OK score.

    A genuine low OK score returns the distinct "low" label (never merged with the
    absent/saturated states); a normal OK score returns None (it is shown by its
    value, not a concern bucket).
    """
    if status == ScoreStatus.OK:
        if value is not None and value <= LOW_SCORE_MAX:
            return FOUR_STATE_LABELS["low"]
        return None
    return FOUR_STATE_LABELS[status.value]


def epistemic_footer(tier: Tier) -> str:
    """The always-visible, never-collapsible epistemic note (approved copy).

    Same universal note for every tier — it is the standing disclaimer, not a
    tier-specific caveat (that is `report.TIER_CAVEATS`). The four-state labels are
    interpolated from FOUR_STATE_LABELS so the footer never drifts from the code.
    """
    low = FOUR_STATE_LABELS["low"]
    insufficient = FOUR_STATE_LABELS[ScoreStatus.INSUFFICIENT_SAMPLE.value]
    na = FOUR_STATE_LABELS[ScoreStatus.NOT_APPLICABLE.value]
    saturated = FOUR_STATE_LABELS[ScoreStatus.MEASUREMENT_SATURATED.value]
    return (
        "How to read this. Every figure here is an observation about one or more "
        "conversations — a description of the collaboration process, not a measure "
        "of ability, retention, or outcome. Four states are kept separate and never "
        f'merged into a single "focus area": {low} (scored, and it was low), '
        f"{insufficient} (too few moments to judge), {na} (the situation never "
        f'arose), and {saturated} (the signal exceeded what this tool can resolve — '
        'reported as a "≥" bound, never an exact maximum). Comparisons are only ever '
        "between your own past and present sessions; there is no population, "
        "percentile, ranking, or leaderboard. This note stays visible on every view."
    )


#: One-time acknowledgement gating the Portfolio view (approved copy).
PORTFOLIO_ACKNOWLEDGEMENT = (
    "Before you open your Portfolio. Your Portfolio gathers patterns across many of "
    "your own conversations over time. Two things to keep in mind — and to agree to: "
    "(1) Everything here compares you only to your own earlier sessions. It is never "
    "a ranking against other people, a percentile, or a leaderboard — none of those "
    "exist here. (2) These are patterns in how you worked with an AI assistant, not a "
    "verdict on your ability and not a prediction of what you can do unassisted. A "
    "rising or falling line is a reason to look closer, not a score to defend."
)
