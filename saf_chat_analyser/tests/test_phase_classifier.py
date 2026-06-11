"""Tests for Stage 3 — phase_classifier."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))

from saf_chat_analyser.src.parser.transcript_parser import Turn
from saf_chat_analyser.src.tagger.intent_tagger import tag_turns
from saf_chat_analyser.src.tagger.phase_classifier import classify_phases

_ALL_PHASES = {"engage", "create", "manage", "design"}


def _turns(*contents: str) -> list:
    turns = []
    for i, c in enumerate(contents):
        role = "human" if i % 2 == 0 else "ai"
        turns.append(Turn(index=i, role=role, content=c, word_count=len(c.split())))
    return turns


# ── Sum-to-one invariant ──────────────────────────────────────────────────────

def test_phases_sum_to_one():
    turns = _turns(
        "Write a summary of this paper.",
        "Here is your summary.",
        "Are you sure that's accurate?",
        "Yes it is.",
        "In my company, the client needs something different.",
    )
    tagged = tag_turns(turns)
    dist = classify_phases(tagged)
    # Values are rounded to 4dp so allow floating-point accumulation
    assert abs(sum(dist.values()) - 1.0) < 1e-3


def test_phase_keys_complete():
    turns = _turns("Write me a report.")
    tagged = tag_turns(turns)
    dist = classify_phases(tagged)
    assert set(dist.keys()) == _ALL_PHASES


def test_no_human_turns_returns_zeros():
    ai_turns = [Turn(index=i, role="ai", content="AI says something.", word_count=3) for i in range(3)]
    tagged = tag_turns(ai_turns)
    dist = classify_phases(tagged)
    assert all(v == 0.0 for v in dist.values())


# ── Phase routing ─────────────────────────────────────────────────────────────

def test_verify_routes_to_engage():
    turns = _turns("Are you sure that's correct?")
    tagged = tag_turns(turns)
    dist = classify_phases(tagged)
    assert dist["engage"] > 0.0


def test_extract_routes_to_manage():
    turns = _turns("Write a detailed report on climate change for my team.")
    tagged = tag_turns(turns)
    dist = classify_phases(tagged)
    assert dist["manage"] > 0.0


def test_ethics_gate_routes_to_design():
    turns = _turns("Make sure to remove all personal data — GDPR compliance required.")
    tagged = tag_turns(turns)
    dist = classify_phases(tagged)
    assert dist["design"] > 0.0


def test_override_routes_to_create():
    turns = _turns("No, that's wrong — that is not what I asked for at all.")
    tagged = tag_turns(turns)
    dist = classify_phases(tagged)
    assert dist["create"] > 0.0
