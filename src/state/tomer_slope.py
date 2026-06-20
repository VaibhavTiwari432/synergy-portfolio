"""
src/state/tomer_slope.py — theory-of-mind signature trajectory (INTERFACES.md §2.4).
Leaf module: imports ONLY from contracts/. Deterministic.

Returns (per-human-turn ToM strengths in 0.0–1.0, fitted least-squares slope).
ToM signatures: prompts that model the AI's perspective, capabilities, or
failure modes. Slope is None for sessions with < 4 human turns —
an insufficient sample is never reported as 0.0 (non-negotiable #12).
"""

from __future__ import annotations

import re

from contracts.schemas import CanonicalSession

#: each distinct signature family found contributes this much strength
_PER_HIT = 0.34

_TOM_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in (
        # modeling the AI's knowledge boundary
        r"\byou (might|may|probably) (not )?(know|have|be aware)\b"
        r"|\b(your|the model'?s) (training|knowledge) (data|cut-?off)\b"
        r"|\bas an ai\b|\byou were trained\b",
        # anticipating failure modes
        r"\bdon'?t (hallucinat|make (things|stuff) up|invent|guess)\b"
        r"|\bif you('?re| are) (not |un)?(sure|certain)\b"
        r"|\bbe careful (not )?to\b|\byou (tend|like) to\b",
        # modeling the AI's processing/perspective
        r"\bfrom your (perspective|point of view)\b|\bhow (do|would) you interpret\b"
        r"|\byou (can'?t|cannot) (see|access|browse|remember)\b"
        r"|\bgiven (your|the) (context window|memory|limitations)\b",
    )
]


def _strength(text: str) -> float:
    hits = sum(1 for p in _TOM_PATTERNS if p.search(text))
    return min(1.0, hits * _PER_HIT)


def _least_squares_slope(values: list[float]) -> float:
    n = len(values)
    xs = range(n)
    x_mean = (n - 1) / 2
    y_mean = sum(values) / n
    denom = sum((x - x_mean) ** 2 for x in xs)
    if denom == 0:
        return 0.0
    return sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, values)) / denom


def tom_slope(session: CanonicalSession) -> tuple[list[float], float | None]:
    series = [_strength(t.text) for t in session.turns if t.role == "human"]
    if len(series) < 4:
        return series, None
    return series, _least_squares_slope(series)
