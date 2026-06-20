"""CSL Phase 3.1 — independence-check wiring over real score rows (data-gated).

The pure statistic lives in `independence.py`. This harness assembles the aligned
per-session rows it needs — ARI dimension scores vs CSL ownership shares — and
GATES the run on corpus size: below `MIN_SESSIONS` aligned sessions it raises a
loud `CorpusInsufficientError` rather than returning a quietly-null result.

The distinction is deliberate:
  - `independence()` degrades gracefully (correlation None) when a single pair is
    thin — that is a per-pair sample guard;
  - this harness fails LOUD when the whole corpus is too small to run the check at
    all — that is the data gate. It is dormant until the corpus exists, and it
    never fits anything on the n=26 pilot (addendum #2/#3).

Inputs are already-computed outputs: one (ARI profile, CSL ownership) pair per
session. Only OK scores/levels contribute a value; absent ≠ zero (#12), so missing
and non-OK entries are simply not added to the row (independence drops them
pairwise).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from contracts.schemas import Dimension, DimensionScore, ScoreStatus
from csl.ownership import OwnershipResult
from csl.validation.errors import CorpusInsufficientError
from csl.validation.independence import IndependenceResult, independence

#: pre-registered corpus gate: the minimum aligned sessions to run the check.
#: Matches `independence(min_n=8)` — fewer rows cannot support a correlation.
MIN_SESSIONS = 8
GATE_NAME = "csl_independence_check"
_UNBLOCK = (
    "grow the gold corpus to >= 8 aligned sessions with archetype spread "
    "(Continuous C.1); no fitting on the pilot"
)


def ari_row(profile: Mapping[Dimension, DimensionScore]) -> dict[str, float]:
    """One session's ARI side: {dimension -> value} for OK dimensions only."""
    return {
        dim.value: s.value
        for dim, s in profile.items()
        if s.status == ScoreStatus.OK and s.value is not None
    }


def csl_row(ownership: Mapping[str, OwnershipResult]) -> dict[str, float]:
    """One session's CSL side: {ACF level -> human ownership share} for OK levels."""
    return {
        level: r.human_pct
        for level, r in ownership.items()
        if r.status == ScoreStatus.OK and r.human_pct is not None
    }


def run_independence_check(
    sessions: Sequence[tuple[Mapping[Dimension, DimensionScore], Mapping[str, OwnershipResult]]],
    *,
    min_sessions: int = MIN_SESSIONS,
    near_one_threshold: float = 0.95,
) -> IndependenceResult:
    """Run the ARI-vs-CSL partition check over aligned session rows.

    Raises `CorpusInsufficientError` (loud, structured) when fewer than
    `min_sessions` sessions are supplied. Otherwise builds the aligned rows and
    delegates to `independence()`, flagging any ARI×CSL pair whose correlation
    meets `near_one_threshold` (a partition failure: CSL re-measuring ARI).
    """
    n = len(sessions)
    if n < min_sessions:
        raise CorpusInsufficientError(
            gate=GATE_NAME, have=n, need=min_sessions, requires=_UNBLOCK,
            detail="The independence check is dormant until the corpus exists.",
        )

    ari_scores = [ari_row(profile) for profile, _ in sessions]
    csl_shares = [csl_row(ownership) for _, ownership in sessions]
    return independence(
        ari_scores, csl_shares,
        near_one_threshold=near_one_threshold,
        min_n=min_sessions,
    )
