"""
src/trait/judge/parser.py — judge response parsing → JudgeOutput.
OWNER: Chief Engineer.

Tolerant of cosmetic model misbehavior (code fences, leading prose), strict on
substance: all 8 dimensions must be present with usable scores or the parse
fails and the client retries. A null score is valid ONLY for ES (event-
triggered dimension) — anywhere else it is a parse failure, because silence
must be a retry, not a silent N/A.
"""

from __future__ import annotations

import json
import re
from typing import Any

from contracts.schemas import (
    Dimension,
    JudgeDimScore,
    JudgeOutput,
    PartnerFamily,
)


class JudgeParseError(Exception):
    """Raised when a judge response cannot be turned into a JudgeOutput."""


_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


def _extract_json(text: str) -> dict[str, Any]:
    candidate = text.strip()
    fence = _FENCE_RE.search(candidate)
    if fence:
        candidate = fence.group(1)
    start = candidate.find("{")
    end = candidate.rfind("}")
    if start == -1 or end <= start:
        raise JudgeParseError("no JSON object in judge response")
    try:
        data = json.loads(candidate[start : end + 1])
    except json.JSONDecodeError as exc:
        raise JudgeParseError(f"judge JSON does not parse: {exc}") from exc
    if not isinstance(data, dict):
        raise JudgeParseError("judge JSON is not an object")
    return data


def _dim_score(dim: Dimension, raw: Any) -> JudgeDimScore:
    if not isinstance(raw, dict):
        raise JudgeParseError(f"{dim.value}: entry is not an object")

    score = raw.get("score")
    if score is None:
        if dim != Dimension.ES:
            raise JudgeParseError(f"{dim.value}: null score is only valid for ES")
    else:
        try:
            score = float(score)
        except (TypeError, ValueError):
            raise JudgeParseError(f"{dim.value}: non-numeric score {score!r}") from None
        if not 0.0 <= score <= 1.0:
            raise JudgeParseError(f"{dim.value}: score {score} out of [0,1]")

    try:
        confidence = float(raw.get("confidence", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0
    confidence = min(1.0, max(0.0, confidence))

    evidence_raw = raw.get("evidence_turns") or []
    evidence = [int(t) for t in evidence_raw if isinstance(t, (int, float)) and int(t) >= 0]

    tom_tag = raw.get("tom_tag")
    if tom_tag is not None:
        tom_tag = str(tom_tag) or None

    return JudgeDimScore(
        score=score, confidence=confidence, evidence_turns=evidence, tom_tag=tom_tag
    )


def parse_judge_response(
    text: str,
    *,
    judge_model: str,
    judge_family: PartnerFamily,
    partner_family: PartnerFamily,
    prompt_version: str,
) -> JudgeOutput:
    data = _extract_json(text)
    scores: dict[Dimension, JudgeDimScore] = {}
    for dim in Dimension:
        if dim.value not in data:
            raise JudgeParseError(f"missing dimension {dim.value}")
        scores[dim] = _dim_score(dim, data[dim.value])

    return JudgeOutput(
        scores=scores,
        judge_model=judge_model,
        judge_family=judge_family,
        prompt_version=prompt_version,
        judge_unavailable=False,
        judge_family_conflict=(judge_family == partner_family),
        raw_response=text,  # literal model output retained for audit (Track 1)
    )


def unavailable_output(
    *,
    judge_model: str,
    judge_family: PartnerFamily,
    partner_family: PartnerFamily,
    prompt_version: str,
) -> JudgeOutput:
    """All-retries-failed result: every score None, judge_unavailable=True —
    N/A, never zero (non-negotiable #12)."""
    return JudgeOutput(
        scores={dim: JudgeDimScore(score=None, confidence=0.0) for dim in Dimension},
        judge_model=judge_model,
        judge_family=judge_family,
        prompt_version=prompt_version,
        judge_unavailable=True,
        judge_family_conflict=(judge_family == partner_family),
    )
