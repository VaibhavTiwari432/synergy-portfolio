"""
Tests for tagger/intent_tagger.py — Stage 2 acceptance criteria.

Five fixture turns, each chosen to fire one specific tag clearly
and assert both the tag set and the dominant_intent.
"""

from __future__ import annotations

import pytest

from chat_classifier.schemas import Turn
from chat_classifier.tagger.intent_tagger import tag_turn, tag_chat, intent_counts
from chat_classifier.schemas import RawChat


def _turn(index: int, role: str, text: str) -> Turn:
    return Turn(index=index, role=role, text=text)  # type: ignore[arg-type]


def _human(index: int, text: str) -> Turn:
    return _turn(index, "human", text)


def _ai(index: int, text: str) -> Turn:
    return _turn(index, "ai", text)


# ── Fixture turns ─────────────────────────────────────────────────────────────

VERIFY_TURN = _human(0, "Are you sure that's correct? Can you double-check that figure?")
EXTRACT_TURN = _human(0, "Write me a detailed summary of this document.")
INJECT_TURN = _human(0, "In our company we use a different process — the client requires weekly sign-off.")
OVERRIDE_TURN = _human(0, "That's wrong. I disagree with your answer — not what I asked for.")
SELF_AUDIT_TURN = _human(0, "Find any flaws in my reasoning above and challenge my logic.")


# ── VERIFY ────────────────────────────────────────────────────────────────────

class TestVerifyTag:
    def test_verify_fires(self):
        result = tag_turn(VERIFY_TURN)
        assert "VERIFY" in result.tags

    def test_extract_does_not_fire_with_verify(self):
        result = tag_turn(VERIFY_TURN)
        assert "EXTRACT" not in result.tags

    def test_dominant_is_verify(self):
        result = tag_turn(VERIFY_TURN)
        assert result.dominant_intent == "VERIFY"


# ── EXTRACT ───────────────────────────────────────────────────────────────────

class TestExtractTag:
    def test_extract_fires(self):
        result = tag_turn(EXTRACT_TURN)
        assert "EXTRACT" in result.tags

    def test_dominant_is_extract(self):
        result = tag_turn(EXTRACT_TURN)
        assert result.dominant_intent == "EXTRACT"


# ── INJECT_CONTEXT ────────────────────────────────────────────────────────────

class TestInjectContextTag:
    def test_inject_fires(self):
        result = tag_turn(INJECT_TURN)
        assert "INJECT_CONTEXT" in result.tags

    def test_dominant_is_inject(self):
        result = tag_turn(INJECT_TURN)
        assert result.dominant_intent == "INJECT_CONTEXT"


# ── OVERRIDE ──────────────────────────────────────────────────────────────────

class TestOverrideTag:
    def test_override_fires(self):
        result = tag_turn(OVERRIDE_TURN)
        assert "OVERRIDE" in result.tags

    def test_dominant_is_override(self):
        result = tag_turn(OVERRIDE_TURN)
        assert result.dominant_intent == "OVERRIDE"


# ── SELF_AUDIT ────────────────────────────────────────────────────────────────

class TestSelfAuditTag:
    def test_self_audit_fires(self):
        result = tag_turn(SELF_AUDIT_TURN)
        assert "SELF_AUDIT" in result.tags

    def test_self_audit_is_dominant_intent(self):
        result = tag_turn(SELF_AUDIT_TURN)
        assert result.dominant_intent == "SELF_AUDIT"


# ── AI turns pass through untagged ───────────────────────────────────────────

def test_ai_turn_has_empty_tags():
    ai = _ai(0, "Here is a detailed answer to your question.")
    result = tag_turn(ai)
    assert result.tags == []
    assert result.dominant_intent is None


# ── Bare turn with no pattern defaults to EXTRACT ─────────────────────────────

def test_bare_turn_defaults_to_extract():
    bare = _human(0, "yes")
    result = tag_turn(bare)
    assert result.tags == ["EXTRACT"]
    assert result.dominant_intent == "EXTRACT"


# ── tag_chat and intent_counts ────────────────────────────────────────────────

def test_tag_chat_returns_one_tagged_turn_per_turn():
    chat = RawChat(
        chat_id="tc-001",
        source_model="chatgpt",
        turns=[
            _human(0, "Write me a plan."),
            _ai(1, "Here's a plan..."),
            _human(2, "Are you sure that's right?"),
            _ai(3, "Yes, I'm confident."),
        ],
    )
    tagged = tag_chat(chat)
    assert len(tagged) == 4


def test_intent_counts_tallies_all_tags():
    chat = RawChat(
        chat_id="tc-002",
        source_model="chatgpt",
        turns=[
            _human(0, "Write me a plan."),
            _ai(1, "Here's a plan..."),
            _human(2, "Are you sure that's correct? Double-check that."),
            _ai(3, "Yes."),
        ],
    )
    tagged = tag_chat(chat)
    counts = intent_counts(tagged)
    assert counts["EXTRACT"] >= 1
    assert counts["VERIFY"] >= 1
