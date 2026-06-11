"""
Stage 2b — A-turn / S-turn Classifier.

Partitions every human turn into:
  A-turn (autonomous-continuation): low-information steering
    — bare acknowledgements, "continue", "ok", "yes" (<5 words, no new constraint)
  S-turn (steered): everything else — any specific constraint, correction,
    narrowing, or stopping rule

Hard rule: any turn tagged OVERRIDE, SCAFFOLD, PIVOT, or INJECT_CONTEXT
is always S-turn regardless of word count.

Outputs per conversation:
  a_turn_ratio: float   # A-turns / total human turns
  s_turn_ratio: float   # S-turns / total human turns
  (a_turn_ratio + s_turn_ratio == 1.0)

Reference: SAF_ARI_Final_Master_Compilation.md §5.3.1, §13.11
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from saf_chat_analyser.src.tagger.intent_tagger import TaggedTurn

# Tags that force S-turn classification regardless of word count
_ALWAYS_S_TAGS = {"OVERRIDE", "SCAFFOLD", "PIVOT", "INJECT_CONTEXT"}

# A-turn keyword patterns — bare low-information acknowledgements
_A_KEYWORDS = re.compile(
    r"^(continue|go on|go ahead|proceed|expand|elaborate|ok|okay|yes|yeah|"
    r"sure|great|thanks|thank you|sounds good|got it|alright|perfect|good|"
    r"nice|understood|i see|makes sense|cool)[\.\!\?]?$",
    re.IGNORECASE,
)

# A-turn word count threshold — turns with >4 words that carry no constraint
# are still scored by other signals; this is the length-only gate
_A_TURN_MAX_WORDS = 4


@dataclass
class TurnClassification:
    is_a_turn: bool  # True = A-turn; False = S-turn


def classify_turn(tt: TaggedTurn) -> TurnClassification:
    """
    Classify a single tagged human turn as A-turn or S-turn.
    AI turns always return S-turn (they are excluded from ratio computation).
    """
    if tt.turn.role != "human":
        return TurnClassification(is_a_turn=False)

    # Hard rule: certain tags always make it an S-turn
    if any(tag in _ALWAYS_S_TAGS for tag in tt.tags):
        return TurnClassification(is_a_turn=False)

    content = tt.turn.content.strip()
    word_count = tt.turn.word_count

    # Bare keyword match → A-turn
    if _A_KEYWORDS.match(content):
        return TurnClassification(is_a_turn=True)

    # Short turn (<= max words) with only EXTRACT tag → likely A-turn
    if word_count <= _A_TURN_MAX_WORDS and set(tt.tags) == {"EXTRACT"}:
        return TurnClassification(is_a_turn=True)

    # Everything else is steered
    return TurnClassification(is_a_turn=False)


def compute_as_ratios(tagged_turns: list[TaggedTurn]) -> dict[str, float]:
    """
    Compute A-turn and S-turn ratios over all human turns.

    Returns:
        {"a_turn_ratio": float, "s_turn_ratio": float}
        Both values are in [0.0, 1.0] and sum to 1.0.
    """
    human_turns = [tt for tt in tagged_turns if tt.turn.role == "human"]
    total = len(human_turns)
    if total == 0:
        return {"a_turn_ratio": 0.0, "s_turn_ratio": 0.0}

    a_count = sum(1 for tt in human_turns if classify_turn(tt).is_a_turn)
    s_count = total - a_count

    return {
        "a_turn_ratio": round(a_count / total, 4),
        "s_turn_ratio": round(s_count / total, 4),
    }
