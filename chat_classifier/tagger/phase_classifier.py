"""
Stage 3 — Phase Classifier.

Maps a tagged conversation to a phase distribution dict:
  explore  — user is orienting, verifying, injecting context, probing
  refine   — user is steering: overriding, pivoting, scaffolding
  extract  — user is delegating output production
  evaluate — user is auditing: self-auditing, ethics-gating

Each human turn is assigned to exactly one dominant phase via the
phase_of_tag mapping below. The distribution is the fraction of
human turns in each phase (sums to 1.0).

AI turns are ignored — phases track the human's cognitive posture.
"""

from __future__ import annotations

from chat_classifier.schemas import IntentTag, TaggedTurn

# Map each intent tag to a phase bucket.
# Derived from CLAUDE_CODE_PROMPT_v2.md phase definitions.
_TAG_TO_PHASE: dict[IntentTag, str] = {
    "VERIFY":           "explore",
    "INJECT_CONTEXT":   "explore",
    "ANTHROPOMORPHIZE": "explore",
    "DECOMPOSE":        "explore",
    "OVERRIDE":         "refine",
    "PIVOT":            "refine",
    "SCAFFOLD":         "refine",
    "EXTRACT":          "extract",
    "ETHICS_GATE":      "evaluate",
    "SELF_AUDIT":       "evaluate",
}

_ALL_PHASES = ["explore", "refine", "extract", "evaluate"]


def classify_phases(tagged_turns: list[TaggedTurn]) -> dict[str, float]:
    """
    Compute the fraction of human turns in each phase bucket.

    Phase is determined by the dominant_intent of each human turn.
    Returns a dict with keys: explore, refine, extract, evaluate.
    Missing phases get 0.0. Fractions sum to 1.0 (within float precision).
    """
    counts: dict[str, int] = {p: 0 for p in _ALL_PHASES}
    total_human = 0

    for tt in tagged_turns:
        if tt.turn.role != "human":
            continue
        total_human += 1
        phase = _phase_for_turn(tt)
        counts[phase] += 1

    if total_human == 0:
        return {p: 0.0 for p in _ALL_PHASES}

    return {p: round(counts[p] / total_human, 4) for p in _ALL_PHASES}


def _phase_for_turn(tt: TaggedTurn) -> str:
    """Return the single phase for a tagged turn using dominant_intent."""
    if tt.dominant_intent is not None:
        return _TAG_TO_PHASE.get(tt.dominant_intent, "extract")
    return "extract"
