"""
Stage 4 — Composite Metrics Calculator.

Derives all 6 behavioural composite metrics + A/S ratios + phase distribution
from tagged turns. No LLM calls — purely deterministic / embedding-based.

Length normalization (§3.7):
  - Frequency-type neurons expressed as rates per 1000 tokens
  - Semantic distance uses all-MiniLM-L6-v2 (lazy loaded)

Returns None gracefully when insufficient data.

Reference: SAF_ARI_Final_Master_Compilation.md §6.4, brief Stage 4
"""

from __future__ import annotations

from dataclasses import dataclass, field

from saf_chat_analyser.src.parser.transcript_parser import Turn
from saf_chat_analyser.src.tagger.intent_tagger import TaggedTurn, intent_counts
from saf_chat_analyser.src.tagger.turn_classifier import compute_as_ratios
from saf_chat_analyser.src.tagger.phase_classifier import classify_phases

# ── Sentence-transformer (lazy) ───────────────────────────────────────────────
_ST_MODEL = None


def _get_st_model():
    global _ST_MODEL
    if _ST_MODEL is None:
        from sentence_transformers import SentenceTransformer  # noqa
        _ST_MODEL = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    return _ST_MODEL


@dataclass
class CompositeMetrics:
    # Core behavioural metrics
    attribution_gap: float | None
    verification_ratio: float | None
    generative_query_ratio: float | None
    actualization_depth: float | None
    iteration_depth: float | None
    semantic_distance_delta: float | None

    # Temporal split (for within-session cognitive debt proxy)
    vr_first_half: float | None
    vr_second_half: float | None
    session_turns: int

    # A/S turn split (foundation of S_human estimator §5.3.1)
    a_turn_ratio: float
    s_turn_ratio: float

    # Phase distribution (AILit/OECD 4-domain)
    phase_distribution: dict[str, float] = field(default_factory=dict)


def compute_metrics(
    turns: list[Turn],
    tagged_turns: list[TaggedTurn],
) -> CompositeMetrics:
    """Compute all composite metrics for a session."""
    human_tt = [tt for tt in tagged_turns if tt.turn.role == "human"]
    total_human = len(human_tt)
    total_ai = sum(1 for t in turns if t.role == "ai")

    # ── verification_ratio ────────────────────────────────────────────────────
    verify_count = sum(1 for tt in human_tt if "VERIFY" in tt.tags)
    vr = verify_count / total_ai if total_ai > 0 else None

    # ── generative_query_ratio ────────────────────────────────────────────────
    _generative = {"VERIFY", "SELF_AUDIT", "INJECT_CONTEXT", "DECOMPOSE", "SCAFFOLD"}
    _extractive = {"EXTRACT"}
    gen = sum(1 for tt in human_tt if any(t in _generative for t in tt.tags))
    ext = sum(
        1 for tt in human_tt
        if any(t in _extractive for t in tt.tags)
        and not any(t in _generative for t in tt.tags)
    )
    pool = gen + ext
    gr = gen / pool if pool > 0 else None

    # ── attribution_gap ───────────────────────────────────────────────────────
    # Proxy: fraction of human turns that are pure passive EXTRACT
    pure_extract = sum(
        1 for tt in human_tt
        if tt.dominant_intent == "EXTRACT" and len(tt.tags) == 1
    )
    attribution_gap = pure_extract / total_human if total_human > 0 else None

    # ── verification half-split ───────────────────────────────────────────────
    vr_first: float | None = None
    vr_second: float | None = None
    if total_human >= 4:
        mid = total_human // 2
        first_half = human_tt[:mid]
        second_half = human_tt[mid:]
        # Count AI turns in each half by turn index boundary
        split_idx = first_half[-1].turn.index
        ai_first = sum(1 for t in turns if t.role == "ai" and t.index <= split_idx)
        ai_second = total_ai - ai_first
        v_first = sum(1 for tt in first_half if "VERIFY" in tt.tags)
        v_second = sum(1 for tt in second_half if "VERIFY" in tt.tags)
        vr_first = v_first / ai_first if ai_first > 0 else 0.0
        vr_second = v_second / ai_second if ai_second > 0 else 0.0

    # ── actualization_depth ───────────────────────────────────────────────────
    _scope_mod = {"OVERRIDE", "SCAFFOLD", "PIVOT", "INJECT_CONTEXT"}
    task_count = max(1, sum(1 for tt in human_tt if "DECOMPOSE" in tt.tags))
    loop_count = sum(
        1 for tt in human_tt[1:]
        if any(tag in _scope_mod for tag in tt.tags)
    )
    actualization_depth = (
        min(loop_count / task_count, 1.0) if total_human > 0 else None
    )

    # ── iteration_depth ───────────────────────────────────────────────────────
    _refinement = {"OVERRIDE", "SCAFFOLD", "PIVOT"}
    refine_count = sum(
        1 for tt in human_tt
        if any(tag in _refinement for tag in tt.tags)
    )
    iteration_depth = refine_count / total_human if total_human > 0 else None

    # ── semantic_distance_delta ───────────────────────────────────────────────
    human_texts = [tt.turn.content for tt in human_tt]
    semantic_distance_delta = _compute_semantic_distance(human_texts)

    # ── A/S ratios ────────────────────────────────────────────────────────────
    as_ratios = compute_as_ratios(tagged_turns)

    # ── Phase distribution ────────────────────────────────────────────────────
    phase_dist = classify_phases(tagged_turns)

    return CompositeMetrics(
        attribution_gap=attribution_gap,
        verification_ratio=vr,
        generative_query_ratio=gr,
        actualization_depth=actualization_depth,
        semantic_distance_delta=semantic_distance_delta,
        iteration_depth=iteration_depth,
        vr_first_half=vr_first,
        vr_second_half=vr_second,
        session_turns=len(turns),
        a_turn_ratio=as_ratios["a_turn_ratio"],
        s_turn_ratio=as_ratios["s_turn_ratio"],
        phase_distribution=phase_dist,
    )


def _compute_semantic_distance(human_texts: list[str]) -> float | None:
    if len(human_texts) < 2:
        return None
    try:
        import numpy as np  # noqa
        model = _get_st_model()
        embeddings = model.encode(
            [human_texts[0], human_texts[-1]],
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        similarity = float(np.dot(embeddings[0], embeddings[1]))
        return float(max(0.0, min(1.0, 1.0 - similarity)))
    except ImportError:
        return None
