"""Unit tests for the sustainability layer. OWNER: Chief Engineer."""

from __future__ import annotations

import pytest

from contracts.schemas import (
    CanonicalSession,
    DebtMode,
    PartnerModel,
    Rung,
    ScoreStatus,
    Turn,
)
from src.sustainability.debt_tracker import is_a_turn, redundancy_of, s_human_hat
from src.sustainability.ewma import debt_ewma, ewma_series
from src.sustainability.lambda_proxy import lambda_estimate
from src.sustainability.probe_schema import load_probe_schema, validate_probe_record


def _session(turns: list[tuple[str, str]]) -> CanonicalSession:
    return CanonicalSession(
        session_id="su-1", source="plaintext",
        partner_model=PartnerModel(family="openai"),
        turns=[Turn(index=i, role=r, text=t) for i, (r, t) in enumerate(turns)],
    )


# ── Ŝ_human ──────────────────────────────────────────────────────────────────


def test_a_turn_detection():
    for text in ("ok", "Continue", "go on", "sounds good!", "yes", "thanks."):
        assert is_a_turn(text), text
    for text in ("ok but limit it to 3 bullet points", "no, use the v2 API",
                 "rewrite the intro to mention pricing"):
        assert not is_a_turn(text), text


def test_redundancy_against_established_content():
    established = {("the", "quick", "brown", "fox")} | set()
    assert redundancy_of("the quick brown fox", established) == 1.0
    assert redundancy_of("a completely different sentence here", established) == 0.0
    assert redundancy_of("two words", established) is None  # too short: no evidence


def test_s_human_computes_when_both_regimes_present():
    repeated = "the same boilerplate explanation repeats here again exactly " * 8
    fresh = "novel constrained answer covering the requested specific tradeoffs " \
            "with distinct vocabulary every clause"
    s = _session([
        ("human", "explain X with a focus on caching tradeoffs"),  # S-turn
        ("ai", repeated),
        ("human", "continue"),                                      # A-turn
        ("ai", repeated),                                           # high r_auto
        ("human", "now restrict it to write-through caches only"),  # S-turn
        ("ai", fresh),                                              # low r_steer
    ])
    result = s_human_hat(s)
    assert result.status == ScoreStatus.OK
    assert result.rung == Rung.MEASURABLE
    assert result.r_auto > result.r_steer
    assert result.value > 0
    assert result.t_steered_out > 0
    assert result.cache_multiplier == 1.0


def test_s_human_declines_without_a_turns():
    s = _session([
        ("human", "explain X under these constraints"),
        ("ai", "answer one"),
        ("human", "now add Y and remove the second section"),
        ("ai", "answer two"),
    ])
    result = s_human_hat(s)
    assert result.status == ScoreStatus.NOT_APPLICABLE
    assert result.value is None
    assert result.rung == Rung.DESIGNED  # declined, not measured


def test_s_human_declines_without_s_turns():
    s = _session([
        ("human", "ok"),
        ("ai", "rambling continuation with plenty of words to count"),
        ("human", "continue"),
        ("ai", "more rambling continuation with plenty of words to count"),
    ])
    result = s_human_hat(s)
    assert result.status == ScoreStatus.NOT_APPLICABLE
    assert result.value is None


# ── debt EWMA ────────────────────────────────────────────────────────────────


def test_single_session_is_insufficient_history_never_a_debt_score():
    result = debt_ewma([0.2])
    assert result.mode == DebtMode.INSUFFICIENT_HISTORY
    assert result.value is None
    assert result.n_sessions == 1


def test_erosion_mode_on_declining_history():
    history = [0.8, 0.75, 0.6, 0.5, 0.4, 0.3]
    result = debt_ewma(history)
    assert result.mode == DebtMode.EROSION
    assert result.value is not None


def test_flat_floor_mode_when_never_built():
    result = debt_ewma([0.15, 0.2, 0.18, 0.22, 0.19])
    assert result.mode == DebtMode.FLAT_FLOOR


def test_none_mode_on_healthy_history():
    result = debt_ewma([0.5, 0.55, 0.6, 0.62, 0.65])
    assert result.mode == DebtMode.NONE


def test_ewma_series_alpha_smoothing():
    s = ewma_series([1.0, 0.0], alpha=0.3)
    assert s == [1.0, pytest.approx(0.7)]


# ── λ stub + probe schema ────────────────────────────────────────────────────


def test_lambda_is_null_and_designed():
    stub = lambda_estimate()
    assert stub.value is None
    assert stub.rung == Rung.DESIGNED


def test_probe_schema_loads_and_validates():
    schema = load_probe_schema()
    assert schema["delivery_in_scope_a"] is False

    good = {
        "probe_id": "p1", "user_ref": "u1", "session_ref": "s1",
        "format": "free_recall", "scheduled_at": "2026-06-14T00:00:00Z",
        "exposure_randomized": True, "rung": "DESIGNED",
    }
    assert validate_probe_record(good) == []

    bad = dict(good, format="recognition")
    assert any("recognition" in p for p in validate_probe_record(bad))

    missing = {k: v for k, v in good.items() if k != "session_ref"}
    assert any("session_ref" in p for p in validate_probe_record(missing))
