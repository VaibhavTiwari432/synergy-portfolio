"""
Stage 5 — Gemini LLM Judge wrapper.
Sends a structured transcript summary to Gemini and returns a validated
JudgeOutput with exactly 107 neuron scores in [0.0, 1.0].

Usage:
    judge = GeminiJudge(api_key="...")
    output = judge.score(summary)
"""

from __future__ import annotations

import json
import os
import re
import time
from typing import Any

from pydantic import ValidationError

from chat_classifier.config import (
    GEMINI_MAX_RETRIES,
    GEMINI_MODEL,
    GEMINI_TEMPERATURE,
    NEURON_COUNT_EXPECTED,
)
from chat_classifier.schemas import (
    CompositeMetrics,
    JudgeOutput,
    RawChat,
    TaggedTurn,
)
from chat_classifier.scorer.judge_prompt import JUDGE_SYSTEM_PROMPT, JUDGE_PROMPT_VERSION


# ── Transcript summary builder ────────────────────────────────────────────────

def build_transcript_summary(
    chat: RawChat,
    tagged_turns: list[TaggedTurn],
    metrics: CompositeMetrics,
    phase_distribution: dict[str, float],
    intent_counts: dict[str, int],
) -> str:
    """
    Produce the structured text summary that the LLM judge receives.
    Sends behavioral evidence, not raw text, to minimise tokens and
    keep the judge focused on what it should score.
    """
    lines: list[str] = []
    lines.append(f"SESSION ID: {chat.chat_id}")
    lines.append(f"SOURCE MODEL: {chat.source_model}")
    lines.append(f"TOTAL TURNS: {len(chat.turns)}")
    lines.append("")

    # Tagged turn summary (human turns only, trimmed to 300 chars each)
    lines.append("=== TAGGED USER TURNS ===")
    human_count = 0
    for tt in tagged_turns:
        if tt.turn.role != "human":
            continue
        human_count += 1
        text_preview = tt.turn.text[:300].replace("\n", " ")
        tag_str = ", ".join(tt.tags) if tt.tags else "EXTRACT"
        dominant = tt.dominant_intent or "EXTRACT"
        lines.append(
            f"[T{tt.turn.index:03d}] [{dominant}] tags=[{tag_str}] "
            f'"{text_preview}"'
        )
    lines.append(f"(Total human turns: {human_count})")
    lines.append("")

    # Intent tag counts
    lines.append("=== INTENT TAG COUNTS ===")
    for tag, count in intent_counts.items():
        lines.append(f"  {tag}: {count}")
    lines.append("")

    # Phase distribution
    lines.append("=== PHASE DISTRIBUTION ===")
    for phase, frac in phase_distribution.items():
        lines.append(f"  {phase}: {frac:.2f}")
    lines.append("")

    # Composite metrics
    lines.append("=== COMPOSITE METRICS ===")
    m = metrics
    lines.append(f"  attribution_gap: {_fmt(m.attribution_gap)}")
    lines.append(f"  verification_ratio: {_fmt(m.verification_ratio)}")
    lines.append(f"  generative_query_ratio: {_fmt(m.generative_query_ratio)}")
    lines.append(f"  actualization_depth: {_fmt(m.actualization_depth)}")
    lines.append(f"  semantic_distance_delta: {_fmt(m.semantic_distance_delta)}")
    lines.append(f"  iteration_depth: {_fmt(m.iteration_depth)}")
    lines.append(f"  verification_ratio_first_half: {_fmt(m.verification_ratio_first_half)}")
    lines.append(f"  verification_ratio_second_half: {_fmt(m.verification_ratio_second_half)}")
    lines.append(f"  session_turns: {m.session_turns}")

    return "\n".join(lines)


def _fmt(v: float | None) -> str:
    return f"{v:.3f}" if v is not None else "N/A"


# ── Response parser ───────────────────────────────────────────────────────────

