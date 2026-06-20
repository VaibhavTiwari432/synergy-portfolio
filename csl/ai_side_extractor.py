"""CSL Phase 2.2 — AI-side displayed-contribution extractor (orthogonal piece).

This is the *only* new extraction in CSL Track 1. The human side is a
re-projection of the existing NeuronMatrix (`projection.py`); the AI side is a
fresh, near-deterministic read over the AI turns asking, at each ACF level: how
much did the AI visibly retrieve, make sense of, direct/check, frame, judge,
make, or steer?

This is the *easy* extraction (v3.2 §2.2): the AI's output is fully displayed,
so there is no foundation inference to do. A 0.0 here is therefore an honest
reading — "the AI did not display this level" — and NOT a fabricated zero. The
absent-≠-zero rule (#12) guards *hidden human foundation*; the AI's contribution
is entirely on the transcript, so its absence is observable.

By construction `C7` (Partnership Steering) is ~0: the AI cannot orchestrate the
collaboration itself — choosing delegation, role boundaries, when to stop using
AI. That is a human act; the AI-side C7 reading is fixed at 0.0.

Output is a 7-vector `{C1: float, ..., C7: float}` on [0, 1], the AI-displayed
strength per ACF level. It feeds the ownership denominator in Phase 2.3; it never
modifies an ARI score (#2) and adds no neuron (#1).

NOTE on the `chat` type: the v3.2 spec names this `RawChat`; the implemented
canonical type is `CanonicalSession` (every extractor's input), so that is what
this takes. It reads only AI turns and calls no judge — fully deterministic.
"""

from __future__ import annotations

import re

from contracts.schemas import CanonicalSession
from csl.crosswalk import ACF_LEVELS, ACFCrosswalk

#: AI-side C7 is fixed at zero: the AI cannot orchestrate the collaboration itself.
_C7_AI_CONTRIBUTION = 0.0

