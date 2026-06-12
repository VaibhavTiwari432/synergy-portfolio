"""
src/dynamics/transitions.py — the five frozen transition-pattern metrics
(INTERFACES.md §2.5; spec §5.9d). Leaf module: imports ONLY from contracts/;
events are read via the queries surface. No new latent variables — derived
counts over the log and the tags, nothing else.

The five (frozen list):
1. verify_after_error_rate          — E-ERR answered by VERIFY within the window
2. constraint_before_generation_rate — generation requests preceded/accompanied
                                       by user constraints (SCAFFOLD/INJECT_CONTEXT)
3. prediction_before_answer_rate    — stated-expectation-before-ask; NO
                                      deterministic instrument exists at Tier 1
                                      (spontaneous predictions need MP-1, Scope
                                      B+), so the cell is permanently gated
                                      n_events=0 here — N/A, never invented
4. accept_run_max / accept_run_mean — consecutive ACCEPT_FLAT runs
5. revision_after_output_rate       — post-output human turns carrying a
                                      material-transformation directive (OVERRIDE)

Every rate is a CellGatedProb gated on MIN_EVENTS_PER_CELL (never a
probability from one event).
"""

from __future__ import annotations

from contracts.event_taxonomy import MIN_EVENTS_PER_CELL, REACTION_WINDOW_K
from contracts.schemas import (
    CellGatedProb,
    Event,
    EventType,
    IntentTag,
    Rung,
    TransitionMetrics,
    TurnTags,
)
from src.eventlog.queries import by_type, turn_of

#: tags that constitute constraint injection ahead of a generation request
_CONSTRAINT_TAGS = frozenset({IntentTag.SCAFFOLD, IntentTag.INJECT_CONTEXT})


def _gated(hits: int, total: int) -> CellGatedProb:
    if total < MIN_EVENTS_PER_CELL:
        return CellGatedProb(value=None, n_events=total)
    return CellGatedProb(value=hits / total, n_events=total)


def _accept_runs(ordered_flags: list[bool]) -> list[int]:
    runs: list[int] = []
    current = 0
    for flat in [*ordered_flags, False]:
        if flat:
            current += 1
        elif current:
            runs.append(current)
            current = 0
    return runs


def compute_transitions(events: list[Event], tags: list[TurnTags]) -> TransitionMetrics:
    ordered = sorted(tags, key=lambda tt: tt.turn_index)
    tags_by_turn = {tt.turn_index: frozenset(tt.tags) for tt in ordered}
    human_turn_order = [tt.turn_index for tt in ordered]

    # 1 — verify after error
    error_events = by_type(events, EventType.E_ERR)
    verify_hits = 0
    for event in error_events:
        origin = turn_of(event)
        if origin is None:
            continue
        window = [t for t in human_turn_order if t > origin][:REACTION_WINDOW_K]
        if any(IntentTag.VERIFY in tags_by_turn[t] for t in window):
            verify_hits += 1
    verify_after_error = _gated(verify_hits, len(error_events))

    # 2 — constraint before generation
    generation_turns = [
        t for t in human_turn_order if IntentTag.DELEGATE in tags_by_turn[t]
    ]
    constrained = 0
    for turn in generation_turns:
        same_turn = tags_by_turn[turn] & _CONSTRAINT_TAGS
        previous = [t for t in human_turn_order if t < turn][-1:]
        prior_turn = previous and (tags_by_turn[previous[0]] & _CONSTRAINT_TAGS)
        if same_turn or prior_turn:
            constrained += 1
    constraint_before_generation = _gated(constrained, len(generation_turns))

    # 3 — prediction before answer: no Tier-1 instrument (see module docstring)
    prediction_before_answer = CellGatedProb(value=None, n_events=0)

    # 4 — accept runs
    if human_turn_order:
        runs = _accept_runs(
            [IntentTag.ACCEPT_FLAT in tags_by_turn[t] for t in human_turn_order]
        )
        accept_run_max = max(runs) if runs else 0
        accept_run_mean = (sum(runs) / len(runs)) if runs else 0.0
    else:
        accept_run_max, accept_run_mean = None, None

    # 5 — revision after output: human turns after the first (each follows an
    # AI output in an alternating session) carrying OVERRIDE
    post_output_turns = human_turn_order[1:]
    revisions = sum(
        1 for t in post_output_turns if IntentTag.OVERRIDE in tags_by_turn[t]
    )
    revision_after_output = _gated(revisions, len(post_output_turns))

    return TransitionMetrics(
        verify_after_error_rate=verify_after_error,
        constraint_before_generation_rate=constraint_before_generation,
        prediction_before_answer_rate=prediction_before_answer,
        accept_run_max=accept_run_max,
        accept_run_mean=accept_run_mean,
        revision_after_output_rate=revision_after_output,
        rung=Rung.MEASURABLE,
    )
