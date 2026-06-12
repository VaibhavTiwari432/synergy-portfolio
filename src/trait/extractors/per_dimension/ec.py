"""
src/trait/extractors/per_dimension/ec.py — EC deterministic extractor.
Leaf module (INTERFACES.md §1.3): imports ONLY from contracts/.

Deterministic EC neurons:
- EC-06 Isolated Verification Rigor — verification-marker rate over human turns
  (VERIFY intent tags are the marker source)
- EC-07 Omission Detection — probing what the AI left out, on multi-sentence turns
- EC-09 Temporal Coherence Validation — VALENCE −1 in the contract table: the
  deterministic detector fires on DEBT occurrences (confident unhedged AI claim
  followed by no verification). The reported strength is the raw debt rate;
  valence inversion is the aggregation consumer's job, NOT this module's.
"""

from __future__ import annotations

import re

from contracts.schemas import (
    CanonicalSession,
    Dimension,
    Event,
    IntentTag,
    Phase,
    TurnTags,
)

DIM = Dimension.EC

_OMISSION_RE = re.compile(
    r"\bwhat about\b|\byou (didn'?t|did not|forgot to) (mention|include|cover|address)\b"
    r"|\bwhat('?s| is) missing\b|\bdid you (consider|include|account for)\b"
    r"|\banything else (i|we) should\b|\bwhat else\b|\bleft out\b",
    re.IGNORECASE,
)
_HEDGE_RE = re.compile(
    r"\b(might|may|could|possibly|probably|perhaps|roughly|approximately|i think|"
    r"i believe|likely|unsure|not certain|it depends)\b",
    re.IGNORECASE,
)
_CONFIDENT_CLAIM_RE = re.compile(
    r"\b(is|are|was|were|will|always|never|must|exactly|definitely|certainly)\b.{0,80}\d"
    r"|\bthe (only|best|correct|right) (way|answer|approach|option)\b",
    re.IGNORECASE,
)


def _sentence_count(text: str) -> int:
    return len([s for s in re.split(r"[.!?]+", text) if s.strip()])


def extract(
    session: CanonicalSession,
    tags: list[TurnTags],
    phases: list[Phase],
    events: list[Event],
) -> dict[str, object]:
    firings: dict[str, float] = {}
    opportunities: dict[str, int] = {}
    evidence: dict[str, list[int]] = {}

    human_turns = [t for t in session.turns if t.role == "human"]
    tags_by_turn = {tt.turn_index: frozenset(tt.tags) for tt in tags}

    # EC-06 — verification-marker rate
    if human_turns:
        verify_turns = [
            t.index for t in human_turns
            if IntentTag.VERIFY in tags_by_turn.get(t.index, frozenset())
        ]
        opportunities["EC-06"] = len(human_turns)
        if verify_turns:
            firings["EC-06"] = len(verify_turns) / len(human_turns)
            evidence["EC-06"] = verify_turns

    # EC-07 — omission probing on multi-sentence human turns
    multi_sentence = [t for t in human_turns if _sentence_count(t.text) >= 2]
    if multi_sentence:
        probes = [t.index for t in multi_sentence if _OMISSION_RE.search(t.text)]
        opportunities["EC-07"] = len(multi_sentence)
        if probes:
            firings["EC-07"] = len(probes) / len(multi_sentence)
            evidence["EC-07"] = probes

    # EC-09 — confident unhedged AI claims left unverified (debt direction)
    confident_ai = [
        t.index for t in session.turns
        if t.role == "ai"
        and _CONFIDENT_CLAIM_RE.search(t.text)
        and not _HEDGE_RE.search(t.text)
    ]
    if confident_ai:
        unverified: list[int] = []
        for ai_idx in confident_ai:
            next_two_human = [
                t.index for t in session.turns if t.role == "human" and t.index > ai_idx
            ][:2]
            if not any(
                IntentTag.VERIFY in tags_by_turn.get(h, frozenset())
                for h in next_two_human
            ):
                unverified.append(ai_idx)
        opportunities["EC-09"] = len(confident_ai)
        if unverified:
            firings["EC-09"] = len(unverified) / len(confident_ai)
            evidence["EC-09"] = unverified

    return {
        "neuron_firings": firings,
        "applicable_opportunities": opportunities,
        "evidence_turns": evidence,
    }
