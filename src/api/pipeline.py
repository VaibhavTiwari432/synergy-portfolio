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

import logging
from dataclasses import dataclass, field, fields, is_dataclass
from enum import Enum
from typing import Callable

log = logging.getLogger(__name__)

from src.provenance import EXTRACTOR_VERSION, provenance_stamp

from contracts.schemas import (
    CanonicalSession,
    ConfidenceInterval,
    Dimension,
    DimensionScore,
    IntentTag,
    JudgeOutput,
    Provenance,
    Rung,
    ScoreResponse,
    ScoreStatus,
    SessionFlags,
    StateValidity,
    StateVector,
    Sustainability,
    TurnTags,
)
from src.aggregate.gates import gate_dimension
from src.aggregate.normalize import normalize_counts
from src.aggregate.saturation import saturation_for
from src.trait.question_quality import question_evidence_rows, score_questions
from src.trait.reliance_metrics import reliance_evidence_rows, reliance_metrics
from src.aggregate.softmin import compute_composite
from src.claims.report import generate_report
from src.claims.tier_engine import detect_tier, enforce
from src.dynamics.overlay import regime_overlay
from src.dynamics.reactions import compute_reactions
from src.dynamics.transitions import compute_transitions
from src.eventlog.queries import split_log
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
from src.trait.judge.cascade_eval import compute_disagreement_metric as _disagree
from src.trait.judge.client import JudgeClient
from src.trait.judge.per_criterion import score_all_neurons_sync as _score_all_neurons
from src.trait.judge.rubric_bank import DIM_OF as _JUDGE_DIM_OF, get_rubric as _get_judge_rubric
from src.trait.phase_classifier import classify_phases
from src.trait.tagger import tag_turns

# CSL (Cognitive Work Layer) — a PARALLEL descriptive layer over ARI. It never
# modifies an ARI score (#2) and is attached as a ScoreRun artifact only; the
# frozen ScoreResponse contract is untouched. The whole chain is failure-isolated.
from csl.ai_side_extractor import extract_ai_contribution
from csl.crosswalk import load_acf_crosswalk
from csl.emergence import reportable_events, scan_emergence
from csl.ownership import CSPCState, compute_ownership
from csl.projection import NeuronMatrix, project_to_acf
from csl.report import build_csl_report

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
    #: P5 EIG question-quality: deterministic per-prompt features + session
    #: complexity summary + neuron-tagged evidence rows (D-020 approved map).
    #: EVIDENCE only — never alters a DimensionScore value (#2) or the 107 (#1).
    question_quality: dict = field(default_factory=dict)
    #: P11 appropriate-reliance: behavioral proxies (WoA/switch) + EC-11 evidence
    #: rows (D-021 approved). EVIDENCE only — never a score (#2) or a new neuron
    #: (#1); appropriate_reliance stays data-gated (None).
    reliance: dict = field(default_factory=dict)
    #: CSL (Cognitive Work Layer) — the parallel per-ACF-level ownership view +
    #: 3-panel report (Phase 2) as a JSON-able artifact dict. {"status": "ok"|"error"}.
    #: Descriptive only: never an ARI score (#2), never in the ScoreResponse. The
    #: chain is failure-isolated — a CSL error never fails the ARI score.
    csl: dict = field(default_factory=dict)
    #: Phase C.1 (D-013 Track 3) — session intent at score-time, derived as the
    #: dominant Phase across human turns (confidence = its share). Research data
    #: (Tier R1, rung DESIGNED): captured + persisted, NEVER conditions a score
    #: (#2) and adds no neuron/dimension/pillar/latent (#1). Reuses the existing
    #: frozen Phase construct — it introduces no new intent ontology.
    session_intent: dict = field(default_factory=dict)


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

    One row per neuron (deterministic or judge-typed) that was evaluated.
    value semantics follow the absent != zero rule (non-negotiable #12):
      - fired / scored              → value = firing strength (or strength_map[level])
      - opportunity present, no fire → value = 0.0  (observed 0-of-N, NOT absent)
      - no applicable opportunity    → row omitted (N/A; never a fabricated 0)
    After A2/A3, firings includes all 98 judge-typed neurons from per-criterion
    scoring; the unified matrix feeds CSL projection (A5).
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


def _jsonable(obj):
    """Recursively convert dataclasses / pydantic models / enums to JSON-able
    primitives for artifact persistence."""
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, Enum):
        return obj.value
    if hasattr(obj, "model_dump"):  # pydantic (ConfidenceInterval, Censored, ...)
        return obj.model_dump(mode="json")
    if is_dataclass(obj):
        return {f.name: _jsonable(getattr(obj, f.name)) for f in fields(obj)}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(x) for x in obj]
    if isinstance(obj, dict):
        return {str(k): _jsonable(v) for k, v in obj.items()}
    return obj


