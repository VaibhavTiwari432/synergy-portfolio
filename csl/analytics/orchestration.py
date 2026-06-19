"""CSL Phase 2.5 — orchestration efficiency (prompt-economy WITH quality).

`orchestration_efficiency` reports prompt economy — how much AI output the human
elicited per unit of their own steering input — but it MUST be carried alongside a
quality measure and is never a standalone ratio.

This is the guard against Tier-4 "cognitive leverage" (Do-NOT #7): a bare
output/input ratio rewards eliciting more text regardless of whether it was any
good. So `quality` is a REQUIRED argument; calling without it raises
(acceptance: "orchestration_efficiency raises/refuses if called without a quality
argument"). The result bundles economy and quality so neither is read alone.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from contracts.schemas import CanonicalSession, Rung

_CAVEAT = (
    "Prompt economy is reported only alongside output quality; it is not a "
    "standalone leverage metric. High economy with low quality is not efficiency."
)


@dataclass(frozen=True)
class OrchestrationResult:
    """Prompt economy bound to quality — never economy alone."""

    prompt_economy: float | None
    quality: float
    human_prompt_tokens: int
    ai_output_tokens: int
    n_human_turns: int
    n_ai_turns: int
    rung: Rung
    caveat: str


def _tokens(text: str) -> int:
    return len(re.findall(r"\w+", text))


def orchestration_efficiency(
    chat: CanonicalSession,
    quality: float | None,
) -> OrchestrationResult:
    """Prompt economy (AI output per human steering token) carried with quality.

    `quality` is required — an external output-quality measure on [0, 1]. Calling
    without it (None) raises: economy is meaningless, and dangerous, without it.
    """
    if quality is None:
        raise ValueError(
            "orchestration_efficiency requires a quality argument: prompt economy "
            "is never reported standalone (Do-NOT #7, cognitive leverage)."
        )
    if not 0.0 <= quality <= 1.0:
        raise ValueError("quality must be in [0, 1]")

    human_tokens = sum(_tokens(t.text) for t in chat.turns if t.role == "human")
    ai_tokens = sum(_tokens(t.text) for t in chat.turns if t.role == "ai")
    n_human = sum(1 for t in chat.turns if t.role == "human")
    n_ai = sum(1 for t in chat.turns if t.role == "ai")

    economy = round(ai_tokens / human_tokens, 6) if human_tokens > 0 else None

    return OrchestrationResult(
        prompt_economy=economy,
        quality=quality,
        human_prompt_tokens=human_tokens,
        ai_output_tokens=ai_tokens,
        n_human_turns=n_human,
        n_ai_turns=n_ai,
        rung=Rung.DESIGNED,
        caveat=_CAVEAT,
    )
