"""Unit tests for the intent tagger (leaf)."""

from __future__ import annotations

import pytest

from contracts.schemas import CanonicalSession, IntentTag, PartnerModel, Turn
from src.trait.tagger import tag_turns


def _session(human_texts: list[str]) -> CanonicalSession:
    turns: list[Turn] = []
    for text in human_texts:
        turns.append(Turn(index=len(turns), role="human", text=text))
        turns.append(Turn(index=len(turns), role="ai", text="reply"))
    return CanonicalSession(
        session_id="tag-1", source="plaintext",
        partner_model=PartnerModel(family="openai"), turns=turns,
    )


def _tags_of(text: str) -> list[IntentTag]:
    return tag_turns(_session([text]))[0].tags


def test_one_turntags_per_human_turn_in_order():
    result = tag_turns(_session(["what is X?", "ok", "no, use Y instead"]))
    assert [tt.turn_index for tt in result] == [0, 2, 4]


@pytest.mark.parametrize("text,tag", [
    ("are you sure that applies here?", IntentTag.VERIFY),
    ("is that correct? you said 100 but the docs say 60", IntentTag.VERIFY),
    ("that's wrong, the API returns a list", IntentTag.VERIFY),
    ("what is the difference between TCP and UDP?", IntentTag.EXTRACT),
    ("explain gradient descent", IntentTag.EXTRACT),
    ("summarize this chapter", IntentTag.EXTRACT),
    ("here is my code:\n```py\nprint(1)\n```", IntentTag.INJECT_CONTEXT),
    ("for context, I'm working on a radar project", IntentTag.INJECT_CONTEXT),
    ("no, use the v2 endpoint instead", IntentTag.OVERRIDE),
    ("don't include the preamble", IntentTag.OVERRIDE),
    ("scratch that, actually let's keep it", IntentTag.OVERRIDE),
    ("am I wrong about how attention works?", IntentTag.SELF_AUDIT),
    ("critique my reasoning above", IntentTag.SELF_AUDIT),
    ("what am I missing here?", IntentTag.SELF_AUDIT),
    ("write me a cover letter", IntentTag.DELEGATE),
    ("can you generate the test cases", IntentTag.DELEGATE),
    ("use this format: bullet points, max 5", IntentTag.SCAFFOLD),
    ("must include the cost analysis, limit it to one page", IntentTag.SCAFFOLD),
    ("step-by-step please", IntentTag.SCAFFOLD),
    ("let's switch to the marketing plan", IntentTag.PIVOT),
    ("forget that, new topic", IntentTag.PIVOT),
    ("break this down into sub-tasks", IntentTag.DECOMPOSE),
    ("let's start with the first part", IntentTag.DECOMPOSE),
    ("ok", IntentTag.ACCEPT_FLAT),
    ("sounds good!", IntentTag.ACCEPT_FLAT),
    ("continue", IntentTag.ACCEPT_FLAT),
])
def test_single_tag_detection(text: str, tag: IntentTag):
    assert tag in _tags_of(text), f"{tag} not found in tags for {text!r}"


def test_accept_flat_is_exclusive():
    assert _tags_of("ok") == [IntentTag.ACCEPT_FLAT]
    assert _tags_of("thanks.") == [IntentTag.ACCEPT_FLAT]


def test_substantive_ok_is_not_accept_flat():
    tags = _tags_of("ok but limit it to 3 bullet points and must include pricing")
    assert IntentTag.ACCEPT_FLAT not in tags
    assert IntentTag.SCAFFOLD in tags


def test_multiple_tags_on_one_turn():
    tags = _tags_of(
        "here is my draft: ```text``` — critique my reasoning, "
        "and rewrite it step-by-step"
    )
    assert IntentTag.INJECT_CONTEXT in tags
    assert IntentTag.SELF_AUDIT in tags
    assert IntentTag.SCAFFOLD in tags
    assert IntentTag.DELEGATE in tags


def test_unmatched_turn_gets_no_tags_never_invented():
    assert _tags_of("the weather was nice in June.") == []


def test_only_human_turns_are_tagged():
    s = _session(["what is X?"])
    assert len(tag_turns(s)) == 1


def test_tags_are_deterministic():
    s = _session(["are you sure? verify that against the docs"])
    assert tag_turns(s) == tag_turns(s)
