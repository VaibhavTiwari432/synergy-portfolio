"""Phase 2.2 acceptance — AI-side displayed-contribution extractor.

Acceptance (v3.2 §2.2): C7 AI-contribution is ~0 on all fixtures; the extractor
is deterministic; output is a 7-vector on [0, 1].
"""

from __future__ import annotations

from contracts.schemas import CanonicalSession, PartnerModel, Turn
from csl.ai_side_extractor import extract_ai_contribution
from csl.crosswalk import ACF_LEVELS, load_acf_crosswalk

CROSSWALK = load_acf_crosswalk()


def _session(*pairs: tuple[str, str]) -> CanonicalSession:
    """Build a session from (role, text) pairs with dense indices."""
    turns = [Turn(index=i, role=role, text=text) for i, (role, text) in enumerate(pairs)]
    return CanonicalSession(
        session_id="ai-side-test",
        source="plaintext",
        partner_model=PartnerModel(family="openai"),
        turns=turns,
    )


def test_output_is_seven_vector_in_unit_range():
    session = _session(
        ("human", "help me"),
        ("ai", "According to the docs, here's a function:\n```py\ndef f(): ...\n```"),
    )
    result = extract_ai_contribution(session, CROSSWALK)

    assert tuple(result) == ACF_LEVELS
    assert len(result) == 7
    for level, value in result.items():
        assert 0.0 <= value <= 1.0, f"{level} out of range: {value}"


def test_c7_is_zero_on_rich_fixture():
    # Even a heavily orchestration-flavoured AI turn must not give the AI C7 credit:
    # the AI cannot orchestrate the collaboration itself (fixed 0 by construction).
    session = _session(
        ("human", "manage this for me"),
        ("ai", "I'll delegate the first part, then verify, then decide when to stop. "
               "Let's break this down: first, second. Here's a draft. Pros and cons follow."),
    )
    result = extract_ai_contribution(session, CROSSWALK)
    assert result["C7"] == 0.0


def test_c7_is_zero_on_empty_and_human_only_fixtures():
    assert extract_ai_contribution(_session(), CROSSWALK)["C7"] == 0.0
    human_only = _session(("human", "hello"), ("human", "still me"))
    assert extract_ai_contribution(human_only, CROSSWALK)["C7"] == 0.0


def test_no_ai_turns_yields_all_zero_not_error():
    # AI output is fully displayed; its absence is an honest 0, not N/A.
    result = extract_ai_contribution(_session(("human", "anyone there?")), CROSSWALK)
    assert all(value == 0.0 for value in result.values())


def test_deterministic_repeated_calls_identical():
    session = _session(
        ("human", "q"),
        ("ai", "The reason is X because Y. However, double-check this. "
               "Here's a draft:\n```\ncode\n```\nPros and cons: tradeoff."),
    )
    first = extract_ai_contribution(session, CROSSWALK)
    second = extract_ai_contribution(session, CROSSWALK)
    assert first == second


def test_sourcing_signal_lifts_c1():
    sourced = _session(
        ("human", "what is it"),
        ("ai", "According to the documentation, https://example.com defines it as X."),
    )
    bare = _session(
        ("human", "what is it"),
        ("ai", "It is a thing."),
    )
    assert extract_ai_contribution(sourced, CROSSWALK)["C1"] > 0.0
    assert extract_ai_contribution(bare, CROSSWALK)["C1"] == 0.0


def test_making_signal_lifts_c6_on_code_block():
    making = _session(
        ("human", "write a function"),
        ("ai", "Here's a function:\n```python\ndef add(a, b):\n    return a + b\n```"),
    )
    assert extract_ai_contribution(making, CROSSWALK)["C6"] > 0.0


def test_strength_is_share_of_ai_turns():
    # Two AI turns; only one carries a C5 (quality-judging) signal -> 0.5.
    session = _session(
        ("human", "a"),
        ("ai", "Here are the pros and cons; option A is better, a clear tradeoff."),
        ("human", "b"),
        ("ai", "Sure, done."),
    )
    assert extract_ai_contribution(session, CROSSWALK)["C5"] == 0.5


def test_blank_ai_turns_excluded_from_denominator():
    session = _session(
        ("human", "a"),
        ("ai", "   "),  # whitespace-only: not content-bearing
        ("ai", "According to the spec, here's the answer."),
    )
    # Only the one content-bearing AI turn counts -> C1 == 1.0, not 0.5.
    assert extract_ai_contribution(session, CROSSWALK)["C1"] == 1.0
