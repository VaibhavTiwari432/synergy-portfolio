"""
src/trait/extractors/per_dimension/cd.py — CD deterministic extractor.
Leaf module (INTERFACES.md §1.3): imports ONLY from contracts/.

The contract table defines NO deterministic neurons for CD (semantic-distance
neurons are embedding-typed; the rest are judge-typed), so this extractor is
structurally present and intentionally empty.
"""

from __future__ import annotations

from contracts.schemas import CanonicalSession, Dimension, Event, Phase, TurnTags

DIM = Dimension.CD


def extract(
    session: CanonicalSession,
    tags: list[TurnTags],
    phases: list[Phase],
    events: list[Event],
) -> dict[str, object]:
    return {"neuron_firings": {}, "applicable_opportunities": {}, "evidence_turns": {}}
