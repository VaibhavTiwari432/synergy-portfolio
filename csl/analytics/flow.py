"""CSL Phase 2.5 — cognitive flow (sequence structure, NOT a score).

`cognitive_flow` returns the ordered cognitive-move transition graph over a
session: which human cognitive moves followed which. It is a structure, never a
scalar — there is no "flow score" (v3.2 §2.5 acceptance: "flow returns a
transition graph, not a score").

The cognitive moves are the existing frozen intent tags (the canonical
per-human-turn move vocabulary, `src/trait/tagger`). This reuses the existing
deterministic ARI tagger — it is NOT a new CSL extraction over the transcript.
"""

from __future__ import annotations

from dataclasses import dataclass

from contracts.schemas import CanonicalSession
from src.trait.tagger import tag_turns


@dataclass(frozen=True)
class FlowEdge:
    """One observed ordered transition between two cognitive moves."""

    from_move: str
    to_move: str
    count: int


@dataclass(frozen=True)
class FlowGraph:
    """A cognitive-move transition graph. No score, no ranking.

    `nodes` are the move types observed (in stable sorted order); `edges` are the
    counted transitions between consecutive tagged human turns; `move_sequence` is
    the ordered per-turn move sets for transparency.
    """

    nodes: tuple[str, ...]
    edges: tuple[FlowEdge, ...]
    move_sequence: tuple[tuple[int, tuple[str, ...]], ...]


def cognitive_flow(chat: CanonicalSession) -> FlowGraph:
    """Build the cognitive-move transition graph for a session.

    A human turn may carry several moves; a transition is drawn from every move on
    turn t to every move on the next tagged turn t+1. Untagged turns contribute no
    nodes or edges (absent ≠ a move).
    """
    tagged = [
        (tt.turn_index, tuple(tag.value for tag in tt.tags))
        for tt in tag_turns(chat)
        if tt.tags
    ]

    nodes: set[str] = set()
    edge_counts: dict[tuple[str, str], int] = {}

    for _, moves in tagged:
        nodes.update(moves)

    for (_, moves_a), (_, moves_b) in zip(tagged, tagged[1:]):
        for a in moves_a:
            for b in moves_b:
                edge_counts[(a, b)] = edge_counts.get((a, b), 0) + 1

    edges = tuple(
        FlowEdge(from_move=a, to_move=b, count=count)
        for (a, b), count in sorted(edge_counts.items())
    )
    return FlowGraph(
        nodes=tuple(sorted(nodes)),
        edges=edges,
        move_sequence=tuple(tagged),
    )
