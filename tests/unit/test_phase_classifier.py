"""Unit tests for the phase classifier (leaf)."""

from __future__ import annotations

import pytest

from contracts.schemas import CanonicalSession, PartnerModel, Phase, Turn
from src.trait.phase_classifier import classify_phases
from src.trait.tagger import tag_turns


def _session(human_texts: list[str]) -> CanonicalSession:
    turns: list[Turn] = []
    for text in human_texts:
        turns.append(Turn(index=len(turns), role="human", text=text))
        turns.append(Turn(index=len(turns), role="ai", text="reply"))
    return CanonicalSession(
        session_id="ph-1", source="plaintext",
        partner_model=PartnerModel(family="openai"), turns=turns,
    )


def _phase_of(text: str) -> Phase:
    s = _session([text])
    return classify_phases(s, tag_turns(s))[0]


def test_output_aligned_with_human_turns():
    s = _session(["what is X?", "ok", "rewrite it"])
    phases = classify_phases(s, tag_turns(s))
    assert len(phases) == 3


@pytest.mark.parametrize("text,phase", [
    ("are you sure that's right?", Phase.EVALUATE),
    ("compare these two approaches", Phase.EVALUATE),
    ("critique my reasoning", Phase.EVALUATE),
    ("what are the trade-offs here?", Phase.EVALUATE),
    ("rewrite the intro, make it shorter", Phase.REFINE),
    ("no, use the other framing instead", Phase.REFINE),
    ("fix the second paragraph", Phase.REFINE),
    ("what is a monad?", Phase.EXTRACT),
    ("write me a summary of this paper", Phase.EXTRACT),
    ("ok", Phase.EXTRACT),  # flat acceptance consumes more output
    ("what if we targeted schools instead of parents?", Phase.EXPLORE),
    ("brainstorm some campaign ideas", Phase.EXPLORE),
    ("let's switch to the budget", Phase.EXPLORE),
    ("random statement with no signal", Phase.EXPLORE),  # default
])
def test_phase_rules(text: str, phase: Phase):
    assert _phase_of(text) == phase


def test_evaluate_beats_refine_when_both_present():
    # "rewrite" (refine) + "are you sure" (evaluate) → EVALUATE wins
    assert _phase_of("are you sure? rewrite it if not") == Phase.EVALUATE


def test_unmatched_question_is_extract():
    assert _phase_of("hmm, where does the money go?") == Phase.EXTRACT


def test_deterministic():
    s = _session(["what if we tried X?", "ok", "is that correct?"])
    t = tag_turns(s)
    assert classify_phases(s, t) == classify_phases(s, t)
