"""
src/state/metacog_classifier.py — per-turn metacognitive mode (INTERFACES.md §2.3).
Leaf module: imports ONLY from contracts/. Deterministic.

One MetacogLabel per HUMAN turn:
- ACTIVE   — monitoring/directing: verification, self-audit, override,
  scaffolding, decomposition, context injection
- PASSIVE  — consuming without direction: extraction, delegation, untagged
- SURRENDER — an accept-run ≥ 3 consecutive ACCEPT_FLAT turns; every turn
  from the run's onset until the first non-ACCEPT_FLAT turn is SURRENDER.

SURRENDER is a CSPC construct (non-negotiable #5): it exists in this module's
output and nowhere user-facing. surrender_onset_turn = first turn index of
the FIRST qualifying run.
"""

from __future__ import annotations

from contracts.schemas import CanonicalSession, IntentTag, MetacogLabel, MetacogResult, TurnTags

#: accept-run length that constitutes metacognitive surrender (brief §3.5)
SURRENDER_RUN_LENGTH = 3

_ACTIVE_TAGS = frozenset({
    IntentTag.VERIFY,
    IntentTag.SELF_AUDIT,
    IntentTag.OVERRIDE,
    IntentTag.SCAFFOLD,
    IntentTag.DECOMPOSE,
    IntentTag.INJECT_CONTEXT,
    IntentTag.PIVOT,
})

# Tags that are evidence of passivity (not merely absence of active tags)
_PASSIVE_TAGS = frozenset({IntentTag.EXTRACT, IntentTag.DELEGATE})


def classify_metacog(session: CanonicalSession, tags: list[TurnTags]) -> MetacogResult:
    tags_by_turn = {tt.turn_index: frozenset(tt.tags) for tt in tags}
    human_indices = [t.index for t in session.turns if t.role == "human"]

    # base labels: B2 — untagged → None (absent ≠ PASSIVE, non-negotiable #12)
    labels: list[MetacogLabel | None] = []
    is_accept_flat: list[bool] = []
    for idx in human_indices:
        turn_tags = tags_by_turn.get(idx, frozenset())
        flat = IntentTag.ACCEPT_FLAT in turn_tags
        is_accept_flat.append(flat)
        if turn_tags & _ACTIVE_TAGS:
            labels.append(MetacogLabel.ACTIVE)
        elif flat or (turn_tags & _PASSIVE_TAGS):
            labels.append(MetacogLabel.PASSIVE)
        else:
            labels.append(None)  # untagged — no metacog evidence

    # surrender overlay: runs of >= SURRENDER_RUN_LENGTH consecutive flat accepts
    surrender_detected = False
    surrender_onset: int | None = None
    run_start: int | None = None
    for pos, flat in enumerate([*is_accept_flat, False]):  # sentinel closes last run
        if flat and run_start is None:
            run_start = pos
        elif not flat and run_start is not None:
            run_length = pos - run_start
            if run_length >= SURRENDER_RUN_LENGTH:
                for p in range(run_start, pos):
                    labels[p] = MetacogLabel.SURRENDER
                if not surrender_detected:
                    surrender_detected = True
                    surrender_onset = human_indices[run_start]
            run_start = None

    return MetacogResult(
        labels=labels,
        surrender_detected=surrender_detected,
        surrender_onset_turn=surrender_onset,
    )
