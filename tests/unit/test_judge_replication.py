"""v3 P2 / ADR-0009 — stratified judge N-replication at the composite-binding
boundary. OWNER: Chief Engineer. No network: a deterministic sequence stub stands
in for the stochastic judge."""

from __future__ import annotations

from contracts.schemas import Dimension, JudgeDimScore, JudgeOutput
from src.trait.judge.replication import (
    ReplicationConfig,
    _binding_flip_rate,
    evaluate_boundary,
    replicate_judge,
)

D = Dimension


def _jo(scores: dict[Dimension, float], *, conf: float = 0.9, unavailable: bool = False) -> JudgeOutput:
    return JudgeOutput(
        scores={d: JudgeDimScore(score=v, confidence=conf) for d, v in scores.items()},
        judge_model="gemini-2.5-flash",
        judge_family="google",
        prompt_version="v2.1",
        judge_unavailable=unavailable,
    )


def _seq(outputs: list[JudgeOutput]):
    """A session->JudgeOutput stub that walks `outputs` once, then repeats the last."""
    it = iter(outputs)
    state = {"last": outputs[-1]}

    def fn(_session):
        try:
            state["last"] = next(it)
        except StopIteration:
            pass
        return state["last"]

    return fn


# ── boundary evaluation ──────────────────────────────────────────────────────


def test_clearcut_session_is_not_a_boundary():
    # min dim (EC 0.8) is far from mid-scale and high-confidence → no re-judge
    out = _jo({D.EC: 0.80, D.PR: 0.85, D.CA: 0.90})
    decision = evaluate_boundary(out, ReplicationConfig())
    assert decision.rejudge is False
    assert decision.ambiguous_dims == ()


def test_binding_mid_range_dimension_triggers_rejudge():
    # EC is the binding (lowest) dim and sits at mid-scale → ambiguous
    out = _jo({D.EC: 0.50, D.PR: 0.82, D.CA: 0.88})
    decision = evaluate_boundary(out, ReplicationConfig())
    assert decision.rejudge is True
    assert D.EC in decision.binding_dims and D.EC in decision.ambiguous_dims


def test_low_confidence_binding_dimension_triggers_rejudge():
    # EC is binding and clear of mid-scale, but the judge is unsure → ambiguous
    out = _jo({D.EC: 0.20, D.PR: 0.85, D.CA: 0.90}, conf=0.3)
    decision = evaluate_boundary(out, ReplicationConfig())
    assert decision.rejudge is True
    assert D.EC in decision.ambiguous_dims


def test_high_confidence_extreme_score_is_not_ambiguous():
    out = _jo({D.EC: 0.05, D.PR: 0.85, D.CA: 0.90}, conf=0.95)
    assert evaluate_boundary(out, ReplicationConfig()).rejudge is False


def test_judge_unavailable_is_never_a_boundary():
    out = _jo({}, unavailable=True)
    assert evaluate_boundary(out, ReplicationConfig()).rejudge is False


def test_always_replicate_mode_forces_rejudge():
    out = _jo({D.EC: 0.95, D.PR: 0.95})
    assert evaluate_boundary(out, ReplicationConfig(always_replicate=True)).rejudge is True


# ── replication + aggregation ────────────────────────────────────────────────


def test_non_boundary_scores_once_with_no_spread():
    out = _jo({D.EC: 0.80, D.PR: 0.85, D.CA: 0.90})
    res = replicate_judge(_seq([out]), None)
    assert res.rejudged is False
    assert res.n_replications == 1
    assert res.binding_flip_rate is None
    assert res.aggregates[D.EC].sd is None  # single sample → no spread, never 0.0


def test_boundary_session_replicates_and_reports_mean_sd():
    ec_vals = [0.45, 0.55, 0.50, 0.40, 0.60]  # first pass 0.45 → mid-range boundary
    runs = [_jo({D.EC: v, D.PR: 0.85, D.CA: 0.90}) for v in ec_vals]
    res = replicate_judge(_seq(runs), None, config=ReplicationConfig(n=5))
    assert res.rejudged is True
    assert res.n_replications == 5
    ec = res.aggregates[D.EC]
    assert ec.n == 5
    assert abs(ec.mean - 0.50) < 1e-9
    assert ec.sd is not None and ec.sd > 0.0
    # EC binds every replication (others fixed high) → stable argmin, zero flips
    assert res.binding_flip_rate == 0.0
    # provenance pinned
    assert res.judge_config["judge_model"] == "gemini-2.5-flash"
    assert res.judge_config["temperature"] == 0.1


def test_binding_flip_rate_counts_argmin_instability():
    # argmin alternates EC / PR across four runs → unstable headline-binding dim
    runs = [
        _jo({D.EC: 0.40, D.PR: 0.50}),
        _jo({D.EC: 0.50, D.PR: 0.40}),
        _jo({D.EC: 0.41, D.PR: 0.50}),
        _jo({D.EC: 0.50, D.PR: 0.42}),
    ]
    rate = _binding_flip_rate(runs)
    # modal argmin appears twice; the other two flip → 0.5
    assert rate == 0.5


def test_unavailable_replication_folds_flag_without_fabricating():
    runs = [
        _jo({D.EC: 0.50, D.PR: 0.85}),       # boundary on first pass
        _jo({}, unavailable=True),            # one bad run mid-stream
        _jo({D.EC: 0.52, D.PR: 0.85}),
        _jo({D.EC: 0.48, D.PR: 0.85}),
        _jo({D.EC: 0.51, D.PR: 0.85}),
    ]
    res = replicate_judge(_seq(runs), None, config=ReplicationConfig(n=5))
    assert res.judge_unavailable is True          # the bad run is surfaced
    assert res.aggregates[D.EC].n == 4            # aggregated only the 4 good runs
