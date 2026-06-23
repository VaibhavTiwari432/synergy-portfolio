"""
src/trait/grounding.py - conversational-grounding function classifier.
Leaf module: imports ONLY from contracts/. Deterministic.

One GroundingFunction per HUMAN turn, in turn order. These labels are precision
conditioners for later EC/CA evidence handling; they never change a score value.
"""

from __future__ import annotations

import re

from contracts.schemas import CanonicalSession, GroundingFunction, IntentTag, TurnTags

_REPAIR_RE = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\byou (said|claimed|wrote|missed|forgot).{0,80}\bbut\b",
        r"\bthat('?s| is| seems) (wrong|incorrect|not right|inaccurate|outdated)\b",
        r"\bthis (contradicts|conflicts with|doesn'?t match)\b",
        r"\bdoesn'?t (that|this|it) contradict\b",
        r"\b(no|actually)[, ]+.{0,80}\b(use|make|do|should|needs?|instead)\b",
        r"\b(correct|fix|repair|revise|update) (that|this|it|your)\b",
        r"\bwhat do you mean\b|\bclarify (that|this|your)\b",
        r"\bcan you clarify\b|\bcould you clarify\b",
    )
]

_GROUNDING_RE = re.compile(
    r"^\s*(ok(ay)?|yes|yeah|yep|sure|got it|understood|makes sense|"
    r"that makes sense|that answers it|sounds good|thanks?|thank you|"
    r"great|cool|perfect|alright|fine)"
    r"[\s.!,]*$",
    re.IGNORECASE,
)

_INITIATION_RE = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\b(for context|background|new topic|different question|separately)\b",
        r"\b(can you|could you|please) (explain|show|write|make|build|summari[sz]e)\b",
        r"\b(let'?s|we should|i want to|i need to)\b",
        r"\b(requirements?|constraints?)\s*:",
        r"^\s*(what|who|when|where|which|why|how)\b",
    )
]

_INITIATION_TAGS = {
    IntentTag.EXTRACT,
    IntentTag.INJECT_CONTEXT,
    IntentTag.DELEGATE,
    IntentTag.SCAFFOLD,
    IntentTag.PIVOT,
    IntentTag.DECOMPOSE,
}


def _grounding_for(text: str, tags: frozenset[IntentTag]) -> GroundingFunction:
    if IntentTag.VERIFY in tags or IntentTag.OVERRIDE in tags:
        return GroundingFunction.REPAIR
    if any(pattern.search(text) for pattern in _REPAIR_RE):
        return GroundingFunction.REPAIR
    if IntentTag.ACCEPT_FLAT in tags or _GROUNDING_RE.match(text):
        return GroundingFunction.GROUNDING
    if tags & _INITIATION_TAGS or any(pattern.search(text) for pattern in _INITIATION_RE):
        return GroundingFunction.INITIATION
    return GroundingFunction.NONE


def classify_grounding(
    session: CanonicalSession,
    tags: list[TurnTags],
) -> list[GroundingFunction]:
    """One GroundingFunction per HUMAN turn, in turn order."""
    tags_by_turn = {turn_tags.turn_index: frozenset(turn_tags.tags) for turn_tags in tags}
    return [
        _grounding_for(turn.text, tags_by_turn.get(turn.index, frozenset()))
        for turn in session.turns
        if turn.role == "human"
    ]