def _build_csl_artifact(
    session: CanonicalSession,
    tier,
    profile: dict[Dimension, DimensionScore],
    neuron_firing_rows: list[dict],
    state_strip: list[StateVector],
    state_validity,
) -> dict:
    """Run the CSL chain and return a JSON-able artifact dict.

    project_to_acf → extract_ai_contribution → compute_ownership → scan_emergence
    (dormant; default AbstainingConfirmer ⇒ 0 reportable) → build_csl_report.

    FAILURE-ISOLATED: any error in the CSL chain is captured and returned as
    {"status": "error", ...}; it never propagates to the ARI score. CSL is a
    parallel descriptive layer and never modifies an ARI score (#2) or the frozen
    ScoreResponse contract.
    """
    try:
        crosswalk = load_acf_crosswalk()
        matrix = NeuronMatrix.from_firing_rows(neuron_firing_rows)
        # F1: state-conditioned precision pooling (per-turn π weights; no per-segment composite)
        precision_map = {sv.turn_index: sv.precision for sv in state_strip}
        human = project_to_acf(matrix, crosswalk, precision_map=precision_map)
        ai = extract_ai_contribution(session, crosswalk)
        ownership = compute_ownership(
            human, ai, CSPCState.from_state(state_strip, state_validity)
        )
        events = scan_emergence(session)  # dormant: judge unwired ⇒ 0 reportable
        reportable = reportable_events(events)
        report = build_csl_report(ownership, events, profile, tier=tier, crosswalk=crosswalk)
        return {
            "status": "ok",
            "report": _jsonable(report),
            "ownership": {level: _jsonable(r) for level, r in ownership.items()},
            "emergence": {
                "reportable_count": len(reportable),
                "candidate_count": len(events),
                "events": [_jsonable(e) for e in reportable],
            },
        }
    except Exception as exc:  # noqa: BLE001 — isolation is the whole point
        return {"status": "error", "error": f"{type(exc).__name__}: {exc}"}


def _session_intent(phases: list) -> dict:
    """Phase C.1 — session intent as the dominant Phase across human turns.

    Deterministic + research-only (Tier R1): describes what the session was for
    without inventing a new intent ontology — it reuses the frozen Phase construct
    (EXPLORE/REFINE/EXTRACT/EVALUATE). `confidence` is the dominant phase's share
    of classified turns. Empty session → intent/confidence None (absent ≠ zero,
    #12). NEVER conditions a score (#2)."""
    from collections import Counter

    labels = [getattr(p, "value", p) for p in phases]
    if not labels:
        return {"intent": None, "confidence": None, "method": "dominant_phase", "rung": "DESIGNED"}
    label, count = Counter(labels).most_common(1)[0]
    return {
        "intent": label,
        "confidence": round(count / len(labels), 6),
        "method": "dominant_phase",
        "rung": "DESIGNED",
    }


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


def _build_transcript_text(session: CanonicalSession) -> str:
    """Flat text for per-criterion judge prompts."""
    lines = []
    for t in session.turns:
        role = "Human" if t.role == "human" else "AI"
        lines.append(f"[{role}]: {t.text}")
    return "\n\n".join(lines)


