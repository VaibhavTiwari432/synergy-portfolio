"""
src/trait/judge/replication.py — judge non-determinism protocol. OWNER: Chief Engineer.

Stratified N-replication of the LLM judge (spec V2 / §A2; ADR-0009). The judge runs
at temperature 0.1 with no seed, so the same chat can score differently across runs.
Rather than fake determinism, we BOUND the variance — and spend replication budget
ONLY where it can change the headline.

This build has no synergy quadrant (#3/#4) and no categorical judge-score gate, so the
spec's "quadrant boundary" is re-grounded (ADR-0009 §1) on the real decision surface:
the softmin composite is dominated by its weakest dimension(s), so a session is
re-judged only when a composite-BINDING dimension is genuinely ambiguous (mid-scale or
low-confidence). Interior sessions cost one judge call, as today.

DORMANT: this module is self-contained and not wired into src/api/pipeline.py. Enabling
re-judging in batch is gated on human review of N + band (ADR-0009 §5).
"""

from __future__ import annotations

import statistics
from collections import Counter
from dataclasses import dataclass, field
from typing import Callable

from contracts.schemas import Dimension, JudgeOutput

#: the judge call this wrapper repeats — a session -> JudgeOutput callable. Tests
#: inject a stochastic stub; production passes JudgeClient.score_session.
ScoreFn = Callable[..., JudgeOutput]


@dataclass(frozen=True)
class ReplicationConfig:
    """The four boundary knobs (ADR-0009 §2). Defaults are the human-reviewed
    values; all are config-tunable, none hardcoded at the call site."""

    n: int = 5  #: replications on a boundary session (total passes, incl. the first)
    band: float = 0.10  #: mid-range half-width → ambiguous score ∈ [0.5-band, 0.5+band]
    bind_margin: float = 0.10  #: within this of the min applicable score == binding
    conf_floor: float = 0.50  #: judge confidence below this triggers re-judge
    always_replicate: bool = False  #: calibration-only blanket mode (ADR-0009 §1)


@dataclass(frozen=True)
class BoundaryDecision:
    rejudge: bool
    binding_dims: tuple[Dimension, ...]
    ambiguous_dims: tuple[Dimension, ...]
    reason: str


@dataclass(frozen=True)
class DimAggregate:
    """Per-dimension aggregate across the replications. sd is None for n<2 (a single
    sample has no spread) — never 0.0, which would falsely claim certainty."""

    dim: Dimension
    mean: float
    sd: float | None
    mean_confidence: float
    n: int
    scores: tuple[float, ...]


@dataclass(frozen=True)
class ReplicatedJudgeResult:
    aggregates: dict[Dimension, DimAggregate]
    n_replications: int
    rejudged: bool
    boundary: BoundaryDecision
    #: across-replication argmin instability — the no-quadrant analogue of the
    #: spec's quadrant-flip rate (ADR-0009 §3). None when n<2.
    binding_flip_rate: float | None
    judge_config: dict[str, object]
    judge_unavailable: bool
    runs: tuple[JudgeOutput, ...] = field(default_factory=tuple)


# ── boundary evaluation ──────────────────────────────────────────────────────


def _applicable(output: JudgeOutput) -> dict[Dimension, float]:
    """dim -> score for dimensions the judge actually scored (score not None)."""
    return {d: s.score for d, s in output.scores.items() if s.score is not None}


def _binding_set(scores: dict[Dimension, float], margin: float) -> tuple[Dimension, ...]:
    """Dimensions within `margin` of the minimum — the softmin-binding proxy."""
    if not scores:
        return ()
    lo = min(scores.values())
    return tuple(d for d, v in scores.items() if v <= lo + margin)


def _argmin(scores: dict[Dimension, float]) -> Dimension | None:
    """The single binding dimension (lowest score; ties broken by enum order for a
    stable modal comparison)."""
    if not scores:
        return None
    lo = min(scores.values())
    return sorted(d for d, v in scores.items() if v == lo)[0]


