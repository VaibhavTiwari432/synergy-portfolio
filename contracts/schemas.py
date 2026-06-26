"""
contracts/schemas.py — FROZEN Stage-0 contracts. OWNER: Chief Engineer. v1.0.0

The six core schemas required by AGENT_REBUILD_BRIEF_v3.md §5 Stage 0 —
Event, CanonicalSession, PartnerModel, DimensionScore, StateVector, ScoreResponse —
plus the supporting enums and leaf-module I/O types referenced by INTERFACES.md.

Juniors: import from this module (and the other contracts/ modules) ONLY.
Never redefine these shapes locally; never add fields. A missing field is a
DISCREPANCY.md entry, not a local workaround (non-negotiable #21).

Design notes (CE decisions, binding):
- Event.t is the ORDINAL position in the append-only log (Tier-1 transcripts have
  no wall-clock). A wall-clock timestamp, when known (Tier 2+), goes in
  Event.metadata["timestamp"] as ISO-8601. Order is the contract; time is metadata.
- Scores are 0.0–1.0 everywhere (gold 0–10 hand scores are divided by 10 by the
  gold loader). Absent evidence is a status, never 0.0 (non-negotiable #12).
- "surrender" is representable ONLY as MetacogLabel.SURRENDER (CSPC construct).
  RegimeLabel deliberately has ACCEPT_RUN and no surrender label (non-negotiable #5).
- Every report-bearing model carries exactly one `rung` (non-negotiable #14).
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

SCHEMA_VERSION = "1.2.0"


# ──────────────────────────────────────────────────────────────────────────────
# Enums — frozen vocabularies
# ──────────────────────────────────────────────────────────────────────────────


class Dimension(str, Enum):
    """The 8 ARI dimensions. Frozen (non-negotiable #1)."""

    AL = "AL"   # AI Literacy
    PR = "PR"   # Prompt Reasoning
    EC = "EC"   # Error Correction & Epistemic Vigilance
    ES = "ES"   # Ethical Sensitivity
    CS = "CS"   # Contextual Synthesis
    CD = "CD"   # Creative Divergence
    AUI = "AUI"  # Augmentation Instinct
    CA = "CA"   # Cognitive Agency


#: Neuron count per dimension — must match contracts/contract_table.yaml (107 total).
DIMENSION_NEURON_COUNTS: dict[Dimension, int] = {
    Dimension.AL: 13,
    Dimension.PR: 15,
    Dimension.EC: 14,
    Dimension.ES: 14,
    Dimension.CS: 11,
    Dimension.CD: 11,
    Dimension.AUI: 12,
    Dimension.CA: 17,
}

#: Aggregation weights (brief §3.1): EC and CS carry 1.5×, all others 1.0.
DIMENSION_WEIGHTS: dict[Dimension, float] = {
    dim: (1.5 if dim in (Dimension.EC, Dimension.CS) else 1.0) for dim in Dimension
}


class Rung(str, Enum):
    """The claims-charter epistemic ladder (spec §0.2). Exactly one per claim."""

    DESIGNED = "DESIGNED"
    MEASURABLE = "MEASURABLE"
    VALIDATED = "VALIDATED"
    ASPIRATIONAL = "ASPIRATIONAL"


class Actor(str, Enum):
    HUMAN = "human"
    AI = "ai"
    SYSTEM = "system"


class Provenance(str, Enum):
    """Evidence provenance: displayed = visible in transcript; implied = inferred."""

    DISPLAYED = "displayed"
    IMPLIED = "implied"


class EventType(str, Enum):
    """Frozen event taxonomy (spec §5.9b) + N-FIRE for neuron firings."""

    E_ERR = "E-ERR"            # AI error detected (judge-flagged or user-evidenced)
    E_CONTRA = "E-CONTRA"      # contradiction (AI-internal, or AI vs user source)
    E_CONFUSE = "E-CONFUSE"    # user confusion marker
    E_FRICTION = "E-FRICTION"  # task failure / error return / blocked progress
    E_CORRECT = "E-CORRECT"    # the AI corrects the user
    E_OVERREACH = "E-OVERREACH"  # unsolicited scope expansion / sycophancy marker
    N_FIRE = "N-FIRE"          # neuron firing


class IntentTag(str, Enum):
    """The 10 intent tags (brief §3.6.1). Frozen."""

    VERIFY = "VERIFY"
    EXTRACT = "EXTRACT"
    INJECT_CONTEXT = "INJECT_CONTEXT"
    OVERRIDE = "OVERRIDE"
    SELF_AUDIT = "SELF_AUDIT"
    DELEGATE = "DELEGATE"
    SCAFFOLD = "SCAFFOLD"
    PIVOT = "PIVOT"
    DECOMPOSE = "DECOMPOSE"
    ACCEPT_FLAT = "ACCEPT_FLAT"


class Phase(str, Enum):
    """Session phase per human turn (brief §3.6.2)."""

    EXPLORE = "explore"
    REFINE = "refine"
    EXTRACT = "extract"
    EVALUATE = "evaluate"


class ResponseClass(str, Enum):
    """Reaction-signature response classes (spec §5.9c)."""

    VERIFY_CHALLENGE = "VERIFY_CHALLENGE"
    SYNTHESIZE = "SYNTHESIZE"
    CONSTRAIN = "CONSTRAIN"
    ACCEPT_FLAT = "ACCEPT_FLAT"
    DISENGAGE = "DISENGAGE"
    DELEGATE_MORE = "DELEGATE_MORE"


class LoadLabel(str, Enum):
    """Per-turn cognitive-load proxy (brief §3.5 L_t)."""

    LOW_LOAD = "LOW_LOAD"
    HIGH_ICL = "HIGH_ICL"
    HIGH_ECL = "HIGH_ECL"
    FATIGUE = "FATIGUE"


class MetacogLabel(str, Enum):
    """Per-turn metacognitive mode (brief §3.5 M_t). SURRENDER is CSPC-owned —
    it must never surface in regime-overlay output or as a user-facing label."""

    ACTIVE = "ACTIVE"
    PASSIVE = "PASSIVE"
    SURRENDER = "SURRENDER"


class RegimeLabel(str, Enum):
    """Regime-overlay labels (spec §5.9f). Rules only; deliberately NO surrender
    label here — accept_run is a behavioral description (non-negotiable #5)."""

    GENERATIVE = "generative"
    EXTRACTIVE = "extractive"
    VERIFICATION = "verification"
    DRIFT = "drift"
    ACCEPT_RUN = "accept_run"


class ScoreStatus(str, Enum):
    """Why a value is present or absent. Absent ≠ zero (non-negotiable #12).

    The three non-OK states are the censored-reporting siblings (v3 §A3/V3):
    NOT_APPLICABLE (the applicability condition never arose — spec STRUCTURAL_NA),
    INSUFFICIENT_SAMPLE (too few items), and MEASUREMENT_SATURATED (the dimension
    topped/bottomed out the instrument's resolution; report "≥ X" / "≤ X", never
    "= max"). These four are NEVER collapsed into one label downstream
    (never-collapse rule, v3 §9 / v3.2 §0.3)."""

    OK = "OK"
    INSUFFICIENT_SAMPLE = "INSUFFICIENT_SAMPLE"
    NOT_APPLICABLE = "N/A"
    MEASUREMENT_SATURATED = "MEASUREMENT_SATURATED"


class DebtMode(str, Enum):
    """Debt-EWMA modes (brief §3.9)."""

    EROSION = "erosion"
    FLAT_FLOOR = "flat_floor"
    NONE = "none"
    INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"


class GroundingFunction(str, Enum):
    """Conversational-grounding function of one human turn (Clark & Brennan;
    v3.21 §3.1 C2). Codex: src/trait/grounding.py. Evidence that conditions EC/CA
    evidence PRECISION only — never a score value (#2); adds no neuron (#1).

      INITIATION : the human turn introduces a new topic/constraint.
      GROUNDING  : the human turn confirms/acknowledges without adding content.
      REPAIR     : the human turn corrects or requests clarification on AI content.
      NONE       : none of the above."""

    INITIATION = "INITIATION"
    GROUNDING = "GROUNDING"
    REPAIR = "REPAIR"
    NONE = "NONE"


# "gold_json" is the internal gold-corpus format (data/gold/chats/*.json) —
# never an API-exposed source; the three public formats are the Scope A surface.
SourceFormat = Literal["claude_export", "chatgpt_export", "plaintext", "gold_json"]
PartnerFamily = Literal["anthropic", "openai", "google", "unknown"]
Tier = Literal[1, 2, 3]


class _Frozen(BaseModel):
    """All contract models are immutable and reject unknown fields."""

    model_config = ConfigDict(frozen=True, extra="forbid")


# ──────────────────────────────────────────────────────────────────────────────
# Core schema 1/6 — PartnerModel (required from Stage 0; non-negotiable #20)
# ──────────────────────────────────────────────────────────────────────────────


class PartnerModel(_Frozen):
    """The AI partner in the analysed chat. era_key feeds the reliability map."""

    family: PartnerFamily
    model_id: str = "unknown"
    era_key: str = Field(pattern=r"^(\d{4}-\d{2}|unknown)$", default="unknown")


# ──────────────────────────────────────────────────────────────────────────────
# Core schema 2/6 — Event (the universal event log record, spec §5.9a)
# ──────────────────────────────────────────────────────────────────────────────


class Event(_Frozen):
    """One append-only, ordered, provenance-tagged log record.

    t is the ordinal log position (0-based, dense). Wall-clock time, when the
    tier provides it, lives in metadata["timestamp"] (ISO-8601 string).
    payload_ref points at the evidence (e.g. "turn:7" or "turn:7#span:120-180");
    it never embeds transcript text — minimization (non-negotiable #16).
    """

    t: int = Field(ge=0)
    event_type: EventType
    actor: Actor
    payload_ref: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    provenance: Provenance
    metadata: dict[str, Any] = Field(default_factory=dict)


# ──────────────────────────────────────────────────────────────────────────────
# Core schema 3/6 — CanonicalSession (every adapter's output, brief §3.3–3.4)
# ──────────────────────────────────────────────────────────────────────────────


class Turn(_Frozen):
    """One transcript turn. index is 0-based and dense within a session."""

    index: int = Field(ge=0)
    role: Literal["human", "ai"]
    text: str
    timestamp: datetime | None = None


class CanonicalSession(_Frozen):
    """The single normalized session format. Nothing downstream reads raw
    source formats — the event log materializes from this."""

    session_id: str
    source: SourceFormat
    partner_model: PartnerModel
    turns: list[Turn]
    detected_tier: Tier = 1
    user_ref: str | None = None
    is_minor: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _turn_indices_dense(self) -> "CanonicalSession":
        for expected, turn in enumerate(self.turns):
            if turn.index != expected:
                raise ValueError(
                    f"turn indices must be dense from 0; got {turn.index} at position {expected}"
                )
        return self


# ──────────────────────────────────────────────────────────────────────────────
# Core schema 4/6 — DimensionScore
# ──────────────────────────────────────────────────────────────────────────────


class ConfidenceInterval(_Frozen):
    low: float = Field(ge=0.0, le=1.0)
    high: float = Field(ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _ordered(self) -> "ConfidenceInterval":
        if self.low > self.high:
            raise ValueError("ci.low must be <= ci.high")
        return self

    @property
    def width(self) -> float:
        return self.high - self.low


class Censored(_Frozen):
    """Right/left-censored bound for a MEASUREMENT_SATURATED dimension (v3 §A3).

    direction "high" → the true value is ≥ bound (instrument ceiling);
    direction "low"  → the true value is ≤ bound (instrument floor).
    The bound is reported in place of a point value, which stays None — stating
    the truth is unknown beyond the saturation point rather than fabricating a
    ceiling/floor value."""

    direction: Literal["high", "low"]
    bound: float = Field(ge=0.0, le=1.0)


class DimensionScore(_Frozen):
    """One ARI dimension's session score. value present iff status == OK.

    Precision (ci width) is the ONLY thing state conditions — never value
    (non-negotiable #2). raw_counts are retained on INSUFFICIENT_SAMPLE so
    nothing is silently erased (brief §3.7).
    """

    dim: Dimension
    status: ScoreStatus
    value: float | None = Field(default=None, ge=0.0, le=1.0)
    ci: ConfidenceInterval | None = None
    n_eff: float = Field(ge=0.0, default=0.0)
    raw_counts: dict[str, int] = Field(default_factory=dict)
    rung: Rung
    evidence_turns: list[int] = Field(default_factory=list)
    provenance_share_displayed: float | None = Field(default=None, ge=0.0, le=1.0)
    status_reason: str | None = None  # e.g. "no_ethics_events_detected" (ES)
    #: present iff status == MEASUREMENT_SATURATED — the censored "≥ X"/"≤ X"
    #: bound that replaces the (still-None) point value (v3 §A3/V3).
    censored: Censored | None = None
    flags: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _value_iff_ok(self) -> "DimensionScore":
        if self.status == ScoreStatus.OK and self.value is None:
            raise ValueError("status OK requires a value")
        if self.status != ScoreStatus.OK and self.value is not None:
            raise ValueError(f"status {self.status.value} must not carry a value (absent != zero)")
        return self

    @model_validator(mode="after")
    def _censored_iff_saturated(self) -> "DimensionScore":
        saturated = self.status == ScoreStatus.MEASUREMENT_SATURATED
        if saturated and self.censored is None:
            raise ValueError("MEASUREMENT_SATURATED requires a censored bound (report ≥ X / ≤ X)")
        if not saturated and self.censored is not None:
            raise ValueError("censored bound is only valid for MEASUREMENT_SATURATED")
        return self


# ──────────────────────────────────────────────────────────────────────────────
# Core schema 5/6 — StateVector (per-turn CSPC proxy output, brief §3.5)
# ──────────────────────────────────────────────────────────────────────────────


class StateVector(_Frozen):
    """One human turn's state proxies. A_t is Tier-2-only — always None in
    Scope A (schema present, needs telemetry)."""

    turn_index: int = Field(ge=0)
    load: LoadLabel | None = None
    epistemic: float | None = Field(default=None, ge=-1.0, le=1.0)
    metacog: MetacogLabel | None = None
    tom_signal: float | None = None
    a_t: float | None = None
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    #: per-turn evidence precision π_t ∈ (0, 1] — the single-turn analogue of the
    #: session precision-merge widening (smaller = degraded evidence context).
    #: None = N/A: the turn has no assessable state (absent ≠ full precision, #12).
    precision: float | None = Field(default=None, ge=0.0, le=1.0)
    #: named per-turn conditions that reduced π_t (e.g. "high_ecl", "surrender").
    #: Empty list = assessed, nothing degraded; never used to imply absence.
    cascade_flags: list[str] = Field(default_factory=list)


class StateValidity(_Frozen):
    """Session-level state validity gate (brief §3.5). M_t collapse widens all
    trait CIs and is reported as a caveat — scores are never suppressed."""

    state_compromised: bool = False
    m_t_collapse: bool = False
    surrender_detected: bool = False
    surrender_onset_turn: int | None = None
    epistemic_mean: float | None = Field(default=None, ge=-1.0, le=1.0)
    epistemic_slope: float | None = None
    tom_slope: float | None = None
    caveats: list[str] = Field(default_factory=list)
    rung: Rung = Rung.MEASURABLE


# ──────────────────────────────────────────────────────────────────────────────
# Dynamics + sustainability + claims components of the response
# ──────────────────────────────────────────────────────────────────────────────


class CellGatedProb(_Frozen):
    """A conditional probability that is N/A unless its event-count gate passes.
    value present iff n_events >= the configured gate — never a prob from 1 event."""

    value: float | None = Field(default=None, ge=0.0, le=1.0)
    n_events: int = Field(ge=0, default=0)


class FrictionTransitionMatrix(_Frozen):
    """The flagship E-FRICTION slice (brief §3.8). Cell-gated."""

    p_verify: CellGatedProb
    p_accept_flat: CellGatedProb
    p_disengage: CellGatedProb
    rung: Rung = Rung.MEASURABLE


class TransitionMetrics(_Frozen):
    """The five frozen transition-pattern metrics (spec §5.9d). None = gated N/A."""

    verify_after_error_rate: CellGatedProb
    constraint_before_generation_rate: CellGatedProb
    prediction_before_answer_rate: CellGatedProb
    accept_run_max: int | None = None
    accept_run_mean: float | None = None
    revision_after_output_rate: CellGatedProb
    rung: Rung = Rung.MEASURABLE


class ReactionSignatures(_Frozen):
    """π(r|e) with Dirichlet partial pooling; every (e, r) cell count-gated."""

    pi: dict[EventType, dict[ResponseClass, CellGatedProb]] = Field(default_factory=dict)
    ftm: FrictionTransitionMatrix
    transition_metrics: TransitionMetrics
    rung: Rung = Rung.MEASURABLE


class RegimeOverlay(_Frozen):
    """Rules-only descriptive overlay (spec §5.9f). No probabilities, no latent
    states — CSPC is the sole owner of latent state (non-negotiable #8)."""

    occupancy: dict[RegimeLabel, float] = Field(default_factory=dict)
    strip: list[RegimeLabel] = Field(default_factory=list)
    run_lengths: dict[RegimeLabel, list[int]] = Field(default_factory=dict)
    rung: Rung = Rung.MEASURABLE


class SHumanHat(_Frozen):
    """Ŝ_human = (r_auto − r_steer) × T_steered_out (brief §3.9/§7 — no κ,
    no counterfactual double-run). Falsifiability contract lives in the
    contract table; value None when A-turn/S-turn partition is degenerate."""

    value: float | None = None
    r_auto: float | None = None
    r_steer: float | None = None
    t_steered_out: float | None = None
    cache_multiplier: float = 1.0  # linear first
    status: ScoreStatus = ScoreStatus.NOT_APPLICABLE
    rung: Rung = Rung.DESIGNED


class DebtEwma(_Frozen):
    """Debt EWMA (α=0.3). Single session → INSUFFICIENT_HISTORY, never a debt
    score (non-negotiables #7, #12)."""

    mode: DebtMode
    value: float | None = None
    alpha: float = 0.3
    n_sessions: int = Field(ge=0, default=1)
    rung: Rung = Rung.MEASURABLE


class LambdaStub(_Frozen):
    """λ is a stub in Scope A: value null, rung DESIGNED, requires multi-session
    + probe (brief §3.9)."""

    value: None = None
    rung: Rung = Rung.DESIGNED
    note: str = "requires multi-session + probe"


class Sustainability(_Frozen):
    s_human_hat: SHumanHat
    debt_ewma: DebtEwma
    lambda_: LambdaStub = Field(default_factory=LambdaStub, alias="lambda")

    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True,
                              serialize_by_alias=True)


class SessionFlags(_Frozen):
    """Flag block of the ScoreResponse (brief §4.2). All inference-language
    flags; never a raw debt score."""

    fluent_incompetence: bool | None = None
    debt_flag: bool | None = None
    accept_run_max: int | None = None
    accept_run_mean: float | None = None
    theater_counter: int = Field(ge=0, default=0)
    judge_unavailable: bool = False
    judge_family_conflict: bool = False  # ADR-0002
    ec_low_calibration_confidence: bool = True  # stays True until corpus grows (#19)
    rung: Rung = Rung.MEASURABLE


class Composite(_Frozen):
    """Soft non-compensatory composite (brief §3.7). value None when gates fail.
    Never presented bare: always with CI + rung (non-negotiable #6)."""

    value: float | None = Field(default=None, ge=0.0, le=1.0)
    ci: ConfidenceInterval | None = None
    status: ScoreStatus = ScoreStatus.OK
    gates_passed: dict[str, bool] = Field(default_factory=dict)  # "scorability", "state_validity"
    state_compromised_caveat: bool = False
    rung: Rung = Rung.MEASURABLE

    @model_validator(mode="after")
    def _value_iff_ok(self) -> "Composite":
        if self.status == ScoreStatus.OK and self.value is None:
            raise ValueError("status OK requires a value")
        if self.status != ScoreStatus.OK and self.value is not None:
            raise ValueError("non-OK composite must not carry a value")
        return self


class Report(_Frozen):
    """Observed / Inferred / Hypothesized evidence levels (spec §9.0). The
    report generator structurally cannot emit above a field's rung; Tier-1
    user-facing text never contains the forbidden words (claims_table.yaml)."""

    observed: list[str] = Field(default_factory=list)
    inferred: list[str] = Field(default_factory=list)
    hypothesized: list[str] = Field(default_factory=list)
    tier_caveat: str
    rung: Rung = Rung.MEASURABLE


# ──────────────────────────────────────────────────────────────────────────────
# Core schema 6/6 — ScoreResponse (the API deliverable, brief §4.2)
# ──────────────────────────────────────────────────────────────────────────────


class ScoreResponse(_Frozen):
    """Full response of GET /v1/sessions/{id}/score."""

    schema_version: str = SCHEMA_VERSION
    session_id: str
    tier: Tier
    profile: dict[Dimension, DimensionScore]
    composite: Composite
    state_strip: list[StateVector]
    state_validity: StateValidity
    flags: SessionFlags
    reaction_signatures: ReactionSignatures
    regime_overlay: RegimeOverlay
    sustainability: Sustainability
    report: Report

    @model_validator(mode="after")
    def _exactly_eight_dimensions(self) -> "ScoreResponse":
        if set(self.profile.keys()) != set(Dimension):
            missing = set(Dimension) - set(self.profile.keys())
            extra = set(self.profile.keys()) - set(Dimension)
            raise ValueError(f"profile must contain exactly the 8 dimensions; missing={missing}, extra={extra}")
        return self


# ──────────────────────────────────────────────────────────────────────────────
# Leaf-module I/O types (referenced by INTERFACES.md)
# ──────────────────────────────────────────────────────────────────────────────


class TurnTags(_Frozen):
    """Intent-tagger output for one human turn (Codex: src/trait/tagger.py)."""

    turn_index: int = Field(ge=0)
    tags: list[IntentTag]


class MetacogResult(_Frozen):
    """Metacog classifier output (Antigravity: src/state/metacog_classifier.py).
    surrender = accept-run >= 3 consecutive flat accepts (brief §3.5)."""

    labels: list[MetacogLabel | None]  # one per human turn; None = untagged (absent ≠ PASSIVE)
    surrender_detected: bool
    surrender_onset_turn: int | None = None


class VigilanceResult(_Frozen):
    """Epistemic-vigilance pattern for a session (Sperber & Mercier; v3.21 §3.1
    C3). Codex: src/trait/vigilance.py. A DISTRIBUTED pattern (justification
    requests, source probing, prior-before-accept, challenge-then-accept) — hard
    to fake across a whole session. The score CONDITIONS EC/CA evidence PRECISION
    only; the score value never changes (#2). absent ≠ zero (#12: 0.0 means a
    genuine absence of signals, score is always present for a non-empty session)."""

    score: float = Field(ge=0.0, le=1.0)
    n_signals: int = Field(ge=0)
    pattern_detected: bool


class DimensionNormalization(_Frozen):
    """normalize.py output for one dimension: fired ÷ applicable opportunities,
    standardized so CA-17 gets no structural edge over AUI-12 (brief §3.7)."""

    dim: Dimension
    fired_weight: float = Field(ge=0.0)
    applicable_opportunities: int = Field(ge=0)
    normalized: float | None = Field(default=None, ge=0.0, le=1.0)
    status: ScoreStatus = ScoreStatus.OK


class NormalizedScores(_Frozen):
    """Full normalize.py output (Codex: src/aggregate/normalize.py)."""

    per_dimension: dict[Dimension, DimensionNormalization]


class JudgeDimScore(_Frozen):
    """One dimension from the LLM judge (dimension-grain, brief §3.6.4)."""

    score: float | None = Field(default=None, ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_turns: list[int] = Field(default_factory=list)
    tom_tag: str | None = None


class JudgeOutput(_Frozen):
    """Full judge result (CE: src/trait/judge/). All-fail → judge_unavailable=True
    and every score None — never zero (non-negotiable #12)."""

    scores: dict[Dimension, JudgeDimScore]
    judge_model: str
    judge_family: PartnerFamily
    prompt_version: str
    judge_unavailable: bool = False
    judge_family_conflict: bool = False  # ADR-0002
    raw_response: str | None = None  # literal model text, retained for audit (Track 1)


__all__ = [
    "SCHEMA_VERSION",
    # enums
    "Dimension", "Rung", "Actor", "Provenance", "EventType", "IntentTag",
    "Phase", "ResponseClass", "LoadLabel", "MetacogLabel", "RegimeLabel",
    "ScoreStatus", "DebtMode", "GroundingFunction", "SourceFormat",
    "PartnerFamily", "Tier",
    # constants
    "DIMENSION_NEURON_COUNTS", "DIMENSION_WEIGHTS",
    # core six
    "PartnerModel", "Event", "CanonicalSession", "DimensionScore",
    "StateVector", "ScoreResponse",
    # components
    "Turn", "ConfidenceInterval", "StateValidity", "CellGatedProb",
    "FrictionTransitionMatrix", "TransitionMetrics", "ReactionSignatures",
    "RegimeOverlay", "SHumanHat", "DebtEwma", "LambdaStub", "Sustainability",
    "SessionFlags", "Composite", "Report",
    # leaf I/O
    "TurnTags", "MetacogResult", "VigilanceResult", "DimensionNormalization",
    "NormalizedScores", "JudgeDimScore", "JudgeOutput",
]