def _extract_json(text: str) -> dict[str, Any]:
    """
    Extract a JSON object from the model's response text.
    Handles three common formats:
      1. Bare JSON object
      2. JSON inside a ```json ... ``` fence
      3. JSON inside a ``` ... ``` fence (no language tag)
    """
    # Try fenced block first
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        return json.loads(fence.group(1))
    # Try first { ... } span
    brace_match = re.search(r"\{.*\}", text, re.DOTALL)
    if brace_match:
        return json.loads(brace_match.group(0))
    raise ValueError(f"No JSON object found in judge response. Raw: {text[:500]}")


def _validate_scores(raw: dict[str, Any]) -> dict[str, float]:
    """
    Coerce and validate the raw score dict.
    - All values clipped to [0.0, 1.0].
    - Missing neurons set to 0.0 with a warning (parser should never drop a key).
    - Returns a new dict with float values.
    """
    from chat_classifier.config import NEURONS_FILE
    import json as _json

    with open(NEURONS_FILE) as f:
        expected_ids = set(_json.load(f).keys())

    validated: dict[str, float] = {}
    missing: list[str] = []

    for nid in expected_ids:
        raw_val = raw.get(nid)
        if raw_val is None:
            missing.append(nid)
            validated[nid] = 0.0
        else:
            validated[nid] = max(0.0, min(1.0, float(raw_val)))

    if missing:
        import warnings
        warnings.warn(
            f"Judge response missing {len(missing)} neurons — set to 0.0: "
            f"{missing[:5]}{'...' if len(missing) > 5 else ''}",
            stacklevel=3,
        )

    return validated


# ── Main judge class ──────────────────────────────────────────────────────────

class GeminiJudge:
    """
    Wrapper around the Gemini API for ARI neuron scoring.
    Each call sends a structured transcript summary and returns a JudgeOutput.
    """

    def __init__(self, api_key: str | None = None, model: str = GEMINI_MODEL):
        try:
            from google import genai
            from google.genai import types
        except ImportError as e:
            raise ImportError(
                "google-genai package not installed. Run: pip install google-genai"
            ) from e

        self._genai = genai
        self._types = types
        self._api_key = api_key or os.environ.get("GEMINI_API_KEY", "")
        if not self._api_key:
            raise ValueError(
                "Gemini API key required. Pass api_key= or set GEMINI_API_KEY env var."
            )
        self._client = genai.Client(api_key=self._api_key)
        self.model = model

    def score(
        self,
        chat: RawChat,
        tagged_turns: list[TaggedTurn],
        metrics: CompositeMetrics,
        phase_distribution: dict[str, float] | None = None,
        intent_counts: dict[str, int] | None = None,
    ) -> JudgeOutput:
        """
        Score a transcript. Retries up to GEMINI_MAX_RETRIES on parse failures.

        Returns:
            JudgeOutput with 107 validated float scores.

        Raises:
            RuntimeError if all retries fail.
        """
        if phase_distribution is None:
            phase_distribution = {}
        if intent_counts is None:
            intent_counts = {}

        summary = build_transcript_summary(
            chat, tagged_turns, metrics, phase_distribution, intent_counts
        )

        last_error: Exception | None = None
        for attempt in range(1, GEMINI_MAX_RETRIES + 1):
            try:
                raw_text = self._call_api(summary)
                raw_dict = _extract_json(raw_text)
                validated_scores = _validate_scores(raw_dict)
                return JudgeOutput(
                    neuron_scores=validated_scores,
                    model_used=self.model,
                )
            except (json.JSONDecodeError, ValidationError, ValueError) as exc:
                last_error = exc
                if attempt < GEMINI_MAX_RETRIES:
                    time.sleep(1.5 * attempt)
                continue

        raise RuntimeError(
            f"Gemini judge failed after {GEMINI_MAX_RETRIES} attempts. "
            f"Last error: {last_error}"
        )

    def _call_api(self, user_content: str) -> str:
        """Single API call. Returns raw response text."""
        response = self._client.models.generate_content(
            model=self.model,
            contents=user_content,
            config=self._types.GenerateContentConfig(
                system_instruction=JUDGE_SYSTEM_PROMPT,
                temperature=GEMINI_TEMPERATURE,
                response_mime_type="application/json",
            ),
        )
        return response.text
