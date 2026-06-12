"""
src/dynamics/overlay.py — descriptive regime overlay (INTERFACES.md §2.6;
spec §5.9f). Leaf module: imports ONLY from contracts/.

RULES ONLY. Deterministic segmentation of human turns into RegimeLabel runs:
no probabilities, no inference, no smoothing — and structurally no way to
emit the CSPC-owned collapse label, because RegimeLabel simply has no such
value (accept_run is a behavioral description). CSPC remains the only owner
of state machinery in the instrument.

Per-turn rules (priority order):
1. accept_run    — the turn sits in a run of ≥2 consecutive ACCEPT_FLAT turns
2. verification  — VERIFY or SELF_AUDIT tagged
3. generative    — SCAFFOLD / INJECT_CONTEXT / DECOMPOSE / OVERRIDE tagged
4. extractive    — EXTRACT / DELEGATE / lone ACCEPT_FLAT tagged
5. drift         — PIVOT tagged, or no tags at all (no detectable task closure)
"""

from __future__ import annotations

from contracts.schemas import (
    Event,
    IntentTag,
    RegimeLabel,
    RegimeOverlay,
    Rung,
    TurnTags,
)

#: minimum consecutive flat accepts to form an accept_run segment
ACCEPT_RUN_MIN = 2

_VERIFICATION_TAGS = frozenset({IntentTag.VERIFY, IntentTag.SELF_AUDIT})
_GENERATIVE_TAGS = frozenset({
    IntentTag.SCAFFOLD, IntentTag.INJECT_CONTEXT, IntentTag.DECOMPOSE, IntentTag.OVERRIDE,
})
_EXTRACTIVE_TAGS = frozenset({IntentTag.EXTRACT, IntentTag.DELEGATE})


def _run_lengths(strip: list[RegimeLabel]) -> dict[RegimeLabel, list[int]]:
    runs: dict[RegimeLabel, list[int]] = {}
    if not strip:
        return runs
    current_label, length = strip[0], 1
    for label in strip[1:]:
        if label == current_label:
            length += 1
        else:
            runs.setdefault(current_label, []).append(length)
            current_label, length = label, 1
    runs.setdefault(current_label, []).append(length)
    return runs


def regime_overlay(events: list[Event], tags: list[TurnTags]) -> RegimeOverlay:
    ordered = sorted(tags, key=lambda tt: tt.turn_index)
    n = len(ordered)
    if n == 0:
        return RegimeOverlay(rung=Rung.MEASURABLE)

    flat = [IntentTag.ACCEPT_FLAT in tt.tags for tt in ordered]

    # mark positions inside accept runs of length >= ACCEPT_RUN_MIN
    in_accept_run = [False] * n
    start: int | None = None
    for pos, is_flat in enumerate([*flat, False]):
        if is_flat and start is None:
            start = pos
        elif not is_flat and start is not None:
            if pos - start >= ACCEPT_RUN_MIN:
                for p in range(start, pos):
                    in_accept_run[p] = True
            start = None

    strip: list[RegimeLabel] = []
    for pos, tt in enumerate(ordered):
        turn_tags = frozenset(tt.tags)
        if in_accept_run[pos]:
            strip.append(RegimeLabel.ACCEPT_RUN)
        elif turn_tags & _VERIFICATION_TAGS:
            strip.append(RegimeLabel.VERIFICATION)
        elif turn_tags & _GENERATIVE_TAGS:
            strip.append(RegimeLabel.GENERATIVE)
        elif turn_tags & _EXTRACTIVE_TAGS or IntentTag.ACCEPT_FLAT in turn_tags:
            strip.append(RegimeLabel.EXTRACTIVE)
        else:
            strip.append(RegimeLabel.DRIFT)

    occupancy = {
        label: strip.count(label) / n for label in RegimeLabel if label in strip
    }

    return RegimeOverlay(
        occupancy=occupancy,
        strip=strip,
        run_lengths=_run_lengths(strip),
        rung=Rung.MEASURABLE,
    )
