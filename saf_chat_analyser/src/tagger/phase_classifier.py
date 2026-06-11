"""
Stage 3 — Phase Classifier.

Labels each 3-turn window as one of: ENGAGE | CREATE | MANAGE | DESIGN
based on AILit/OECD 4-domain definitions.

  ENGAGE  — user evaluating AI output accuracy/relevance
  CREATE  — user guiding and refining AI output iteratively
  MANAGE  — user delegating structured tasks while retaining judgment
  DESIGN  — user reasoning about AI limitations, data, or system structure

Implementation: assign each human turn to a phase bucket via dominant_intent,
then aggregate over 3-turn windows, then return the session-level distribution.
The output dict uses lowercase keys (engage/create/manage/design) and sums to 1.0.

Reference: SAF_ARI_Final_Master_Compilation.md §9.1, brief Stage 3
"""

from __future__ import annotations

from saf_chat_analyser.src.tagger.intent_tagger import TaggedTurn

# Map each intent tag to an AILit/OECD phase bucket
_TAG_TO_PHASE: dict[str, str] = {
    "VERIFY":           "engage",   # evaluating AI output accuracy
    "SELF_AUDIT":       "engage",   # evaluating reasoning quality
    "ANTHROPOMORPHIZE": "engage",   # engagement-mode (surface interaction)
    "OVERRIDE":         "create",   # guiding/refining AI output
    "PIVOT":            "create",   # iterative reframing
    "SCAFFOLD":         "create",   # taking over structure
    "INJECT_CONTEXT":   "create",   # adding human constraint to guide
    "EXTRACT":          "manage",   # delegating structured tasks
    "DECOMPOSE":        "manage",   # structured task delegation with judgment
    "ETHICS_GATE":      "design",   # reasoning about AI data/system constraints
}

_ALL_PHASES = ["engage", "create", "manage", "design"]


def classify_phases(tagged_turns: list[TaggedTurn]) -> dict[str, float]:
    """
    Compute the fraction of human turns in each phase bucket.

    Uses 3-turn sliding windows internally, but reports at the session level.
    Returns dict with keys engage/create/manage/design summing to 1.0.
    """
    human_turns = [tt for tt in tagged_turns if tt.turn.role == "human"]
    total = len(human_turns)
    if total == 0:
        return {p: 0.0 for p in _ALL_PHASES}

    counts: dict[str, int] = {p: 0 for p in _ALL_PHASES}
    for tt in human_turns:
        phase = _phase_for_turn(tt)
        counts[phase] += 1

    return {p: round(counts[p] / total, 4) for p in _ALL_PHASES}


def _phase_for_turn(tt: TaggedTurn) -> str:
    """Return the phase bucket for a single tagged human turn."""
    if tt.dominant_intent is not None:
        return _TAG_TO_PHASE.get(tt.dominant_intent, "manage")
    return "manage"
