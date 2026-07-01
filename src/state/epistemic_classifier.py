"""
src/state/epistemic_classifier.py — per-turn epistemic stance (INTERFACES.md §2.2).
Leaf module: imports ONLY from contracts/. Deterministic.

One E_t ∈ [−1.0, +1.0] per HUMAN turn: extractive (−1) ↔ generative (+1).
Primary signal: the intent tags' generative/extractive poles
(contracts.intent_tags). Text contributes a bounded modifier: substantial
own-content pushes generative; bare interrogatives push extractive.
Session mean and slope are computed downstream (the estimator) — this module
returns the per-turn series only.
"""

from __future__ import annotations

import re

from contracts.intent_tags import EXTRACTIVE_TAGS, GENERATIVE_TAGS
from contracts.schemas import CanonicalSession, TurnTags

#: text modifier weight (tags dominate; text nudges)
_TEXT_NUDGE = 0.2
#: a human turn this long is contributing material, not just asking
_SUBSTANTIAL_WORDS = 80

_BARE_QUESTION_RE = re.compile(r"^\s*(what|who|when|where|which|why|how)\b.{0,160}\?\s*$",
                               re.IGNORECASE | re.DOTALL)


def classify_epistemic(session: CanonicalSession, tags: list[TurnTags]) -> list[float | None]:
    """B3: returns None for turns with no tag signal and no substantial content
    (absent ≠ neutral-0.0, non-negotiable #12). Session mean/slope computed
    over assessable turns only in the estimator."""
    tags_by_turn = {tt.turn_index: frozenset(tt.tags) for tt in tags}
    series: list[float | None] = []

    for turn in session.turns:
        if turn.role != "human":
            continue
        turn_tags = tags_by_turn.get(turn.index, frozenset())
        generative = len(turn_tags & GENERATIVE_TAGS)
        extractive = len(turn_tags & EXTRACTIVE_TAGS)
        word_count = len(re.findall(r"\w+", turn.text))

        score: float | None
        if generative + extractive > 0:
            score = (generative - extractive) / (generative + extractive)
            if word_count >= _SUBSTANTIAL_WORDS:
                score += _TEXT_NUDGE
            elif _BARE_QUESTION_RE.match(turn.text):
                score -= _TEXT_NUDGE
        elif word_count >= _SUBSTANTIAL_WORDS:
            score = _TEXT_NUDGE           # substantial content, no tags: assessable as generative
        elif _BARE_QUESTION_RE.match(turn.text):
            score = -_TEXT_NUDGE          # bare question, no tags: assessable as extractive
        else:
            score = None                  # unassessable — no signal

        series.append(max(-1.0, min(1.0, score)) if score is not None else None)
    return series