def _add_judge_neuron_firings(
    results: dict[str, dict],
    firings: dict[Dimension, dict[str, float]],
    opportunities: dict[Dimension, dict[str, int]],
) -> None:
    """Convert per-criterion level indices → [0,1] strengths and merge into firings.

    Only successful (non-error) neuron results are included. A neuron that was
    scored counts as one opportunity even if the strength is 0.0 (absent ≠ zero).
    """
    for nid, result in results.items():
        if result.get("error"):
            continue
        level = result.get("final_score_after_leniency_penalty")
        if level is None:
            continue
        dim_key = _JUDGE_DIM_OF.get(nid)
        if dim_key is None:
            continue
        try:
            dim = Dimension(dim_key)
        except ValueError:
            continue
        rb = _get_judge_rubric(nid)
        sm = rb["strength_map"]
        idx = max(0, min(len(sm) - 1, int(level)))
        firings.setdefault(dim, {})[nid] = sm[idx]
        opportunities.setdefault(dim, {})[nid] = 1


def _per_dim_neuron_stats(results: dict[str, dict]) -> dict[Dimension, dict[str, int]]:
    """Per-dimension attempted/succeeded/failed counts from per_neuron_out results."""
    stats: dict[Dimension, dict[str, int]] = {}
    for nid, result in results.items():
        dim_key = _JUDGE_DIM_OF.get(nid)
        if dim_key is None:
            continue
        try:
            dim = Dimension(dim_key)
        except ValueError:
            continue
        entry = stats.setdefault(dim, {"attempted": 0, "succeeded": 0, "failed": 0})
        entry["attempted"] += 1
        if result.get("error"):
            entry["failed"] += 1
        else:
            entry["succeeded"] += 1
    return stats


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
    neuron_stats: dict[Dimension, dict[str, int]] | None = None,
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

        flags: list[str] = []
        share = None
        if dim == Dimension.EC:
            share = ec_evidence.displayed_share
            flags.append("ec_low_calibration_confidence")  # stays until corpus grows (#19)
        if judge_output.judge_family_conflict:
            flags.append("judge_family_conflict")

        # A3: neuron-grain aggregate value (judge + deterministic unified)
        norm = normalized.get(dim)
        raw_counts: dict[str, int] = {}
        dim_firings = (extractor_firings or {}).get(dim, {})
        # only prefer neuron-grain when at least one judge-typed neuron contributed;
        # if per-criterion scoring failed entirely fall back to the joint judge score
        has_judge_neurons = any(nid in _JUDGE_DIM_OF for nid in dim_firings)

        # A4: CI from within-dim neuron disagreement (not LLM self-confidence).
        # Self-confidence is demoted to a secondary flag only.
        judge_strengths = [v for nid, v in dim_firings.items() if nid in _JUDGE_DIM_OF]
        if judge_strengths and len(judge_strengths) > 1:
            disagreement = _disagree(judge_strengths)
            half = _CI_FLOOR + _CI_SPAN * disagreement
            if js.confidence < 0.5:
                flags.append("low_judge_confidence")
            flags.append("ci_from_disagreement")  # item 3: CI source is observable variance
        else:
            # fallback: use joint confidence (per-criterion unavailable for this dim)
            half = _CI_FLOOR + _CI_SPAN * (1.0 - js.confidence)
            flags.append("ci_from_self_confidence")  # item 3: CI source is LLM self-report
        if dim == Dimension.EC:
            half *= 1.0 + _THEATER_WIDENING_STEP * ec_evidence.theater_counter
        if norm is not None and norm.status == ScoreStatus.OK:
            raw_counts = {
                "neuron_opportunities": norm.applicable_opportunities,
                "neuron_mean_pct": int(round(100 * (norm.normalized or 0.0))),
                "joint_judge_pct": int(round(100 * js.score)) if js.score is not None else 0,
            }

        # item 4: neuron success rate per dimension
        dim_stats = (neuron_stats or {}).get(dim)
        if dim_stats is not None:
            raw_counts["neurons_attempted"] = dim_stats["attempted"]
            raw_counts["neurons_succeeded"] = dim_stats["succeeded"]
            raw_counts["neurons_failed"] = dim_stats["failed"]
            if dim_stats["failed"] > 0:
                flags.append("partial_neuron_coverage")

        if (norm is not None and norm.status == ScoreStatus.OK
                and norm.normalized is not None and has_judge_neurons):
            value = norm.normalized
            n_eff_val = float(norm.applicable_opportunities)
        else:
            value = js.score
            n_eff_val = float(n_human)

        # item 2: per-criterion vs joint divergence (only when per-criterion was used)
        if (has_judge_neurons and norm is not None and norm.normalized is not None
                and js.score is not None):
            divergence = abs(norm.normalized - js.score)
            raw_counts["pc_joint_divergence"] = int(round(100 * divergence))  # percentage points
            if divergence > 0.25:
                flags.append("large_per_criterion_joint_divergence")
                log.warning(
                    "[PIPELINE] %s: per-criterion/joint divergence=%.3f — "
                    "evidence_turns may not match score",
                    dim.value, divergence,
                )

        # instrument saturation: a confident, well-sampled, unflagged ceiling-hit
        # becomes a censored "≥ tau" rather than a point value (v3 P1 / ADR-0010).
        # Precision only — the score value is never asserted past saturation.
        censored = saturation_for(dim, value, n_eff_val, js.confidence, flags)
        if censored is not None:
            profile[dim] = DimensionScore(
                dim=dim,
                status=ScoreStatus.MEASUREMENT_SATURATED,
                censored=censored,
                n_eff=n_eff_val,
                raw_counts=raw_counts,
                rung=Rung.MEASURABLE,
                evidence_turns=js.evidence_turns,
                provenance_share_displayed=share,
                status_reason=f"score {value:g} >= ceiling tau {censored.bound:g}",
                flags=flags,
            )
            continue

        profile[dim] = DimensionScore(
            dim=dim,
            status=ScoreStatus.OK,
            value=value,
            ci=ConfidenceInterval(
                low=max(0.0, value - half), high=min(1.0, value + half)
            ),
            n_eff=n_eff_val,
            raw_counts=raw_counts,
            rung=Rung.MEASURABLE,
            evidence_turns=js.evidence_turns,
            provenance_share_displayed=share,
            flags=flags,
        )
    return profile


