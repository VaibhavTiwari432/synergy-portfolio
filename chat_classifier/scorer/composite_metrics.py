"""
Stage 4 — Composite Metrics Calculator.

Derives behavioural composite metrics from tagged turns and raw chat.
These metrics feed directly into the judge prompt and the risk flag evaluator.

All metrics are derived from observable behaviour only — no LLM calls.
"""

from __future__ import annotations

from chat_classifier.schemas import CompositeMetrics, RawChat, TaggedTurn


def compute_metrics(chat: RawChat, tagged_turns: list[TaggedTurn]) -> CompositeMetrics:
    """
    Compute all composite metrics for a session.

    Metrics that require data we don't have yet (semantic similarity,
    actualization depth) are left as None rather than fabricated.
    """
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

    # ── metrics that require NLP / embeddings (deferred) ─────────────────────
    # actualization_depth, semantic_distance_delta, iteration_depth
    # are left None — they will be filled by a separate embedding pass
    # once we have sentence-transformer support wired up.

    return CompositeMetrics(
        attribution_gap=attribution_gap,
        verification_ratio=vr,
        generative_query_ratio=gr,
        actualization_depth=None,
        semantic_distance_delta=None,
        iteration_depth=None,
        verification_ratio_first_half=vr_first,
        verification_ratio_second_half=vr_second,
        session_turns=len(chat.turns),
    )
