"""
src/trait/judge/client.py — the LLM judge client. OWNER: Chief Engineer.

Gemini 2.5 Flash primary (google-generativeai), OpenRouter fallback, temp 0.1,
3 attempts total across providers per session. All attempts failing →
parser.unavailable_output (N/A + judge_unavailable=True, never zero).

Family rule (non-negotiable #20): the judge family is GOOGLE. A google-partner
session still gets scored, but JudgeOutput.judge_family_conflict=True
(ADR-0002 / D-001) and the flag propagates to the ScoreResponse.

Tests inject `generate` — a (system_prompt, user_prompt) -> str callable — so
no network or SDK is touched in CI. The real transports are lazy imports.
"""

from __future__ import annotations

import os
import time
from typing import Callable, Protocol

from contracts.schemas import CanonicalSession, JudgeOutput, PartnerFamily
from src.trait.judge.parser import parse_judge_response, unavailable_output
from src.trait.judge.prompt import JUDGE_PROMPT_VERSION, SYSTEM_PROMPT, build_user_prompt

JUDGE_MODEL = "gemini-2.5-flash"
JUDGE_FAMILY: PartnerFamily = "google"
OPENROUTER_MODEL = "google/gemini-2.5-flash"
TEMPERATURE = 0.1
MAX_ATTEMPTS = 3
RETRY_BACKOFF_S = 2.0

REJUDGE_MODEL_ENV = "SAF_REJUDGE_MODEL"
DEFAULT_OPENAI_JUDGE_MODEL = "openai/gpt-4o-mini"

GenerateFn = Callable[[str, str], str]


class Transport(Protocol):  # pragma: no cover - typing only
    def __call__(self, system_prompt: str, user_prompt: str) -> str: ...


def _gemini_generate(system_prompt: str, user_prompt: str) -> str:
    import google.generativeai as genai  # lazy: never imported in CI tests

    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY / GOOGLE_API_KEY not set")
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(JUDGE_MODEL, system_instruction=system_prompt)
    response = model.generate_content(
        user_prompt,
        generation_config={"temperature": TEMPERATURE},
    )
    return response.text


def _openrouter_transport(model: str) -> GenerateFn:
    """Build an OpenRouter transport bound to a specific model id."""

    def generate(system_prompt: str, user_prompt: str) -> str:
        import httpx  # lazy

        api_key = os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            raise RuntimeError("OPENROUTER_API_KEY not set")
        resp = httpx.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": model,
                "temperature": TEMPERATURE,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            },
            timeout=120.0,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    return generate


# Default Gemini-fallback path: identical behavior to the pre-refactor function.
_openrouter_generate: GenerateFn = _openrouter_transport(OPENROUTER_MODEL)


class JudgeClient:
    """Scores a CanonicalSession at dimension grain."""

    def __init__(
        self,
        generate: GenerateFn | None = None,
        fallback: GenerateFn | None = None,
        *,
        judge_model: str | None = None,
        judge_family: PartnerFamily | None = None,
        max_attempts: int = MAX_ATTEMPTS,
        backoff_s: float = RETRY_BACKOFF_S,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._generate = generate or _gemini_generate
        self._fallback = fallback if fallback is not None else (
            _openrouter_generate if generate is None else None
        )
        self._judge_model = judge_model if judge_model is not None else JUDGE_MODEL
        self._judge_family = judge_family if judge_family is not None else JUDGE_FAMILY
        self._max_attempts = max_attempts
        self._backoff_s = backoff_s
        self._sleep = sleep

    def score_session(self, session: CanonicalSession) -> JudgeOutput:
        user_prompt = build_user_prompt(session)
        partner_family = session.partner_model.family

        # attempt plan: primary for all attempts, except the last goes to the
        # fallback transport when one exists (e.g. [gemini, gemini, openrouter])
        plan: list[GenerateFn] = [self._generate] * self._max_attempts
        if self._fallback is not None and self._max_attempts >= 2:
            plan[-1] = self._fallback

        for i, transport in enumerate(plan):
            try:
                raw = transport(SYSTEM_PROMPT, user_prompt)
                return parse_judge_response(
                    raw,
                    judge_model=self._judge_model,
                    judge_family=self._judge_family,
                    partner_family=partner_family,
                    prompt_version=JUDGE_PROMPT_VERSION,
                )
            except Exception:  # noqa: BLE001 — transport + parse errors both retry
                if i < len(plan) - 1:
                    self._sleep(self._backoff_s * (i + 1))

        return unavailable_output(
            judge_model=self._judge_model,
            judge_family=self._judge_family,
            partner_family=partner_family,
            prompt_version=JUDGE_PROMPT_VERSION,
        )


def openai_family_judge(model: str | None = None, **kwargs) -> JudgeClient:
    """An OpenAI-family judge over OpenRouter, for re-judging google-partner
    gold chats (gc-003, gc-016, gc-018 — non-negotiable #20 / ADR-0002).

    Primary transport is OpenRouter bound to `model` (default: the
    SAF_REJUDGE_MODEL env var, else "openai/gpt-4o-mini"). NO Gemini fallback:
    the fallback is None unless the caller passes one explicitly. Anthropic
    models are forbidden as judges (non-negotiable #20), and OpenAI provenance
    is assigned ONLY to genuinely OpenAI-family model ids — the id must carry
    the OpenRouter "openai/" prefix (D-003: a google model must never be
    recorded as judge_family="openai").

    Tests may inject a fake transport via kwargs (generate=..., sleep=...).
    """
    chosen = model or os.environ.get(REJUDGE_MODEL_ENV) or DEFAULT_OPENAI_JUDGE_MODEL
    lowered = chosen.lower()
    if "claude" in lowered or "anthropic" in lowered:
        raise ValueError(
            f"judge model {chosen!r} is Anthropic-family — forbidden as a judge "
            "(non-negotiable #20)"
        )
    if not lowered.startswith("openai/"):
        raise ValueError(
            f"judge model {chosen!r} is not OpenAI-family (id must start with "
            "'openai/') — OpenAI provenance would be false (D-003)"
        )
    kwargs.setdefault("generate", _openrouter_transport(chosen))
    return JudgeClient(judge_model=chosen, judge_family="openai", **kwargs)