#: Per-level displayed-contribution signals over AI turn text. Each level asks a
#: different question of the AI's *visible* output (mirrors the crosswalk
#: foundation_signal, read from the AI side rather than the human side).
_LEVEL_SIGNALS: dict[str, list[re.Pattern[str]]] = {
    # C1 Knowledge Sourcing — the AI retrieves / cites / supplies knowledge.
    "C1": [
        re.compile(p, re.IGNORECASE)
        for p in (
            r"https?://",
            r"\baccording to\b|\bstudies? show\b|\bresearch (shows|suggests)\b",
            r"\bthe (docs?|documentation|paper|spec|standard|manual)\b",
            r"\bis defined as\b|\brefers to\b|\bstands for\b|\bdefinition\b",
            r"\bfor (example|instance)\b|\be\.g\.\b",
            r"\bas of\b|\bcommonly\b|\btypically\b",
        )
    ],
    # C2 Sense-Making — the AI explains mechanism / causal account.
    "C2": [
        re.compile(p, re.IGNORECASE)
        for p in (
            r"\bbecause\b|\bthe reason (is|why)\b|\bthis is why\b",
            r"\bworks by\b|\bhappens when\b|\bcaused by\b|\bdue to\b",
            r"\bin other words\b|\bessentially\b|\bthat is to say\b|\bi\.e\.\b",
            r"\bthink of (it|this) as\b|\banalogy\b|\blike a\b",
            r"\bstep[- ]by[- ]step\b|\bhow it works\b",
        )
    ],
    # C3 Direction and Checking — the AI self-checks, caveats, flags limits.
    "C3": [
        re.compile(p, re.IGNORECASE)
        for p in (
            r"\bnote that\b|\bkeep in mind\b|\bbe (careful|aware)\b|\bcaveat\b",
            r"\bhowever\b|\bbut be\b|\bthat said\b|\bone caveat\b",
            r"\b(double[- ]?check|verify|confirm|test) (this|that|it|your)\b",
            r"\bi (might|may) be (wrong|mistaken)\b|\bthis (may|might|could) be (incorrect|outdated)\b",
            r"\bmake sure (to|you)\b|\bcheck (that|whether|the)\b",
            r"\blimitation(s)?\b|\bedge case(s)?\b",
        )
    ],
    # C4 Problem Framing — the AI decomposes / frames / restructures the problem.
    "C4": [
        re.compile(p, re.IGNORECASE)
        for p in (
            r"\blet'?s break (this|it) down\b|\bbreak(ing)? this into\b",
            r"\bthere are (several|two|three|four|\d+) (ways|approaches|options|steps)\b",
            r"\bthe (key|real|core|underlying) (question|problem|issue) is\b",
            r"\bwe can (think of|frame|approach) this\b|\bone way to frame\b",
            r"\bfirst[,]?\b.*\bsecond[,]?\b",
            r"\bstep 1\b|\b1\.\s|\b2\.\s",
        )
    ],
    # C5 Quality Judging — the AI evaluates / compares / weighs tradeoffs.
    "C5": [
        re.compile(p, re.IGNORECASE)
        for p in (
            r"\bpros and cons\b|\badvantages?\b|\bdisadvantages?\b|\bdrawback(s)?\b",
            r"\btrade[- ]?off(s)?\b|\bon the other hand\b|\bcompared to\b|\bversus\b|\bvs\.?\b",
            r"\bi('?d| would) recommend\b|\bthe best (option|choice|approach)\b|\bbetter to\b",
            r"\bmore (efficient|robust|reliable|maintainable)\b|\bless (efficient|reliable)\b",
            r"\bweigh\b|\bdepends on\b|\bif .* then .* otherwise\b",
        )
    ],
    # C6 Original Making — the AI generates / drafts / synthesises a new artifact.
    "C6": [
        re.compile(p, re.IGNORECASE)
        for p in (
            r"```",                                   # code/artifact block
            r"\bhere'?s (a|an|the|your|my)\b|\bhere is (a|an|the)\b",
            r"\bi('?ll| will) (write|draft|create|build|generate|design|compose)\b",
            r"\bdraft\b|\bversion 1\b|\bproposed\b",
            r"\bfunction\b|\bclass\b|\bdef \b|\bimport \b",  # generated code surface
        )
    ],
    # C7 Partnership Steering — AI cannot orchestrate itself; fixed 0 (see above).
    "C7": [],
}


def _content_ai_turns(session: CanonicalSession) -> list[str]:
    """AI turns with content-bearing text, after trivial whitespace strip."""
    return [t.text for t in session.turns if t.role == "ai" and t.text.strip()]


def _level_strength(turns: list[str], patterns: list[re.Pattern[str]]) -> float:
    """Share of AI turns that visibly display this level's contribution.

    Deterministic and bounded on [0, 1]: a turn counts once if any of the level's
    signals match (intensity within a turn is not double-counted, keeping the
    measure a clean displayed-prevalence read).
    """
    if not turns or not patterns:
        return 0.0
    hits = sum(1 for text in turns if any(p.search(text) for p in patterns))
    return round(hits / len(turns), 6)


def extract_ai_contribution(
    chat: CanonicalSession,
    crosswalk: ACFCrosswalk,
) -> dict[str, float]:
    """Return AI displayed-contribution strength per ACF level, `{C1..C7}`.

    Deterministic read over the AI turns; calls no judge, reads no human turns,
    touches no ARI score. `crosswalk` is taken to anchor the canonical C1–C7 level
    set (and keep the interface symmetric with `project_to_acf`); the per-level
    signals are AI-side displayed-behaviour patterns, not the human neuron map.
    """
    ai_turns = _content_ai_turns(chat)
    contribution: dict[str, float] = {}
    for level in ACF_LEVELS:
        if level == "C7":
            contribution[level] = _C7_AI_CONTRIBUTION
            continue
        contribution[level] = _level_strength(ai_turns, _LEVEL_SIGNALS[level])
    return contribution
