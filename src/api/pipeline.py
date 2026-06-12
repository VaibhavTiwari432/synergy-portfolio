"""
src/api/pipeline.py — the Scope-A orchestrator. OWNER: Chief Engineer.

Wires the spine end-to-end TODAY, with junior leaf modules slotting in as
they land: each leaf is imported optionally; a missing leaf degrades to an
honest absence (empty tags, gated-N/A metrics, caveated state channels) —
never a fabricated value. Stage 2 replaces the optional imports with hard
ones once the board is green.

Data flow (INTERFACES.md §4):
  session → event log → [tags, phases] → judge + evidence → trait profile
          → state estimator → precision merge → gates → composite
          → dynamics → sustainability → claims gate → ScoreResponse
"""

from __future__ import annotations

from typing import Callable

from contracts.schemas import (
    CanonicalSession,
    CellGatedProb,
    ConfidenceInterval,
    Dimension,
    DimensionScore,
    JudgeOutput,
    RegimeOverlay,
    Rung,
    ScoreResponse,
    ScoreStatus,
    SessionFlags,
    Sustainability,
    TransitionMetrics,
    TurnTags,
)
from src.aggregate.gates import gate_dimension
from src.aggregate.softmin import compute_composite
from src.claims.report import generate_report
from src.claims.tier_engine import detect_tier, enforce
from src.dynamics.reactions import compute_reactions
from src.eventlog.writer import new_log
from src.merge.precision import merge
from src.state.estimator import ProxyEstimator, StateEstimator
from src.sustainability.debt_tracker import s_human_hat
from src.sustainability.ewma import debt_ewma
from src.sustainability.lambda_proxy import lambda_estimate
from src.trait.evidence import assess_ec_evidence
from src.trait.judge.client import JudgeClient

#: judge confidence → CI half-width (heuristic until calibration refines it):
#: full confidence still carries a floor; zero confidence spans half the scale
_CI_FLOOR = 0.05
_CI_SPAN = 0.45
#: each theater-flagged verification widens EC's CI by this factor increment
_THEATER_WIDENING_STEP = 0.10


def _optional_leaves() -> dict[str, Callable | None]:
    """Junior leaf modules — optional until their owners deliver (Stage 1)."""
    leaves: dict[str, Callable | None] = {}
    try:
        from src.trait.tagger import tag_turns  # Codex
        leaves["tag_turns"] = tag_turns
    except ImportError:
        leaves["tag_turns"] = None
    try:
        from src.state import (  # Antigravity
            epistemic_classifier,
            load_classifier,
            metacog_classifier,
            tomer_slope,
        )
        leaves["classify_load"] = load_classifier.classify_load
        leaves["classify_epistemic"] = epistemic_classifier.classify_epistemic
        leaves["classify_metacog"] = metacog_classifier.classify_metacog
        leaves["tom_slope"] = tomer_slope.tom_slope
    except ImportError:
        leaves.update(classify_load=None, classify_epistemic=None,
                      classify_metacog=None, tom_slope=None)
    try:
        from src.dynamics.transitions import compute_transitions  # Antigravity
        leaves["compute_transitions"] = compute_transitions
    except ImportError:
        leaves["compute_transitions"] = None
    try:
        from src.dynamics.overlay import regime_overlay  # Antigravity
        leaves["regime_overlay"] = regime_overlay
    except ImportError:
        leaves["regime_overlay"] = None
    return leaves


def _profile_from_judge(
    judge_output: JudgeOutput,
    session: CanonicalSession,
    tags: list[TurnTags],
) -> dict[Dimension, DimensionScore]:
    ec_evidence = assess_ec_evidence(session, tags)
    profile: dict[Dimension, DimensionScore] = {}
    # the judge assesses the whole session: its evidence sample is every human
    # turn, not the exemplar turns it cites — n_eff reflects the sample
    n_human = sum(1 for t in session.turns if t.role == "human")

    for dim, js in judge_output.scores.items():
        if js.score is None:
            reason = (
                "no_ethics_events_detected" if dim == Dimension.ES
                else ("judge_unavailable" if judge_output.judge_unavailable else None)
            )
            profile[dim] = DimensionScore(
                dim=dim,
                status=ScoreStatus.NOT_APPLICABLE,
                rung=Rung.MEASURABLE,
                status_reason=reason,
            )
            continue

        half = _CI_FLOOR + _CI_SPAN * (1.0 - js.confidence)
        flags: list[str] = []
        share = None
        if dim == Dimension.EC:
            share = ec_evidence.displayed_share
            flags.append("ec_low_calibration_confidence")  # stays until corpus grows (#19)
            half *= 1.0 + _THEATER_WIDENING_STEP * ec_evidence.theater_counter
        if judge_output.judge_family_conflict:
            flags.append("judge_family_conflict")

        profile[dim] = DimensionScore(
            dim=dim,
            status=ScoreStatus.OK,
            value=js.score,
            ci=ConfidenceInterval(
                low=max(0.0, js.score - half), high=min(1.0, js.score + half)
            ),
            n_eff=float(n_human),
            rung=Rung.MEASURABLE,
            evidence_turns=js.evidence_turns,
            provenance_share_displayed=share,
            flags=flags,
        )
    return profile


