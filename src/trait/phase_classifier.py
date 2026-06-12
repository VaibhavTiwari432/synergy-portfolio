"""
src/trait/phase_classifier.py — per-turn session phase (INTERFACES.md §1.2).
Leaf module: imports ONLY from contracts/. Deterministic rules over turn text
+ intent tags.

One Phase per HUMAN turn, same length/order as the tagger output.
Priority (specific → general): EVALUATE > REFINE > EXTRACT > EXPLORE.
EXPLORE is also the default for turns that match nothing — an unclassifiable
open statement reads as exploration, never as a fabricated specific phase.
"""

from __future__ import annotations

import re

from contracts.schemas import CanonicalSession, IntentTag, Phase, TurnTags

_EVALUATE_RE = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\b(compare|assess|evaluate|judge|rate|review)\b",
        r"\bwhich (is|one'?s?) (better|best|right|correct)\b",
        r"\bpros and cons\b|\btrade[- ]?offs?\b",
        r"\bdoes (this|that|it) (hold|stand up|make sense)\b",
    )
]

_REFINE_RE = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\b(rewrite|revise|improve|polish|tweak|adjust|shorten|lengthen|tighten)\b",
        r"\bmake (it|this|that) (more|less|shorter|longer|clearer|simpler)\b",
        r"\b(fix|change|update|edit) (it|this|that|the)\b",
        r"\b(second|another|new) (draft|version|attempt|pass)\b",
        r"\binstead\b",
    )
]

_EXPLORE_RE = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\bwhat if\b|\bimagine\b|\bsuppose\b",
        r"\bbrainstorm\b|\bideas?\b|\boptions?\b|\balternatives?\b",
        r"\bcould (we|i|you)\b|\bpossibilit(y|ies)\b",
        r"\bopen[- ]ended\b|\bany (other|different) (ways?|approach)\b",
    )
]

#: tag-driven phase signals, checked in priority order
_EVALUATE_TAGS = {IntentTag.VERIFY, IntentTag.SELF_AUDIT}
_REFINE_TAGS = {IntentTag.OVERRIDE}
_EXTRACT_TAGS = {IntentTag.EXTRACT, IntentTag.DELEGATE, IntentTag.ACCEPT_FLAT}
_EXPLORE_TAGS = {IntentTag.PIVOT, IntentTag.DECOMPOSE}


#: exploratory framing that outranks iteration markers ("what if X instead?"
#: is exploration, not refinement)
_STRONG_EXPLORE_RE = re.compile(r"\bwhat if\b|\bimagine\b|\bsuppose\b|\bbrainstorm\b", re.IGNORECASE)


def _phase_for(text: str, tags: frozenset[IntentTag]) -> Phase:
    if tags & _EVALUATE_TAGS or any(p.search(text) for p in _EVALUATE_RE):
        return Phase.EVALUATE
    if _STRONG_EXPLORE_RE.search(text):
        return Phase.EXPLORE
    if tags & _REFINE_TAGS or any(p.search(text) for p in _REFINE_RE):
        return Phase.REFINE
    if tags & _EXTRACT_TAGS:
        return Phase.EXTRACT
    if tags & _EXPLORE_TAGS or any(p.search(text) for p in _EXPLORE_RE):
        return Phase.EXPLORE
    if "?" in text:
        return Phase.EXTRACT  # an unmatched question is an ask
    return Phase.EXPLORE


def classify_phases(session: CanonicalSession, tags: list[TurnTags]) -> list[Phase]:
    """One Phase per HUMAN turn, in turn order (INTERFACES.md §1.2)."""
    tags_by_turn = {tt.turn_index: frozenset(tt.tags) for tt in tags}
    return [
        _phase_for(turn.text, tags_by_turn.get(turn.index, frozenset()))
        for turn in session.turns
        if turn.role == "human"
    ]
