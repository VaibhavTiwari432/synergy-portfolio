"""FIX-0.5 provenance classifier tests."""

from __future__ import annotations

import pytest

from contracts.schemas import CanonicalSession, PartnerModel, Turn
from src.classifier.provenance_classifier import (
    ProvenanceClass,
    apply_provenance_weights,
    classify_provenance,
    classify_session_turns,
    neuron_provenance_weights,
    provenance_weight,
    text_similarity,
)


def _session(*turns: tuple[str, str], telemetry=None) -> CanonicalSession:
    return CanonicalSession(
        session_id="s",
        source="plaintext",
        partner_model=PartnerModel(family="unknown"),
        turns=[Turn(index=i, role=role, text=text) for i, (role, text) in enumerate(turns)],
        metadata={"telemetry": telemetry or {}},
    )


def test_verbatim_ai_text_is_zero_weight():
    text = "Use a binary search over the sorted array and return the midpoint."
    decision = classify_provenance(text, ai_sources=[text])
    assert decision.label is ProvenanceClass.VERBATIM
    assert decision.weight == 0.0


def test_high_overlap_copy_is_zero_weight():
    ai = "Create the React component with a header, chart, and export button."
    human = "Create the React component with header chart and export button."
    decision = classify_provenance(human, ai_sources=[ai])
    assert decision.label is ProvenanceClass.COPY
    assert decision.weight == 0.0


def test_moderate_overlap_is_ai_assisted_not_zeroed():
    decision = classify_provenance(
        "I used your outline, but I want the risk section inverted.",
        ai_sources=["Outline: goals, risks, milestones, owner mapping."],
    )
    assert decision.label is ProvenanceClass.AI_ASSISTED
    assert decision.weight == 0.5


def test_distinct_human_text_is_original():
    decision = classify_provenance(
        "My constraint is latency under 200ms because the kiosk times out.",
        ai_sources=["Here is a generic project plan."],
    )
    assert decision.label is ProvenanceClass.HUMAN_ORIGINAL
    assert decision.weight == 1.0


def test_copy_request_is_assisted_but_not_verbatim():
    decision = classify_provenance("Give me the full file text to copy-paste.")
    assert decision.label is ProvenanceClass.AI_ASSISTED
    assert decision.weight == 0.5


def test_telemetry_copy_large_code_payload_is_copy():
    code = "import React from 'react'\n" + "const x = 1\n" * 200
    decision = classify_provenance(code, metadata={"copy_events": 1})
    assert decision.label is ProvenanceClass.COPY
    assert decision.weight == 0.0


def test_pasted_code_payload_is_copy():
    decision = classify_provenance("```js\nconst a = 1\n```", metadata={"pasted": True})
    assert decision.label is ProvenanceClass.COPY
    assert decision.weight == 0.0


def test_empty_text_is_unknown_not_zeroed():
    decision = classify_provenance("")
    assert decision.label is ProvenanceClass.UNKNOWN
    assert decision.weight == 1.0


def test_provenance_weight_zeroes_only_copy_and_verbatim():
    assert provenance_weight(ProvenanceClass.COPY) == 0.0
    assert provenance_weight(ProvenanceClass.VERBATIM) == 0.0
    assert provenance_weight(ProvenanceClass.HUMAN_ORIGINAL) == 1.0


def test_session_turns_compare_human_against_previous_ai():
    session = _session(
        ("ai", "Use a queue and process each node once."),
        ("human", "Use a queue and process each node once."),
    )
    decisions = classify_session_turns(session)
    assert decisions[1].label is ProvenanceClass.VERBATIM


def test_neuron_weights_use_evidence_turns_and_unknown_when_absent():
    session = _session(
        ("ai", "The answer is copy me exactly."),
        ("human", "The answer is copy me exactly."),
        ("human", "My own reasoning is different."),
    )
    decisions = neuron_provenance_weights(
        session,
        {
            "EC-01": {"evidence_turns": [1]},
            "CA-16": {},
        },
    )
    assert decisions["EC-01"].weight == 0.0
    assert decisions["CA-16"].label is ProvenanceClass.UNKNOWN
    assert decisions["CA-16"].weight == 1.0


def test_apply_provenance_weights_sets_copy_verbatim_to_zero():
    firings = {"EC": {"EC-01": 0.82, "EC-02": 0.55}}
    session = _session(
        ("ai", "Use a queue and process each node once."),
        ("human", "Use a queue and process each node once."),
    )
    decisions = neuron_provenance_weights(session, {"EC-01": {"evidence_turns": [1]}})

    zeroed = apply_provenance_weights(firings, decisions)

    assert zeroed == 1
    assert firings["EC"]["EC-01"] == 0.0
    assert firings["EC"]["EC-02"] == 0.55


def test_similarity_is_stable_for_reordered_spacing():
    assert text_similarity("A   B C", "a b   c") == pytest.approx(1.0)

