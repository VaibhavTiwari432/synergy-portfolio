"""Unit tests for the 8 per-dimension extractors (leaves)."""

from __future__ import annotations

import importlib

import pytest

from contracts.schemas import (
    Actor,
    CanonicalSession,
    Dimension,
    Event,
    EventType,
    PartnerModel,
    Provenance,
    Turn,
)
from src.trait.extractors.per_dimension import al, aui, ca, cd, cs, ec, es, pr
from src.trait.phase_classifier import classify_phases
from src.trait.tagger import tag_turns

ALL_MODULES = {m.DIM: m for m in (al, pr, ec, es, cs, cd, aui, ca)}


def _session(turns: list[tuple[str, str]]) -> CanonicalSession:
    return CanonicalSession(
        session_id="x-1", source="plaintext",
        partner_model=PartnerModel(family="openai"),
        turns=[Turn(index=i, role=r, text=t) for i, (r, t) in enumerate(turns)],
    )


def _run(module, session, events=()):
    tags = tag_turns(session)
    phases = classify_phases(session, tags)
    return module.extract(session, tags, phases, list(events))


def _ethics_event(turn_index: int = 0) -> Event:
    return Event(t=0, event_type=EventType.E_OVERREACH, actor=Actor.SYSTEM,
                 confidence=0.9, provenance=Provenance.DISPLAYED,
                 payload_ref=f"turn:{turn_index}")


# ── structural conformance for all 8 ────────────────────────────────────────


def test_every_dimension_has_an_extractor_with_matching_dim():
    assert set(ALL_MODULES.keys()) == set(Dimension)
    for dim, module in ALL_MODULES.items():
        assert module.DIM == dim


def test_extract_returns_the_three_keys_and_only_own_neurons():
    s = _session([("human", "are you sure? what about the missing step?"),
                  ("ai", "answer")])
    for dim, module in ALL_MODULES.items():
        out = _run(module, s)
        assert set(out.keys()) == {"neuron_firings", "applicable_opportunities", "evidence_turns"}
        for nid in {**out["neuron_firings"], **out["applicable_opportunities"]}:
            assert nid.startswith(dim.value + "-")


def test_judge_owned_dimensions_fire_nothing():
    s = _session([("human", "here is my draft, critique my reasoning step by step"),
                  ("ai", "feedback")])
    for module in (cs, cd, aui, ca):
        out = _run(module, s)
        assert out == {"neuron_firings": {}, "applicable_opportunities": {},
                       "evidence_turns": {}}


# ── AL-08 ────────────────────────────────────────────────────────────────────


def test_al08_fires_when_recency_flagged():
    s = _session([
        ("human", "what is the latest python version?"),
        ("ai", "As of 2025, the latest version is 3.13."),
        ("human", "your training data might be outdated — check the latest docs"),
        ("ai", "fair point."),
    ])
    out = _run(al, s)
    assert out["applicable_opportunities"]["AL-08"] == 1
    assert out["neuron_firings"]["AL-08"] == 1.0
    assert out["evidence_turns"]["AL-08"] == [2]


def test_al08_opportunity_without_flag_reports_zero_of_n():
    s = _session([
        ("human", "what's new?"),
        ("ai", "Recently, the framework shipped v9 in 2025."),
        ("human", "ok"),
    ])
    out = _run(al, s)
    assert out["applicable_opportunities"]["AL-08"] == 1
    assert "AL-08" not in out["neuron_firings"]


def test_al08_absent_without_temporal_claims():
    s = _session([("human", "explain recursion"), ("ai", "recursion is ...")])
    out = _run(al, s)
    assert "AL-08" not in out["applicable_opportunities"]  # no opportunity at all


# ── PR ───────────────────────────────────────────────────────────────────────


def test_pr_neurons_fire_on_their_signals():
    s = _session([
        ("human", "walk me through it step by step, format it as a table with columns"),
        ("ai", "done"),
        ("human", "here are examples: input: 2 output: 4. input: 3 output: 9"),
        ("ai", "got it"),
        ("human", "now critique your own answer and find the flaws in your reasoning"),
        ("ai", "ok"),
    ])
    out = _run(pr, s)
    assert out["neuron_firings"]["PR-02"] == pytest.approx(1 / 3)
    assert out["neuron_firings"]["PR-05"] == 1.0
    assert out["neuron_firings"]["PR-07"] == pytest.approx(1 / 3)
    # PR-14: applicable prompts are those after the first AI turn (2 of them)
    assert out["applicable_opportunities"]["PR-14"] == 2
    assert out["neuron_firings"]["PR-14"] == pytest.approx(1 / 2)


def test_pr02_matches_contract_markers_not_generic_step_sequencing():
    s = _session([
        ("human", "walk me through it step by step"),
        ("ai", "done"),
        ("human", "the goal is a safe migration; must include rollback, for example blue-green"),
        ("ai", "understood"),
    ])
    out = _run(pr, s)
    assert out["neuron_firings"]["PR-02"] == 0.5
    assert out["evidence_turns"]["PR-02"] == [2]


def test_pr05_generative_vs_extractive_ratio_and_two_prompt_gate():
    s = _session([
        ("human", "explain why this fails"),
        ("ai", "analysis"),
        ("human", "compare alternatives"),
        ("ai", "comparison"),
        ("human", "write the final summary"),
        ("ai", "summary"),
    ])
    out = _run(pr, s)
    assert out["applicable_opportunities"]["PR-05"] == 3
    assert out["neuron_firings"]["PR-05"] == pytest.approx(2 / 3)
    assert out["evidence_turns"]["PR-05"] == [0, 2]

    single = _run(pr, _session([("human", "explain this"), ("ai", "answer")]))
    assert "PR-05" not in single["applicable_opportunities"]


