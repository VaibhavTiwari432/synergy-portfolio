import pytest

from src.db.queries import (
    capture_completeness_error,
    capture_validation_error,
    reconcile_captured_count,
)


def test_capture_validation_accepts_balanced_chat():
    assert capture_validation_error([
        {"role": "user", "text": "Question"},
        {"role": "assistant", "text": "Answer"},
        {"role": "user", "text": "Follow-up"},
    ]) is None


def test_capture_validation_rejects_missing_assistant_turns():
    assert capture_validation_error([
        {"role": "user", "text": "Question"},
        {"role": "user", "text": "Follow-up"},
    ]) == "capture has no assistant turns"


def test_capture_validation_rejects_imbalanced_transcript():
    reason = capture_validation_error(
        [{"role": "user", "text": f"Question {i}"} for i in range(8)] +
        [{"role": "assistant", "text": "Answer"}]
    )
    assert reason == "capture turn roles are imbalanced (user=8, assistant=1)"


def test_capture_validation_rejects_unknown_roles():
    assert capture_validation_error([
        {"role": "system", "text": "hidden instruction"},
        {"role": "user", "text": "Question"},
        {"role": "assistant", "text": "Answer"},
    ]) == "unsupported turn role: system"


# ── completeness gate (ADR-0007 / D-015) ─────────────────────────────────────

def test_completeness_unknown_is_accepted():
    # null capture_complete + null expected = legacy / scroll-probe fallback path:
    # completeness UNKNOWN → defer to the role-balance gate, do NOT quarantine.
    assert capture_completeness_error(
        expected_turn_count=None,
        captured_turn_count=12,
        capture_complete=None,
    ) is None


def test_completeness_proven_complete_is_accepted():
    assert capture_completeness_error(
        expected_turn_count=10,
        captured_turn_count=10,
        capture_complete=True,
    ) is None


def test_completeness_proven_incomplete_is_quarantined():
    assert capture_completeness_error(
        expected_turn_count=42,
        captured_turn_count=30,
        capture_complete=False,
    ) == "capture proven incomplete (captured 30 of 42 turns)"


def test_completeness_false_without_counts_still_quarantined():
    assert capture_completeness_error(
        expected_turn_count=None,
        captured_turn_count=None,
        capture_complete=False,
    ) == "capture proven incomplete"


def test_completeness_truncation_quarantined_even_if_flag_claims_complete():
    # A truthy flag must not smuggle a truncated transcript past the gate — the
    # counts win (and the migration-007 CHECK enforces the same at rest).
    assert capture_completeness_error(
        expected_turn_count=20,
        captured_turn_count=8,
        capture_complete=True,
    ) == "capture truncated (captured 8 of 20 turns)"


def test_completeness_live_tail_beyond_expected_is_accepted():
    # captured > expected is legitimate: the DOM-streamed tail extends past the
    # intercepted history count (D-015 §6). Only captured < expected is truncation.
    assert capture_completeness_error(
        expected_turn_count=10,
        captured_turn_count=12,
        capture_complete=True,
    ) is None


# ── server-derived captured count (ADR-0007 / D-015) ─────────────────────────

def test_captured_count_is_server_derived_when_client_omits():
    assert reconcile_captured_count(turns_len=7, client_captured=None) == 7


def test_captured_count_accepts_matching_client_value():
    assert reconcile_captured_count(turns_len=7, client_captured=7) == 7


def test_captured_count_rejects_client_overclaim():
    # The attack the DB CHECK can't see: claim 10 captured while delivering 3.
    with pytest.raises(ValueError, match="does not match"):
        reconcile_captured_count(turns_len=3, client_captured=10)


def test_captured_count_rejects_client_underclaim():
    with pytest.raises(ValueError, match="does not match"):
        reconcile_captured_count(turns_len=9, client_captured=4)
