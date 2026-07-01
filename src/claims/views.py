"""
src/claims/views.py — the three P6 view contexts + theater-rate panel.
OWNER: Chief Engineer. (Brief §P6; spec V3/G8.)

Three views keyed to the ID hierarchy, each carrying the never-collapsible
epistemic footer and rendering the four reporting states as distinct labels:

  render_chat_view(saf_session_id, response)        -> ChatView
  render_project_view(project_id, responses)        -> ProjectView
  render_portfolio_view(subject_id, responses, *, acknowledged) -> PortfolioView
  theater_rate(responses)                           -> TheaterRatePanel

Hard rules enforced here (spec §P6):
  * Every view carries the epistemic footer (a REQUIRED model field — a view
    cannot exist without it; that is the "never-collapsible" guarantee).
  * The four states (low OK / INSUFFICIENT_SAMPLE / STRUCTURAL_NA /
    MEASUREMENT_SATURATED) render as four distinct labels; no "focus area" bucket.
  * Comparisons are user-vs-own-previous ONLY. There is no cross-subject sorting,
    percentile, rank, or leaderboard anywhere in this module (asserted by test).
  * The theater-rate panel is a single AGGREGATE rate, never a per-subject score.
  * All emitted user-facing text passes forbidden_word_scan before return.

Scope note: resolving project_id / subject_id → their member sessions is a DB
concern. There is no `projects` schema yet, so the router-level resolver for
render_project_view is deferred (data-gated); the renderer here operates over the
session responses it is given and is fully exercised by tests.
"""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field

from contracts.schemas import Dimension, DimensionScore, ScoreResponse, ScoreStatus, Tier
from src.claims.footer import (
    PORTFOLIO_ACKNOWLEDGEMENT,
    epistemic_footer,
    four_state_label,
)
from src.claims.report import ForbiddenWordViolation, forbidden_word_scan

#: aggregate views span sessions of mixed tier → scan at the strictest tier (1)
_STRICTEST_TIER: Tier = 1


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class TheaterRatePanel(_Frozen):
    """Population-level theater monitoring (spec G8): the SHARE of sessions whose
    verification-shaped moves produced no downstream behavioural change. A single
    aggregate rate — never a per-subject score, never a ranking."""

    n_sessions: int = Field(ge=0)
    n_theater_sessions: int = Field(ge=0)
    theater_rate: float | None = Field(default=None, ge=0.0, le=1.0)
    caveat: str


class ChatView(_Frozen):
    session_id: str
    tier: Tier
    #: dimensions in one of the four never-collapse states → their distinct label
    dimension_states: dict[str, str]
    n_scored: int = Field(ge=0)
    observed: list[str]
    inferred: list[str]
    hypothesized: list[str]
    tier_caveat: str
    footer: str  # required → the footer can never be absent/collapsed


class ProjectView(_Frozen):
    project_id: str
    n_sessions: int = Field(ge=0)
    personal_trend: dict
    theater: TheaterRatePanel
    footer: str


class PortfolioView(_Frozen):
    subject_id: str
    n_sessions: int = Field(ge=0)
    personal_trend: dict
    theater: TheaterRatePanel
    footer: str


class PortfolioAcknowledgementRequired(Exception):
    """Raised when the Portfolio view is requested without the one-time
    acknowledgement. Carries the acknowledgement copy to display."""

    def __init__(self, acknowledgement: str = PORTFOLIO_ACKNOWLEDGEMENT) -> None:
        self.acknowledgement = acknowledgement
        super().__init__("portfolio view requires the one-time acknowledgement")


def _enforce_clean(texts: Sequence[str], tier: Tier) -> None:
    violations = forbidden_word_scan([t for t in texts if t], tier)
    if violations:
        raise ForbiddenWordViolation("; ".join(violations))


def _dimension_states(profile: dict[Dimension, DimensionScore]) -> tuple[dict[str, str], int]:
    """Map dimensions to their never-collapse label; count normally-scored dims.

    Saturated dimensions render with their real censored bound substituted into
    the label. A normal OK score is not a 'concern' state — it is counted, not
    bucketed (and never shown as a bare number here)."""
    states: dict[str, str] = {}
    n_scored = 0
    for dim, s in profile.items():
        if s.status == ScoreStatus.MEASUREMENT_SATURATED and s.censored is not None:
            states[dim.value] = f"Above the instrument's range (≥ {s.censored.bound:.2f})"
            continue
        label = four_state_label(s.status, s.value)
        if label is None:
            n_scored += 1  # a normal OK score: counted, not bucketed
        else:
            states[dim.value] = label
    return states, n_scored


