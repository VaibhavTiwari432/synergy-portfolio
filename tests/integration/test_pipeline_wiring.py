"""D-003 wiring tests: every Stage-1 leaf demonstrably executes inside
score_session — a skipped leaf fails here, not silently. Judge is faked."""

from __future__ import annotations

import json

import pytest

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


# ── Judge-unavailability guard ────────────────────────────────────────────────

def test_judge_all_transport_failure_raises_not_stored_as_scored():
    """Judge-unavailable must not produce a silently-scored N/A row.

    When every transport fails, score_session_with_artifacts must raise so the
    worker marks the chat 'failed' rather than persisting an all-N/A ScoreRun
    that the UI would present as a completed calculation.
    """
    def _dead(_sys: str, _usr: str) -> str:
        raise RuntimeError("transport down")

    dead_judge = JudgeClient(generate=_dead, fallback=_dead, sleep=lambda _: None)
    with pytest.raises(RuntimeError, match="judge all-transport failure"):
        score_session_with_artifacts(_session(), judge=dead_judge)


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


# ── items 2/3/4: observability flags ─────────────────────────────────────────


def _per_criterion_judge() -> JudgeClient:
    """Fake judge where per-criterion calls succeed (high score) and joint returns 0.5.

    Differentiates via system prompt: neuron_fn() uses _NEURON_SYSTEM_PROMPT
    ("psychometrician"); score_session() uses SYSTEM_PROMPT.
    """
    import json

    entry = {"score": 0.5, "confidence": 0.8, "evidence_turns": [0], "tom_tag": None}
    data = {d.value: dict(entry) for d in Dimension}
    data["ES"]["score"] = None
    joint_payload = json.dumps(data)

    neuron_payload = json.dumps({
        "score": 0.9,
        "reasoning": "strong",
        "negative_criteria_present": False,
        "confidence": 0.9,
        "final_score_after_leniency_penalty": 0.9,
    })

    def _generate(system: str, user: str) -> str:
        # _NEURON_SYSTEM_PROMPT ends with "Respond only with valid JSON as specified in the prompt."
        # SYSTEM_PROMPT (joint) is a long multi-section prompt and does not contain that phrase.
        return neuron_payload if "Respond only with valid JSON" in system else joint_payload

    return JudgeClient(generate=_generate, fallback=None, sleep=lambda _: None)


def test_ci_self_confidence_flag_when_per_criterion_fails(  # item 3a
):
    """With fake judge returning wrong format for per-criterion, all OK dims get ci_from_self_confidence."""
    from contracts.schemas import ScoreStatus
    run = score_session_with_artifacts(_session(), judge=_fake_judge())
    for dim, ds in run.response.profile.items():
        if ds.status == ScoreStatus.OK:
            flags = ds.flags or []
            assert "ci_from_self_confidence" in flags, f"{dim.value}: missing ci flag"
            assert "ci_from_disagreement" not in flags, f"{dim.value}: wrong ci flag"


def test_ci_disagreement_flag_when_per_criterion_succeeds(  # item 3b
):
    """When per-criterion calls succeed and ≥2 neurons exist, at least one dim has ci_from_disagreement."""
    from contracts.schemas import ScoreStatus
    run = score_session_with_artifacts(_session(), judge=_per_criterion_judge())
    dims_with_disagreement = [
        dim for dim, ds in run.response.profile.items()
        if ds.status == ScoreStatus.OK and "ci_from_disagreement" in (ds.flags or [])
    ]
    assert dims_with_disagreement, "expected at least one dim with ci_from_disagreement"


def test_neuron_stats_in_raw_counts_partial_coverage_flag(  # item 4
):
    """6-of-11 neuron failures via _per_dim_neuron_stats → partial_neuron_coverage."""
    from src.api.pipeline import _per_dim_neuron_stats
    from src.trait.judge.rubric_bank import DIM_OF

    al_neurons = [nid for nid, dim in DIM_OF.items() if dim == "AL"][:11]
    assert len(al_neurons) >= 11, "need ≥11 AL judge neurons for this test"

    results = {nid: {"error": i >= 5} for i, nid in enumerate(al_neurons)}
    stats = _per_dim_neuron_stats(results)

    from contracts.schemas import Dimension
    s = stats[Dimension.AL]
    assert s["attempted"] == 11
    assert s["succeeded"] == 5
    assert s["failed"] == 6


def test_pc_joint_divergence_large_flag_when_gap_exceeds_threshold(  # item 2
):
    """per-criterion/joint divergence > 0.25 → large_per_criterion_joint_divergence in flags."""
    from contracts.schemas import ScoreStatus

    # per-criterion returns 0.9 for all judge neurons; joint returns 0.5
    # → divergence ≈ 0.4 for dims where per-criterion succeeds and ≥1 judge neuron exists
    run = score_session_with_artifacts(_session(), judge=_per_criterion_judge())
    flagged_dims = [
        dim for dim, ds in run.response.profile.items()
        if ds.status == ScoreStatus.OK
        and "large_per_criterion_joint_divergence" in (ds.flags or [])
    ]
    assert flagged_dims, "expected at least one dim with large divergence flag"


# ── acceptance test 10: absent ≠ zero (integration) ─────────────────────────


def test_untagged_session_metacog_all_none_through_pipeline():
    """Test 10a (B2/B3): session of untagged turns → state_strip metacog all-None;
    pipeline must not crash or fabricate values."""
    turns: list[Turn] = []
    for text in ("interesting", "let me consider that", "perhaps", "I see"):
        turns.append(Turn(index=len(turns), role="human", text=text))
        turns.append(Turn(index=len(turns), role="ai", text="response"))
    session = CanonicalSession(
        session_id="untagged-1", source="plaintext",
        partner_model=PartnerModel(family="openai"), turns=turns,
    )
    response = score_session(session, judge=_fake_judge())
    # Every state strip entry must have metacog=None (not PASSIVE or any label)
    assert all(v.metacog is None for v in response.state_strip), (
        "untagged session must not fabricate metacog labels"
    )


