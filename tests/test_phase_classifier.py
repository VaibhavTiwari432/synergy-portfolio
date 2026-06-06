"""
Tests for tagger/phase_classifier.py — Stage 3 acceptance criteria.

Three turn sequences asserting correct phase distribution:
  1. VERIFY-heavy sequence → dominated by 'explore'
  2. OVERRIDE-heavy sequence → dominated by 'refine'
  3. Pure EXTRACT sequence → entirely 'extract'
"""

from __future__ import annotations

import pytest

from chat_classifier.schemas import TaggedTurn, Turn
from chat_classifier.tagger.phase_classifier import classify_phases


def _tagged(index: int, text: str, tags: list[str], dominant: str | None) -> TaggedTurn:
    turn = Turn(index=index, role="human", text=text)  # type: ignore[arg-type]
    return TaggedTurn(turn=turn, tags=tags, dominant_intent=dominant)  # type: ignore[arg-type]


def _ai_tagged(index: int) -> TaggedTurn:
    turn = Turn(index=index, role="ai", text="AI response.")  # type: ignore[arg-type]
    return TaggedTurn(turn=turn, tags=[], dominant_intent=None)


# ── Sequence 1: VERIFY-heavy → explore ───────────────────────────────────────

VERIFY_SEQUENCE = [
    _tagged(0, "Is that correct?", ["VERIFY"], "VERIFY"),
    _ai_tagged(1),
    _tagged(2, "Are you sure about that?", ["VERIFY"], "VERIFY"),
    _ai_tagged(3),
    _tagged(4, "Write me a summary.", ["EXTRACT"], "EXTRACT"),
    _ai_tagged(5),
]


class TestExplorePhase:
    def test_explore_is_dominant(self):
        dist = classify_phases(VERIFY_SEQUENCE)
        assert dist["explore"] > dist["extract"]
        assert dist["explore"] > dist["refine"]

    def test_explore_fraction_correct(self):
        dist = classify_phases(VERIFY_SEQUENCE)
        assert dist["explore"] == pytest.approx(2 / 3, abs=0.001)
        assert dist["extract"] == pytest.approx(1 / 3, abs=0.001)

    def test_missing_phases_are_zero(self):
        dist = classify_phases(VERIFY_SEQUENCE)
        assert dist["refine"] == 0.0
        assert dist["evaluate"] == 0.0


# ── Sequence 2: OVERRIDE-heavy → refine ──────────────────────────────────────

REFINE_SEQUENCE = [
    _tagged(0, "That's wrong.", ["OVERRIDE"], "OVERRIDE"),
    _ai_tagged(1),
    _tagged(2, "Forget that, let's try differently.", ["PIVOT"], "PIVOT"),
    _ai_tagged(3),
    _tagged(4, "Use my structure instead.", ["SCAFFOLD"], "SCAFFOLD"),
    _ai_tagged(5),
]


class TestRefinePhase:
    def test_refine_is_dominant(self):
        dist = classify_phases(REFINE_SEQUENCE)
        assert dist["refine"] == pytest.approx(1.0, abs=0.001)

    def test_other_phases_zero(self):
        dist = classify_phases(REFINE_SEQUENCE)
        assert dist["explore"] == 0.0
        assert dist["extract"] == 0.0
        assert dist["evaluate"] == 0.0


# ── Sequence 3: Pure EXTRACT → extract ───────────────────────────────────────

EXTRACT_SEQUENCE = [
    _tagged(0, "Write me a plan.", ["EXTRACT"], "EXTRACT"),
    _ai_tagged(1),
    _tagged(2, "Summarize this.", ["EXTRACT"], "EXTRACT"),
    _ai_tagged(3),
    _tagged(4, "Generate a list.", ["EXTRACT"], "EXTRACT"),
    _ai_tagged(5),
]


class TestExtractPhase:
    def test_extract_is_complete(self):
        dist = classify_phases(EXTRACT_SEQUENCE)
        assert dist["extract"] == pytest.approx(1.0, abs=0.001)

    def test_other_phases_zero(self):
        dist = classify_phases(EXTRACT_SEQUENCE)
        assert dist["explore"] == 0.0
        assert dist["refine"] == 0.0
        assert dist["evaluate"] == 0.0


# ── Edge cases ────────────────────────────────────────────────────────────────

def test_empty_sequence_returns_all_zeros():
    dist = classify_phases([])
    assert all(v == 0.0 for v in dist.values())


def test_ai_only_sequence_returns_all_zeros():
    ai_only = [_ai_tagged(0), _ai_tagged(1)]
    dist = classify_phases(ai_only)
    assert all(v == 0.0 for v in dist.values())


def test_fractions_sum_to_one():
    dist = classify_phases(VERIFY_SEQUENCE)
    assert sum(dist.values()) == pytest.approx(1.0, abs=0.001)


def test_all_phases_present_in_result():
    dist = classify_phases(VERIFY_SEQUENCE)
    assert set(dist.keys()) == {"explore", "refine", "extract", "evaluate"}
