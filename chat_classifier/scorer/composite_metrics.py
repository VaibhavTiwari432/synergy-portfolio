"""
Stage 4 — Composite Metrics Calculator.

Derives behavioural composite metrics from tagged turns and raw chat.
These metrics feed directly into the judge prompt and the risk flag evaluator.

All metrics are derived from observable behaviour only — no LLM calls.
"""

from __future__ import annotations

from chat_classifier.schemas import CompositeMetrics, RawChat, TaggedTurn

# ── Sentence-transformer model (lazy, loaded on first use) ────────────────────
# Avoids a 3–4 s startup cost for callers that don't need semantic distance.
_ST_MODEL = None


def _get_st_model():
    global _ST_MODEL
    if _ST_MODEL is None:
        from sentence_transformers import SentenceTransformer  # noqa: PLC0415
        _ST_MODEL = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    return _ST_MODEL


def _compute_semantic_distance(human_texts: list[str]) -> float | None:
    """
    1 - cosine_similarity(first_human_prompt, last_human_prompt).
    Returns None if fewer than 2 human turns exist (no meaningful delta).
    Falls back to None if sentence-transformers is not installed.
    """
    if len(human_texts) < 2:
        return None
    try:
        import numpy as np  # noqa: PLC0415
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


def compute_metrics(chat: RawChat, tagged_turns: list[TaggedTurn]) -> CompositeMetrics:
    """Compute all composite metrics for a session."""
    human_turns = [tt for tt in tagged_turns if tt.turn.role == "human"]
    total_human = len(human_turns)
    total_ai = sum(1 for t in chat.turns if t.role == "ai")

    # ── verification_ratio ────────────────────────────────────────────────────
    # Fraction of AI turns that received a VERIFY response from the human.
    verify_count = sum(1 for tt in human_turns if "VERIFY" in tt.tags)
    vr = verify_count / total_ai if total_ai > 0 else None

    # ── generative_query_ratio ────────────────────────────────────────────────
    # Fraction of human turns that are generative (VERIFY + SELF_AUDIT +
    # INJECT_CONTEXT) vs extractive (EXTRACT), excluding OVERRIDE and others.
    generative_tags = {"VERIFY", "SELF_AUDIT", "INJECT_CONTEXT", "DECOMPOSE", "SCAFFOLD"}
    extractive_tags = {"EXTRACT"}
    gen_count = sum(
        1 for tt in human_turns
        if any(t in generative_tags for t in tt.tags)
    )
    ext_count = sum(
        1 for tt in human_turns
        if any(t in extractive_tags for t in tt.tags)
        and not any(t in generative_tags for t in tt.tags)
    )
    pool = gen_count + ext_count
    gr = gen_count / pool if pool > 0 else None

    # ── attribution_gap ───────────────────────────────────────────────────────
    # Proxy: fraction of human turns that are pure EXTRACT with no generative
    # signal. High value = user passively consuming AI output.
    pure_extract = sum(
        1 for tt in human_turns
        if tt.dominant_intent == "EXTRACT"
        and len(tt.tags) == 1
    )
    attribution_gap = pure_extract / total_human if total_human > 0 else None

    # ── verification decay (first half vs second half) ────────────────────────
    # Tracks whether the user's verification behaviour drops off over time.
    vr_first: float | None = None
    vr_second: float | None = None
    if total_human >= 4:
        mid = total_human // 2
        first_half = human_turns[:mid]
        second_half = human_turns[mid:]
        ai_first = sum(1 for t in chat.turns[:chat.turns[first_half[-1].turn.index].index + 1] if t.role == "ai")
        ai_second = total_ai - ai_first
        v_first = sum(1 for tt in first_half if "VERIFY" in tt.tags)
        v_second = sum(1 for tt in second_half if "VERIFY" in tt.tags)
        vr_first = v_first / ai_first if ai_first > 0 else 0.0
        vr_second = v_second / ai_second if ai_second > 0 else 0.0

    # ── actualization_depth ───────────────────────────────────────────────────
    # A complete actualization loop = user sends prompt → receives AI output →
    # sends a follow-up that modifies scope/content (OVERRIDE, SCAFFOLD, PIVOT,
    # INJECT_CONTEXT), not just a clarification.
    # tasks = number of DECOMPOSE turns (each marks a sub-task boundary) or 1
    # if no DECOMPOSE exists (whole session is one task).
    # Score = min(loops / tasks, 1.0)
    _SCOPE_MODIFYING = {"OVERRIDE", "SCAFFOLD", "PIVOT", "INJECT_CONTEXT"}
    task_count = max(1, sum(1 for tt in human_turns if "DECOMPOSE" in tt.tags))
    # Skip the first human turn (it's the initial prompt, not a follow-up)
    loop_count = sum(
        1 for tt in human_turns[1:]
        if any(tag in _SCOPE_MODIFYING for tag in tt.tags)
    )
    actualization_depth = min(loop_count / task_count, 1.0) if total_human > 0 else None

    # ── iteration_depth ───────────────────────────────────────────────────────
    # Fraction of human turns that are substantive refinements.
    # OVERRIDE, SCAFFOLD, PIVOT = refinement; EXTRACT alone = not.
    _REFINEMENT_TAGS = {"OVERRIDE", "SCAFFOLD", "PIVOT"}
    refinement_count = sum(
        1 for tt in human_turns
        if any(tag in _REFINEMENT_TAGS for tag in tt.tags)
    )
    iteration_depth = refinement_count / total_human if total_human > 0 else None

    # ── semantic_distance_delta ───────────────────────────────────────────────
    # 1 - cosine_similarity(first_human_prompt, last_human_prompt).
    # High = user redirected substantially; low = accepted AI's initial frame.
    # Returns None when <2 human turns (no meaningful delta exists).
    human_texts = [tt.turn.text for tt in human_turns]
    semantic_distance_delta = _compute_semantic_distance(human_texts)

    return CompositeMetrics(
        attribution_gap=attribution_gap,
        verification_ratio=vr,
        generative_query_ratio=gr,
        actualization_depth=actualization_depth,
        semantic_distance_delta=semantic_distance_delta,
        iteration_depth=iteration_depth,
        verification_ratio_first_half=vr_first,
        verification_ratio_second_half=vr_second,
        session_turns=len(chat.turns),
    )