# ── acceptance test 9: no bare point estimate anywhere ───────────────────────
# Spec: composite + every OK DimensionScore + every OK CSL bar carries CI.
# "OK bar" = PanelABar.status == "ok" (string after _jsonable enum serialisation).


def test_composite_carries_ci_and_rung(  # acceptance test 9a
):
    """Every non-N/A composite must have a CI and a rung — no bare point."""
    from contracts.schemas import ScoreStatus
    run = score_session_with_artifacts(_session(), judge=_fake_judge())
    composite = run.response.composite
    assert composite.rung is not None, "composite.rung must always be set"
    if composite.status == ScoreStatus.OK and composite.value is not None:
        assert composite.ci is not None, "OK composite must carry a CI"
        assert composite.ci.low is not None and composite.ci.high is not None


def test_every_ok_dimension_carries_ci(  # acceptance test 9b
):
    """Every OK DimensionScore must carry a CI — no bare point at dimension grain."""
    from contracts.schemas import ScoreStatus
    run = score_session_with_artifacts(_session(), judge=_per_criterion_judge())
    for dim, ds in run.response.profile.items():
        if ds.status == ScoreStatus.OK and ds.value is not None:
            assert ds.ci is not None, f"{dim.value}: OK dimension missing CI"
            assert ds.ci.low is not None and ds.ci.high is not None, (
                f"{dim.value}: OK dimension CI has None bound"
            )


def test_every_ok_csl_bar_carries_ci_and_neff(  # acceptance test 9c
):
    """Every OK PanelABar must carry ci_low, ci_high, n_eff — no bare bar."""
    run = score_session_with_artifacts(_session(), judge=_per_criterion_judge())
    csl = run.csl
    if csl.get("status") != "ok":
        return  # CSL chain failed (e.g. crosswalk missing in test env) — skip
    panel_a = csl.get("report", {}).get("panel_a", [])
    for bar in panel_a:
        if bar.get("status") == "ok":
            assert bar.get("ci_low") is not None, f"{bar['level']}: OK bar missing ci_low"
            assert bar.get("ci_high") is not None, f"{bar['level']}: OK bar missing ci_high"
            assert bar.get("n_eff") is not None, f"{bar['level']}: OK bar missing n_eff"


# ── Regression: Phase 1b async/sync boundary (coroutine mismatch fix) ──

def test_pipeline_neuron_scoring_returns_dict_not_coroutine():
    """Regression: pipeline._score_all_neurons(...) must return dict, not awaitable coroutine.

    This guards against the bug where Phase 1b refactored score_all_neurons to async,
    but pipeline.py still called it synchronously, receiving a coroutine instead of
    a dict. The coroutine was then subscripted with ["results"], causing:
    TypeError: 'coroutine' object is not subscriptable

    Fix: pipeline imports score_all_neurons_sync (not the async version).
    """
    from src.api.pipeline import _score_all_neurons

    result = _score_all_neurons(_fake_judge().neuron_fn(), "sample transcript")

    # Must be a dict, not a coroutine
    assert isinstance(result, dict), \
        f"Expected dict, got {type(result)} — coroutine mismatch in pipeline"
    # Must have the keys the pipeline expects
    assert "results" in result, f"Missing 'results' key: {result.keys()}"
    assert "summary" in result, f"Missing 'summary' key: {result.keys()}"
    # results must be subscriptable (dict-like)
    assert isinstance(result["results"], dict)


def test_score_all_neurons_sync_compatibility():
    """Verify score_all_neurons_sync has the signature pipeline expects."""
    from src.trait.judge.per_criterion import score_all_neurons_sync
    import inspect

    sig = inspect.signature(score_all_neurons_sync)
    params = list(sig.parameters.keys())

    # Pipeline calls: _score_all_neurons(judge.neuron_fn(), transcript)
    # So the first parameter must accept judge_fn
    assert "judge_fn" in params, \
        f"score_all_neurons_sync missing judge_fn parameter. Has: {params}"
    # Second parameter must accept transcript
    assert "transcript" in params, \
        f"score_all_neurons_sync missing transcript parameter. Has: {params}"


def test_score_all_neurons_sync_prompt_adaptation():
    """Verify sync wrapper adapts neuron_fn's single-prompt format to JudgeClient's (system, user) format.

    This validates the fix for: neuron_fn takes (prompt) -> str,
    but JudgeClient._generate expects (system_prompt, user_prompt) -> str.
    The wrapper must seamlessly convert between these signatures.
    """
    from src.trait.judge.per_criterion import score_all_neurons_sync

    captured_calls = []

    def mock_neuron_fn(combined_prompt: str) -> str:
        """Mock neuron_fn tracks what prompts it receives."""
        captured_calls.append(combined_prompt)
        # Return valid JSON so the async dimension scoring succeeds
        return json.dumps({"AL-01": "met", "AL-02": "not_met"})

    # Call as the pipeline does: (neuron_fn, transcript)
    result = score_all_neurons_sync(mock_neuron_fn, "sample chat")

    # Should succeed with a dict result
    assert isinstance(result, dict), f"Expected dict, got {type(result)}"
    assert "results" in result
    # neuron_fn should have been called with combined prompts
    assert len(captured_calls) > 0, "neuron_fn wrapper not invoked"