def _empty_transitions() -> TransitionMetrics:
    gated = CellGatedProb()
    return TransitionMetrics(
        verify_after_error_rate=gated,
        constraint_before_generation_rate=gated,
        prediction_before_answer_rate=gated,
        revision_after_output_rate=gated,
    )


def score_session(
    session: CanonicalSession,
    *,
    judge: JudgeClient | None = None,
    estimator: StateEstimator | None = None,
) -> ScoreResponse:
    leaves = _optional_leaves()
    log = new_log(session)  # detectors append as leaf modules land
    tier = detect_tier(session)

    # ── tags (Codex leaf; absent → empty tag lists, honestly untagged) ──
    if leaves["tag_turns"] is not None:
        tags = leaves["tag_turns"](session)
    else:
        tags = [
            TurnTags(turn_index=t.index, tags=[])
            for t in session.turns
            if t.role == "human"
        ]

    # ── trait channel ──
    judge = judge or JudgeClient()
    judge_output = judge.score_session(session)
    trait_profile = _profile_from_judge(judge_output, session, tags)

    # ── state channel (sibling, same inputs) ──
    estimator = estimator or ProxyEstimator(
        classify_load=leaves["classify_load"],
        classify_epistemic=leaves["classify_epistemic"],
        classify_metacog=leaves["classify_metacog"],
        tom_slope=leaves["tom_slope"],
    )
    state_strip, state_validity = estimator.estimate(session, tags)

    # ── the one meeting point ──
    merged = merge(trait_profile, state_validity, state_strip)
    profile = {dim: gate_dimension(score) for dim, score in merged.items()}

    composite = compute_composite(profile, state_validity)

    # ── dynamics (Antigravity leaves; absent → gated N/A) ──
    events = list(log.events)
    transitions = (
        leaves["compute_transitions"](events, tags)
        if leaves["compute_transitions"] is not None
        else _empty_transitions()
    )
    overlay = (
        leaves["regime_overlay"](events, tags)
        if leaves["regime_overlay"] is not None
        else RegimeOverlay()
    )
    reactions = compute_reactions(events, tags, transitions)

    # ── sustainability ──
    ec_evidence = assess_ec_evidence(session, tags)
    sustainability = Sustainability(
        s_human_hat=s_human_hat(session),
        debt_ewma=debt_ewma(_history_signal(session)),
        **{"lambda": lambda_estimate()},
    )

    flags = SessionFlags(
        fluent_incompetence=None,  # requires extractor evidence (Stage 2)
        debt_flag=None,            # requires multi-session history
        accept_run_max=transitions.accept_run_max,
        accept_run_mean=transitions.accept_run_mean,
        theater_counter=ec_evidence.theater_counter,
        judge_unavailable=judge_output.judge_unavailable,
        judge_family_conflict=judge_output.judge_family_conflict,
    )

    report = generate_report(
        tier=tier,
        profile=profile,
        composite=composite,
        state_validity=state_validity,
        flags=flags,
        reactions=reactions,
        sustainability=sustainability,
        is_minor=session.is_minor,
    )

    response = ScoreResponse(
        session_id=session.session_id,
        tier=tier,
        profile=profile,
        composite=composite,
        state_strip=state_strip,
        state_validity=state_validity,
        flags=flags,
        reaction_signatures=reactions,
        regime_overlay=overlay,
        sustainability=sustainability,
        report=report,
    )
    return enforce(response, is_minor=session.is_minor)


def _history_signal(session: CanonicalSession) -> list[float]:
    """Single-session history → the EWMA reports INSUFFICIENT_HISTORY.
    Multi-session trajectories assemble real history (routes/trajectory)."""
    return [0.5]  # length-1 history; debt_ewma gates on n >= 2


def judge_score_fn() -> "Callable[[CanonicalSession], dict[Dimension, float | None]]":
    """Calibration adapter: session → per-dimension point predictions."""
    client = JudgeClient()

    def fn(session: CanonicalSession) -> dict[Dimension, float | None]:
        response = score_session(session, judge=client)
        return {
            dim: score.value for dim, score in response.profile.items()
        }

    return fn