def test_pr14_not_applicable_before_any_ai_response():
    s = _session([("human", "critique your answer")])  # no AI turn yet
    out = _run(pr, s)
    assert "PR-14" not in out["applicable_opportunities"]


# ── EC ───────────────────────────────────────────────────────────────────────


def test_ec06_verification_rate_from_tags():
    s = _session([
        ("human", "are you sure that's correct?"),
        ("ai", "yes"),
        ("human", "ok"),
        ("ai", "…"),
    ])
    out = _run(ec, s)
    assert out["applicable_opportunities"]["EC-06"] == 2
    assert out["neuron_firings"]["EC-06"] == 0.5
    assert out["evidence_turns"]["EC-06"] == [0]


def test_ec07_interrogative_to_affirmative_ratio():
    s = _session([
        ("human", "Nice summary. But what about the failure modes? You didn't mention them."),
        ("ai", "right"),
    ])
    out = _run(ec, s)
    assert out["applicable_opportunities"]["EC-07"] == 1
    assert out["neuron_firings"]["EC-07"] == pytest.approx(1 / 3)
    assert out["evidence_turns"]["EC-07"] == [0]


def test_ec07_affirmative_multisentence_turn_is_measured_zero():
    s = _session([("human", "This is clear. I will use it."), ("ai", "great")])
    out = _run(ec, s)
    assert out["applicable_opportunities"]["EC-07"] == 1
    assert "EC-07" not in out["neuron_firings"]


def test_ec09_debt_rate_for_unverified_confident_claims():
    s = _session([
        ("human", "how many users does it support?"),
        ("ai", "It supports exactly 10000 users. This is definitely the correct number for 2026."),
        ("human", "ok thanks"),
        ("ai", "…"),
    ])
    out = _run(ec, s)
    assert out["applicable_opportunities"]["EC-09"] == 1
    assert out["neuron_firings"]["EC-09"] == 1.0  # debt direction
    assert out["evidence_turns"]["EC-09"] == [2]


def test_ec09_verified_claim_does_not_fire():
    s = _session([
        ("human", "how many users?"),
        ("ai", "It supports exactly 10000 users. That is definitely the spec for 2026."),
        ("human", "are you sure? verify that against the spec sheet"),
        ("ai", "checked."),
    ])
    out = _run(ec, s)
    assert out["applicable_opportunities"]["EC-09"] == 1
    assert "EC-09" not in out["neuron_firings"]


def test_ec09_final_ai_claim_without_human_response_is_not_applicable():
    s = _session([
        ("human", "how many users?"),
        ("ai", "It supports exactly 10000 users. This is definitely correct."),
    ])
    out = _run(ec, s)
    assert "EC-09" not in out["applicable_opportunities"]


# ── ES (event-triggered) ─────────────────────────────────────────────────────


def test_es_returns_empty_without_ethics_events():
    s = _session([("human", "contact me at a@b.com, please [REDACTED] my name"), ("ai", "ok")])
    out = _run(es, s, events=())
    assert out == {"neuron_firings": {}, "applicable_opportunities": {}, "evidence_turns": {}}


def test_es01_fires_with_ethics_event_and_redaction():
    s = _session([
        ("human", "process this list: john@example.com, +91 98765 43210 — anonymize the personal details first"),
        ("ai", "done"),
    ])
    out = _run(es, s, events=[_ethics_event()])
    assert out["applicable_opportunities"]["ES-01"] == 1
    assert out["neuron_firings"]["ES-01"] == 1.0


def test_es01_pii_without_redaction_reports_zero_of_n():
    s = _session([("human", "email john@example.com and tell him"), ("ai", "ok")])
    out = _run(es, s, events=[_ethics_event()])
    assert out["applicable_opportunities"]["ES-01"] == 1
    assert "ES-01" not in out["neuron_firings"]


def test_all_evidence_indices_point_to_human_turns():
    s = _session([
        ("human", "must include an example: input: 1 output: 2; explain why"),
        ("ai", "As of 2026, it supports exactly 10000 users, definitely."),
        ("human", "ok thanks"),
        ("ai", "noted"),
    ])
    human_indices = {turn.index for turn in s.turns if turn.role == "human"}
    for module in ALL_MODULES.values():
        out = _run(module, s, events=[_ethics_event()])
        for indices in out["evidence_turns"].values():
            assert set(indices) <= human_indices


# ── only contract-table deterministic neurons may ever fire ─────────────────


def test_fired_neurons_are_contract_table_deterministic():
    import yaml
    from pathlib import Path

    table = yaml.safe_load(
        (Path(__file__).resolve().parents[2] / "contracts" / "contract_table.yaml")
        .read_text(encoding="utf-8")
    )
    deterministic = {
        n["id"] for n in table["neurons"] if n["extractor_type"] == "deterministic"
    }
    s = _session([
        ("human", "step by step: are you sure? what about X? format as a table. "
                  "for example: input: 1 output: 2. anonymize john@example.com please."),
        ("ai", "As of 2025 the answer is exactly 42, definitely."),
        ("human", "your training data may be outdated. critique your own answer. "
                  "You didn't mention the edge cases. What about them?"),
        ("ai", "noted"),
    ])
    for module in ALL_MODULES.values():
        out = _run(module, s, events=[_ethics_event()])
        fired = set(out["neuron_firings"]) | set(out["applicable_opportunities"])
        assert fired <= deterministic
