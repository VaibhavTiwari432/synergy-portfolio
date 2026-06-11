"""Tests for Stage 2b — turn_classifier (A/S ratios)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))

from saf_chat_analyser.src.parser.transcript_parser import Turn
from saf_chat_analyser.src.tagger.intent_tagger import TaggedTurn, tag_turns
from saf_chat_analyser.src.tagger.turn_classifier import classify_turn, compute_as_ratios


def _human(content: str, idx: int = 0) -> Turn:
    return Turn(index=idx, role="human", content=content, word_count=len(content.split()))


def _ai(idx: int = 1) -> Turn:
    return Turn(index=idx, role="ai", content="AI response here.", word_count=3)


def _tagged(content: str, idx: int = 0) -> TaggedTurn:
    turns = [_human(content, idx)]
    return tag_turns(turns)[0]


# ── A-turn detection ──────────────────────────────────────────────────────────

def test_continue_is_a_turn():
    tt = _tagged("continue")
    assert classify_turn(tt).is_a_turn is True


def test_ok_is_a_turn():
    tt = _tagged("ok")
    assert classify_turn(tt).is_a_turn is True


def test_thanks_is_a_turn():
    tt = _tagged("thanks")
    assert classify_turn(tt).is_a_turn is True


# ── S-turn detection ──────────────────────────────────────────────────────────

def test_inject_context_forces_s_turn():
    tt = _tagged("In my company, the client specifically needs a different approach.")
    assert classify_turn(tt).is_a_turn is False


def test_override_forces_s_turn():
    tt = _tagged("No, that's wrong. Not what I asked for.")
    assert classify_turn(tt).is_a_turn is False


def test_long_request_is_s_turn():
    tt = _tagged("Please write a detailed analysis of the market landscape including competitive dynamics.")
    assert classify_turn(tt).is_a_turn is False


# ── Ratio invariant ───────────────────────────────────────────────────────────

def test_a_plus_s_equals_one():
    turns = [
        _human("ok", 0),
        _ai(1),
        _human("Write me a report on climate change.", 2),
        _ai(3),
        _human("Are you sure that's correct?", 4),
        _ai(5),
        _human("continue", 6),
    ]
    tagged = tag_turns(turns)
    ratios = compute_as_ratios(tagged)
    assert abs(ratios["a_turn_ratio"] + ratios["s_turn_ratio"] - 1.0) < 1e-9


def test_all_a_turns():
    turns = [_human("ok", 0), _ai(1), _human("continue", 2), _ai(3)]
    tagged = tag_turns(turns)
    ratios = compute_as_ratios(tagged)
    assert ratios["a_turn_ratio"] == 1.0
    assert ratios["s_turn_ratio"] == 0.0


def test_no_human_turns_returns_zero_ratio():
    turns = [_ai(0), _ai(1)]
    tagged = tag_turns(turns)
    ratios = compute_as_ratios(tagged)
    assert ratios["a_turn_ratio"] == 0.0
    assert ratios["s_turn_ratio"] == 0.0


def test_ratios_in_unit_interval():
    turns = [_human(f"Turn {i}", i) for i in range(5)]
    tagged = tag_turns(turns)
    ratios = compute_as_ratios(tagged)
    assert 0.0 <= ratios["a_turn_ratio"] <= 1.0
    assert 0.0 <= ratios["s_turn_ratio"] <= 1.0