# ── D2: fluent incompetence gate ──────────────────────────────────────────────
# Behavioral (not state) gate: high-PR user who rarely verifies, and when they
# do it is theater, and whose epistemic engagement is low. rule #2 preserved:
# state_validity stays caveat-only; this gate fires on behavioral evidence.
_TAU_PR_HIGH = 0.70
_TAU_V = 0.10   # min fraction of human turns with VERIFY tag
_TAU_A = 0.50   # max theater fraction before gate fires
_TAU_GEN = 0.30  # min epistemic mean (positive = generative)


def _build_event_log_artifact(log) -> list[dict]:
    """D4: flat list (existing contract) + two-table split for reconciliation.

    The returned list is the existing ScoreRun.event_log contract (flat, all events).
    The two-table split (human_control_signals / ai_action_firings) is embedded as a
    summary so callers can reconcile: len(human) + len(ai) == len(event_log).
    """
    all_events = [ev.model_dump(mode="json") for ev in log.events]
    human_ctrl, ai_fire = split_log(log.events)
    # ponytail: embedding split as first sentinel element keeps the flat contract intact
    return [
        {
            "__d4_split__": True,
            "human_control_count": len(human_ctrl),
            "ai_action_count": len(ai_fire),
            "total": len(all_events),
        },
        *all_events,
    ]


