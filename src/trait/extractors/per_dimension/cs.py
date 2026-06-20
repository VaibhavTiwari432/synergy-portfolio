"""
src/trait/extractors/per_dimension/cs.py — CS deterministic extractor.
Leaf module (INTERFACES.md §1.3): imports ONLY from contracts/.

The contract table defines NO deterministic neurons for CS (all 11 are
llm_judge / embedding typed), so this extractor is structurally present and
intentionally empty — CS evidence comes from the judge. Adding heuristic
firings here would put unaudited signals into a judge-owned dimension.
"""

from __future__ import annotations

from contracts.schemas import CanonicalSession, Dimension, Event, Phase, TurnTags

DIM = Dimension.CS


def extract(
    session: CanonicalSession,
    tags: list[TurnTags],
    phases: list[Phase],
    events: list[Event],
) -> dict[str, object]:
    return {"neuron_firings": {}, "applicable_opportunities": {}, "evidence_turns": {}}
