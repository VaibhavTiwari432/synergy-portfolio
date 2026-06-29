"""Evidence provenance classifier for FIX-0.5.

COPY and VERBATIM are observed evidence states, not missingness. The scorer
therefore preserves the opportunity and sets the corresponding contribution to
0.0 instead of deleting the row.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from enum import Enum
from typing import Iterable, Mapping

from contracts.schemas import CanonicalSession


class ProvenanceClass(str, Enum):
    HUMAN_ORIGINAL = "HUMAN_ORIGINAL"
    AI_ASSISTED = "AI_ASSISTED"
    COPY = "COPY"
    VERBATIM = "VERBATIM"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class ProvenanceDecision:
    label: ProvenanceClass
    weight: float
    similarity: float
    reason: str


_CODE_FENCE_RE = re.compile(r"```|^\s*(import|export|function|class|const|let|var)\s+", re.I | re.M)
_COPY_REQUEST_RE = re.compile(
    r"\b(copy[- ]?paste|verbatim|exact text|full file|complete code|do not summarize|"
    r"all app code|file-by-file)\b",
    re.I,
)


def normalize_text(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9_./#:-]+", text.lower()))


def text_similarity(left: str, right: str) -> float:
    a = normalize_text(left)
    b = normalize_text(right)
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def _max_similarity(text: str, candidates: Iterable[str]) -> float:
    return max((text_similarity(text, c) for c in candidates if c), default=0.0)


def classify_provenance(
    text: str,
    *,
    ai_sources: Iterable[str] = (),
    metadata: Mapping | None = None,
) -> ProvenanceDecision:
    """Classify one evidence text span against known AI/source text."""
    metadata = metadata or {}
    max_sim = _max_similarity(text, ai_sources)
    exact_match = any(
        normalize_text(text) == normalize_text(source)
        for source in ai_sources
        if normalize_text(source)
    )
    copy_events = int(metadata.get("copy_events", 0) or 0)
    pasted = bool(metadata.get("pasted", False))

    if exact_match:
        return ProvenanceDecision(ProvenanceClass.VERBATIM, 0.0, max_sim, "near_exact_ai_match")
    if max_sim >= 0.82:
        return ProvenanceDecision(ProvenanceClass.COPY, 0.0, max_sim, "high_ai_overlap")
    if copy_events > 0 and (_CODE_FENCE_RE.search(text) or len(text) > 1200):
        return ProvenanceDecision(ProvenanceClass.COPY, 0.0, max_sim, "telemetry_copy_with_large_payload")
    if pasted and (_CODE_FENCE_RE.search(text) or max_sim >= 0.65):
        return ProvenanceDecision(ProvenanceClass.COPY, 0.0, max_sim, "pasted_payload")
    if _COPY_REQUEST_RE.search(text):
        return ProvenanceDecision(ProvenanceClass.AI_ASSISTED, 0.5, max_sim, "copy_request")
    if max_sim >= 0.44:
        return ProvenanceDecision(ProvenanceClass.AI_ASSISTED, 0.5, max_sim, "moderate_ai_overlap")
    if text.strip():
        return ProvenanceDecision(ProvenanceClass.HUMAN_ORIGINAL, 1.0, max_sim, "distinct_human_text")
    return ProvenanceDecision(ProvenanceClass.UNKNOWN, 1.0, 0.0, "empty_text")


def provenance_weight(label: ProvenanceClass | str) -> float:
    label = ProvenanceClass(label)
    return 0.0 if label in {ProvenanceClass.COPY, ProvenanceClass.VERBATIM} else 1.0


def classify_session_turns(session: CanonicalSession) -> dict[int, ProvenanceDecision]:
    """Classify human turns against previous AI turns and telemetry copy counts."""
    previous_ai: list[str] = []
    telemetry = session.metadata.get("telemetry") if isinstance(session.metadata, dict) else None
    copy_events = telemetry.get("copy_events") if isinstance(telemetry, dict) else None
    decisions: dict[int, ProvenanceDecision] = {}

    for turn in session.turns:
        if turn.role == "ai":
            previous_ai.append(turn.text)
            continue
        copy_count = 0
        if isinstance(copy_events, (list, tuple)) and turn.index < len(copy_events):
            raw = copy_events[turn.index]
            copy_count = int(raw) if isinstance(raw, (int, float)) else 0
        decisions[turn.index] = classify_provenance(
            turn.text,
            ai_sources=previous_ai,
            metadata={"copy_events": copy_count},
        )
    return decisions


def neuron_provenance_weights(
    session: CanonicalSession,
    per_neuron_results: Mapping[str, Mapping],
) -> dict[str, ProvenanceDecision]:
    """Map judge-neuron evidence turns to provenance decisions.

    When a judge result lacks evidence turns, the classifier returns UNKNOWN with
    weight 1.0. That keeps the scorer conservative rather than guessing.
    """
    by_turn = classify_session_turns(session)
    out: dict[str, ProvenanceDecision] = {}
    for nid, result in per_neuron_results.items():
        turns = result.get("evidence_turns") or result.get("evidence_turn_indices") or []
        if not turns:
            out[nid] = ProvenanceDecision(ProvenanceClass.UNKNOWN, 1.0, 0.0, "no_evidence_turns")
            continue
        decisions = [by_turn[t] for t in turns if t in by_turn]
        if not decisions:
            out[nid] = ProvenanceDecision(ProvenanceClass.UNKNOWN, 1.0, 0.0, "evidence_turns_not_human")
            continue
        strongest = min(decisions, key=lambda d: d.weight)
        out[nid] = strongest
    return out


def apply_provenance_weights(
    firings: dict,
    decisions: Mapping[str, ProvenanceDecision],
) -> int:
    """Apply COPY/VERBATIM weights in-place and return the zeroed count."""
    zeroed = 0
    for dim_firings in firings.values():
        for nid in list(dim_firings):
            decision = decisions.get(nid)
            if decision is not None and decision.weight == 0.0:
                dim_firings[nid] = 0.0
                zeroed += 1
    return zeroed
