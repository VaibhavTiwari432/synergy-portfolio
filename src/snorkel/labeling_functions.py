"""
src/snorkel/labeling_functions.py — Phase 4: Snorkel weak supervision labeling functions.
OWNER: Chief Engineer.

Labeling functions for the 9 deterministic neurons. Each LF extracts structural
signals from a CanonicalSession (transcript) and returns a [0.0, 1.0] score.

These are session-level aggregators (not chunk-scoped for now; chunking is Phase 5).
All LFs operate on the full transcript and return a normalized evidence score.

LFs are designed to be:
- **Deterministic:** No randomness, no LLM calls
- **Fast:** O(n) scan where n = transcript length
- **Interpretable:** Clear extraction logic (count markers, compute ratios, check presence)
- **Snorkel-ready:** Return [0.0, 1.0] scores that can be used as weak labels for SetFit training
"""

import re
from contracts.schemas import CanonicalSession, Turn


def _count_in_text(text: str, patterns: list[str]) -> int:
    """Count non-overlapping regex pattern matches in text (case-insensitive)."""
    count = 0
    for pattern in patterns:
        count += len(re.findall(pattern, text, re.IGNORECASE))
    return count


def _human_turns(session: CanonicalSession) -> list[Turn]:
    """Extract all human turns from the session."""
    return [turn for turn in session.turns if turn.role == "human"]


def _ai_turns(session: CanonicalSession) -> list[Turn]:
    """Extract all AI turns from the session."""
    return [turn for turn in session.turns if turn.role == "ai"]


# ── EC-06: Verification Markers (count_verification_markers) ──────────────────

_VERIFICATION_MARKERS = [
    r"\bis\s+that\s+correct\b",
    r"\blet\s+me\s+verify\b",
    r"\bactually\b",
    r"\bthat'?s\s+wrong\b",
    r"\bi\s+checked\b",
    r"\bsource\s*:\b",
    r"\bcitation\b",
    r"\bdouble.?check\b",
    r"\bconfirm\b",
    r"\bwait\s*[–—]",
    r"\bthat\s+doesn'?t\s+seem\s+right\b",
    r"\bi\s+disagree\b",
    r"\bthat'?s\s+not\s+right\b",
    r"\bi\s+don'?t\s+think\s+that'?s\s+correct\b",
]


def lf_ec_06_verification_markers(session: CanonicalSession) -> float:
    """
    EC-06: Count explicit verification markers in human turns.

    Higher count → higher score (normalized by turn count to avoid length bias).
    Score = min(1.0, count / max(1, len(human_turns)))
    """
    human_turns_list = _human_turns(session)
    if not human_turns_list:
        return 0.0

    total_markers = sum(
        _count_in_text(turn.text, _VERIFICATION_MARKERS)
        for turn in human_turns_list
    )

    # Normalize by turn count to reduce length bias
    normalized = total_markers / max(1, len(human_turns_list))
    return min(1.0, normalized)


# ── EC-07: Interrogative Ratio (interrogative_to_affirmative_ratio) ────────────

def lf_ec_07_interrogative_ratio(session: CanonicalSession) -> float:
    """
    EC-07: Ratio of question-ending sentences to affirmative sentences in human turns.

    High ratio → human asks many questions (active interrogation of AI).
    Score = interrogatives / (interrogatives + affirmatives)
    """
    human_turns_list = _human_turns(session)
    if not human_turns_list:
        return 0.5  # Neutral if no human turns

    all_human_text = " ".join(turn.text for turn in human_turns_list)

    # Count sentences ending in ?
    interrogatives = len(re.findall(r"[?!]\s*$", all_human_text, re.MULTILINE))
    # Count affirmative sentences (., but not ?!)
    affirmatives = len(re.findall(r"[.]\s*$", all_human_text, re.MULTILINE))

    total = interrogatives + affirmatives
    if total == 0:
        return 0.5  # Neutral if no clear sentence boundaries

    ratio = interrogatives / total
    return min(1.0, ratio)


# ── EC-09: Unverified Confident Claims ──────────────────────────────────────

_HEDGING_MARKERS = [
    r"\bi\s+think\b",
    r"\bmight\b",
    r"\bcould\b",
    r"\bmaybe\b",
    r"\bperhaps\b",
    r"\bunsure\b",
    r"\buncertain\b",
    r"\bapproximately\b",
    r"\bsomewhat\b",
    r"\broughly\b",
]


