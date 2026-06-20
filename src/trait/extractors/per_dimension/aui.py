"""
src/trait/extractors/per_dimension/aui.py — AUI deterministic extractor.
Leaf module (INTERFACES.md §1.3): imports ONLY from contracts/.

The contract table defines NO deterministic neurons for AUI. The accept-run
signal the brief mentions for AUI flows through dynamics/transitions.py
(accept_run_max/mean) into the flags block — not through neuron firings, so
it is not duplicated here. Structurally present, intentionally empty.
"""

from __future__ import annotations

from contracts.schemas import CanonicalSession, Dimension, Event, Phase, TurnTags

DIM = Dimension.AUI


def extract(
    session: CanonicalSession,
    tags: list[TurnTags],
    phases: list[Phase],
    events: list[Event],
) -> dict[str, object]:
    return {"neuron_firings": {}, "applicable_opportunities": {}, "evidence_turns": {}}
