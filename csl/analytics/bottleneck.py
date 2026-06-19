"""CSL Phase 2.5 — bottleneck detection (task-conditioned, refuse-by-default).

`bottleneck` looks across an ownership history for an ACF level where the human
shows consistently low displayed-ownership. It is a LEADING INDICATOR, never a
capability claim — there is no ground truth and no probe, so it cannot and does
not infer "what the human could do without AI" (Do-NOT #12).

Appropriateness is NEVER inferred from correctness. It is a declared task-context
input (`delegation_policy`):

  - a level marked `"appropriate"`  → low ownership is fine; never flagged.
  - a level marked `"human_required"`→ consistently low ownership IS a bottleneck.
  - a level with NO policy entry     → indeterminate; REFUSED (not flagged).

Refuse-by-default: ambiguous low ownership is treated as possibly-appropriate
delegation, not a deficiency (acceptance: "refuses to flag a level as a bottleneck
when task-context marks the delegation appropriate"). A bottleneck requires both a
consistent low-ownership pattern AND an explicit `human_required` policy.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from contracts.schemas import Rung, ScoreStatus
from csl.crosswalk import ACF_LEVELS
from csl.ownership import OwnershipResult

#: provisional displayed-ownership floor (NOT corpus-calibrated — a reporting
#: heuristic, not a frozen statistical cut). Below this mean, ownership is "low".
DEFAULT_LOW_OWNERSHIP = 0.34
#: a pattern needs several sessions; one session is never a bottleneck.
DEFAULT_MIN_SESSIONS = 3

_CAVEAT = (
    "Leading indicator of displayed human ownership across sessions, "
    "task-conditioned. Not a capability or deficiency claim — establishing what "
    "the human could do unaided requires the retention/transfer probe. Levels "
    "without a task-delegation policy are not flagged."
)


@dataclass(frozen=True)
class LevelBottleneck:
    """One ACF level's cross-session ownership verdict."""

    level: str
    mean_human_pct: float | None
    n_observations: int
    #: "bottleneck" | "appropriate_delegation" | "indeterminate" | "adequate"
    #: | "insufficient_history"
    verdict: str
    flagged: bool
    reason: str


@dataclass(frozen=True)
class BottleneckReport:
    levels: tuple[LevelBottleneck, ...]
    flagged_levels: tuple[str, ...]
    n_sessions: int
    min_sessions: int
    status: ScoreStatus
    rung: Rung
    caveat: str


def bottleneck(
    ownership_history: Sequence[Mapping[str, OwnershipResult]],
    *,
    delegation_policy: Mapping[str, str] | None = None,
    low_ownership_threshold: float = DEFAULT_LOW_OWNERSHIP,
    min_sessions: int = DEFAULT_MIN_SESSIONS,
) -> BottleneckReport:
    """Detect consistently-weak ACF levels across an ownership history.

    `ownership_history` is one `compute_ownership` result per session. Only OK
    results contribute an observation (absent ≠ zero). A level is flagged only when
    its mean human ownership is below `low_ownership_threshold` across at least
    `min_sessions` observations AND the policy marks it `human_required`.
    """
    policy = dict(delegation_policy or {})
    n_sessions = len(ownership_history)

    if n_sessions < min_sessions:
        levels = tuple(
            LevelBottleneck(
                level=lvl, mean_human_pct=None, n_observations=0,
                verdict="insufficient_history", flagged=False,
                reason=f"need >= {min_sessions} sessions, have {n_sessions}",
            )
            for lvl in ACF_LEVELS
        )
        return BottleneckReport(
            levels=levels, flagged_levels=(), n_sessions=n_sessions,
            min_sessions=min_sessions, status=ScoreStatus.INSUFFICIENT_SAMPLE,
            rung=Rung.DESIGNED, caveat=_CAVEAT,
        )

    level_results: list[LevelBottleneck] = []
    flagged: list[str] = []

    for level in ACF_LEVELS:
        observations = [
            r.human_pct
            for session in ownership_history
            if (r := session.get(level)) is not None
            and r.status == ScoreStatus.OK
            and r.human_pct is not None
        ]
        n_obs = len(observations)

        if n_obs < min_sessions:
            level_results.append(LevelBottleneck(
                level=level, mean_human_pct=None, n_observations=n_obs,
                verdict="insufficient_history", flagged=False,
                reason=f"only {n_obs} OK observations (< {min_sessions})",
            ))
            continue

        mean_pct = round(sum(observations) / n_obs, 6)

        if mean_pct >= low_ownership_threshold:
            level_results.append(LevelBottleneck(
                level=level, mean_human_pct=mean_pct, n_observations=n_obs,
                verdict="adequate", flagged=False,
                reason=f"mean human ownership {mean_pct:g} >= {low_ownership_threshold:g}",
            ))
            continue

        # low ownership: the verdict depends ONLY on declared task-context.
        stance = policy.get(level)
        if stance == "appropriate":
            level_results.append(LevelBottleneck(
                level=level, mean_human_pct=mean_pct, n_observations=n_obs,
                verdict="appropriate_delegation", flagged=False,
                reason="low ownership, but task-context marks delegation appropriate",
            ))
        elif stance == "human_required":
            level_results.append(LevelBottleneck(
                level=level, mean_human_pct=mean_pct, n_observations=n_obs,
                verdict="bottleneck", flagged=True,
                reason="consistently low ownership on a task-context human_required level",
            ))
            flagged.append(level)
        else:
            # no policy → cannot distinguish weakness from appropriate delegation
            # without correctness ground truth → refuse to flag.
            level_results.append(LevelBottleneck(
                level=level, mean_human_pct=mean_pct, n_observations=n_obs,
                verdict="indeterminate", flagged=False,
                reason="low ownership but no task-delegation policy; refused (not flagged)",
            ))

    return BottleneckReport(
        levels=tuple(level_results),
        flagged_levels=tuple(flagged),
        n_sessions=n_sessions,
        min_sessions=min_sessions,
        status=ScoreStatus.OK,
        rung=Rung.DESIGNED,
        caveat=_CAVEAT,
    )
