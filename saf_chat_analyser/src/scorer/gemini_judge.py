"""
Stage 5 — Gemini LLM Judge with Dual-Granularity Transcript Views.

CRITICAL ARCHITECTURAL CHANGE from prior build:
  The judge receives TWO VIEWS, not one:
  1. Chunk-level view (3-turn sliding windows) for state-diagnostic neurons:
     EC, PR, AL, ES — captures per-turn trajectory (verify/override events)
  2. Chat-level view (full session summary) for competency-diagnostic neurons:
     CS, CA, CD, AUI — requires global session context

Why dual-granularity matters:
  A user who verified in turns 1-6 then surrendered in turns 7-14 must
  score differently on EC than a user with consistent low verification.
  An aggregate summary cannot show this trajectory collapse.

Reference: SAF_ARI_Final_Master_Compilation.md §2.1, §6.2, brief Stage 5
"""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any

from saf_chat_analyser.src.parser.transcript_parser import Turn
from saf_chat_analyser.src.tagger.intent_tagger import TaggedTurn
from saf_chat_analyser.src.metrics.composite_metrics import CompositeMetrics
from saf_chat_analyser.src.scorer.judge_prompt import (
    JUDGE_SYSTEM_PROMPT,
    JUDGE_PROMPT_VERSION,
)

# ── Configuration ─────────────────────────────────────────────────────────────
GEMINI_MODEL = "gemini-2.0-flash"
GEMINI_TEMPERATURE = 0.1
MAX_RETRIES = 2
NEURON_COUNT_EXPECTED = 107
CHUNK_WINDOW = 3        # 3-turn sliding window for chunk-level view
TURN_PREVIEW_CHARS = 120

# Neurons that use chunk-level (state-diagnostic) view
_STATE_DIAGNOSTIC_DIMS = {"EC", "PR", "AL", "ES"}
# Neurons that use chat-level (competency-diagnostic) view
_COMPETENCY_DIAGNOSTIC_DIMS = {"CS", "CA", "CD", "AUI"}

# Path to neurons file — relative to this file's package root
_NEURONS_FILE = Path(__file__).parents[3] / "data" / "neurons_v6.json"


# ── Chunk-level view builder ──────────────────────────────────────────────────

def _build_chunk_view(
    turns: list[Turn],
    tagged_turns: list[TaggedTurn],
) -> str:
    """
    Build the chunk-level view: 3-turn sliding windows showing per-turn
    behavioral trajectory. Used for EC, PR, AL, ES scoring.
    """
    lines: list[str] = []
    lines.append("=== VIEW 1: CHUNK-LEVEL (for EC, PR, AL, ES scoring) ===")
    lines.append("3-turn sliding windows. Captures verification/override trajectory.")
    lines.append("")

    tag_by_index: dict[int, TaggedTurn] = {tt.turn.index: tt for tt in tagged_turns}
    n = len(turns)

    # Sliding 3-turn windows; step by 1 for overlap
    step = max(1, CHUNK_WINDOW - 1)
    windows: list[tuple[int, int]] = []
    i = 0
    while i < n:
        end = min(i + CHUNK_WINDOW, n)
        windows.append((i, end))
        if end == n:
            break
        i += step

    for w_num, (start, end) in enumerate(windows, 1):
        window_turns = turns[start:end]
        lines.append(f"--- Window {w_num} (turns {start}–{end - 1}) ---")

        verify_events: list[str] = []
        override_events: list[str] = []

        for t in window_turns:
            tt = tag_by_index.get(t.index)
            tags_str = ", ".join(tt.tags) if tt and tt.tags else "EXTRACT"
            preview = t.content[:TURN_PREVIEW_CHARS].replace("\n", " ")
            role_label = "H" if t.role == "human" else "A"
            lines.append(
                f"  [T{t.index:03d}][{role_label}] tags=[{tags_str}] \"{preview}\""
            )
            if tt and "VERIFY" in tt.tags:
                verify_events.append(f"T{t.index:03d}")
            if tt and "OVERRIDE" in tt.tags:
                override_events.append(f"T{t.index:03d}")

        if verify_events:
            lines.append(f"  ** VERIFY events: {', '.join(verify_events)}")
        if override_events:
            lines.append(f"  ** OVERRIDE events: {', '.join(override_events)}")
        lines.append("")

    return "\n".join(lines)


# ── Chat-level view builder ───────────────────────────────────────────────────

