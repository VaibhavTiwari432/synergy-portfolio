"""v3 P6 — reporting views, never-collapse footer, theater-rate panel.
OWNER: Chief Engineer. (Brief §P6; spec V3/G8.)

Six locked acceptance criteria, each testable here:
  1. the four reporting states render as four DISTINCT labels (never-collapse);
  2. Portfolio view is unreachable without the one-time acknowledgement;
  3. the epistemic footer is present on every view and cannot be absent;
  4. no population-ranking surface exists (personal baseline only);
  5. the theater-rate panel is a single aggregate (share of null-delta sessions);
  6. all emitted user-facing text is forbidden-word clean.
"""

from __future__ import annotations

import json

import pytest

from contracts.schemas import (
    CanonicalSession,
    Censored,
    Dimension,
    DimensionScore,
    PartnerModel,
    Rung,
    ScoreStatus,
    Turn,
)
from src.api.pipeline import score_session
from src.claims.footer import (
    FOUR_STATE_LABELS,
    PORTFOLIO_ACKNOWLEDGEMENT,
    epistemic_footer,
    four_state_label,
)
from src.claims.report import ForbiddenWordViolation, forbidden_word_scan
from src.claims.views import (
    ChatView,
    PortfolioAcknowledgementRequired,
    PortfolioView,
    ProjectView,
    TheaterRatePanel,
    _dimension_states,
    render_chat_view,
    render_portfolio_view,
    render_project_view,
    theater_rate,
)
from src.trait.judge.client import JudgeClient


def _fake_judge(score: float = 0.5) -> JudgeClient:
    entry = {"score": score, "confidence": 0.8, "evidence_turns": [0], "tom_tag": None}
    data = {d.value: dict(entry) for d in Dimension}
    data["ES"]["score"] = None  # ES → NOT_APPLICABLE (a real second state)
    return JudgeClient(generate=lambda s, u: json.dumps(data), fallback=None, sleep=lambda _: None)


def _session(sid: str = "v-1") -> CanonicalSession:
    texts = [
        "walk me through it step by step, must include the cost analysis",
        "are you sure that's correct? you said 100 but the docs say 60",
        "ok", "continue", "sounds good",
    ]
    turns: list[Turn] = []
    for t in texts:
        turns.append(Turn(index=len(turns), role="human", text=t))
        turns.append(Turn(index=len(turns), role="ai", text="a long enough ai reply here"))
    return CanonicalSession(
        session_id=sid, source="plaintext",
        partner_model=PartnerModel(family="openai"), turns=turns,
    )


def _response(sid: str = "v-1", score: float = 0.5):
    return score_session(_session(sid), judge=_fake_judge(score))


# ── 1. four states render as four distinct, non-substringable labels ────────


def test_four_state_labels_are_distinct_and_non_substringable():
    labels = list(FOUR_STATE_LABELS.values())
    assert len(labels) == 4
    assert len(set(labels)) == 4
    for a in labels:
        for b in labels:
            if a is not b:
                assert a not in b  # no label is a substring of another (never-collapse)


def test_dimension_states_render_all_four_distinctly():
    profile = {
        Dimension.AL: DimensionScore(dim=Dimension.AL, status=ScoreStatus.OK, value=0.2, rung=Rung.MEASURABLE),
        Dimension.PR: DimensionScore(dim=Dimension.PR, status=ScoreStatus.OK, value=0.8, rung=Rung.MEASURABLE),
        Dimension.EC: DimensionScore(dim=Dimension.EC, status=ScoreStatus.INSUFFICIENT_SAMPLE, rung=Rung.MEASURABLE),
        Dimension.ES: DimensionScore(dim=Dimension.ES, status=ScoreStatus.NOT_APPLICABLE, rung=Rung.MEASURABLE),
        Dimension.CS: DimensionScore(
            dim=Dimension.CS, status=ScoreStatus.MEASUREMENT_SATURATED,
            censored=Censored(direction="high", bound=0.93), rung=Rung.MEASURABLE,
        ),
    }
    states, n_scored = _dimension_states(profile)
    assert n_scored == 1  # PR (a normal OK score is counted, not bucketed)
    assert states["AL"] == FOUR_STATE_LABELS["low"]
    assert states["EC"] == FOUR_STATE_LABELS[ScoreStatus.INSUFFICIENT_SAMPLE.value]
    assert states["ES"] == FOUR_STATE_LABELS[ScoreStatus.NOT_APPLICABLE.value]
    assert "Above the instrument's range" in states["CS"] and "≥ 0.93" in states["CS"]
    assert len({states["AL"], states["EC"], states["ES"], states["CS"]}) == 4


