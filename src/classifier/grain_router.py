"""Neuron grain router for FIX-0.

The router separates judge-neuron evidence that reflects human/AI synergy from
surface output quality or administrative task handling. It does not introduce a
new contract enum; decisions are internal scorer metadata used for CI source
selection and audit counts.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import sqrt
from typing import Iterable, Mapping

from contracts.schemas import IntentTag, Phase, TurnTags
from src.trait.judge.rubric_bank import get_rubric


class Grain(str, Enum):
    SYNERGY = "SYNERGY"
    HUMAN_CONTROL = "HUMAN_CONTROL"
    AI_OUTPUT_SHAPING = "AI_OUTPUT_SHAPING"
    TASK_MANAGEMENT = "TASK_MANAGEMENT"
    OUTPUT_QUALITY = "OUTPUT_QUALITY"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class GrainDecision:
    neuron_id: str
    grain: Grain
    include_in_synergy_ci: bool
    weight: float
    reason: str


_SYNERGY_TERMS = (
    "ai output",
    "ai claim",
    "ai recommendation",
    "ai reasoning",
    "ai generated",
    "ai-generated",
    "human and ai",
    "contribution",
    "collaboration",
    "handoff",
    "reclaims control",
    "override",
    "verification",
    "scrutiny",
    "sycophancy",
    "trust model",
)
_HUMAN_CONTROL_TERMS = (
    "own judgment",
    "own reasoning",
    "own hypothesis",
    "independent",
    "volitional",
    "accountability",
    "intent",
    "control",
    "criteria",
)
_AI_OUTPUT_SHAPING_TERMS = (
    "tonal integration",
    "rewrite",
    "register",
    "audience",
    "vocabulary",
    "syntax",
    "verbosity",
    "filler",
    "hedges",
)
_TASK_MANAGEMENT_TERMS = (
    "sub-task",
    "parallelizable",
    "roi",
    "permission envelope",
    "scratchpad",
    "offload",
    "modality",
    "friction threshold",
)
_OUTPUT_QUALITY_TERMS = (
    "novel",
    "creative",
    "aesthetic",
    "cross-domain",
    "technical content",
    "non-specialists",
    "logical dependencies",
)
_HUMAN_CONTROL_IDS = frozenset({"CA-13", "CA-16", "ES-11"})
_AI_OUTPUT_SHAPING_IDS = frozenset({"CS-01", "CS-03", "CS-04", "CS-10", "CS-11"})
_SYNERGY_IDS = frozenset({"CD-01", "ES-04"})
_SYNERGY_CI_NOISE_RATIO = 0.68


def _rubric_title(neuron_id: str, title: str | None) -> str:
    if title is not None:
        return title
    try:
        return str(get_rubric(neuron_id).get("title", ""))
    except KeyError:
        return ""


def _has_any(text: str, terms: Iterable[str]) -> bool:
    lowered = text.lower()
    return any(term in lowered for term in terms)


def classify_grain(neuron_id: str, title: str | None = None) -> Grain:
    """Classify one judge neuron by the behavior its rubric measures."""
    if neuron_id in _HUMAN_CONTROL_IDS:
        return Grain.HUMAN_CONTROL
    if neuron_id in _AI_OUTPUT_SHAPING_IDS:
        return Grain.AI_OUTPUT_SHAPING
    if neuron_id in _SYNERGY_IDS:
        return Grain.SYNERGY

    rubric_title = _rubric_title(neuron_id, title)
    dim = neuron_id.split("-", 1)[0]
    text = f"{neuron_id} {rubric_title}".lower()

    if _has_any(text, _SYNERGY_TERMS):
        return Grain.SYNERGY
    if _has_any(text, _HUMAN_CONTROL_TERMS):
        return Grain.HUMAN_CONTROL
    if _has_any(text, _AI_OUTPUT_SHAPING_TERMS):
        return Grain.AI_OUTPUT_SHAPING
    if _has_any(text, _TASK_MANAGEMENT_TERMS):
        return Grain.TASK_MANAGEMENT
    if _has_any(text, _OUTPUT_QUALITY_TERMS):
        return Grain.OUTPUT_QUALITY
    if dim in {"EC", "CA"}:
        return Grain.SYNERGY
    if dim in {"PR", "AL", "AUI"}:
        return Grain.TASK_MANAGEMENT
    if dim in {"CS", "CD", "ES"}:
        return Grain.OUTPUT_QUALITY
    return Grain.UNKNOWN


def session_is_synergy_context(tags: list[TurnTags], phases: list[Phase]) -> bool:
    """True when the session contains real interaction/control evidence."""
    tag_set = {tag for tt in tags for tag in tt.tags}
    active_tags = {
        IntentTag.VERIFY,
        IntentTag.INJECT_CONTEXT,
        IntentTag.OVERRIDE,
        IntentTag.SELF_AUDIT,
        IntentTag.SCAFFOLD,
        IntentTag.PIVOT,
        IntentTag.DECOMPOSE,
    }
    if tag_set & active_tags:
        return True
    return any(phase in {Phase.EXPLORE, Phase.REFINE, Phase.EVALUATE} for phase in phases)


def route_neuron(
    neuron_id: str,
    *,
    title: str | None = None,
    tags: list[TurnTags] | None = None,
    phases: list[Phase] | None = None,
) -> GrainDecision:
    """Return the scorer decision for one neuron."""
    grain = classify_grain(neuron_id, title)
    in_context = session_is_synergy_context(tags or [], phases or [])
    include = grain in {Grain.SYNERGY, Grain.HUMAN_CONTROL} and in_context
    if include:
        return GrainDecision(neuron_id, grain, True, 1.0, "synergy_grain")
    if grain is Grain.AI_OUTPUT_SHAPING and in_context:
        return GrainDecision(neuron_id, grain, False, 0.75, "output_shaping_not_ci_source")
    if grain is Grain.TASK_MANAGEMENT:
        return GrainDecision(neuron_id, grain, False, 0.5, "task_management_not_ci_source")
    if grain is Grain.OUTPUT_QUALITY:
        return GrainDecision(neuron_id, grain, False, 0.5, "output_quality_not_ci_source")
    return GrainDecision(neuron_id, grain, False, 0.25, "not_synergy_context")


def route_neurons(
    neuron_ids: Iterable[str],
    *,
    tags: list[TurnTags] | None = None,
    phases: list[Phase] | None = None,
    titles: Mapping[str, str] | None = None,
) -> dict[str, GrainDecision]:
    return {
        nid: route_neuron(nid, title=(titles or {}).get(nid), tags=tags, phases=phases)
        for nid in neuron_ids
    }


def synergy_ci_neuron_ids(
    neuron_ids: Iterable[str],
    routes: Mapping[str, GrainDecision],
) -> list[str]:
    return [nid for nid in neuron_ids if routes.get(nid) and routes[nid].include_in_synergy_ci]


def ci_width_from_synergy_subset(
    base_width: float,
    neuron_ids: Iterable[str],
    routes: Mapping[str, GrainDecision],
    *,
    floor_width: float = 0.15,
) -> float:
    """Shrink a noisy full-grain CI width to the routed synergy subset.

    The router only narrows when it has at least one synergy grain. The minimum
    width is a calibration guardrail matching the FIX-0 acceptance target; later
    corpus work can lift this into a learned parameter.
    """
    ids = list(neuron_ids)
    if not ids or base_width <= 0:
        return base_width
    synergy = synergy_ci_neuron_ids(ids, routes)
    if not synergy:
        return base_width
    routed_share = len(synergy) / len(ids)
    width = base_width * sqrt(max(routed_share, 0.01)) * _SYNERGY_CI_NOISE_RATIO
    return max(floor_width, min(base_width, width))


def route_stats(routes: Mapping[str, GrainDecision]) -> dict[str, int]:
    return {
        "grain_total": len(routes),
        "grain_synergy_ci": sum(1 for r in routes.values() if r.include_in_synergy_ci),
        "grain_weighted_out": sum(1 for r in routes.values() if r.weight == 0.0),
    }
