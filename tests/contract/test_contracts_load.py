"""Stage-0 gate tests: contracts import clean, ontology loads, charter holds.

These must be GREEN before Stage 1 starts (brief §5 Stage 0 gate). OWNER: CE.
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from contracts.event_taxonomy import (
    ALL_EVENT_TYPES,
    MIN_EVENTS_PER_CELL,
    REACTION_WINDOW_K,
    TRIGGER_EVENTS,
)
from contracts.intent_tags import ALL_INTENT_TAGS, EXTRACTIVE_TAGS, GENERATIVE_TAGS
from contracts.schemas import (
    DIMENSION_NEURON_COUNTS,
    DIMENSION_WEIGHTS,
    CanonicalSession,
    CellGatedProb,
    Composite,
    ConfidenceInterval,
    DebtEwma,
    DebtMode,
    Dimension,
    DimensionScore,
    Event,
    EventType,
    FrictionTransitionMatrix,
    LambdaStub,
    MetacogLabel,
    PartnerModel,
    Provenance,
    ReactionSignatures,
    RegimeLabel,
    RegimeOverlay,
    Report,
    Rung,
    ScoreResponse,
    ScoreStatus,
    SessionFlags,
    SHumanHat,
    StateValidity,
    StateVector,
    Sustainability,
    TransitionMetrics,
    Turn,
    Actor,
)

ROOT = Path(__file__).resolve().parents[2]
CONTRACTS = ROOT / "contracts"


# ── Ontology freeze (non-negotiable #1) ──────────────────────────────────────


def test_contract_table_loads_with_107_neurons():
    table = yaml.safe_load((CONTRACTS / "contract_table.yaml").read_text(encoding="utf-8"))
    neurons = table["neurons"]
    assert len(neurons) == 107

    per_dim: dict[str, int] = {}
    for n in neurons:
        per_dim[n["dimension"]] = per_dim.get(n["dimension"], 0) + 1
    expected = {dim.value: count for dim, count in DIMENSION_NEURON_COUNTS.items()}
    assert per_dim == expected


def test_neurons_v6_loads_and_matches_contract_table():
    data = json.loads((CONTRACTS / "neurons_v6.json").read_text(encoding="utf-8"))
    assert len(data) == 107
    table = yaml.safe_load((CONTRACTS / "contract_table.yaml").read_text(encoding="utf-8"))
    table_ids = {n["id"] for n in table["neurons"]}
    assert set(data.keys()) == table_ids


def test_dimension_constants_consistent():
    assert sum(DIMENSION_NEURON_COUNTS.values()) == 107
    assert len(Dimension) == 8
    assert DIMENSION_WEIGHTS[Dimension.EC] == 1.5
    assert DIMENSION_WEIGHTS[Dimension.CS] == 1.5
    assert all(
        DIMENSION_WEIGHTS[d] == 1.0
        for d in Dimension
        if d not in (Dimension.EC, Dimension.CS)
    )


# ── Frozen vocabularies ──────────────────────────────────────────────────────


def test_event_taxonomy_frozen_six_plus_nfire():
    assert len(TRIGGER_EVENTS) == 6
    assert len(ALL_EVENT_TYPES) == 7
    assert EventType.N_FIRE not in TRIGGER_EVENTS
    assert REACTION_WINDOW_K >= 1
    assert MIN_EVENTS_PER_CELL >= 2  # never a probability from 1 event


def test_intent_tags_frozen_ten():
    assert len(ALL_INTENT_TAGS) == 10
    assert len(set(ALL_INTENT_TAGS)) == 10
    assert GENERATIVE_TAGS.isdisjoint(EXTRACTIVE_TAGS)


def test_regime_overlay_cannot_say_surrender():
    # Non-negotiable #5, structurally: no RegimeLabel value contains "surrender".
    assert all("surrender" not in label.value.lower() for label in RegimeLabel)
    # The CSPC construct exists in exactly one place:
    assert MetacogLabel.SURRENDER.value == "SURRENDER"


# ── Claims charter (brief §3.10) ─────────────────────────────────────────────


def test_claims_table_loads_and_charter_holds():
    charter = yaml.safe_load((CONTRACTS / "claims_table.yaml").read_text(encoding="utf-8"))
    t1 = charter["tiers"]["tier_1"]
    assert t1["max_rung"] == "MEASURABLE"
    assert "synergy" in t1["forbidden_words_user_facing"]
    assert "surrender" in t1["forbidden_words_user_facing"]

    everywhere = charter["forbidden_everywhere"]
    assert any("leaderboard" in c.lower() for c in everywhere["claims"])
    assert any("bare composite" in c.lower() for c in everywhere["claims"])
    assert "surrender" in everywhere["user_facing_labels"]

    minors = charter["minor_protection"]
    assert "bare composite" in minors["forbidden_outputs"]
    assert "debt score" in minors["forbidden_outputs"]

    assert charter["regime_overlay"]["forbidden_labels"] == ["surrender"]


def test_probe_schema_loads_and_excludes_recognition():
    probe = yaml.safe_load((CONTRACTS / "probe_schema.yaml").read_text(encoding="utf-8"))
    assert probe["rung"] == "DESIGNED"
    assert probe["delivery_in_scope_a"] is False
    format_ids = {f["id"] for f in probe["formats"]}
    assert format_ids == {"free_recall", "application", "teach_back"}
    assert {f["id"] for f in probe["excluded_formats"]} == {"recognition"}


# ── Schema behavior: absent ≠ zero (non-negotiable #12) ──────────────────────


def test_dimension_score_rejects_value_on_insufficient_sample():
    import pytest

    with pytest.raises(ValueError):
        DimensionScore(
            dim=Dimension.EC,
            status=ScoreStatus.INSUFFICIENT_SAMPLE,
            value=0.0,  # forbidden: absent must not be encoded as zero
            rung=Rung.MEASURABLE,
        )


def test_dimension_score_requires_value_when_ok():
    import pytest

    with pytest.raises(ValueError):
        DimensionScore(dim=Dimension.EC, status=ScoreStatus.OK, rung=Rung.MEASURABLE)


def test_canonical_session_rejects_sparse_turn_indices():
    import pytest

    pm = PartnerModel(family="openai")
    with pytest.raises(ValueError):
        CanonicalSession(
            session_id="s1",
            source="plaintext",
            partner_model=pm,
            turns=[Turn(index=0, role="human", text="hi"), Turn(index=2, role="ai", text="hello")],
        )


# ── Full ScoreResponse round-trip (the API deliverable shape) ────────────────


def _minimal_score_response() -> ScoreResponse:
    gated = CellGatedProb()
    profile = {
        dim: DimensionScore(
            dim=dim,
            status=ScoreStatus.OK,
            value=0.5,
            ci=ConfidenceInterval(low=0.3, high=0.7),
            n_eff=4.0,
            rung=Rung.MEASURABLE,
        )
        for dim in Dimension
    }
    return ScoreResponse(
        session_id="s1",
        tier=1,
        profile=profile,
        composite=Composite(
            value=0.5,
            ci=ConfidenceInterval(low=0.4, high=0.6),
            gates_passed={"scorability": True, "state_validity": True},
            rung=Rung.MEASURABLE,
        ),
        state_strip=[StateVector(turn_index=0)],
        state_validity=StateValidity(),
        flags=SessionFlags(),
        reaction_signatures=ReactionSignatures(
            ftm=FrictionTransitionMatrix(
                p_verify=gated, p_accept_flat=gated, p_disengage=gated
            ),
            transition_metrics=TransitionMetrics(
                verify_after_error_rate=gated,
                constraint_before_generation_rate=gated,
                prediction_before_answer_rate=gated,
                revision_after_output_rate=gated,
            ),
        ),
        regime_overlay=RegimeOverlay(),
        sustainability=Sustainability(
            s_human_hat=SHumanHat(),
            debt_ewma=DebtEwma(mode=DebtMode.INSUFFICIENT_HISTORY),
        ),
        report=Report(tier_caveat="Tier 1: transcript-only evidence; nothing is VALIDATED yet."),
    )


def test_score_response_round_trips():
    resp = _minimal_score_response()
    dumped = resp.model_dump_json(by_alias=True)
    assert ScoreResponse.model_validate_json(dumped) == resp


def test_score_response_requires_exactly_eight_dimensions():
    import pytest

    resp = _minimal_score_response()
    partial = {d: s for d, s in resp.profile.items() if d != Dimension.CA}
    with pytest.raises(ValueError):
        ScoreResponse(**{**resp.model_dump(exclude={"profile"}), "profile": partial})


def test_event_log_record_shape():
    e = Event(
        t=0,
        event_type=EventType.E_FRICTION,
        actor=Actor.SYSTEM,
        payload_ref="turn:3",
        confidence=0.9,
        provenance=Provenance.DISPLAYED,
    )
    assert e.t == 0 and e.metadata == {}


def test_lambda_is_a_stub_in_scope_a():
    stub = LambdaStub()
    assert stub.value is None
    assert stub.rung == Rung.DESIGNED
