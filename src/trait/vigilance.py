"""
src/trait/vigilance.py - session-level epistemic-vigilance pattern.
Leaf module: imports ONLY from contracts/. Deterministic.

The score is an evidence-precision conditioner for EC/CA, never a score
multiplier or a new ontology item.
"""

from __future__ import annotations

import re

from contracts.schemas import CanonicalSession, IntentTag, Turn, TurnTags, VigilanceResult

_JUSTIFICATION_RE = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\bwhy\b.{0,80}\b(true|correct|right|safe|valid|works?)\b",
        r"\bhow do you know\b|\bhow can (we|i) know\b",
        r"\b(show|explain) (your )?(reasoning|work|evidence)\b",
        r"\bjustify (that|this|it|your)\b",
        r"\bwhat('?s| is) the rationale\b",
        r"\bprove (it|that)\b",
    )
]

_SOURCE_RE = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\b(source|sources|citation|citations|cite|reference|references)\b",
        r"\bwhere did (that|this|it) come from\b",
        r"\bwhere are you getting\b",
        r"\b(check|compare) (the|against) (docs|documentation|paper|study|spec)\b",
        r"\baccording to (the|my|our)\b",
    )
]

_PRIOR_RE = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\bi (think|believe|thought|expected|understand|understood)\b",
        r"\bmy understanding is\b|\bas far as i know\b",
        r"\bthe (docs|spec|paper|study) (say|says|show|shows)\b",
        r"\baccording to (the|my|our)\b",
    )
]

_CHALLENGE_RE = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\byou (said|claimed|wrote).{0,80}\bbut\b",
        r"\bthat('?s| is| seems) (wrong|incorrect|not right|inaccurate|outdated)\b",
        r"\bdoesn'?t (that|this|it) contradict\b",
        r"\bwait[, ]+.{0,80}\b(no|why|how|is that)\b",
    )
]

_ACCEPT_RE = re.compile(
    r"^\s*(ok(ay)?|yes|yeah|yep|sure|got it|understood|makes sense|"
    r"that makes sense|sounds good|thanks?|thank you|great|cool|perfect|"
    r"alright|fine)"
    r"[\s.!,]*$",
    re.IGNORECASE,
)


def _matches(text: str, patterns: list[re.Pattern[str]]) -> bool:
    return any(pattern.search(text) for pattern in patterns)


def _has_later_accept(
    human_turns: list[Turn],
    tags_by_turn: dict[int, frozenset[IntentTag]],
    start_position: int,
) -> bool:
    for turn in human_turns[start_position + 1:]:
        tags = tags_by_turn.get(turn.index, frozenset())
        if IntentTag.ACCEPT_FLAT in tags or _ACCEPT_RE.match(turn.text):
            return True
    return False


def score_vigilance(
    session: CanonicalSession,
    tags: list[TurnTags],
) -> VigilanceResult:
    """Return a bounded session-level vigilance signal."""
    human_turns = [turn for turn in session.turns if turn.role == "human"]
    tags_by_turn = {turn_tags.turn_index: frozenset(turn_tags.tags) for turn_tags in tags}

    n_signals = 0
    signal_turns: set[int] = set()
    has_sequence_signal = False

    for position, turn in enumerate(human_turns):
        turn_tags = tags_by_turn.get(turn.index, frozenset())
        text = turn.text

        justification = IntentTag.VERIFY in turn_tags or _matches(text, _JUSTIFICATION_RE)
        source_probe = _matches(text, _SOURCE_RE)
        prior_before_accept = _matches(text, _PRIOR_RE) and _has_later_accept(
            human_turns, tags_by_turn, position
        )
        challenge_then_accept = (
            IntentTag.VERIFY in turn_tags or _matches(text, _CHALLENGE_RE)
        ) and _has_later_accept(human_turns, tags_by_turn, position)

        turn_signals = [
            justification,
            source_probe,
            prior_before_accept,
            challenge_then_accept,
        ]
        count = sum(1 for signal in turn_signals if signal)
        if count:
            n_signals += count
            signal_turns.add(turn.index)
        if prior_before_accept or challenge_then_accept:
            has_sequence_signal = True

    score = min(1.0, n_signals / 4.0)
    pattern_detected = n_signals >= 2 and (len(signal_turns) >= 2 or has_sequence_signal)
    return VigilanceResult(
        score=score,
        n_signals=n_signals,
        pattern_detected=pattern_detected,
    )