def _build_chat_view(
    turns: list[Turn],
    tagged_turns: list[TaggedTurn],
    metrics: CompositeMetrics,
    phase_distribution: dict[str, float],
    intent_counts: dict[str, int],
) -> str:
    """
    Build the chat-level view: full session aggregate.
    Used for CS, CA, CD, AUI scoring.
    """
    lines: list[str] = []
    lines.append("=== VIEW 2: CHAT-LEVEL (for CS, CA, CD, AUI scoring) ===")
    lines.append("Full-session aggregate. Captures global competency traits.")
    lines.append("")

    human_turns = [t for t in turns if t.role == "human"]
    lines.append(f"Total turns: {len(turns)} ({len(human_turns)} human, {len(turns) - len(human_turns)} AI)")
    lines.append("")

    lines.append("Phase distribution:")
    for phase, frac in phase_distribution.items():
        lines.append(f"  {phase}: {frac:.2f}")
    lines.append("")

    lines.append("Intent tag counts:")
    for tag, count in sorted(intent_counts.items()):
        lines.append(f"  {tag}: {count}")
    lines.append("")

    lines.append("Composite metrics:")
    m = metrics
    lines.append(f"  attribution_gap: {_fmt(m.attribution_gap)}")
    lines.append(f"  verification_ratio: {_fmt(m.verification_ratio)}")
    lines.append(f"  generative_query_ratio: {_fmt(m.generative_query_ratio)}")
    lines.append(f"  actualization_depth: {_fmt(m.actualization_depth)}")
    lines.append(f"  iteration_depth: {_fmt(m.iteration_depth)}")
    lines.append(f"  semantic_distance_delta: {_fmt(m.semantic_distance_delta)}")
    lines.append(f"  vr_first_half: {_fmt(m.vr_first_half)}")
    lines.append(f"  vr_second_half: {_fmt(m.vr_second_half)}")
    lines.append(f"  a_turn_ratio: {m.a_turn_ratio:.3f}")
    lines.append(f"  s_turn_ratio: {m.s_turn_ratio:.3f}")
    lines.append(f"  session_turns: {m.session_turns}")
    lines.append("")

    # Human turns summary — last 10 for recency context
    lines.append("Recent human turns (last 10):")
    human_tt = [tt for tt in tagged_turns if tt.turn.role == "human"]
    for tt in human_tt[-10:]:
        tags_str = ", ".join(tt.tags) if tt.tags else "EXTRACT"
        preview = tt.turn.content[:200].replace("\n", " ")
        lines.append(f"  [T{tt.turn.index:03d}] [{tags_str}] \"{preview}\"")

    return "\n".join(lines)


def _fmt(v: float | None) -> str:
    return f"{v:.3f}" if v is not None else "N/A"


# ── Response parser and validator ─────────────────────────────────────────────

def _extract_json(text: str) -> dict[str, Any]:
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        return json.loads(fence.group(1))
    brace = re.search(r"\{.*\}", text, re.DOTALL)
    if brace:
        return json.loads(brace.group(0))
    raise ValueError(f"No JSON object in judge response. Raw: {text[:500]}")


def _validate_scores(raw: dict[str, Any]) -> dict[str, float]:
    """Validate and coerce scores; set missing neurons to 0.0 with warning."""
    with open(_NEURONS_FILE, encoding="utf-8") as f:
        expected_ids: set[str] = set(json.load(f).keys())

    assert len(expected_ids) == NEURON_COUNT_EXPECTED, (
        f"neurons_v6.json has {len(expected_ids)} entries, expected {NEURON_COUNT_EXPECTED}"
    )

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
    Gemini-based ARI neuron judge with dual-granularity transcript views.
    Separate model family from user-facing model (blind annotation property).
    """

    def __init__(self, api_key: str | None = None, model: str = GEMINI_MODEL):
        try:
            from google import genai
            from google.genai import types
        except ImportError as e:
            raise ImportError(
                "google-genai not installed. Run: pip install google-genai"
            ) from e

        self._genai = genai
        self._types = types
        self._api_key = api_key or os.environ.get("GEMINI_API_KEY", "")
        if not self._api_key:
            raise ValueError(
                "Gemini API key required. Pass api_key= or set GEMINI_API_KEY."
            )
        self._client = genai.Client(api_key=self._api_key)
        self.model = model
        self.prompt_version = JUDGE_PROMPT_VERSION

    def score(
        self,
        session_id: str,
        turns: list[Turn],
        tagged_turns: list[TaggedTurn],
        metrics: CompositeMetrics,
        phase_distribution: dict[str, float] | None = None,
        intent_counts: dict[str, int] | None = None,
    ) -> dict[str, float]:
        """
        Score a session with dual-granularity views.

        Returns:
            Dict of 107 validated float scores keyed by neuron code.

        Raises:
            RuntimeError after MAX_RETRIES failures.
        """
        if phase_distribution is None:
            phase_distribution = metrics.phase_distribution
        if intent_counts is None:
            from saf_chat_analyser.src.tagger.intent_tagger import intent_counts as _ic
            intent_counts = _ic(tagged_turns)

        prompt = self._build_dual_prompt(
            session_id, turns, tagged_turns, metrics, phase_distribution, intent_counts
        )

        last_error: Exception | None = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                raw_text = self._call_api(prompt)
                raw_dict = _extract_json(raw_text)
                return _validate_scores(raw_dict)
            except (json.JSONDecodeError, ValueError, AssertionError) as exc:
                last_error = exc
                if attempt < MAX_RETRIES:
                    time.sleep(1.5 * attempt)

        raise RuntimeError(
            f"Gemini judge failed after {MAX_RETRIES} attempts. "
            f"Last error: {last_error}"
        )

    def _build_dual_prompt(
        self,
        session_id: str,
        turns: list[Turn],
        tagged_turns: list[TaggedTurn],
        metrics: CompositeMetrics,
        phase_distribution: dict[str, float],
        intent_counts: dict[str, int],
    ) -> str:
        """Assemble the dual-granularity prompt for the judge."""
        header = (
            f"SESSION: {session_id}\n"
            f"Prompt version: {JUDGE_PROMPT_VERSION}\n\n"
            "Score all 107 ARI neurons using BOTH views below.\n"
            "Use VIEW 1 (chunk-level) for EC, PR, AL, ES neurons.\n"
            "Use VIEW 2 (chat-level) for CS, CA, CD, AUI neurons.\n\n"
        )
        chunk_view = _build_chunk_view(turns, tagged_turns)
        chat_view = _build_chat_view(
            turns, tagged_turns, metrics, phase_distribution, intent_counts
        )
        return header + chunk_view + "\n\n" + chat_view

    def _call_api(self, user_content: str) -> str:
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