def _compute_fluent_incompetence(
    profile: dict[Dimension, DimensionScore],
    ec_evidence,
    tags: list[TurnTags],
    state_validity: StateValidity,
) -> bool:
    pr = profile.get(Dimension.PR)
    if pr is None or pr.value is None or pr.value <= _TAU_PR_HIGH:
        return False
    n = len(tags)
    if n == 0:
        return False
    verify_ratio = sum(1 for tt in tags if IntentTag.VERIFY in frozenset(tt.tags)) / n
    n_verify = len(ec_evidence.tags)
    theater_frac = ec_evidence.theater_counter / n_verify if n_verify > 0 else 0.0
    ep_mean = state_validity.epistemic_mean
    if ep_mean is None:
        return False  # absent epistemic evidence → don't trigger (#12)
    return verify_ratio < _TAU_V and theater_frac > _TAU_A and ep_mean < _TAU_GEN


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

    # ── P5 EIG question-quality (deterministic; evidence only, no score impact) ──
    qq = score_questions(session)

    # ── P11 appropriate-reliance (deterministic; evidence only, no score impact) ──
    rel = reliance_metrics(session)

    # ── trait channel ──
    judge = judge or JudgeClient()
    # A2: per-neuron scoring (neuron-grain, replaces joint call as value source)
    per_neuron_out = _score_all_neurons(judge.neuron_fn(), _build_transcript_text(session))
    _add_judge_neuron_firings(per_neuron_out["results"], firings, opportunities)
    neuron_stats = _per_dim_neuron_stats(per_neuron_out["results"])
    # joint call retained for provenance metadata (flags, raw_response, family check)
    judge_output = judge.score_session(session)
    if judge_output.judge_unavailable:
        # All transports failed — storing all-N/A as "scored" is a false positive.
        # Raise so the worker marks this chat "failed" and it stays re-scoreable.
        raise RuntimeError(
            "judge all-transport failure: every dimension N/A — "
            "chat deferred for re-scoring when the judge is restored"
        )
    raw_profile = _profile_from_judge(
        judge_output, session, tags, firings, opportunities,
        neuron_stats=neuron_stats,
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

    # ── sustainability (needed before D2 gate check) ──
    ec_evidence = assess_ec_evidence(session, tags)
    s_hat = s_human_hat(session)
    sustainability = Sustainability(
        s_human_hat=s_hat,
        debt_ewma=debt_ewma(_history_signal(session)),
        **{"lambda": lambda_estimate()},
    )

    # ── D2: fluent_incompetence gate (behavioral, not state; rule #2 preserved) ──
    fluent_incompat = _compute_fluent_incompetence(profile, ec_evidence, tags, state_validity)

    composite = compute_composite(profile, state_validity, fluent_incompetence=fluent_incompat)

    # ── dynamics (event log + tags only) ──
    events = list(log.events)
    transitions = compute_transitions(events, tags)
    overlay = regime_overlay(events, tags)
    reactions = compute_reactions(events, tags, transitions)

    flags = SessionFlags(
        fluent_incompetence=fluent_incompat,
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

    # ── CSL parallel layer: per-ACF-level ownership + 3-panel report ──
    # Failure-isolated artifact; the ARI ScoreResponse below is never affected.
    neuron_firing_rows = _neuron_firing_rows(firings, opportunities, log)
    csl_artifact = _build_csl_artifact(
        session, tier, profile, neuron_firing_rows, state_strip, state_validity
    )
    # Phase C.2 — falsification data for Ŝ_human, captured but NEVER used to
    # condition a score (Tier R1: capture now, gate use). The A/S-turn partition
    # (autonomous-redundancy r_auto vs steered-redundancy r_steer) and ΔR let us
    # later test whether the steering term carries signal — if ΔR ≈ 0 across users
    # the S_human metric is dropped. Stored on the (catch-all) csl artifact blob;
    # additive even when the CSL chain itself errored (it is independent of it).
    csl_artifact["s_human_detail"] = {
        "r_auto": s_hat.r_auto,
        "r_steer": s_hat.r_steer,
        "delta_r": (
            (s_hat.r_auto - s_hat.r_steer)
            if (s_hat.r_auto is not None and s_hat.r_steer is not None)
            else None
        ),
        "t_steered_out": s_hat.t_steered_out,
        "value": s_hat.value,
        "rung": "DESIGNED",
        "note": (
            "falsification data for S_human — drop the metric if delta_r ≈ 0 "
            "across users; research-only, never conditions a score (#2)"
        ),
    }

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
        neuron_firings=neuron_firing_rows,
        event_log=_build_event_log_artifact(log),
        judge_run=_judge_run_record(judge_output),
        provenance=provenance_stamp(
            judge_model_id=judge_output.judge_model,
            judge_model_version=None,
        ),
        turn_state=_turn_state_rows(state_strip),
        question_quality={
            "features": [f.model_dump() for f in qq.per_turn],
            "session_summary": qq.session_summary.model_dump(),
            "neuron_evidence": question_evidence_rows(qq),
        },
        reliance={
            "metrics": rel.model_dump(),
            "ec_evidence": reliance_evidence_rows(rel),
        },
        csl=csl_artifact,
        session_intent=_session_intent(phases),
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
