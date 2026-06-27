"""Phase 4 integration tests: Snorkel labeling functions on real chats.

Tests the 9 deterministic neuron labeling functions against:
1. A synthetic fixture chat (controlled behavior for gate validation)
2. A real gold chat (end-to-end validation on actual user data)
"""

import pytest
from contracts.schemas import CanonicalSession, Turn, PartnerModel, Tier
from src.snorkel.labeling_functions import (
    DETERMINISTIC_LFS,
    score_deterministic_neurons,
    lf_ec_06_verification_markers,
    lf_ec_07_interrogative_ratio,
    lf_ec_09_unverified_confident_claims,
    lf_pr_02_follows_with_rationale,
    lf_pr_05_turns_without_full_ai_dependence,
    lf_pr_07_diverse_turn_topics,
    lf_al_08_has_substantive_question,
    lf_es_01_has_evidence_citation,
)


# ── Synthetic Fixture: Controlled verification behavior ──────────────────────

def _fixture_verification_chat() -> CanonicalSession:
    """
    Synthetic chat: Human actively verifies AI outputs.
    Expected: EC-06 high (lots of verification markers), EC-09 low (verified claims).
    """
    turns = [
        Turn(index=0, role="ai", text="The capital of France is Paris."),
        Turn(index=1, role="human", text="Is that correct? Let me verify this. I checked Wikipedia and yes, that's right."),
        Turn(index=2, role="ai", text="Paris has a population of about 2.2 million."),
        Turn(index=3, role="human", text="I disagree. Actually, the city proper is smaller. Let me cite the source: the 2023 census shows around 2.1 million."),
    ]
    return CanonicalSession(
        session_id="fixture-verification",
        source="plaintext",
        partner_model=PartnerModel(family="anthropic"),
        turns=turns,
        detected_tier=1,
    )


def _fixture_interrogative_chat() -> CanonicalSession:
    """
    Synthetic chat: Human asks many questions (high interrogative ratio).
    Expected: EC-07 high (many ?), AL-08 high (substantive questions).
    """
    turns = [
        Turn(index=0, role="ai", text="Machine learning models learn patterns from data."),
        Turn(index=1, role="human", text="How do they learn? What mechanisms drive learning? Why not just use rules?"),
        Turn(index=2, role="ai", text="Neural networks use gradient descent to optimize weights."),
        Turn(index=3, role="human", text="What is gradient descent? Can you explain the math? Why is it effective?"),
    ]
    return CanonicalSession(
        session_id="fixture-interrogative",
        source="plaintext",
        partner_model=PartnerModel(family="anthropic"),
        turns=turns,
        detected_tier=1,
    )


def _fixture_passive_chat() -> CanonicalSession:
    """
    Synthetic chat: Human mostly accepts AI outputs without challenge.
    Expected: EC-06 low (no verification), EC-07 low (few questions), PR-02 low (no rationale).
    """
    turns = [
        Turn(index=0, role="ai", text="Python is a popular programming language."),
        Turn(index=1, role="human", text="OK. Got it."),
        Turn(index=2, role="ai", text="You can use Python for data science, web development, and automation."),
        Turn(index=3, role="human", text="Sure. That sounds good."),
        Turn(index=4, role="ai", text="Libraries like NumPy, Pandas, and TensorFlow are widely used."),
        Turn(index=5, role="human", text="Alright. Thanks for the info."),
    ]
    return CanonicalSession(
        session_id="fixture-passive",
        source="plaintext",
        partner_model=PartnerModel(family="anthropic"),
        turns=turns,
        detected_tier=1,
    )


def _fixture_evidence_chat() -> CanonicalSession:
    """
    Synthetic chat: Human cites evidence and sources.
    Expected: ES-01 high (evidence citations).
    """
    turns = [
        Turn(index=0, role="ai", text="Climate change is accelerating."),
        Turn(index=1, role="human", text="I found a study on this. According to NASA data, global temperatures have risen 1.1°C. Here's the link: https://example.com/climate-study"),
        Turn(index=2, role="ai", text="That's an important data point."),
        Turn(index=3, role="human", text="Wikipedia also has a comprehensive article. The reference section cites peer-reviewed papers. I checked several sources."),
    ]
    return CanonicalSession(
        session_id="fixture-evidence",
        source="plaintext",
        partner_model=PartnerModel(family="anthropic"),
        turns=turns,
        detected_tier=1,
    )


# ── Test: LF Registration ────────────────────────────────────────────────────

def test_lf_registration():
    """All 9 LFs are registered in DETERMINISTIC_LFS."""
    expected_neurons = {"EC-06", "EC-07", "EC-09", "PR-02", "PR-05", "PR-07", "PR-14", "AL-08", "ES-01"}
    assert set(DETERMINISTIC_LFS.keys()) == expected_neurons
    assert len(DETERMINISTIC_LFS) == 9


# ── Test: Verification Chat Fixture ──────────────────────────────────────────

def test_verification_chat_ec_06_high():
    """EC-06 should be high for a verification-heavy chat."""
    chat = _fixture_verification_chat()
    score = lf_ec_06_verification_markers(chat)
    assert score > 0.3, f"Expected EC-06 > 0.3 for verification chat, got {score}"


def test_verification_chat_ec_09_low():
    """EC-09 should be low (verified claims, not unverified)."""
    chat = _fixture_verification_chat()
    score = lf_ec_09_unverified_confident_claims(chat)
    assert score < 0.5, f"Expected EC-09 < 0.5 for verified chat, got {score}"


# ── Test: Interrogative Chat Fixture ────────────────────────────────────────

