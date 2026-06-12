"""
src/trait/tagger.py — the 10-tag intent tagger (INTERFACES.md §1.1).
Leaf module: imports ONLY from contracts/. Deterministic.

One TurnTags per HUMAN turn, in turn order. A turn may carry several tags or
none (empty list — never an invented tag). ACCEPT_FLAT is exclusive: a turn
that is nothing but a bare acceptance carries exactly that tag, because a
bare "ok" is not also an extraction or a delegation.
"""

from __future__ import annotations

import re

from contracts.schemas import CanonicalSession, IntentTag, TurnTags

#: a whole turn that is a bare acceptance/continuation (exclusive tag)
_ACCEPT_FLAT_RE = re.compile(
    r"^\s*(ok(ay)?|yes|yeah|yep|sure|continue|go on|next|more|proceed|"
    r"keep going|sounds good|thanks?|thank you|great|cool|nice|perfect|"
    r"got it|do it|please continue|alright|fine|hmm+|k)"
    r"[\s.!,…]*$",
    re.IGNORECASE,
)

#: per-tag detection patterns (any match fires the tag)
_TAG_PATTERNS: dict[IntentTag, list[re.Pattern[str]]] = {
    IntentTag.VERIFY: [
        re.compile(p, re.IGNORECASE)
        for p in (
            r"\bare you (sure|certain)\b",
            r"\bis (that|this) (right|correct|true|accurate)\b",
            r"\b(double[- ]?check|cross[- ]?check|fact[- ]?check)\b",
            r"\b(verify|confirm) (that|this|it|the)\b",
            r"\bwhat('?s| is) your source\b|\bcite\b|\bcitation\b",
            r"\byou (said|claimed|wrote).{0,80}\bbut\b",
            r"\bthat('?s| is| seems) (wrong|incorrect|not right|inaccurate|outdated)\b",
            r"\b(really|actually) true\b",
            r"\bdoesn'?t (that|this) contradict\b",
            r"\bprove (it|that)\b",
        )
    ],
    IntentTag.EXTRACT: [
        re.compile(p, re.IGNORECASE)
        for p in (
            r"^\s*(what|who|when|where|which|why|how)\b.{0,200}\?",
            r"\b(explain|describe|define|clarify)\b",
            r"\b(tell|show) me\b",
            r"\bsummari[sz]e\b|\bgive me (a|the) (summary|overview|list)\b",
            r"\bwhat (is|are|was|were)\b",
        )
    ],
    IntentTag.INJECT_CONTEXT: [
        re.compile(p, re.IGNORECASE)
        for p in (
            r"\b(here is|here'?s|this is) (my|our|the)\b",
            r"\bfor (context|background|reference)\b",
            r"\b(my|our) (code|project|essay|draft|data|setup|situation|profile|resume|cv)\b",
            r"\bi('?m| am) working on\b",
            r"\bcontext\s*:",
            r"\baccording to (the|my|our)\b",
            r"```",  # pasted material
        )
    ],
    IntentTag.OVERRIDE: [
        re.compile(p, re.IGNORECASE)
        for p in (
            r"\bno[,.]? (use|do|make|try|let'?s)\b",
            r"\binstead\b",
            r"\bdon'?t (use|do|include|add)\b",
            r"\bignore (that|the previous|your)\b",
            r"\bactually[, ]+(use|do|make|let'?s|i want)\b",
            r"\bnot (that|this) way\b",
            r"\boverride\b|\bscratch that\b",
        )
    ],
    IntentTag.SELF_AUDIT: [
        re.compile(p, re.IGNORECASE)
        for p in (
            r"\bam i (wrong|right|missing|misunderstanding)\b",
            r"\b(critique|check|review|audit) my\b",
            r"\bwhat am i missing\b",
            r"\b(is|was) my (approach|reasoning|logic|understanding|assumption)s?\b",
            r"\bdid i (make a mistake|get .{0,30}wrong|mess)\b",
            r"\bpoke holes in my\b|\bwhere am i going wrong\b",
            r"\bmy (mistake|error|fault)\b",
        )
    ],
    IntentTag.DELEGATE: [
        re.compile(p, re.IGNORECASE)
        for p in (
            r"\b(write|draft|create|generate|make|build|produce|compose) (me |us |a |an |the |some )",
            r"\bdo (it|this|that) for me\b",
            r"\bcan you (write|make|create|generate|build|draft)\b",
            r"\bredo\b|\brewrite (it|the|this)\b",
            r"\bfix (it|this|the) for me\b",
        )
    ],
    IntentTag.SCAFFOLD: [
        re.compile(p, re.IGNORECASE)
        for p in (
            r"\b(use|follow|stick to) (this|the|that) (format|structure|template|style)\b",
            r"\bstep[- ]by[- ]step\b",
            r"\bconstraints?\s*:|\brequirements?\s*:",
            r"\bmust (include|contain|have|be|not)\b",
            r"\b(limit|restrict|keep) (it|this|the|your)\b",
            r"\bin the (style|format|form) of\b",
            r"\b(at most|no more than|exactly|max(imum)?) \d+\b",
            r"\bbefore (you )?(answer|start|write)[, ]",
            r"\bonly (use|include|cover)\b",
        )
    ],
    IntentTag.PIVOT: [
        re.compile(p, re.IGNORECASE)
        for p in (
            r"\b(let'?s )?(switch|change|move) (to|on|topics?|gears?)\b",
            r"\bnew (topic|question|subject)\b",
            r"\bforget (that|it|the previous)\b",
            r"\bmoving on\b",
            r"\bdifferent (question|topic|thing)\b",
            r"\bunrelated[,:]\b|\bby the way\b|\bseparately\b",
        )
    ],
    IntentTag.DECOMPOSE: [
        re.compile(p, re.IGNORECASE)
        for p in (
            r"\bbreak (this|it|that|the problem) (down|into)\b",
            r"\b(split|divide) (this|it|into)\b",
            r"\bone (at a time|by one|part at a time)\b",
            r"\b(let'?s )?(start|begin) with (the )?(first|step|part)\b",
            r"\bfirst[, ].{0,80}\bthen\b",
            r"\bstep \d\b|\bpart \d\b|\bphase \d\b",
            r"\bsub[- ]?(problems?|tasks?|questions?)\b",
        )
    ],
}


def _tags_for(text: str) -> list[IntentTag]:
    if _ACCEPT_FLAT_RE.match(text):
        return [IntentTag.ACCEPT_FLAT]
    found = [
        tag
        for tag, patterns in _TAG_PATTERNS.items()
        if any(p.search(text) for p in patterns)
    ]
    # canonical order (contracts/intent_tags.py ordering via enum definition)
    order = {tag: i for i, tag in enumerate(IntentTag)}
    return sorted(found, key=lambda t: order[t])


def tag_turns(session: CanonicalSession) -> list[TurnTags]:
    """One TurnTags per HUMAN turn, in turn order (INTERFACES.md §1.1)."""
    return [
        TurnTags(turn_index=turn.index, tags=_tags_for(turn.text))
        for turn in session.turns
        if turn.role == "human"
    ]
