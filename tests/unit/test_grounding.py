"""Unit tests for conversational grounding classification."""

from __future__ import annotations

from contracts.schemas import CanonicalSession, GroundingFunction, PartnerModel, Turn
from src.trait.grounding import classify_grounding
from src.trait.tagger import tag_turns


def _session(human_texts: list[str]) -> CanonicalSession:
    turns: list[Turn] = []
    for text in human_texts:
        turns.append(Turn(index=len(turns), role="human", text=text))
        turns.append(Turn(index=len(turns), role="ai", text="reply"))
    return CanonicalSession(
        session_id="ground-1",
        source="plaintext",
        partner_model=PartnerModel(family="openai"),
        turns=turns,
    )


def test_grounding_happy_path_labels_human_turns_in_order():
    session = _session([
        "For context, the API returns JSON.",
        "ok",
        "You said it returns XML, but the docs say JSON.",
        "The weather was nice in June.",
    ])

    assert classify_grounding(session, tag_turns(session)) == [
        GroundingFunction.INITIATION,
        GroundingFunction.GROUNDING,
        GroundingFunction.REPAIR,
        GroundingFunction.NONE,
    ]


def test_grounding_empty_session_returns_empty_list():
    session = CanonicalSession(
        session_id="ground-empty",
        source="plaintext",
        partner_model=PartnerModel(family="openai"),
        turns=[],
    )

    assert classify_grounding(session, tag_turns(session)) == []


def test_absent_grounding_signal_is_none_not_grounding():
    session = _session(["The weather was nice in June."])

    assert classify_grounding(session, tag_turns(session)) == [GroundingFunction.NONE]
