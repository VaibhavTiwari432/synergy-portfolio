"""ADR-0019 eligibility gate — unit tests.

The shipped matrix is a permissive scaffold (excludes nothing); these tests pin
the gate machinery and the scaffold's safe no-op contract, not domain mappings.
"""

import pytest

from contracts.schemas import ScoreStatus
from src.aggregate.eligibility_gate import (
    BEHAVIORAL_NA,
    STRUCTURAL_NA,
    EligibilityGate,
    default_gate,
)


def test_matrix_covers_all_judge_typed_and_exempts_deterministic():
    from src.trait.judge import rubric_bank as rb

    g = EligibilityGate()
    assert set(g.matrix) == set(rb.JUDGE_TYPED_NEURONS)
    assert set(g.exempt) == set(rb.DETERMINISTIC_NEURONS)
    assert len(g.matrix) == 98 and len(g.exempt) == 9
    assert len(g.intent_tags) == 10


def test_full_tag_set_covers_all_single_intent_filters():
    """Tightened matrix (v1.1.0): the full 10-tag set covers every neuron (each
    cell has >=1 valid tag); a single intent yields a proper subset."""
    g = EligibilityGate()
    assert g.determine_scorable_neurons(g.intent_tags) == set(g.matrix)
    verify = g.determine_scorable_neurons(["VERIFY"])
    assert 0 < len(verify) < len(g.matrix)  # gate actually filters now


def test_empty_or_unknown_intents_score_nothing():
    g = EligibilityGate()
    assert g.determine_scorable_neurons([]) == set()
    assert g.determine_scorable_neurons(["NOT_A_REAL_TAG"]) == set()


def test_classify_na_reason_structural_vs_behavioral():
    g = EligibilityGate()
    assert g.classify_na_reason("CA-16", []) == STRUCTURAL_NA
    assert g.classify_na_reason("CA-16", ["VERIFY"]) == BEHAVIORAL_NA


def test_exempt_neuron_is_not_intent_filtered():
    g = EligibilityGate()
    with pytest.raises(KeyError):
        g.classify_na_reason("EC-06", ["VERIFY"])


def test_na_status_reuses_existing_not_applicable():
    assert EligibilityGate().na_status() is ScoreStatus.NOT_APPLICABLE


def test_default_gate_is_cached_singleton():
    assert default_gate() is default_gate()


def test_tightened_cell_excludes_when_intent_absent():
    """Simulate a reviewed cell: tightening triggers_on makes the gate filter."""
    g = EligibilityGate()
    g.matrix["CA-16"]["triggers_on"] = ["OVERRIDE", "PIVOT", "SELF_AUDIT"]
    assert "CA-16" not in g.determine_scorable_neurons(["EXTRACT"])
    assert "CA-16" in g.determine_scorable_neurons(["OVERRIDE"])
    assert g.classify_na_reason("CA-16", ["EXTRACT"]) == STRUCTURAL_NA
