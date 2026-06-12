"""
src/trait/extractors/per_dimension/al.py — AL deterministic extractor.
Leaf module (INTERFACES.md §1.3): imports ONLY from contracts/.

Deterministic AL neuron: AL-08 (Training Data Recency Sensitivity) — the
human flags time-indexed AI claims for verification. Opportunity = an AI turn
making a temporal claim; firing = a following human turn raising recency /
knowledge-cutoff concerns. Strength = flagged opportunities ÷ opportunities.
"""

from __future__ import annotations

import re

from contracts.schemas import CanonicalSession, Dimension, Event, Phase, TurnTags

DIM = Dimension.AL

_TEMPORAL_CLAIM_RE = re.compile(
    r"\bas of (20\d\d|now|today)\b|\b(currently|recently|this year|latest|newest)\b"
    r"|\b20(2[4-9]|3\d)\b",
    re.IGNORECASE,
)
_RECENCY_FLAG_RE = re.compile(
    r"\b(knowledge|training) (cut-?off|data)\b|\bout-?dated\b|\bis (that|this) still\b"
    r"|\bas of when\b|\bup[- ]to[- ]date\b|\bmight have changed\b|\bcheck (the|for) (latest|current)\b",
    re.IGNORECASE,
)


def extract(
    session: CanonicalSession,
    tags: list[TurnTags],
    phases: list[Phase],
    events: list[Event],
) -> dict[str, object]:
    firings: dict[str, float] = {}
    opportunities: dict[str, int] = {}
    evidence: dict[str, list[int]] = {}

    temporal_ai_turns = [
        t.index for t in session.turns if t.role == "ai" and _TEMPORAL_CLAIM_RE.search(t.text)
    ]
    if temporal_ai_turns:
        flagged: list[int] = []
        human_after = lambda idx: [  # noqa: E731 — next 2 human turns after idx
            t for t in session.turns if t.role == "human" and t.index > idx
        ][:2]
        for ai_idx in temporal_ai_turns:
            for human_turn in human_after(ai_idx):
                if _RECENCY_FLAG_RE.search(human_turn.text):
                    flagged.append(human_turn.index)
                    break
        opportunities["AL-08"] = len(temporal_ai_turns)
        if flagged:
            firings["AL-08"] = min(1.0, len(flagged) / len(temporal_ai_turns))
            evidence["AL-08"] = flagged
        # zero flags with opportunities present: no firing key (absent ≠ zero
        # only applies to evidence absence; here opportunity existed and the
        # behavior provably did not occur — the consumer reads 0-of-N from
        # opportunities without a firing entry)

    return {
        "neuron_firings": firings,
        "applicable_opportunities": opportunities,
        "evidence_turns": evidence,
    }
