"""
Stage 5 (alt backend) — OpenRouter judge wrapper.
Drop-in replacement for GeminiJudge: same score() signature, same JudgeOutput.
Uses the OpenAI-compatible OpenRouter API so no extra SDK is needed.
"""

from __future__ import annotations

import json
import os
import time

import requests
from pydantic import ValidationError

from chat_classifier.config import GEMINI_MAX_RETRIES, NEURON_COUNT_EXPECTED
from chat_classifier.schemas import CompositeMetrics, JudgeOutput, RawChat, TaggedTurn
from chat_classifier.scorer.gemini_judge import (
    _extract_json,
    _validate_scores,
    build_transcript_summary,
)
from chat_classifier.scorer.judge_prompt import JUDGE_SYSTEM_PROMPT

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_OR_MODEL = "google/gemini-2.0-flash-lite"


class OpenRouterJudge:
    """
    Calls the OpenRouter API to score a transcript.
    Returns a validated JudgeOutput with exactly 107 neuron scores in [0.0, 1.0].
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str = DEFAULT_OR_MODEL,
    ):
        self._api_key = api_key or os.environ.get("OPENROUTER_API_KEY", "")
        if not self._api_key:
            raise ValueError(
                "OpenRouter API key required. Pass api_key= or set OPENROUTER_API_KEY env var."
            )
        self.model = model

    def score(
        self,
        chat: RawChat,
        tagged_turns: list[TaggedTurn],
        metrics: CompositeMetrics,
        phase_distribution: dict[str, float] | None = None,
        intent_counts: dict[str, int] | None = None,
    ) -> JudgeOutput:
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
            f"OpenRouter judge failed after {GEMINI_MAX_RETRIES} attempts. "
            f"Last error: {last_error}"
        )

    def _call_api(self, user_content: str) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            "temperature": 0.0,
            "response_format": {"type": "json_object"},
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        resp = requests.post(
            OPENROUTER_API_URL,
            headers=headers,
            json=payload,
            timeout=120,
        )
        if resp.status_code != 200:
            raise RuntimeError(
                f"OpenRouter API error {resp.status_code}: {resp.text[:500]}"
            )
        return resp.json()["choices"][0]["message"]["content"]