def lf_ec_09_unverified_confident_claims(session: CanonicalSession) -> float:
    """
    EC-09: Fires when AI makes confident (low-hedging) claims that human doesn't verify.

    Score high (closer to 1.0) when:
    - AI turns have low hedging markers (confident language)
    - AND human turns have low verification markers (no follow-up verification)

    This indicates a potential risk: confident but unverified claim.
    """
    ai_turns_list = _ai_turns(session)
    human_turns_list = _human_turns(session)

    if not ai_turns_list or not human_turns_list:
        return 0.0

    # Count hedging in AI turns (low = confident)
    ai_hedging_count = sum(
        _count_in_text(turn.text, _HEDGING_MARKERS)
        for turn in ai_turns_list
    )
    ai_confidence = 1.0 - min(1.0, ai_hedging_count / max(1, len(ai_turns_list)))

    # Count verification markers in human turns (high = verified)
    human_verification_count = sum(
        _count_in_text(turn.text, _VERIFICATION_MARKERS)
        for turn in human_turns_list
    )
    human_verification_rate = min(1.0, human_verification_count / max(1, len(human_turns_list)))

    # Risk = confident but not verified
    risk_score = ai_confidence * (1.0 - human_verification_rate)
    return min(1.0, risk_score)


# ── PR-02: Follows With Rationale (turn_completion) ──────────────────────────

def lf_pr_02_follows_with_rationale(session: CanonicalSession) -> float:
    """
    PR-02: When human follows AI recommendation, do they add their own reasoning?

    Heuristic: Look for patterns like "Yes, because", "OK, and", "That makes sense,",
    or other indicators that human is extending the AI response with rationale.

    Score = fraction of human turns that follow affirmative language with their own additions.
    """
    human_turns_list = _human_turns(session)
    if not human_turns_list:
        return 0.5

    # Patterns indicating human is adding rationale after accepting AI
    rationale_indicators = [
        r"(yes|ok|okay|agreed?|exactly)\s*,\s+",  # Agreement + comma = continuation
        r"(because|so|that'?s)\s+why\b",
        r"i\s+(think|believe|agree)\s+.*\b(because|since|as|for)\b",
        r"that\s+makes\s+sense",
        r"right\s*,",
    ]

    turns_with_rationale = sum(
        1 for turn in human_turns_list
        if any(re.search(pattern, turn.text, re.IGNORECASE) for pattern in rationale_indicators)
    )

    score = turns_with_rationale / max(1, len(human_turns_list))
    return min(1.0, score)


# ── PR-05: Turns Without Full AI Dependence ──────────────────────────────────

def lf_pr_05_turns_without_full_ai_dependence(session: CanonicalSession) -> float:
    """
    PR-05: Human occasionally leads conversation, not always following AI.

    Heuristic: Measure the degree to which human initiates topics vs only responding to AI.
    High value = human has independent agency; low = human always follows AI.

    Simple metric: fraction of human turns that are >3 sentences (suggesting independent thought).
    """
    human_turns_list = _human_turns(session)
    if not human_turns_list:
        return 0.5

    # Count sentences in each human turn
    independent_turns = sum(
        1 for turn in human_turns_list
        if len(re.split(r'[.!?]+', turn.text.strip())) >= 3
    )

    score = independent_turns / max(1, len(human_turns_list))
    return min(1.0, score)


# ── PR-07: Diverse Turn Topics ───────────────────────────────────────────────

def lf_pr_07_diverse_turn_topics(session: CanonicalSession) -> float:
    """
    PR-07: Human raises diverse topics independently, not just responding to AI.

    Heuristic: Measure vocabulary diversity in human turns. High diversity suggests
    human is introducing varied topics; low diversity suggests repetitive responses to AI.

    Simple metric: unique words in human turns / total words.
    """
    human_turns_list = _human_turns(session)
    if not human_turns_list:
        return 0.5

    all_human_text = " ".join(turn.text.lower() for turn in human_turns_list)
    words = re.findall(r"\b\w+\b", all_human_text)

    if not words:
        return 0.5

    unique_words = len(set(words))
    diversity = unique_words / len(words)  # Higher = more diverse vocabulary
    return min(1.0, diversity)


# ── AL-08: Has Substantive Question ──────────────────────────────────────────