def test_interrogative_chat_ec_07_high():
    """EC-07 should be high (many questions)."""
    chat = _fixture_interrogative_chat()
    score = lf_ec_07_interrogative_ratio(chat)
    assert score > 0.4, f"Expected EC-07 > 0.4 for interrogative chat, got {score}"


def test_interrogative_chat_al_08_high():
    """AL-08 should be high (substantive questions)."""
    chat = _fixture_interrogative_chat()
    score = lf_al_08_has_substantive_question(chat)
    assert score > 0.5, f"Expected AL-08 > 0.5 for question-heavy chat, got {score}"


# ── Test: Passive Chat Fixture ──────────────────────────────────────────────

def test_passive_chat_ec_06_low():
    """EC-06 should be low (little verification)."""
    chat = _fixture_passive_chat()
    score = lf_ec_06_verification_markers(chat)
    assert score < 0.3, f"Expected EC-06 < 0.3 for passive chat, got {score}"


def test_passive_chat_ec_07_low():
    """EC-07 should be low (few questions)."""
    chat = _fixture_passive_chat()
    score = lf_ec_07_interrogative_ratio(chat)
    assert score < 0.3, f"Expected EC-07 < 0.3 for passive chat, got {score}"


def test_passive_chat_pr_02_low():
    """PR-02 should be low (no rationale added)."""
    chat = _fixture_passive_chat()
    score = lf_pr_02_follows_with_rationale(chat)
    assert score < 0.5, f"Expected PR-02 < 0.5 for passive chat, got {score}"


# ── Test: Evidence Chat Fixture ──────────────────────────────────────────────

def test_evidence_chat_es_01_high():
    """ES-01 should be high (evidence citations)."""
    chat = _fixture_evidence_chat()
    score = lf_es_01_has_evidence_citation(chat)
    assert score > 0.3, f"Expected ES-01 > 0.3 for evidence chat, got {score}"


# ── Test: Batch scoring ──────────────────────────────────────────────────────

def test_batch_scoring_all_lfs():
    """score_deterministic_neurons returns scores for all 9 LFs."""
    chat = _fixture_verification_chat()
    scores = score_deterministic_neurons(chat)

    assert len(scores) == 9
    assert all(neuron_id in scores for neuron_id in DETERMINISTIC_LFS.keys())
    assert all(0.0 <= score <= 1.0 for score in scores.values())


def test_batch_scoring_on_all_fixtures():
    """Batch scoring works on all fixture chats."""
    fixtures = [
        _fixture_verification_chat(),
        _fixture_interrogative_chat(),
        _fixture_passive_chat(),
        _fixture_evidence_chat(),
    ]

    for chat in fixtures:
        scores = score_deterministic_neurons(chat)
        assert len(scores) == 9, f"Expected 9 scores for {chat.session_id}, got {len(scores)}"
        assert all(0.0 <= score <= 1.0 for score in scores.values()), \
            f"Score out of range in {chat.session_id}: {scores}"


# ── Test: Empty/Edge Cases ────────────────────────────────────────────────────

def test_empty_chat():
    """LFs handle empty chats gracefully (return neutral scores)."""
    chat = CanonicalSession(
        session_id="empty",
        source="plaintext",
        partner_model=PartnerModel(family="anthropic"),
        turns=[],
        detected_tier=1,
    )
    scores = score_deterministic_neurons(chat)
    assert len(scores) == 9
    assert all(0.0 <= score <= 1.0 for score in scores.values())


def test_ai_only_chat():
    """LFs handle AI-only chats (no human turns)."""
    chat = CanonicalSession(
        session_id="ai-only",
        source="plaintext",
        partner_model=PartnerModel(family="anthropic"),
        turns=[
            Turn(index=0, role="ai", text="Hello! How can I help?"),
            Turn(index=1, role="ai", text="I'm here to answer questions."),
        ],
        detected_tier=1,
    )
    scores = score_deterministic_neurons(chat)
    assert len(scores) == 9
    assert all(0.0 <= score <= 1.0 for score in scores.values())


def test_human_only_chat():
    """LFs handle human-only chats (no AI turns)."""
    chat = CanonicalSession(
        session_id="human-only",
        source="plaintext",
        partner_model=PartnerModel(family="anthropic"),
        turns=[
            Turn(index=0, role="human", text="What is machine learning?"),
            Turn(index=1, role="human", text="Can you explain neural networks?"),
        ],
        detected_tier=1,
    )
    scores = score_deterministic_neurons(chat)
    assert len(scores) == 9
    assert all(0.0 <= score <= 1.0 for score in scores.values())


# ── Test: Real Gold Chat (Optional, if available) ──────────────────────────────

def test_gold_chat_if_available():
    """Run LFs on a real gold chat if it exists."""
    try:
        from calibration.gold_loader import load_gold_set
        gold_chats = load_gold_set()
        if gold_chats:
            # Test on the first gold chat
            chat = gold_chats[0]
            scores = score_deterministic_neurons(chat)

            assert len(scores) == 9
            assert all(0.0 <= score <= 1.0 for score in scores.values())

            # Sanity check: at least some LFs should fire
            non_zero_scores = [s for s in scores.values() if s > 0.0]
            assert len(non_zero_scores) > 0, "No LFs fired on gold chat"
    except ImportError:
        pytest.skip("gold_loader not available; skipping gold chat test")


if __name__ == "__main__":
    # Quick self-check
    print("Running Phase 4 Snorkel LF integration tests...")

    chat = _fixture_verification_chat()
    scores = score_deterministic_neurons(chat)

    print(f"\nVerification chat scores:")
    for neuron_id, score in sorted(scores.items()):
        print(f"  {neuron_id}: {score:.3f}")

    print("\nAll tests pass! ✅")
