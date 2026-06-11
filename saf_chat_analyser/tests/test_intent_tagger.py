"""Tests for Stage 2a — intent_tagger."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))

from saf_chat_analyser.src.parser.transcript_parser import Turn
from saf_chat_analyser.src.tagger.intent_tagger import (
    TaggedTurn,
    intent_counts,
    tag_turn,
    tag_turns,
)


def _human(content: str, idx: int = 0) -> Turn:
    return Turn(index=idx, role="human", content=content, word_count=len(content.split()))


def _ai(idx: int = 1) -> Turn:
    return Turn(index=idx, role="ai", content="AI response.", word_count=2)


# ── VERIFY detection ──────────────────────────────────────────────────────────

def test_verify_fires_on_is_that_accurate():
    tt = tag_turn(_human("Is that accurate?"))
    assert "VERIFY" in tt.tags


def test_verify_fires_on_are_you_sure():
    tt = tag_turn(_human("Are you sure about that?"))
    assert "VERIFY" in tt.tags


def test_verify_fires_on_double_check():
    tt = tag_turn(_human("Let me double-check this claim."))
    assert "VERIFY" in tt.tags


# ── EXTRACT mutual exclusion ──────────────────────────────────────────────────

def test_extract_fires_on_pure_delegation():
    tt = tag_turn(_human("Write me a summary of this document."))
    assert "EXTRACT" in tt.tags


def test_extract_excluded_when_verify_fires():
    tt = tag_turn(_human("Is that correct? Write a correction."))
    assert "VERIFY" in tt.tags
    assert "EXTRACT" not in tt.tags


# ── Default fallback ──────────────────────────────────────────────────────────

def test_fallback_to_extract_when_no_match():
    tt = tag_turn(_human("Something unrecognisable xyzzy."))
    assert "EXTRACT" in tt.tags
    assert len(tt.tags) >= 1


# ── AI turns passthrough ──────────────────────────────────────────────────────

def test_ai_turns_get_empty_tags():
    tt = tag_turn(_ai())
    assert tt.tags == []
    assert tt.dominant_intent is None


# ── Multi-tag turns ───────────────────────────────────────────────────────────

def test_inject_context_fires():
    tt = tag_turn(_human("In my company, the client wants X and specifically we need Y."))
    assert "INJECT_CONTEXT" in tt.tags


def test_ethics_gate_fires():
    tt = tag_turn(_human("Make sure to remove any personal data — GDPR compliance."))
    assert "ETHICS_GATE" in tt.tags


def test_override_fires():
    tt = tag_turn(_human("No, that's wrong. Not what I asked for."))
    assert "OVERRIDE" in tt.tags


def test_self_audit_fires():
    tt = tag_turn(_human("I wrote this analysis — can you find flaws in my reasoning?"))
    assert "SELF_AUDIT" in tt.tags


# ── dominant_intent ───────────────────────────────────────────────────────────

def test_dominant_intent_set():
    tt = tag_turn(_human("I wrote this, can you evaluate my reasoning? Also, is that correct?"))
    assert tt.dominant_intent is not None


# ── tag_turns and intent_counts ───────────────────────────────────────────────

def test_tag_turns_processes_all():
    turns = [_human("Write a report.", i * 2) for i in range(3)]
    tagged = tag_turns(turns)
    assert len(tagged) == 3


def test_intent_counts_returns_all_tags():
    turns = [_human("Write something."), _ai(), _human("Are you sure?")]
    tagged = tag_turns(turns)
    counts = intent_counts(tagged)
    assert "VERIFY" in counts
    assert "EXTRACT" in counts
    assert counts["VERIFY"] >= 1
