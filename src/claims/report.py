"""
src/claims/report.py — report generation + forbidden-word enforcement.
OWNER: Chief Engineer. (Brief §3.10.)

The report separates Observed / Inferred / Hypothesized and is the ONLY
user-facing text surface. Every string it emits passes the forbidden-word
scan for the session's tier before the ScoreResponse is assembled — the test
suite proves the generator cannot emit any Tier-1 forbidden term (the
collaboration buzzword, the regime-overlay state word, or the dependency
adjective — see the forbidden-word table / non-negotiables #4-#5) through any
path. Those literal words are deliberately absent from this surface file
(non-negotiable #5; enforced by the CI forbidden-word gate).
"""

from __future__ import annotations

import re

from contracts.schemas import (
    Composite,
    Dimension,
    DimensionScore,
    ReactionSignatures,
    Report,
    Rung,
    ScoreStatus,
    SessionFlags,
    StateValidity,
    Sustainability,
    Tier,
)
from src.claims.rungs import forbidden_words_for_tier


class ForbiddenWordViolation(Exception):
    """A user-facing string contains a tier-forbidden word. This is a bug in
    the generator, never something to strip silently in production."""


def forbidden_word_scan(texts: list[str], tier: Tier) -> list[str]:
    """Return violations like 'synergy in: <snippet>' (empty = clean).

    Words are matched by stem so derivatives are caught too:
    synergy → synergistic/synergies; dependent → dependence/dependency.
    """
    violations: list[str] = []
    for word in forbidden_words_for_tier(tier):
        stem = word[:-1] if word[-1] in "yt" else word
        pattern = re.compile(rf"\b{re.escape(stem)}\w*", re.IGNORECASE)
        for text in texts:
            if pattern.search(text):
                violations.append(f"{word!r} in: {text[:80]!r}")
    return violations


TIER_CAVEATS: dict[int, str] = {
    1: (
        "Tier 1 (transcript-only): these are collaboration-process observations "
        "from a single conversation. No quantity here is a validated measure; "
        "cognitive-load and engagement statements are proxy inferences from text. "
        "Nothing in this report is a statement about ability, retention, or outcomes."
    ),
    2: (
        "Tier 2 (extension telemetry): within-session trajectory observations; "
        "flags are inferences, not proven outcomes."
    ),
    3: (
        "Tier 3 (controlled platform): claims at the VALIDATED rung only where "
        "the predictive-validity gate has fired."
    ),
}


def _fmt(x: float) -> str:
    return f"{x:.2f}"


def generate_report(
    *,
    tier: Tier,
    profile: dict[Dimension, DimensionScore],
    composite: Composite,
    state_validity: StateValidity,
    flags: SessionFlags,
    reactions: ReactionSignatures,
    sustainability: Sustainability,
    is_minor: bool = False,
) -> Report:
    observed: list[str] = []
    inferred: list[str] = []
    hypothesized: list[str] = []

    # ── observed: things countable in the transcript/log ──
    # The three non-OK states are reported as DISTINCT clauses, never merged
    # into one "no evidence" bucket (never-collapse rule, v3 §9 / v3.2 §0.3).
    scored = [d for d, s in profile.items() if s.status == ScoreStatus.OK]
    saturated = [
        (d, s) for d, s in profile.items() if s.status == ScoreStatus.MEASUREMENT_SATURATED
    ]
    insufficient = [
        d for d, s in profile.items() if s.status == ScoreStatus.INSUFFICIENT_SAMPLE
    ]
    not_applicable = [
        d for d, s in profile.items() if s.status == ScoreStatus.NOT_APPLICABLE
    ]
    line = f"{len(scored)} of 8 dimensions had scoreable evidence"
    for dim, s in saturated:
        cmp = "≥" if s.censored and s.censored.direction == "high" else "≤"
        bound = _fmt(s.censored.bound) if s.censored else "?"
        line += f"; {dim.value} {cmp} {bound} (instrument saturated)"
    if insufficient:
        line += f"; too few items to score: {', '.join(d.value for d in insufficient)}"
    if not_applicable:
        line += f"; no applicable evidence for: {', '.join(d.value for d in not_applicable)}"
    observed.append(line)
    if flags.accept_run_max is not None:
        observed.append(
            f"longest run of consecutive unmodified acceptances: {flags.accept_run_max} turns"
        )
    if flags.theater_counter:
        observed.append(
            f"{flags.theater_counter} verification-shaped turn(s) produced no downstream change"
        )
    tm = reactions.transition_metrics
    if tm.verify_after_error_rate.value is not None:
        observed.append(
            f"after a detected error, the next move was verification "
            f"{_fmt(tm.verify_after_error_rate.value)} of the time "
            f"(n={tm.verify_after_error_rate.n_events})"
        )

    # ── inferred: proxy/flag language, never direct claims ──
    if not is_minor and composite.status == ScoreStatus.OK and composite.value is not None:
        ci = composite.ci
        ci_text = f" (CI {_fmt(ci.low)}–{_fmt(ci.high)})" if ci else ""
        inferred.append(
            f"composite collaboration-process index: {_fmt(composite.value)}{ci_text} "
            f"[rung: {composite.rung.value}]"
        )
    if state_validity.state_compromised:
        inferred.append(
            "engagement-pattern signals consistent with reduced metacognitive "
            "monitoring in part of the session; all scores carry widened "
            "uncertainty rather than adjustment"
        )
    if flags.fluent_incompetence:
        inferred.append(
            "output fluency outpaced demonstrated verification — flag, not a finding"
        )
    if flags.judge_family_conflict:
        inferred.append(
            "judge and partner model share a family for this session; judge-derived "
            "evidence carries reduced weight (see methodology note)"
        )

    # ── hypothesized: explicitly unproven ──
    if flags.debt_flag:
        hypothesized.append(
            "the session pattern is consistent with reliance accumulating over "
            "time; only a delayed recall probe could test this"
        )
    sh = sustainability.s_human_hat
    if sh.status == ScoreStatus.OK and sh.value is not None:
        hypothesized.append(
            f"steering appears to have removed redundant output "
            f"(estimate {_fmt(sh.value)} tokens-weighted; unvalidated estimator)"
        )

    report = Report(
        observed=observed,
        inferred=inferred,
        hypothesized=hypothesized,
        tier_caveat=TIER_CAVEATS[tier]
        + (" Reported in minor-protective form: bands and next habits only." if is_minor else ""),
        rung=Rung.MEASURABLE,
    )

    violations = forbidden_word_scan(
        [*report.observed, *report.inferred, *report.hypothesized, report.tier_caveat],
        tier,
    )
    if violations:
        raise ForbiddenWordViolation("; ".join(violations))
    return report
