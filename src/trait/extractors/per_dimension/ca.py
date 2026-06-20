"""
src/trait/extractors/per_dimension/ca.py — CA deterministic extractor.
Leaf module (INTERFACES.md §1.3): imports ONLY from contracts/.

The contract table defines NO deterministic neurons for CA. SELF_AUDIT
presence (the brief's CA hint) reaches the judge as tag context and CA-17
vigilance is a judge rubric rule — neither is a contract-table deterministic
neuron, so nothing fires here. Structurally present, intentionally empty.
"""

from __future__ import annotations

from contracts.schemas import CanonicalSession, Dimension, Event, Phase, TurnTags

DIM = Dimension.CA


def extract(
    session: CanonicalSession,
    tags: list[TurnTags],
    phases: list[Phase],
    events: list[Event],
) -> dict[str, object]:
    return {"neuron_firings": {}, "applicable_opportunities": {}, "evidence_turns": {}}