def evaluate_boundary(output: JudgeOutput, config: ReplicationConfig) -> BoundaryDecision:
    """Decide whether a first-pass result sits on the composite-binding boundary."""
    if config.always_replicate:
        return BoundaryDecision(True, (), (), "always_replicate (calibration mode)")
    if output.judge_unavailable:
        return BoundaryDecision(False, (), (), "judge_unavailable: nothing to replicate")

    scores = _applicable(output)
    binding = _binding_set(scores, config.bind_margin)
    ambiguous: list[Dimension] = []
    for d in binding:
        s = output.scores[d]
        mid_range = abs(scores[d] - 0.5) <= config.band
        low_conf = s.confidence < config.conf_floor
        if mid_range or low_conf:
            ambiguous.append(d)

    if ambiguous:
        return BoundaryDecision(
            True, binding, tuple(ambiguous),
            f"binding dimension(s) ambiguous (mid-range |score-0.5|≤{config.band} "
            f"or confidence<{config.conf_floor}): {[d.value for d in ambiguous]}",
        )
    return BoundaryDecision(
        False, binding, (),
        "no binding dimension is ambiguous — single pass sufficient",
    )


# ── replication + aggregation ────────────────────────────────────────────────


def _aggregate(runs: list[JudgeOutput]) -> dict[Dimension, DimAggregate]:
    aggs: dict[Dimension, DimAggregate] = {}
    dims = {d for r in runs for d, s in r.scores.items() if s.score is not None}
    for d in dims:
        vals = [r.scores[d].score for r in runs if r.scores.get(d) and r.scores[d].score is not None]
        confs = [r.scores[d].confidence for r in runs if r.scores.get(d) and r.scores[d].score is not None]
        if not vals:
            continue
        aggs[d] = DimAggregate(
            dim=d,
            mean=statistics.fmean(vals),
            sd=statistics.stdev(vals) if len(vals) >= 2 else None,
            mean_confidence=statistics.fmean(confs) if confs else 0.0,
            n=len(vals),
            scores=tuple(vals),
        )
    return aggs


def _binding_flip_rate(runs: list[JudgeOutput]) -> float | None:
    """Fraction of replications whose argmin differs from the modal argmin."""
    if len(runs) < 2:
        return None
    argmins = [_argmin(_applicable(r)) for r in runs]
    argmins = [a for a in argmins if a is not None]
    if len(argmins) < 2:
        return None
    modal, _ = Counter(argmins).most_common(1)[0]
    return sum(1 for a in argmins if a != modal) / len(argmins)


def _judge_config(output: JudgeOutput, temperature: float) -> dict[str, object]:
    return {
        "judge_model": output.judge_model,
        "judge_family": output.judge_family,
        "prompt_version": output.prompt_version,
        "temperature": temperature,
    }


def replicate_judge(
    score_fn: ScoreFn,
    session,
    *,
    config: ReplicationConfig | None = None,
    temperature: float = 0.1,
) -> ReplicatedJudgeResult:
    """Score `session` once; if it sits on the composite-binding boundary, re-judge to
    `config.n` total passes and report per-dimension mean ± SD. `score_fn` is a
    session -> JudgeOutput callable (JudgeClient.score_session in production; a stub in
    tests), kept injectable so this wrapper never constructs transports itself."""
    config = config or ReplicationConfig()
    first = score_fn(session)
    boundary = evaluate_boundary(first, config)
    cfg = _judge_config(first, temperature)

    if first.judge_unavailable or not boundary.rejudge:
        return ReplicatedJudgeResult(
            aggregates=_aggregate([first]),
            n_replications=1,
            rejudged=False,
            boundary=boundary,
            binding_flip_rate=None,
            judge_config=cfg,
            judge_unavailable=first.judge_unavailable,
            runs=(first,),
        )

    runs = [first]
    for _ in range(max(0, config.n - 1)):
        runs.append(score_fn(session))

    # if any replication came back unavailable, fold that into the flag but still
    # aggregate the runs that succeeded (never fabricate a score for a failed run).
    any_unavailable = any(r.judge_unavailable for r in runs)
    return ReplicatedJudgeResult(
        aggregates=_aggregate([r for r in runs if not r.judge_unavailable] or runs),
        n_replications=len(runs),
        rejudged=True,
        boundary=boundary,
        binding_flip_rate=_binding_flip_rate([r for r in runs if not r.judge_unavailable]),
        judge_config=cfg,
        judge_unavailable=any_unavailable,
        runs=tuple(runs),
    )
