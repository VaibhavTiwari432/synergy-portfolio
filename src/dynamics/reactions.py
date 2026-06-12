"""
src/dynamics/reactions.py — E→R reaction signatures. OWNER: Chief Engineer.
(Spec §5.9c; brief §3.8.)

For each trigger event, classify the first substantive human response within
the reaction window into a ResponseClass, then estimate π(r|e) with Dirichlet
partial pooling toward a uniform prior. EVERY (e, r) cell is gated on event
count: fewer than MIN_EVENTS_PER_CELL occurrences of e → value None — never a
probability from one event. The flagship slice is the Friction Transition
Matrix. Events are state-channel observables, responses are trait-channel
behaviors; conditioning the second on the first preserves the partition — no
new latent variables (the no-latent-variable audit greps this module).
"""

from __future__ import annotations

from collections import Counter

from contracts.event_taxonomy import (
    MIN_EVENTS_PER_CELL,
    REACTION_WINDOW_K,
    TRIGGER_EVENTS,
)
from contracts.schemas import (
    CellGatedProb,
    Event,
    EventType,
    FrictionTransitionMatrix,
    IntentTag,
    ReactionSignatures,
    ResponseClass,
    Rung,
    TransitionMetrics,
    TurnTags,
)
from src.eventlog.queries import turn_of

#: Dirichlet pooling strength: pseudo-counts spread uniformly over classes.
#: With few events the estimate stays near uniform; data dominates as n grows.
DIRICHLET_ALPHA = 1.0

#: intent tags → response class, in priority order (first match wins)
_TAG_TO_CLASS: list[tuple[IntentTag, ResponseClass]] = [
    (IntentTag.VERIFY, ResponseClass.VERIFY_CHALLENGE),
    (IntentTag.OVERRIDE, ResponseClass.VERIFY_CHALLENGE),
    (IntentTag.INJECT_CONTEXT, ResponseClass.SYNTHESIZE),
    (IntentTag.SCAFFOLD, ResponseClass.CONSTRAIN),
    (IntentTag.DECOMPOSE, ResponseClass.CONSTRAIN),
    (IntentTag.PIVOT, ResponseClass.DISENGAGE),
    (IntentTag.DELEGATE, ResponseClass.DELEGATE_MORE),
    (IntentTag.ACCEPT_FLAT, ResponseClass.ACCEPT_FLAT),
    (IntentTag.EXTRACT, ResponseClass.DELEGATE_MORE),
]


def classify_response(tags: frozenset[IntentTag]) -> ResponseClass | None:
    """Map a human turn's intent tags to its response class (None = untagged)."""
    for tag, cls in _TAG_TO_CLASS:
        if tag in tags:
            return cls
    return None


def _first_response(
    event: Event,
    human_turn_order: list[int],
    tags_by_turn: dict[int, frozenset[IntentTag]],
) -> ResponseClass | None:
    """First classifiable human response within REACTION_WINDOW_K human turns
    strictly after the event's evidence turn."""
    origin = turn_of(event)
    if origin is None:
        return None
    following = [t for t in human_turn_order if t > origin][:REACTION_WINDOW_K]
    for turn_index in following:
        cls = classify_response(tags_by_turn.get(turn_index, frozenset()))
        if cls is not None:
            return cls
    return None


def _pooled_cell(count: int, total: int, n_classes: int) -> float:
    """Dirichlet posterior mean with uniform prior (partial pooling)."""
    return (count + DIRICHLET_ALPHA) / (total + DIRICHLET_ALPHA * n_classes)


def compute_reactions(
    events: list[Event],
    tags: list[TurnTags],
    transition_metrics: TransitionMetrics,
) -> ReactionSignatures:
    human_turn_order = sorted(tt.turn_index for tt in tags)
    tags_by_turn = {tt.turn_index: frozenset(tt.tags) for tt in tags}
    n_classes = len(ResponseClass)

    # observed (event, response) counts
    response_counts: dict[EventType, Counter[ResponseClass]] = {
        e: Counter() for e in TRIGGER_EVENTS
    }
    event_totals: Counter[EventType] = Counter()
    for event in events:
        if event.event_type not in TRIGGER_EVENTS:
            continue
        response = _first_response(event, human_turn_order, tags_by_turn)
        if response is None:
            continue  # no classifiable response in window — not a cell observation
        event_totals[event.event_type] += 1
        response_counts[event.event_type][response] += 1

    pi: dict[EventType, dict[ResponseClass, CellGatedProb]] = {}
    for event_type in TRIGGER_EVENTS:
        total = event_totals[event_type]
        row: dict[ResponseClass, CellGatedProb] = {}
        for cls in ResponseClass:
            if total < MIN_EVENTS_PER_CELL:
                row[cls] = CellGatedProb(value=None, n_events=total)
            else:
                row[cls] = CellGatedProb(
                    value=_pooled_cell(response_counts[event_type][cls], total, n_classes),
                    n_events=total,
                )
        pi[event_type] = row

    friction = pi[EventType.E_FRICTION]
    ftm = FrictionTransitionMatrix(
        p_verify=friction[ResponseClass.VERIFY_CHALLENGE],
        p_accept_flat=friction[ResponseClass.ACCEPT_FLAT],
        p_disengage=friction[ResponseClass.DISENGAGE],
        rung=Rung.MEASURABLE,
    )

    return ReactionSignatures(
        pi=pi,
        ftm=ftm,
        transition_metrics=transition_metrics,
        rung=Rung.MEASURABLE,
    )