def test_normal_ok_score_is_not_a_concern_bucket():
    assert four_state_label(ScoreStatus.OK, 0.8) is None
    assert four_state_label(ScoreStatus.OK, 0.2) == FOUR_STATE_LABELS["low"]


# ── 2. Portfolio is unreachable without the acknowledgement ─────────────────


def test_portfolio_requires_acknowledgement():
    responses = [_response("v-1"), _response("v-2")]
    with pytest.raises(PortfolioAcknowledgementRequired) as exc:
        render_portfolio_view("subj-1", responses, acknowledged=False)
    assert exc.value.acknowledgement == PORTFOLIO_ACKNOWLEDGEMENT

    view = render_portfolio_view("subj-1", responses, acknowledged=True)
    assert isinstance(view, PortfolioView)


# ── 3. the epistemic footer is present on every view ────────────────────────


def test_every_view_carries_the_footer():
    responses = [_response("v-1"), _response("v-2", 0.6)]
    chat = render_chat_view("v-1", responses[0])
    project = render_project_view("proj-1", responses)
    portfolio = render_portfolio_view("subj-1", responses, acknowledged=True)
    for view in (chat, project, portfolio):
        assert view.footer == epistemic_footer(_TIER := 1) or view.footer  # non-empty
        assert "stays visible on every view" in view.footer


def test_footer_is_a_required_field():
    # a view model cannot be constructed without the footer (structural never-collapse)
    with pytest.raises(Exception):
        ChatView(
            session_id="x", tier=1, dimension_states={}, n_scored=0,
            observed=[], inferred=[], hypothesized=[], tier_caveat="c",
        )  # footer missing → ValidationError


# ── 4. no population-ranking surface (personal baseline only) ───────────────


def test_no_population_ranking_surface():
    banned = ("rank", "percentile", "leaderboard", "population")
    for model in (ChatView, ProjectView, PortfolioView, TheaterRatePanel):
        for fname in model.model_fields:
            assert not any(b in fname.lower() for b in banned), f"{model.__name__}.{fname}"
    # the theater panel is a single aggregate, never a per-subject mapping
    panel = theater_rate([_response("v-1")])
    assert isinstance(panel.theater_rate, (float, type(None)))
    # personal trend commits to the subject's OWN baseline
    view = render_portfolio_view("subj-1", [_response("a"), _response("b", 0.7)], acknowledged=True)
    assert "your own" in view.personal_trend["composite"]["basis"]


def test_personal_trend_direction_is_rising_when_own_scores_climb():
    responses = [_response("a", 0.25), _response("b", 0.5), _response("c", 0.85)]
    view = render_project_view("proj-1", responses)
    assert view.personal_trend["composite"]["direction"] == "rising"
    assert view.n_sessions == 3


# ── 5. theater-rate panel = share of null-delta sessions ────────────────────


def test_theater_rate_is_share_of_null_delta_sessions():
    # the verification turn in _session has no downstream delta → theater_counter > 0
    responses = [_response("a"), _response("b"), _response("c")]
    panel = theater_rate(responses)
    assert panel.n_sessions == 3
    assert 0.0 <= panel.theater_rate <= 1.0
    assert panel.n_theater_sessions == sum(
        1 for r in responses if (r.flags.theater_counter or 0) > 0
    )
    assert theater_rate([]).theater_rate is None  # empty set → no rate, not 0


# ── 6. all emitted user-facing copy is forbidden-word clean ─────────────────


def test_all_copy_is_forbidden_word_clean():
    for tier in (1, 2, 3):
        assert forbidden_word_scan([epistemic_footer(tier)], tier) == []
    assert forbidden_word_scan([PORTFOLIO_ACKNOWLEDGEMENT], 1) == []
    for label in FOUR_STATE_LABELS.values():
        assert forbidden_word_scan([label], 1) == []
    # the rendered views must not raise the forbidden-word guard
    responses = [_response("v-1"), _response("v-2", 0.7)]
    render_chat_view("v-1", responses[0])
    render_project_view("proj-1", responses)
    render_portfolio_view("subj-1", responses, acknowledged=True)


def test_forbidden_scan_would_catch_a_planted_word():
    # sanity: the guard is live (not a no-op) — a planted Tier-1 word is caught
    assert forbidden_word_scan(["this conversation shows real synergy"], 1)