def lf_al_08_has_substantive_question(session: CanonicalSession) -> float:
    """
    AL-08: Binary flag for whether human asked any substantive question.

    Heuristic: Look for question marks in human turns, excluding trivial ones
    (e.g., "ok?" or single-word questions).

    Score: 1.0 if at least one substantive question found, 0.0 otherwise.
    For weak labeling, return the fraction of substantive turns.
    """
    human_turns_list = _human_turns(session)
    if not human_turns_list:
        return 0.0

    # Substantive question patterns
    substantive_patterns = [
        r"\b(why|how|what|when|where|which|who|whose)\b.*[?]",
        r"[?][a-z]",  # Capitalized word after ?
        r"\b(could|would|should|can|may|might|do|does|did|have|has|is|are|was|were)\s+\w+.*[?]",
    ]

    substantive_questions = sum(
        1 for turn in human_turns_list
        if any(re.search(pattern, turn.text, re.IGNORECASE) for pattern in substantive_patterns)
    )

    score = substantive_questions / max(1, len(human_turns_list))
    return min(1.0, score)


# ── PR-14: Follows With Rationale (alternative signature) ────────────────────

def lf_pr_14_follows_with_rationale_strong(session: CanonicalSession) -> float:
    """
    PR-14: When human follows AI (accepts output), they add their own reasoning.

    This is a complementary measure to PR-02, focusing on explicit follow-ups
    where human demonstrates they're adding value, not just accepting.

    Score: fraction of AI turns followed by human-added reasoning/commentary.
    """
    ai_turns_list = _ai_turns(session)
    if not ai_turns_list:
        return 0.5

    # Find human turns that follow AI turns
    followed_with_rationale = 0
    for i, ai_turn in enumerate(ai_turns_list):
        # Find the next human turn after this AI turn
        next_human_idx = None
        for j in range(ai_turn.index + 1, len(session.turns)):
            if session.turns[j].role == "human":
                next_human_idx = j
                break

        if next_human_idx is not None:
            human_response = session.turns[next_human_idx].text
            # Check if human adds rationale (not just agreement)
            has_rationale = any([
                len(human_response.split()) > 5,  # Non-trivial response
                any(re.search(p, human_response, re.IGNORECASE) for p in [
                    r"(because|since|as|for)\b",
                    r"(so|therefore|thus)\b",
                    r"i\s+(think|believe|agree|understand)",
                ])
            ])
            if has_rationale:
                followed_with_rationale += 1

    score = followed_with_rationale / max(1, len(ai_turns_list)) if ai_turns_list else 0.0
    return min(1.0, score)


# ── ES-01: Has Evidence Citation ────────────────────────────────────────────

_EVIDENCE_INDICATORS = [
    r"\bcited?\b",
    r"\bsource\b",
    r"\blink\b",
    r"\breference\b",
    r"\bgoogle\b",
    r"\bwikipedia\b",
    r"\barticle\b",
    r"\bstudy\b",
    r"\bpaper\b",
    r"\bdata\b",
    r"\bevidence\b",
    r"\bfact.?check\b",
    r"\baccording\s+to\b",
    r"\bi\s+found\b",
    r"\bi\s+read\b",
]


def lf_es_01_has_evidence_citation(session: CanonicalSession) -> float:
    """
    ES-01: Binary flag for whether human cited/requested external evidence.

    Heuristic: Look for evidence-related keywords in human turns.

    Score: fraction of human turns that mention evidence or citations.
    """
    human_turns_list = _human_turns(session)
    if not human_turns_list:
        return 0.0

    turns_with_evidence = sum(
        1 for turn in human_turns_list
        if any(re.search(pattern, turn.text, re.IGNORECASE) for pattern in _EVIDENCE_INDICATORS)
    )

    score = turns_with_evidence / max(1, len(human_turns_list))
    return min(1.0, score)


# ── LF Registry ──────────────────────────────────────────────────────────────

DETERMINISTIC_LFS = {
    "EC-06": lf_ec_06_verification_markers,
    "EC-07": lf_ec_07_interrogative_ratio,
    "EC-09": lf_ec_09_unverified_confident_claims,
    "PR-02": lf_pr_02_follows_with_rationale,
    "PR-05": lf_pr_05_turns_without_full_ai_dependence,
    "PR-07": lf_pr_07_diverse_turn_topics,
    "PR-14": lf_pr_14_follows_with_rationale_strong,
    "AL-08": lf_al_08_has_substantive_question,
    "ES-01": lf_es_01_has_evidence_citation,
}


def score_deterministic_neurons(session: CanonicalSession) -> dict[str, float]:
    """
    Score all 9 deterministic neurons for a session.

    Returns: {neuron_id: score [0.0, 1.0]} for all deterministic neurons.
    """
    return {
        neuron_id: lf(session)
        for neuron_id, lf in DETERMINISTIC_LFS.items()
    }


if __name__ == "__main__":
    # Quick self-test
    print("Snorkel labeling functions loaded.")
    print(f"Registered LFs: {list(DETERMINISTIC_LFS.keys())}")
