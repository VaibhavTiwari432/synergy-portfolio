"""
All Pydantic data contracts for the Chat Classifier v2.
Field names here are fixed — downstream stages must match them exactly.
Source: ChatClassifier_v2_Implementation_Brief.md §5 + CLAUDE_CODE_PROMPT_v2.md.

Score convention (v2): neuron scores are floats 0.0–1.0 throughout the pipeline.
  0.0 = No evidence the behavior was exhibited
  0.3 = Weak or inconsistent evidence
  0.6 = Moderate, recurring evidence
  1.0 = Strong, consistent, exemplary evidence
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


# ── Input layer ─────────────────────────────────────────────────────────────

class Turn(BaseModel):
    index: int                          # 0-based turn order
    role: Literal["human", "ai"]
    text: str
    timestamp: datetime | None = None


class RawChat(BaseModel):
    chat_id: str
    source_model: str                   # "chatgpt" | "claude" | "gemini" | ...
    turns: list[Turn]
    metadata: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def turns_are_sequentially_indexed(self) -> "RawChat":
        for i, t in enumerate(self.turns):
            if t.index != i:
                raise ValueError(
                    f"Turn at position {i} has index={t.index}; expected {i}."
                )
        return self


# ── Chunker output ───────────────────────────────────────────────────────────

class Chunk(BaseModel):
    chunk_index: int
    turn_start: int      # inclusive
    turn_end: int        # inclusive
    turns: list[Turn]


# ── Intent tagger output ─────────────────────────────────────────────────────

IntentTag = Literal[
    "VERIFY",
    "EXTRACT",
    "INJECT_CONTEXT",
    "PIVOT",
    "ANTHROPOMORPHIZE",
    "ETHICS_GATE",
    "OVERRIDE",
    "DECOMPOSE",
    "SCAFFOLD",
    "SELF_AUDIT",
]

class TaggedTurn(BaseModel):
    turn: Turn
    tags: list[IntentTag]
    dominant_intent: IntentTag | None   # single primary intent for the turn


# ── Neuron contract (loaded from contract_table.yaml) ────────────────────────

class NeuronContract(BaseModel):
    id: str
    dimension: str
    type: Literal["behavioral", "metacognitive", "structural"]
    context_scope: Literal["chunk", "chat"]
    extractor_type: Literal["deterministic", "embedding", "llm_judge"]
    micro_rubric: dict[str, str] | None = None
    detector: str | None = None
    valence: Literal[1, -1]
    applicability_rule: str
    sector_universal: bool


# ── Neuron data record (loaded from neurons_v6.json) ─────────────────────────

class NeuronMeta(BaseModel):
    code: str
    dimension: str
    layer: str
    name: str
    definition: str
    version: str
    weight: float = 1.0


# ── Extraction output ────────────────────────────────────────────────────────

class ItemResponse(BaseModel):
    neuron_id: str
    dimension: str
    scope: Literal["chunk", "chat"]
    chunk_index: int | None            # None for chat-scope items
    applicable: bool
    score: float | None = None         # 0.0–1.0 if applicable, else None
    raw_value: float | None = None     # pre-discretization continuous value
    extractor: str

    @model_validator(mode="after")
    def absent_is_not_zero(self) -> "ItemResponse":
        """Non-applicable neurons must have score=None. Absent ≠ scored zero."""
        if not self.applicable and self.score is not None:
            raise ValueError(
                f"Neuron {self.neuron_id}: non-applicable items must have "
                "score=None. Absent ≠ scored zero. (Brief §2 guardrail 1)"
            )
        return self

    @model_validator(mode="after")
    def score_in_range(self) -> "ItemResponse":
        if self.score is not None and not (0.0 <= self.score <= 1.0):
            raise ValueError(
                f"Neuron {self.neuron_id}: score={self.score} out of range [0.0, 1.0]."
            )
        return self


NeuronMatrix = list[ItemResponse]


# ── Judge output ─────────────────────────────────────────────────────────────

class JudgeOutput(BaseModel):
    """Raw validated output from the Gemini LLM judge (Stage 5)."""
    neuron_scores: dict[str, float]   # exactly 107 keys, all values in [0.0, 1.0]
    model_used: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None

    @model_validator(mode="after")
    def validate_scores(self) -> "JudgeOutput":
        from chat_classifier.config import NEURON_COUNT_EXPECTED
        if len(self.neuron_scores) != NEURON_COUNT_EXPECTED:
            raise ValueError(
                f"JudgeOutput has {len(self.neuron_scores)} neuron scores; "
                f"expected exactly {NEURON_COUNT_EXPECTED}."
            )
        for k, v in self.neuron_scores.items():
            if not (0.0 <= v <= 1.0):
                raise ValueError(
                    f"Neuron {k} score={v} out of range [0.0, 1.0]."
                )
        return self


# ── Composite metrics (Stage 4) ───────────────────────────────────────────────

class CompositeMetrics(BaseModel):
    attribution_gap: float | None = None          # 0.0–1.0; high = offloading
    verification_ratio: float | None = None       # VERIFY turns / AI response turns
    generative_query_ratio: float | None = None   # generative / (generative + extractive)
    actualization_depth: float | None = None      # avg complete loops per task
    semantic_distance_delta: float | None = None  # first vs final prompt similarity
    iteration_depth: float | None = None          # avg refinement cycles per task
    # For cognitive-debt flag (session split):
    verification_ratio_first_half: float | None = None
    verification_ratio_second_half: float | None = None
    session_turns: int = 0


# ── Scoring output ───────────────────────────────────────────────────────────

class NeuronContribution(BaseModel):
    neuron_id: str
    signed_contribution: float   # how much this item moved the score


class DimensionScore(BaseModel):
    dimension: str
    scorable: bool
    na_reason: Literal["structural", "insufficient_length"] | None = None
    score: float | None = None               # 0.0–1.0 weighted mean
    credible_interval: tuple[float, float] | None = None
    n_items: int = 0
    top_contributors: list[NeuronContribution] = Field(default_factory=list)

    @model_validator(mode="after")
    def na_reason_consistent(self) -> "DimensionScore":
        if not self.scorable and self.na_reason is None:
            raise ValueError(
                f"Dimension {self.dimension} not scorable but na_reason is None."
            )
        if self.scorable and self.na_reason is not None:
            raise ValueError(
                f"Dimension {self.dimension} scorable but na_reason={self.na_reason!r} set."
            )
        return self

    @model_validator(mode="after")
    def score_requires_interval(self) -> "DimensionScore":
        if self.scorable and self.score is not None and self.credible_interval is None:
            raise ValueError(
                f"Dimension {self.dimension}: score set without credible_interval. "
                "Every estimate ships with uncertainty."
            )
        return self


class SynergyReport(BaseModel):
    """Final output of the full pipeline — matches CLAUDE_CODE_PROMPT_v2.md §output."""
    session_id: str
    user_id: str = "anonymous"
    transcript_turns: int
    neuron_scores: dict[str, float] = Field(default_factory=dict)
    dimension_scores: dict[str, float | None] = Field(default_factory=dict)
    pillar_scores: dict[str, float | None] = Field(default_factory=dict)
    composite_metrics: CompositeMetrics = Field(default_factory=CompositeMetrics)
    risk_flags: dict[str, bool] = Field(default_factory=dict)
    synergy_score_kappa: float | None = None
    phase_distribution: dict[str, float] = Field(default_factory=dict)
    intent_tag_counts: dict[str, int] = Field(default_factory=dict)
    coverage: dict[str, int] = Field(default_factory=dict)   # {"scored": k, "total": n}
    flags: list[str] = Field(default_factory=list)
    confidence_note: str = ""


# ── Calibration types ────────────────────────────────────────────────────────

class GoldCodeRow(BaseModel):
    chat_id: str
    neuron_id: str
    dimension: str
    rater_id: str
    score: float        # 0.0–1.0, human-assigned
    notes: str = ""


class ICCResult(BaseModel):
    dimension: str
    inter_rater_icc: float | None = None
    judge_human_icc: float | None = None
    certified: bool = False
    note: str = ""
