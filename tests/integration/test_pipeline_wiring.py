"""D-003 wiring tests: every Stage-1 leaf demonstrably executes inside
score_session — a skipped leaf fails here, not silently. Judge is faked."""

from __future__ import annotations

import json

from contracts.schemas import (
    CanonicalSession,
    Dimension,
    EventType,
    LoadLabel,
    PartnerModel,
    RegimeLabel,
    Turn,
)
from src.api.pipeline import score_session, score_session_with_artifacts
from src.trait.judge.client import JudgeClient


def _fake_judge() -> JudgeClient:
    entry = {"score": 0.5, "confidence": 0.8, "evidence_turns": [0], "tom_tag": None}
    data = {d.value: dict(entry) for d in Dimension}
    data["ES"]["score"] = None
    payload = json.dumps(data)
    return JudgeClient(generate=lambda s, u: payload, fallback=None, sleep=lambda _: None)


def _session() -> CanonicalSession:
    texts = [
        "walk me through it step by step, must include the cost analysis",  # SCAFFOLD → PR fires
        "are you sure that's correct? you said 100 but the docs say 60 — fix it",  # VERIFY
        "ok",
        "continue",
        "sounds good",
    ]
    turns: list[Turn] = []
    for t in texts:
        turns.append(Turn(index=len(turns), role="human", text=t))
        turns.append(Turn(index=len(turns), role="ai", text="a long enough ai reply here"))
    return CanonicalSession(
        session_id="wire-1", source="plaintext",
        partner_model=PartnerModel(family="openai"), turns=turns,
    )


def test_every_leaf_contributes_to_the_response():
    response = score_session(_session(), judge=_fake_judge())

    # tagger + overlay (rules over tags): accept-run of 3 must appear
    assert RegimeLabel.ACCEPT_RUN in response.regime_overlay.strip
    assert RegimeLabel.VERIFICATION in response.regime_overlay.strip

    # transitions: accept_run metrics flow into flags
    assert response.flags.accept_run_max == 3

    # state classifiers: strip is populated with real labels, full confidence
    assert len(response.state_strip) == 5
    assert all(v.confidence == 1.0 for v in response.state_strip)
    assert all(v.load in set(LoadLabel) for v in response.state_strip)
    # metacog leaf: 3 flat accepts = surrender → state validity gate fires
    assert response.state_validity.surrender_detected is True

    # extractors: deterministic firings became raw_counts evidence (PR fired)
    assert response.profile[Dimension.PR].raw_counts.get("neuron_opportunities", 0) > 0


def test_extractor_firings_are_logged_as_nfire_events():
    # the log is internal; prove it via the reaction signatures' event counts —
    # N-FIRE events are not triggers, so pi rows stay gated at n_events=0
    response = score_session(_session(), judge=_fake_judge())
    for row in response.reaction_signatures.pi.values():
        for cell in row.values():
            assert cell.n_events == 0  # only N-FIRE in the log; triggers come later


# ── Track 1: the artifacts a score can't regenerate after the transcript purges ──

def test_score_run_carries_neuron_firings_with_absent_not_zero_semantics():
    run = score_session_with_artifacts(_session(), judge=_fake_judge())

    assert run.neuron_firings, "deterministic firings must be persisted, not discarded"
    by_code = {r["neuron_code"]: r for r in run.neuron_firings}

    # every row is a real evaluation: fired (>0) or observed-0-of-N (==0.0),
    # NEVER a fabricated value for an absent neuron (non-negotiable #12).
    for r in run.neuron_firings:
        assert r["dimension"] is not None
        assert r["extractor_version"]
        # a row only exists when there was an opportunity OR it fired
        assert r["value"] is not None
        if r["value"] == 0.0:
            assert r["applicable_opportunities"] > 0  # observed 0-of-N, not N/A
        assert isinstance(r["evidence_turn_indices"], list)

    # PR fired on the SCAFFOLD turn → a positive-value PR row with evidence
    pr_rows = [r for r in run.neuron_firings if r["dimension"] == Dimension.PR.value]
    assert pr_rows, "PR scaffold prompt must produce at least one firing row"
    assert any(r["value"] and r["value"] > 0.0 for r in pr_rows)


def test_score_run_carries_event_log_for_reaction_recompute():
    run = score_session_with_artifacts(_session(), judge=_fake_judge())
    assert run.event_log, "event log must be persisted so reactions can be recomputed"
    # N-FIRE events for the deterministic firings are present in the log
    assert any(ev.get("event_type") == EventType.N_FIRE.value for ev in run.event_log)


def test_score_run_carries_judge_audit_trail():
    run = score_session_with_artifacts(_session(), judge=_fake_judge())
    jr = run.judge_run
    # literal judge output retained for audit, plus model identity + per-dim conf
    assert jr["raw_response"]
    assert jr["judge_model_id"]
    assert jr["judge_unavailable"] is False
    assert set(jr["per_dimension_confidence"]) == {d.value for d in Dimension}


def test_score_run_stamps_full_provenance():
    run = score_session_with_artifacts(_session(), judge=_fake_judge())
    prov = run.provenance
    # all six instrument-identity keys present so a score is reproducible
    assert set(prov) >= {
        "framework_version",
        "schema_version",
        "contract_table_version",
        "code_git_sha",
        "judge_model_id",
        "judge_model_version",
    }
    assert prov["framework_version"] and prov["schema_version"]
    assert prov["judge_model_id"]  # carries the judge model the score depends on


# ── Track 2: per-turn state strip + per-turn precision π_t, computed now ──

def test_score_run_carries_per_turn_state_with_precision():
    run = score_session_with_artifacts(_session(), judge=_fake_judge())

    # one row per human turn (5 human turns in _session)
    assert len(run.turn_state) == 5
    human_indices = [t.index for t in _session().turns if t.role == "human"]
    assert [r["turn_index"] for r in run.turn_state] == human_indices

    for r in run.turn_state:
        assert isinstance(r["cascade_flags"], list)
        # this session has assessable state on every turn → π_t is real, in (0, 1]
        assert r["precision"] is not None
        assert 0.0 < r["precision"] <= 1.0


def test_surrendered_turns_have_lower_precision_than_active_turns():
    # _session ends in a 3-accept run → SURRENDER on the later turns. A turn whose
    # own state is degraded must carry strictly lower precision than an undegraded
    # turn (per-turn π mirrors the session widening, not a session-flat scalar).
    run = score_session_with_artifacts(_session(), judge=_fake_judge())
    by_turn = {r["turn_index"]: r for r in run.turn_state}

    surrendered = [r for r in run.turn_state if r["metacog"] == "SURRENDER"]
    active = [r for r in run.turn_state if r["metacog"] == "ACTIVE"]
    assert surrendered and active, "fixture must produce both modes"
    assert "surrender" in surrendered[0]["cascade_flags"]
    assert max(r["precision"] for r in surrendered) < min(r["precision"] for r in active)


# ── E1: determinism — same input → identical output ──────────────────────────


def test_deterministic_layers_are_bit_identical():
    """E1: tag/phase/extractor/normalize/state layers produce identical output
    across two calls with the same session and same (fake) judge."""
    s = _session()
    run1 = score_session_with_artifacts(s, judge=_fake_judge())
    run2 = score_session_with_artifacts(s, judge=_fake_judge())
    assert run1.response.profile == run2.response.profile
    assert run1.response.composite == run2.response.composite
    assert run1.turn_state == run2.turn_state
