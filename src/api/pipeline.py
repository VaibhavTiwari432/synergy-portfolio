"""
src/api/pipeline.py — the Scope-A orchestrator. OWNER: Chief Engineer.

Stage-2 wiring (D-003): every Stage-1 leaf is a HARD import — a leaf that
stops importing breaks the pipeline loudly instead of silently degrading.

Data flow (INTERFACES.md §4):
  session → event log → tags → phases → extractors (N-FIRE events) + judge
          ∥ state estimator → precision merge → gates → composite
          → dynamics → sustainability → claims gate → ScoreResponse

Deterministic extractor firings enter as EVIDENCE (N-FIRE events in the log +
raw counts/provenance on the DimensionScore). The judge remains the VALUE
source for dimension scores in this calibration cycle — blending deterministic
values is a calibration decision taken against MAE data, not by default
(legacy lesson: v1.3's score path was judge-grounded; change one variable at
a time).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from src.provenance import EXTRACTOR_VERSION, provenance_stamp

from contracts.schemas import (
    CanonicalSession,
    ConfidenceInterval,
    Dimension,
    DimensionScore,
    JudgeOutput,
    Provenance,
    Rung,
    ScoreResponse,
    ScoreStatus,
    SessionFlags,
    StateVector,
    Sustainability,
    TurnTags,
)
from src.aggregate.gates import gate_dimension
from src.aggregate.normalize import normalize_counts
from src.aggregate.saturation import saturation_for
from src.aggregate.softmin import compute_composite
from src.claims.report import generate_report
from src.claims.tier_engine import detect_tier, enforce
from src.dynamics.overlay import regime_overlay
from src.dynamics.reactions import compute_reactions
from src.dynamics.transitions import compute_transitions
from src.eventlog.writer import append_neuron_firing, new_log
from src.merge.precision import merge
from src.state.epistemic_classifier import classify_epistemic
from src.state.estimator import ProxyEstimator, StateEstimator
from src.state.load_classifier import classify_load
from src.state.metacog_classifier import classify_metacog
from src.state.tomer_slope import tom_slope
from src.sustainability.debt_tracker import s_human_hat
from src.sustainability.ewma import debt_ewma
from src.sustainability.lambda_proxy import lambda_estimate
from src.trait.evidence import assess_ec_evidence
from src.trait.extractors.per_dimension import al, aui, ca, cd, cs, ec, es, pr
from src.trait.judge.client import JudgeClient
from src.trait.phase_classifier import classify_phases
from src.trait.tagger import tag_turns

#: the eight deterministic extractors, in dimension order
EXTRACTORS = (al, pr, ec, es, cs, cd, aui, ca)

#: judge confidence → CI half-width (heuristic until calibration refines it):
#: full confidence still carries a floor; zero confidence spans half the scale
_CI_FLOOR = 0.05
_CI_SPAN = 0.45
#: each theater-flagged verification widens EC's CI by this factor increment
_THEATER_WIDENING_STEP = 0.10


@dataclass(frozen=True)
class ScoreRun:
    response: ScoreResponse
    raw_profile: dict[Dimension, DimensionScore]
    telemetry_metrics: dict
    #: Track 1 — evidence/provenance the worker persists so a score can be
    #: reproduced and audited after the transcript purges.
    neuron_firings: list[dict]   # one row per deterministic neuron evaluated
    event_log: list[dict]        # full N-FIRE/event log → reaction recompute
    judge_run: dict              # raw judge output + model id + per-dim confidence
    provenance: dict             # framework/schema/contract/git_sha/judge model
    turn_state: list[dict]       # per-human-turn state strip + per-turn π (Track 2)


def telemetry_metrics(session: CanonicalSession) -> dict:
    telemetry = session.metadata.get("telemetry")
    if not isinstance(telemetry, dict):
        return {
            "present": False,
            "tier_input": False,
            "selector_health": None,
            "turns_with_dwell": 0,
            "copy_events_total": 0,
            "edit_detected_total": 0,
            "mean_dwell_ms": None,
        }

    dwell = telemetry.get("dwell_ms")
    copies = telemetry.get("copy_events")
    edits = telemetry.get("edit_detected")
    dwell_values = [v for v in dwell if isinstance(v, int | float)] if isinstance(dwell, list | tuple) else []
    copy_values = [v for v in copies if isinstance(v, int | float)] if isinstance(copies, list | tuple) else []
    edit_values = [v for v in edits if isinstance(v, bool)] if isinstance(edits, list | tuple) else []
    return {
        "present": True,
        "tier_input": True,
        "selector_health": telemetry.get("selector_health"),
        "capture_mode": telemetry.get("capture_mode"),
        "turns_with_dwell": len(dwell_values),
        "copy_events_total": int(sum(copy_values)),
        "edit_detected_total": int(sum(1 for v in edit_values if v)),
        "mean_dwell_ms": (
            round(sum(dwell_values) / len(dwell_values), 3) if dwell_values else None
        ),
    }


def _run_extractors(
    session: CanonicalSession,
    tags: list[TurnTags],
    phases: list,
    log,
) -> tuple[dict[Dimension, dict[str, float]], dict[Dimension, dict[str, int]]]:
    """Run the 8 deterministic extractors; write every firing into the event
    log as N-FIRE (order preserved) and return firings + opportunities."""
    firings: dict[Dimension, dict[str, float]] = {}
    opportunities: dict[Dimension, dict[str, int]] = {}
    for module in EXTRACTORS:
        out = module.extract(session, tags, phases, list(log.events))
        firings[module.DIM] = out["neuron_firings"]
        opportunities[module.DIM] = out["applicable_opportunities"]
        for neuron_id, strength in out["neuron_firings"].items():
            turns = out["evidence_turns"].get(neuron_id) or [0]
            append_neuron_firing(
                log,
                neuron_id=neuron_id,
                strength=strength,
                turn_index=turns[0],
                provenance=Provenance.DISPLAYED,
            )
    return firings, opportunities


def _neuron_firing_rows(
    firings: dict[Dimension, dict[str, float]],
    opportunities: dict[Dimension, dict[str, int]],
    log,
) -> list[dict]:
    """Flatten per-neuron extractor output into persistable rows.

    One row per deterministic neuron the extractors actually evaluated (had an
    opportunity for, or fired). value semantics follow the absent != zero rule
    (non-negotiable #12):
      - fired                       → value = firing strength
      - opportunity present, no fire → value = 0.0  (observed 0-of-N, NOT absent)
      - no applicable opportunity    → row omitted (N/A; never a fabricated 0)
    The 98 llm_judge neurons remain dimension-grain (judge is not per-neuron),
    so they do not appear here — that is a known scope boundary, not a drop.
    """
    evidence_by_neuron: dict[str, list[int]] = {}
    for ev in log.events:
        nid = ev.metadata.get("neuron_id") if isinstance(ev.metadata, dict) else None
        if nid is not None and ev.payload_ref and ev.payload_ref.startswith("turn:"):
            evidence_by_neuron.setdefault(nid, []).append(int(ev.payload_ref.split(":", 1)[1]))

    rows: list[dict] = []
    for dim in firings:
        dim_firings = firings.get(dim, {})
        dim_opps = opportunities.get(dim, {})
        for code in sorted(set(dim_firings) | set(dim_opps)):
            opp = int(dim_opps.get(code, 0))
            if code in dim_firings:
                value: float | None = float(dim_firings[code])
            elif opp > 0:
                value = 0.0  # opportunity existed, behaviour provably did not occur
            else:
                continue  # no opportunity → N/A → no row (absent != zero)
            rows.append({
                "neuron_code": code,
                "dimension": dim.value,
                "value": value,
                "applicable_opportunities": opp,
                "n_eff": float(opp),
                "evidence_turn_indices": evidence_by_neuron.get(code, []),
                "extractor_version": EXTRACTOR_VERSION,
            })
    return rows


def _turn_state_rows(state_strip: list[StateVector]) -> list[dict]:
    """One persistable row per human turn: the state proxies plus the per-turn
    precision π_t and cascade flags the estimator computed (Track 2). Enum labels
    become their string value; None stays None (absent ≠ zero, #12)."""
    rows: list[dict] = []
    for v in state_strip:
        rows.append({
            "turn_index": v.turn_index,
            "load": v.load.value if v.load is not None else None,
            "epistemic": v.epistemic,
            "metacog": v.metacog.value if v.metacog is not None else None,
            "tom_signal": v.tom_signal,
            "a_t": v.a_t,
            "confidence": v.confidence,
            "precision": v.precision,
            "cascade_flags": list(v.cascade_flags),
        })
    return rows


def _judge_run_record(judge_output: JudgeOutput) -> dict:
    """The judge_runs row: literal output + model identity + per-dim confidence."""
    return {
        "raw_response": judge_output.raw_response,
        "judge_model_id": judge_output.judge_model,
        "judge_model_version": None,  # id carries the version (e.g. gemini-2.5-flash)
        "judge_family": judge_output.judge_family,
        "prompt_version": judge_output.prompt_version,
        "per_dimension_confidence": {
            dim.value: js.confidence for dim, js in judge_output.scores.items()
        },
        "judge_unavailable": judge_output.judge_unavailable,
        "judge_family_conflict": judge_output.judge_family_conflict,
    }


def _profile_from_judge(
    judge_output: JudgeOutput,
    session: CanonicalSession,
    tags: list[TurnTags],
    extractor_firings: dict[Dimension, dict[str, float]] | None = None,
    extractor_opportunities: dict[Dimension, dict[str, int]] | None = None,
) -> dict[Dimension, DimensionScore]:
    ec_evidence = assess_ec_evidence(session, tags)
    profile: dict[Dimension, DimensionScore] = {}
    # the judge assesses the whole session: its evidence sample is every human
    # turn, not the exemplar turns it cites — n_eff reflects the sample
    n_human = sum(1 for t in session.turns if t.role == "human")
    normalized = normalize_counts(
        extractor_firings or {}, extractor_opportunities or {}
    ).per_dimension

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

        # deterministic evidence enrichment: raw counts ride on the score so
        # nothing the extractors saw is lost, even while the judge owns value
        norm = normalized.get(dim)
        raw_counts: dict[str, int] = {}
        if norm is not None and norm.status == ScoreStatus.OK:
            raw_counts = {
                "extractor_opportunities": norm.applicable_opportunities,
                "extractor_fired_pct": int(round(100 * (norm.normalized or 0.0))),
            }

        # instrument saturation: a confident, well-sampled, unflagged ceiling-hit
        # becomes a censored "≥ tau" rather than a point value (v3 P1 / ADR-0010).
        # Precision only — the score value is never asserted past saturation.
        censored = saturation_for(dim, js.score, float(n_human), js.confidence, flags)
        if censored is not None:
            profile[dim] = DimensionScore(
                dim=dim,
                status=ScoreStatus.MEASUREMENT_SATURATED,
                censored=censored,
                n_eff=float(n_human),
                raw_counts=raw_counts,
                rung=Rung.MEASURABLE,
                evidence_turns=js.evidence_turns,
                provenance_share_displayed=share,
                status_reason=f"score {js.score:g} >= ceiling tau {censored.bound:g}",
                flags=flags,
            )
            continue

        profile[dim] = DimensionScore(
            dim=dim,
            status=ScoreStatus.OK,
            value=js.score,
            ci=ConfidenceInterval(
                low=max(0.0, js.score - half), high=min(1.0, js.score + half)
            ),
            n_eff=float(n_human),
            raw_counts=raw_counts,
            rung=Rung.MEASURABLE,
            evidence_turns=js.evidence_turns,
            provenance_share_displayed=share,
            flags=flags,
        )
    return profile


def score_session_with_artifacts(
    session: CanonicalSession,
    *,
    judge: JudgeClient | None = None,
    estimator: StateEstimator | None = None,
) -> ScoreRun:
    log = new_log(session)
    tier = detect_tier(session)
    tel_metrics = telemetry_metrics(session)

    # ── leaves: tags → phases → deterministic extractors (N-FIRE events) ──
    tags = tag_turns(session)
    phases = classify_phases(session, tags)
    firings, opportunities = _run_extractors(session, tags, phases, log)

    # ── trait channel ──
    judge = judge or JudgeClient()
    judge_output = judge.score_session(session)
    raw_profile = _profile_from_judge(
        judge_output, session, tags, firings, opportunities
    )

    # ── state channel (sibling, same inputs) ──
    estimator = estimator or ProxyEstimator(
        classify_load=classify_load,
        classify_epistemic=classify_epistemic,
        classify_metacog=classify_metacog,
        tom_slope=tom_slope,
    )
    state_strip, state_validity = estimator.estimate(session, tags)

    # ── the one meeting point ──
    merged = merge(raw_profile, state_validity, state_strip)
    profile = {dim: gate_dimension(score) for dim, score in merged.items()}

    composite = compute_composite(profile, state_validity)

    # ── dynamics (event log + tags only) ──
    events = list(log.events)
    transitions = compute_transitions(events, tags)
    overlay = regime_overlay(events, tags)
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
    return ScoreRun(
        response=enforce(response, is_minor=session.is_minor),
        raw_profile=raw_profile,
        telemetry_metrics=tel_metrics,
        neuron_firings=_neuron_firing_rows(firings, opportunities, log),
        event_log=[ev.model_dump(mode="json") for ev in log.events],
        judge_run=_judge_run_record(judge_output),
        provenance=provenance_stamp(
            judge_model_id=judge_output.judge_model,
            judge_model_version=None,
        ),
        turn_state=_turn_state_rows(state_strip),
    )


def score_session(
    session: CanonicalSession,
    *,
    judge: JudgeClient | None = None,
    estimator: StateEstimator | None = None,
) -> ScoreResponse:
    return score_session_with_artifacts(
        session, judge=judge, estimator=estimator
    ).response


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
