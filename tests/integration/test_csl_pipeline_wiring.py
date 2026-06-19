"""CSL pipeline wiring: the CSL chain runs as a ScoreRun artifact, the frozen
ScoreResponse contract is untouched, emergence is dormant, and a CSL failure is
isolated from the ARI score."""

from __future__ import annotations

import json

import pytest

from contracts.schemas import CanonicalSession, Dimension, PartnerModel, Turn
from src.api import pipeline as pipeline_mod
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
        "walk me through it step by step, must include the cost analysis",
        "are you sure that's correct? you said 100 but the docs say 60 — fix it",
        "ok",
        "continue",
        "sounds good",
    ]
    turns: list[Turn] = []
    for t in texts:
        turns.append(Turn(index=len(turns), role="human", text=t))
        turns.append(Turn(index=len(turns), role="ai", text="a long enough ai reply here"))
    return CanonicalSession(
        session_id="csl-wire-1", source="plaintext",
        partner_model=PartnerModel(family="openai"), turns=turns,
    )


def test_csl_artifact_present_after_scored_session():
    run = score_session_with_artifacts(_session(), judge=_fake_judge())

    assert run.csl, "CSL artifact must be attached to ScoreRun"
    assert run.csl["status"] == "ok"
    # the three CSL surfaces are present
    assert "report" in run.csl
    assert "ownership" in run.csl
    assert "emergence" in run.csl
    # ownership is a 7-level vector (never a session scalar)
    assert set(run.csl["ownership"]) == {"C1", "C2", "C3", "C4", "C5", "C6", "C7"}
    # report carries the three panels
    report = run.csl["report"]
    assert len(report["panel_a"]) == 7
    assert len(report["panel_c"]) == 7
    assert "panel_b" in report


def test_score_response_contract_untouched_by_csl_wiring():
    """The frozen ScoreResponse carries no CSL and round-trips against its own
    schema unchanged — the contract surface (fields, 8 dimensions) is intact."""
    from contracts.schemas import ScoreResponse

    response = score_session(_session(), judge=_fake_judge())
    dumped = response.model_dump(mode="json")

    # CSL never leaks into the ARI contract
    assert "csl" not in dumped
    # exactly the 8 frozen dimensions, nothing added/removed
    assert set(dumped["profile"]) == {d.value for d in Dimension}
    # the response round-trips against the frozen schema byte-for-byte
    assert ScoreResponse(**dumped).model_dump(mode="json") == dumped


def test_score_response_fields_unchanged_field_set():
    # the ScoreResponse field set is exactly the frozen contract — no csl field.
    from contracts.schemas import ScoreResponse
    assert "csl" not in ScoreResponse.model_fields


def test_emergence_ribbon_empty_not_error_with_abstaining_confirmer():
    run = score_session_with_artifacts(_session(), judge=_fake_judge())
    csl = run.csl
    assert csl["status"] == "ok"
    # dormant judge → zero reportable emergence events, but a valid ribbon
    assert csl["emergence"]["reportable_count"] == 0
    assert csl["emergence"]["events"] == []
    ribbon = csl["report"]["panel_b"]
    assert ribbon["count"] == 0
    assert "This session contained 0 emergence events" in ribbon["caveat"]


def test_csl_failure_is_isolated_from_ari_score(monkeypatch):
    # force the CSL chain to blow up; the ARI score must still be produced.
    def _boom(*a, **k):
        raise RuntimeError("synthetic CSL failure")

    monkeypatch.setattr(pipeline_mod, "build_csl_report", _boom)

    run = score_session_with_artifacts(_session(), judge=_fake_judge())

    # ARI score is intact
    assert run.response is not None
    assert set(run.response.profile) == set(Dimension)
    # CSL artifact records the failure instead of propagating it
    assert run.csl["status"] == "error"
    assert "synthetic CSL failure" in run.csl["error"]


def test_csl_failure_before_score_response_still_scores(monkeypatch):
    # even if the very first CSL step fails, the ARI path is unaffected.
    def _boom(*a, **k):
        raise ValueError("crosswalk load failure")

    monkeypatch.setattr(pipeline_mod, "load_acf_crosswalk", _boom)
    run = score_session_with_artifacts(_session(), judge=_fake_judge())

    assert run.response is not None
    assert run.csl["status"] == "error"
    assert "crosswalk load failure" in run.csl["error"]


def test_csl_artifact_is_json_serializable():
    run = score_session_with_artifacts(_session(), judge=_fake_judge())
    # the artifact must round-trip through JSON (it is persisted by the worker)
    json.dumps(run.csl)
