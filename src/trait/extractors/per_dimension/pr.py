"""
src/trait/extractors/per_dimension/pr.py — PR deterministic extractor.
Leaf module (INTERFACES.md §1.3): imports ONLY from contracts/.

Deterministic PR neurons:
- PR-02 constraint/example/success-criteria presence in human prompts
- PR-05 generative-vs-extractive prompt ratio (requires at least two prompts)
- PR-07 Inductive Example Provisioning — few-shot examples supplied
- PR-14 Recursive Self-Critique Elicitation — directing the AI to critique
  its own prior output (applicable only after the first AI response)

Strength = prompts exhibiting the behavior ÷ applicable prompts.
"""

from __future__ import annotations

import re

from contracts.schemas import CanonicalSession, Dimension, Event, Phase, TurnTags

DIM = Dimension.PR

_CONSTRAINT_EXAMPLE_SUCCESS_RE = re.compile(
    r"\b(must|should not|must not|cannot|only)\b"
    r"|\b(limit(ed)? to|at most|no more than|exactly)\b"
    r"|\bdon'?t (include|use|add|exceed)\b|\brequirements?\s*:"
    r"|\b(for example|e\.g\.|such as|like this)\b"
    r"|\bhere (is|are) (an |some )?examples?\b|\binput\s*:.{0,120}output\s*:"
    r"|\b(goal|objective) is\b|\bi need the output to\b"
    r"|\bshould look like\b|\bsuccess (means|is)\b|\bdone when\b",
    re.IGNORECASE,
)
_GENERATIVE_RE = re.compile(
    r"\bexplain\b|\bwhat are (the )?(alternatives|options|trade[- ]?offs)\b"
    r"|\b(find|identify) (the )?(flaw|weakness|risk)s?\b|\bcritique\b"
    r"|\bcompare\b|\bwhy\b|\bhow could\b",
    re.IGNORECASE,
)
_EXTRACTIVE_RE = re.compile(
    r"\b(write|generate|list|summari[sz]e|finish|complete|draft|produce)\b",
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
        ("PR-02", _CONSTRAINT_EXAMPLE_SUCCESS_RE, human_turns),
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

    if len(human_turns) >= 2:
        generative = [t.index for t in human_turns if _GENERATIVE_RE.search(t.text)]
        extractive = [t.index for t in human_turns if _EXTRACTIVE_RE.search(t.text)]
        opportunities["PR-05"] = len(human_turns)
        signal_count = len(generative) + len(extractive)
        if generative and signal_count:
            firings["PR-05"] = len(generative) / signal_count
            evidence["PR-05"] = generative

    return {
        "neuron_firings": firings,
        "applicable_opportunities": opportunities,
        "evidence_turns": evidence,
    }
