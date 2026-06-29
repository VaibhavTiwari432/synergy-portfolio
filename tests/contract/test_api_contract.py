"""API contract tests (Stage-2 Gates B/D, run from day one): a Tier-1 payload
cannot elicit a Tier-2+ claim through any API path; forbidden words never
appear; auth fails closed; minors never receive a bare composite.
OWNER: Chief Engineer. Judge is faked — no network."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from contracts.schemas import Dimension, Rung
from src.api.main import create_app
from src.api.store import SessionStore
from src.trait.judge.client import JudgeClient

API_KEY = "test-key-123"


def _fake_judge_json() -> str:
    entry = {"score": 0.55, "confidence": 0.7, "evidence_turns": [0], "tom_tag": None}
    data = {d.value: dict(entry) for d in Dimension}
    data["ES"]["score"] = None
    return json.dumps(data)


@pytest.fixture()
def client(monkeypatch) -> TestClient:
    monkeypatch.setenv("SAF_API_KEY", API_KEY)
    # the pipeline builds JudgeClient() — give every instance a fake transport
    monkeypatch.setattr(
        "src.api.pipeline.JudgeClient",
        lambda: JudgeClient(generate=lambda s, u: _fake_judge_json(), fallback=None,
                            sleep=lambda _: None),
    )
    return TestClient(create_app(store=SessionStore(":memory:")))


def _headers() -> dict[str, str]:
    return {"X-API-Key": API_KEY}


def _create_session(client: TestClient, **overrides) -> str:
    body = {
        "payload": "User: explain caching\nAssistant: sure...\nUser: are you sure about TTLs? fix the example",
        **overrides,
    }
    resp = client.post("/v1/sessions", json=body, headers=_headers())
    assert resp.status_code == 200, resp.text
    return resp.json()["session_id"]


# ── auth fails closed ────────────────────────────────────────────────────────


def test_missing_key_is_401(client: TestClient):
    resp = client.post("/v1/sessions", json={"payload": "User: hi"})
    assert resp.status_code == 401


def test_unconfigured_server_is_503(monkeypatch):
    monkeypatch.delenv("SAF_API_KEY", raising=False)
    bare = TestClient(create_app(store=SessionStore(":memory:")))
    resp = bare.post("/v1/sessions", json={"payload": "User: hi"},
                     headers={"X-API-Key": "anything"})
    assert resp.status_code == 503


def test_health_and_contracts_are_open(client: TestClient):
    # health is liveness ("status") + a db readiness field (Track 4); no auth
    health = client.get("/v1/health").json()
    assert health["status"] == "ok"
    assert health["db"] in ("ok", "unavailable")
    contracts = client.get("/v1/contracts").json()
    assert contracts["judge_prompt_version"] == "v2.2"


# ── POST → GET score end-to-end (Gate D shape) ───────────────────────────────


def test_post_then_score_returns_full_response(client: TestClient):
    session_id = _create_session(client)
    resp = client.get(f"/v1/sessions/{session_id}/score", headers=_headers())
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["tier"] == 1
    assert set(body["profile"].keys()) == {d.value for d in Dimension}
    assert body["profile"]["ES"]["status"] == "N/A"  # no ethics events
    assert body["composite"]["rung"] == "MEASURABLE"
    assert body["sustainability"]["lambda"]["value"] is None
    assert body["sustainability"]["debt_ewma"]["mode"] == "INSUFFICIENT_HISTORY"
    assert "report" in body and body["report"]["tier_caveat"]


def test_unknown_session_is_404(client: TestClient):
    resp = client.get("/v1/sessions/nope/score", headers=_headers())
    assert resp.status_code == 404


# ── the claims charter, end to end ───────────────────────────────────────────


def test_tier1_payload_cannot_elicit_above_measurable(client: TestClient):
    session_id = _create_session(client)
    body = client.get(f"/v1/sessions/{session_id}/score", headers=_headers()).json()

    rungs = [body["composite"]["rung"], body["report"]["rung"],
             body["state_validity"]["rung"], body["flags"]["rung"],
             body["regime_overlay"]["rung"],
             body["sustainability"]["s_human_hat"]["rung"],
             body["sustainability"]["debt_ewma"]["rung"],
             body["sustainability"]["lambda"]["rung"],
             *(d["rung"] for d in body["profile"].values())]
    assert Rung.VALIDATED.value not in rungs


def test_forbidden_words_absent_from_entire_tier1_response(client: TestClient):
    session_id = _create_session(client)
    raw = client.get(f"/v1/sessions/{session_id}/score", headers=_headers()).text.lower()
    report = json.loads(raw)["report"]
    report_text = " ".join(
        [*report["observed"], *report["inferred"], *report["hypothesized"],
         report["tier_caveat"]]
    ).lower()
    for word in ("synergy", "surrender", "dependent"):
        assert word not in report_text
    # and the overlay labels cannot carry it structurally
    assert "surrender" not in json.dumps(json.loads(raw)["regime_overlay"]).lower()


def test_minor_gets_no_bare_composite(client: TestClient):
    session_id = _create_session(client, is_minor=True)
    body = client.get(f"/v1/sessions/{session_id}/score", headers=_headers()).json()
    assert body["composite"]["value"] is None
    assert body["composite"]["status"] == "N/A"
    assert body["sustainability"]["debt_ewma"]["value"] is None


# ── trajectory ───────────────────────────────────────────────────────────────


def test_trajectory_insufficient_history_on_one_session(client: TestClient):
    session_id = _create_session(client, user_ref="u-1")
    client.get(f"/v1/sessions/{session_id}/score", headers=_headers())
    resp = client.get("/v1/users/u-1/trajectory", headers=_headers())
    assert resp.json()["status"] == "INSUFFICIENT_HISTORY"


def test_trajectory_with_two_sessions(client: TestClient):
    for _ in range(2):
        sid = _create_session(client, user_ref="u-2")
        client.get(f"/v1/sessions/{sid}/score", headers=_headers())
    body = client.get("/v1/users/u-2/trajectory", headers=_headers()).json()
    assert body["status"] == "ok"
    assert len(body["composite_history"]) == 2
    assert "debt_ewma" in body
