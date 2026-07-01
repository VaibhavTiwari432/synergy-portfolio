from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from src.api.main import create_app
from src.api.routers import projects, users

API_KEY = "test-key-123"


@pytest.fixture()
def client(monkeypatch) -> TestClient:
    monkeypatch.setenv("SAF_API_KEY", API_KEY)
    app = create_app()
    app.dependency_overrides[users._require_pool] = lambda: object()
    app.dependency_overrides[projects._require_pool] = lambda: object()
    return TestClient(app, raise_server_exceptions=False)


def _headers(extra: dict[str, str] | None = None) -> dict[str, str]:
    return {"X-API-Key": API_KEY, **(extra or {})}


def test_feedback_rejects_invalid_match_rating(client: TestClient):
    resp = client.post(
        f"/v1/users/u/chats/{uuid.uuid4()}/feedback",
        json={"match_rating": "maybe"},
        headers=_headers(),
    )
    assert resp.status_code == 422


@pytest.mark.parametrize(
    "body",
    [
        {"match_rating": "yes", "turn_index": -1},
        {"match_rating": "partial", "comment": "x" * 281},
        {"match_rating": "yes", "dimension_scores": {"UNKNOWN": 0.5}},
        {"match_rating": "yes", "dimension_scores": {"EC": -0.1}},
    ],
)
def test_feedback_rejects_malformed_body_fields(client: TestClient, body: dict):
    resp = client.post(
        f"/v1/users/u/chats/{uuid.uuid4()}/feedback",
        json=body,
        headers=_headers(),
    )
    assert resp.status_code == 422


@pytest.mark.parametrize(
    "body",
    [
        {"name": ""},
        {"name": "   "},
        {"name": "x" * 121},
    ],
)
def test_create_project_rejects_invalid_name(client: TestClient, body: dict):
    resp = client.post("/v1/users/u/projects", json=body, headers=_headers())
    assert resp.status_code == 422


def test_update_project_requires_if_match(client: TestClient):
    resp = client.patch(
        f"/v1/users/u/projects/{uuid.uuid4()}",
        json={"name": "renamed"},
        headers=_headers(),
    )
    assert resp.status_code == 428


def test_update_project_rejects_bad_if_match(client: TestClient):
    resp = client.patch(
        f"/v1/users/u/projects/{uuid.uuid4()}",
        json={"name": "renamed"},
        headers=_headers({"If-Match": "not-a-version"}),
    )
    assert resp.status_code == 422
