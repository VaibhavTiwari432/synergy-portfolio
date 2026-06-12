"""
src/trait/extractors/per_dimension/pr.py — PR deterministic extractor.
Leaf module (INTERFACES.md §1.3): imports ONLY from contracts/.

Deterministic PR neurons:
- PR-02 Cognitive Scaffolding — sequential/multi-step reasoning directives
- PR-05 Output Topology Definition — explicit output-structure commands
- PR-07 Inductive Example Provisioning — few-shot examples supplied
- PR-14 Recursive Self-Critique Elicitation — directing the AI to critique
  its own prior output (applicable only after the first AI response)

Strength = prompts exhibiting the behavior ÷ applicable prompts.
"""

from __future__ import annotations

import re

from contracts.schemas import CanonicalSession, Dimension, Event, Phase, TurnTags

DIM = Dimension.PR

_SCAFFOLD_RE = re.compile(
    r"\bstep[- ]by[- ]step\b|\breason (through|about|it out)\b|\bthink (it )?through\b"
    r"|\bfirst[, ].{0,80}\bthen\b|\bone (step|part) at a time\b|\bbefore (you )?answer\b"
    r"|\bwalk me through\b|\bshow your (work|reasoning|steps)\b",
    re.IGNORECASE,
)
_TOPOLOGY_RE = re.compile(
    r"\b(format|structure|organi[sz]e) (it|this|the|your)\b|\bin (a table|json|yaml|markdown|bullet)\b"
    r"|\bas (a list|bullets?|a table|sections)\b|\bwith (columns|sections|headers|headings)\b"
    r"|\b(max(imum)?|at most|exactly|no more than) \d+ (words?|lines?|bullets?|points?|sentences?|pages?)\b"
    r"|\bbullet points?\b",
    re.IGNORECASE,
)
_FEWSHOT_RE = re.compile(
    r"\b(for example|e\.g\.)[,:].{0,200}(→|->|=>|:)\b|\blike this[,:]\b"
    r"|\bexample \d\b|\bhere (is|are) (an |some )?examples?\b|\binput\s*:.{0,120}output\s*:",
    re.IGNORECASE | re.DOTALL,
)
_SELF_CRITIQUE_RE = re.compile(
    r"\b(critique|criticize|evaluate|review|grade|attack|poke holes in) your( own)? "
    r"(answer|output|response|reasoning|work|draft)\b"
    r"|\bwhat('?s| is) (wrong|weak|missing) (with|in) your\b"
    r"|\bfind (the )?(flaws?|errors?|problems?) in your\b"
    r"|\bcheck your( own)? (work|answer|output)\b",
    re.IGNORECASE,
)


def extract(
    session: CanonicalSession,
    tags: list[TurnTags],
    phases: list[Phase],
    events: list[Event],
) -> dict[str, object]:
    firings: dict[str, float] = {}
    opportunities: dict[str, int] = {}
    evidence: dict[str, list[int]] = {}

    human_turns = [t for t in session.turns if t.role == "human"]
    if not human_turns:
        return {"neuron_firings": {}, "applicable_opportunities": {}, "evidence_turns": {}}

    first_ai_index = next((t.index for t in session.turns if t.role == "ai"), None)
    post_ai_prompts = [
        t for t in human_turns if first_ai_index is not None and t.index > first_ai_index
    ]

    per_neuron: list[tuple[str, re.Pattern[str], list]] = [
        ("PR-02", _SCAFFOLD_RE, human_turns),
        ("PR-05", _TOPOLOGY_RE, human_turns),
        ("PR-07", _FEWSHOT_RE, human_turns),
        ("PR-14", _SELF_CRITIQUE_RE, post_ai_prompts),
    ]
    for neuron_id, pattern, applicable in per_neuron:
        if not applicable:
            continue  # no applicable prompts → neuron entirely absent
        hits = [t.index for t in applicable if pattern.search(t.text)]
        opportunities[neuron_id] = len(applicable)
        if hits:
            firings[neuron_id] = len(hits) / len(applicable)
            evidence[neuron_id] = hits

    return {
        "neuron_firings": firings,
        "applicable_opportunities": opportunities,
        "evidence_turns": evidence,
    }
