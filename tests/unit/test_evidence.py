"""Unit tests for EC provenance + theater check. OWNER: Chief Engineer."""

from __future__ import annotations

from contracts.schemas import (
    CanonicalSession,
    IntentTag,
    PartnerModel,
    Provenance,
    Turn,
    TurnTags,
)
from src.trait.evidence import assess_ec_evidence


def _session(human_texts: list[str]) -> CanonicalSession:
    turns: list[Turn] = []
    for i, text in enumerate(human_texts):
        turns.append(Turn(index=len(turns), role="human", text=text))
        turns.append(Turn(index=len(turns), role="ai", text=f"ai reply {i}"))
    return CanonicalSession(
        session_id="e-1", source="plaintext",
        partner_model=PartnerModel(family="openai"), turns=turns,
    )


def _tags(session: CanonicalSession, tag_map: dict[int, list[IntentTag]]) -> list[TurnTags]:
    return [
        TurnTags(turn_index=t.index, tags=tag_map.get(t.index, []))
        for t in session.turns
        if t.role == "human"
    ]


def test_no_verify_turns_means_no_evidence_not_zero():
    s = _session(["give me a summary", "ok thanks"])
    result = assess_ec_evidence(s, _tags(s, {}))
    assert result.tags == ()
    assert result.displayed_share is None  # absent ≠ zero
    assert result.theater_counter == 0


def test_displayed_provenance_for_pasted_error():
    s = _session([
        "run this",
        "I got this:\nTraceback (most recent call last)\nValueError: bad — fix the parsing",
    ])
    tags = _tags(s, {2: [IntentTag.VERIFY]})
    result = assess_ec_evidence(s, tags)
    assert len(result.tags) == 1
    assert result.tags[0].provenance == Provenance.DISPLAYED
    assert result.tags[0].is_theater is False  # "fix" names the delta
    assert result.displayed_share == 1.0


def test_implied_provenance_for_asserted_check():
    s = _session([
        "what is the rate limit",
        "I checked and that limit is outdated, change the example",
    ])
    tags = _tags(s, {2: [IntentTag.VERIFY]})
    result = assess_ec_evidence(s, tags)
    assert result.tags[0].provenance == Provenance.IMPLIED
    assert result.tags[0].is_theater is False  # "change" = downstream delta
    assert result.displayed_share == 0.0


def test_theater_verification_with_no_downstream_delta():
    s = _session([
        "are you sure about that?",   # VERIFY, but…
        "ok sounds good",             # …flat accept
        "thanks, continue",           # …flat accept
        "great",                      # …flat accept
    ])
    tags = _tags(s, {
        0: [IntentTag.VERIFY],
        2: [IntentTag.ACCEPT_FLAT],
        4: [IntentTag.ACCEPT_FLAT],
        6: [IntentTag.ACCEPT_FLAT],
    })
    result = assess_ec_evidence(s, tags)
    assert result.tags[0].is_theater is True
    assert result.theater_counter == 1


def test_real_verification_followed_by_override_is_not_theater():
    s = _session([
        "are you sure this applies to v2 of the API?",
        "use the v2 endpoint instead, and add retry logic",
    ])
    tags = _tags(s, {0: [IntentTag.VERIFY], 2: [IntentTag.OVERRIDE]})
    result = assess_ec_evidence(s, tags)
    assert result.tags[0].is_theater is False
    assert result.theater_counter == 0


def test_quoted_contradiction_counts_as_displayed():
    s = _session([
        'you said "the limit is 100" but the docs say it is 60',
    ])
    tags = _tags(s, {0: [IntentTag.VERIFY]})
    result = assess_ec_evidence(s, tags)
    assert result.tags[0].provenance == Provenance.DISPLAYED


def test_mixed_share_computed_over_verify_turns_only():
    s = _session([
        "according to the paper, that constant is 3.9, not 4.2 — correct it",  # displayed
        "I tested it and it didn't work, redo it",                              # implied
        "just summarize the rest",                                              # not VERIFY
    ])
    tags = _tags(s, {0: [IntentTag.VERIFY], 2: [IntentTag.VERIFY], 4: [IntentTag.EXTRACT]})
    result = assess_ec_evidence(s, tags)
    assert len(result.tags) == 2
    assert result.displayed_share == 0.5
