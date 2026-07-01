"""Unit tests for the epistemic-vigilance precision conditioner."""

from __future__ import annotations

from contracts.schemas import CanonicalSession, PartnerModel, Turn
from src.trait.tagger import tag_turns
from src.trait.vigilance import score_vigilance


def _session(human_texts: list[str]) -> CanonicalSession:
    turns: list[Turn] = []
    for text in human_texts:
        turns.append(Turn(index=len(turns), role="human", text=text))
        turns.append(Turn(index=len(turns), role="ai", text="reply"))
    return CanonicalSession(
        session_id="vig-1",
        source="plaintext",
        partner_model=PartnerModel(family="openai"),
        turns=turns,
    )


def test_vigilance_happy_path_detects_distributed_pattern():
    session = _session([
        "The docs say this endpoint returns 202, not 200.",
        "Can you cite the source and explain your reasoning?",
        "ok",
    ])

    result = score_vigilance(session, tag_turns(session))

    assert result.n_signals == 4
    assert result.score == 1.0
    assert result.pattern_detected is True


def test_vigilance_empty_session_is_zero_signal_result():
    session = CanonicalSession(
        session_id="vig-empty",
        source="plaintext",
        partner_model=PartnerModel(family="openai"),
        turns=[],
    )

    result = score_vigilance(session, tag_turns(session))

    assert result.n_signals == 0
    assert result.score == 0.0
    assert result.pattern_detected is False


def test_absent_vigilance_signal_is_real_zero_not_missing():
    session = _session(["Please summarize this chapter.", "continue"])

    result = score_vigilance(session, tag_turns(session))

    assert result.n_signals == 0
    assert result.score == 0.0
    assert result.pattern_detected is False