def _personal_trend(responses: Sequence[ScoreResponse]) -> dict:
    """Direction of the composite over the subject's OWN sessions (present vs the
    mean of their earlier sessions). Personal baseline only — no other subject's
    data is ever read, and nothing is ranked."""
    values = [
        r.composite.value
        for r in responses
        if r.composite.status == ScoreStatus.OK and r.composite.value is not None
    ]
    if len(values) < 2:
        return {
            "composite": {
                "direction": "not enough sessions yet",
                "basis": "your own sessions",
                "n": len(values),
            }
        }
    present = values[-1]
    prior_mean = sum(values[:-1]) / len(values[:-1])
    delta = present - prior_mean
    direction = "rising" if delta > 0.02 else "falling" if delta < -0.02 else "flat"
    return {
        "composite": {
            "direction": direction,
            "basis": f"your own previous {len(values) - 1} session(s)",
            "n": len(values),
        }
    }


def theater_rate(responses: Sequence[ScoreResponse]) -> TheaterRatePanel:
    """Aggregate theater rate over a set of sessions (spec G8 TR panel)."""
    n = len(responses)
    n_theater = sum(1 for r in responses if (r.flags.theater_counter or 0) > 0)
    rate = round(n_theater / n, 6) if n else None
    caveat = (
        "Aggregate monitoring signal: the share of sessions in which a "
        "verification-shaped move produced no downstream change. A population "
        "rate, not a per-person score, and not a ranking."
    )
    return TheaterRatePanel(
        n_sessions=n, n_theater_sessions=n_theater, theater_rate=rate, caveat=caveat
    )


def render_chat_view(saf_session_id: str, response: ScoreResponse) -> ChatView:
    """Single-session view: the existing Observed/Inferred/Hypothesized report plus
    the four-state dimension panel and the standing epistemic footer."""
    states, n_scored = _dimension_states(response.profile)
    footer = epistemic_footer(response.tier)
    rpt = response.report
    _enforce_clean(
        [*states.values(), *rpt.observed, *rpt.inferred, *rpt.hypothesized,
         rpt.tier_caveat, footer],
        response.tier,
    )
    return ChatView(
        session_id=saf_session_id,
        tier=response.tier,
        dimension_states=states,
        n_scored=n_scored,
        observed=list(rpt.observed),
        inferred=list(rpt.inferred),
        hypothesized=list(rpt.hypothesized),
        tier_caveat=rpt.tier_caveat,
        footer=footer,
    )


def render_project_view(project_id: str, responses: Sequence[ScoreResponse]) -> ProjectView:
    """Project view: personal trend + theater panel over the project's sessions.

    NB: resolving project_id → its sessions is schema-gated (no projects table yet);
    callers supply the responses. The rendering itself is real and tested."""
    footer = epistemic_footer(_STRICTEST_TIER)
    trend = _personal_trend(responses)
    panel = theater_rate(responses)
    _enforce_clean([footer, panel.caveat, trend["composite"]["basis"]], _STRICTEST_TIER)
    return ProjectView(
        project_id=project_id,
        n_sessions=len(responses),
        personal_trend=trend,
        theater=panel,
        footer=footer,
    )


def render_portfolio_view(
    subject_id: str,
    responses: Sequence[ScoreResponse],
    *,
    acknowledged: bool,
) -> PortfolioView:
    """Portfolio view: gated behind the one-time acknowledgement. Personal trend +
    theater panel over the subject's own sessions; never a population rank."""
    if not acknowledged:
        raise PortfolioAcknowledgementRequired()
    footer = epistemic_footer(_STRICTEST_TIER)
    trend = _personal_trend(responses)
    panel = theater_rate(responses)
    _enforce_clean(
        [footer, panel.caveat, trend["composite"]["basis"], PORTFOLIO_ACKNOWLEDGEMENT],
        _STRICTEST_TIER,
    )
    return PortfolioView(
        subject_id=subject_id,
        n_sessions=len(responses),
        personal_trend=trend,
        theater=panel,
        footer=footer,
    )
