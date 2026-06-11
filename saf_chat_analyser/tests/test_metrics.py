"""Tests for Stage 4 — composite_metrics."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))

from saf_chat_analyser.src.parser.transcript_parser import Turn
from saf_chat_analyser.src.tagger.intent_tagger import tag_turns
from saf_chat_analyser.src.metrics.composite_metrics import CompositeMetrics, compute_metrics


def _make_turns(*contents: str) -> list[Turn]:
    turns = []
    for i, c in enumerate(contents):
        role = "human" if i % 2 == 0 else "ai"
        turns.append(Turn(index=i, role=role, content=c, word_count=len(c.split())))
    return turns


# ── A/S ratio invariant ───────────────────────────────────────────────────────

def test_as_ratio_sums_to_one():
    turns = _make_turns(
        "Write a report on climate.",
        "Here it is.",
        "Are you sure that is correct?",
        "Yes.",
        "ok",
        "Great.",
        "In my company we need something different — GDPR applies.",
    )
    tagged = tag_turns(turns)
    m = compute_metrics(turns, tagged)
    assert abs(m.a_turn_ratio + m.s_turn_ratio - 1.0) < 1e-9


def test_as_ratios_in_unit_interval():
    turns = _make_turns("Write a summary.", "Here you go.", "continue", "Noted.")
    tagged = tag_turns(turns)
    m = compute_metrics(turns, tagged)
    assert 0.0 <= m.a_turn_ratio <= 1.0
    assert 0.0 <= m.s_turn_ratio <= 1.0


# ── Phase distribution invariant ─────────────────────────────────────────────

def test_phase_distribution_sums_to_one():
    turns = _make_turns(
        "Write a report.",
        "Here it is.",
        "Are you sure?",
        "Yes.",
        "Remove all personal data — GDPR.",
    )
    tagged = tag_turns(turns)
    m = compute_metrics(turns, tagged)
    # Values are rounded to 4dp so allow floating-point accumulation
    assert abs(sum(m.phase_distribution.values()) - 1.0) < 1e-3


def test_phase_distribution_has_four_keys():
    turns = _make_turns("Write something.", "Here you go.")
    tagged = tag_turns(turns)
    m = compute_metrics(turns, tagged)
    assert set(m.phase_distribution.keys()) == {"engage", "create", "manage", "design"}


# ── Verification ratio ────────────────────────────────────────────────────────

def test_verification_ratio_zero_when_no_verify():
    turns = _make_turns("Write a report.", "Here.", "Write another.", "Done.")
    tagged = tag_turns(turns)
    m = compute_metrics(turns, tagged)
    assert m.verification_ratio is None or m.verification_ratio == 0.0


def test_verification_ratio_positive_when_verify_present():
    turns = _make_turns(
        "Write a report.",
        "Here it is.",
        "Are you sure that's accurate?",
        "Yes.",
    )
    tagged = tag_turns(turns)
    m = compute_metrics(turns, tagged)
    assert m.verification_ratio is not None
    assert m.verification_ratio > 0.0


# ── Session turns ─────────────────────────────────────────────────────────────

def test_session_turns_counts_all():
    turns = _make_turns("First.", "Second.", "Third.")
    tagged = tag_turns(turns)
    m = compute_metrics(turns, tagged)
    assert m.session_turns == 3


# ── Metrics dataclass completeness ───────────────────────────────────────────

def test_metrics_has_expected_fields():
    turns = _make_turns("Write a report.", "Here.", "ok", "Good.")
    tagged = tag_turns(turns)
    m = compute_metrics(turns, tagged)
    assert hasattr(m, "attribution_gap")
    assert hasattr(m, "verification_ratio")
    assert hasattr(m, "generative_query_ratio")
    assert hasattr(m, "actualization_depth")
    assert hasattr(m, "iteration_depth")
    assert hasattr(m, "semantic_distance_delta")
    assert hasattr(m, "vr_first_half")
    assert hasattr(m, "vr_second_half")
