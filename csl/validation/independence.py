"""ARI-vs-CSL partition check for v3.2.

Near-perfect correlation means CSL is probably re-measuring ARI instead of
providing a distinct ownership view.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from typing import Mapping


@dataclass(frozen=True)
class CorrelationResult:
    ari_key: str
    csl_key: str
    n: int
    correlation: float | None
    flag_if_near_one: bool


@dataclass(frozen=True)
class IndependenceResult:
    per_pair: tuple[CorrelationResult, ...]
    flagged: tuple[CorrelationResult, ...]
    near_one_threshold: float
    min_n: int


def _as_float(value: object) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if numeric != numeric:  # NaN
        return None
    return numeric


def _pearson(xs: list[float], ys: list[float]) -> float | None:
    n = len(xs)
    if n == 0 or n != len(ys):
        return None
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    dx = [x - mean_x for x in xs]
    dy = [y - mean_y for y in ys]
    denom_x = sum(x * x for x in dx)
    denom_y = sum(y * y for y in dy)
    if denom_x == 0 or denom_y == 0:
        return None
    return sum(x * y for x, y in zip(dx, dy)) / sqrt(denom_x * denom_y)


def independence(
    ari_scores: list[Mapping[str, object]],
    csl_shares: list[Mapping[str, object]],
    *,
    near_one_threshold: float = 0.95,
    min_n: int = 8,
) -> IndependenceResult:
    """Compute the pre-registered ARI-vs-CSL independence sanity check.

    Inputs are aligned session rows. Missing and nonnumeric values are dropped
    pairwise; they are never coerced to zero.
    """
    if len(ari_scores) != len(csl_shares):
        raise ValueError("ari_scores and csl_shares must have the same session count")
    if not 0.0 < near_one_threshold <= 1.0:
        raise ValueError("near_one_threshold must be in (0, 1]")
    if min_n < 2:
        raise ValueError("min_n must be at least 2")

    ari_keys = sorted({key for row in ari_scores for key in row})
    csl_keys = sorted({key for row in csl_shares for key in row})
    results: list[CorrelationResult] = []

    for ari_key in ari_keys:
        for csl_key in csl_keys:
            xs: list[float] = []
            ys: list[float] = []
            for ari_row, csl_row in zip(ari_scores, csl_shares):
                x = _as_float(ari_row.get(ari_key))
                y = _as_float(csl_row.get(csl_key))
                if x is None or y is None:
                    continue
                xs.append(x)
                ys.append(y)

            corr = _pearson(xs, ys) if len(xs) >= min_n else None
            flagged = corr is not None and abs(corr) >= near_one_threshold
            results.append(
                CorrelationResult(
                    ari_key=ari_key,
                    csl_key=csl_key,
                    n=len(xs),
                    correlation=corr,
                    flag_if_near_one=flagged,
                )
            )

    flagged_results = tuple(result for result in results if result.flag_if_near_one)
    return IndependenceResult(
        per_pair=tuple(results),
        flagged=flagged_results,
        near_one_threshold=near_one_threshold,
        min_n=min_n,
    )

