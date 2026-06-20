"""
src/sustainability/ewma.py — debt EWMA over session history.
OWNER: Chief Engineer. (Brief §3.9.)

Input: a chronological per-session healthy-engagement series (0–1; e.g. the
generative-vs-extractive balance mapped to [0,1]). α = 0.3. Modes:
- erosion     — the smoothed signal declines materially over the history
- flat_floor  — the signal never rose above the floor (never built, not lost)
- none        — neither pattern
- INSUFFICIENT_HISTORY — fewer than 2 sessions; a single session is NEVER a
  debt signal (non-negotiables #7, #12).
"""

from __future__ import annotations

from contracts.schemas import DebtEwma, DebtMode, Rung

ALPHA = 0.3
#: smoothed decline this large (absolute, on the 0–1 scale) reads as erosion
EROSION_DROP = 0.10
#: a history that never smooths above this floor was never built
FLAT_FLOOR = 0.30


def ewma_series(values: list[float], alpha: float = ALPHA) -> list[float]:
    smoothed: list[float] = []
    for v in values:
        smoothed.append(v if not smoothed else alpha * v + (1 - alpha) * smoothed[-1])
    return smoothed


def debt_ewma(history: list[float], alpha: float = ALPHA) -> DebtEwma:
    """history: per-session signals, oldest first, current session last."""
    n = len(history)
    if n < 2:
        return DebtEwma(
            mode=DebtMode.INSUFFICIENT_HISTORY,
            value=None,
            alpha=alpha,
            n_sessions=n,
            rung=Rung.MEASURABLE,
        )

    smoothed = ewma_series(history, alpha)
    current = smoothed[-1]
    peak = max(smoothed)

    if peak <= FLAT_FLOOR:
        mode = DebtMode.FLAT_FLOOR
    elif (peak - current) >= EROSION_DROP and smoothed[-1] < smoothed[0]:
        mode = DebtMode.EROSION
    else:
        mode = DebtMode.NONE

    return DebtEwma(
        mode=mode, value=current, alpha=alpha, n_sessions=n, rung=Rung.MEASURABLE
    )
