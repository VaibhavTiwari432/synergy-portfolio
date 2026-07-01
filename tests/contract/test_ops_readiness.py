"""Audit Track 4 — ops readiness (no DB; runs in CI).

Proves the health endpoint reports liveness + a db readiness field, and the
fail-loud env validator reports missing required vars.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from src.api.main import create_app
from src.api.store import SessionStore
from src.startup_checks import check_any_env, check_env


def test_health_reports_status_and_db_readiness():
    client = TestClient(create_app(store=SessionStore(":memory:")))
    r = client.get("/v1/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["db"] in ("ok", "unavailable")  # readiness field present
    assert body["scoring"] in ("ok", "missing_judge_key")


def test_check_env_flags_missing_required(monkeypatch):
    monkeypatch.delenv("SAF_NONEXISTENT_REQUIRED_XYZ", raising=False)
    missing = check_env(component="test", required=["SAF_NONEXISTENT_REQUIRED_XYZ"])
    assert missing == ["SAF_NONEXISTENT_REQUIRED_XYZ"]

    monkeypatch.setenv("SAF_NONEXISTENT_REQUIRED_XYZ", "present")
    assert check_env(component="test", required=["SAF_NONEXISTENT_REQUIRED_XYZ"]) == []


def test_check_env_no_required_is_clean():
    assert check_env(component="test", required=[], optional=["DEFINITELY_UNSET_OPT"]) == []


def test_check_any_env_requires_one_provider(monkeypatch):
    monkeypatch.delenv("SAF_PROVIDER_A", raising=False)
    monkeypatch.delenv("SAF_PROVIDER_B", raising=False)
    assert check_any_env(
        component="test",
        names=["SAF_PROVIDER_A", "SAF_PROVIDER_B"],
        purpose="test provider",
    ) is False

    monkeypatch.setenv("SAF_PROVIDER_B", "present")
    assert check_any_env(
        component="test",
        names=["SAF_PROVIDER_A", "SAF_PROVIDER_B"],
        purpose="test provider",
    ) is True


def test_extension_preflight_allows_api_key_header():
    client = TestClient(create_app(store=SessionStore(":memory:")))
    r = client.options(
        "/v1/users/saf-smoke/chats",
        headers={
            "Origin": "https://chatgpt.com",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "X-API-Key",
        },
    )
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == "https://chatgpt.com"
    assert "X-API-Key" in r.headers["access-control-allow-headers"]


def test_chrome_extension_cors_is_not_wildcard_by_default(monkeypatch):
    monkeypatch.delenv("SAF_EXTENSION_ORIGIN_REGEX", raising=False)
    client = TestClient(create_app(store=SessionStore(":memory:")))
    r = client.options(
        "/v1/users/saf-smoke/chats",
        headers={
            "Origin": "chrome-extension://abcdefghijklmnopabcdefghijklmnop",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "X-API-Key",
        },
    )
    assert r.status_code == 400
    assert "access-control-allow-origin" not in r.headers


def test_chrome_extension_cors_can_be_configured(monkeypatch):
    monkeypatch.setenv(
        "SAF_EXTENSION_ORIGIN_REGEX",
        r"chrome-extension://abcdefghijklmnopabcdefghijklmnop",
    )
    client = TestClient(create_app(store=SessionStore(":memory:")))
    r = client.options(
        "/v1/users/saf-smoke/chats",
        headers={
            "Origin": "chrome-extension://abcdefghijklmnopabcdefghijklmnop",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "X-API-Key",
        },
    )
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == "chrome-extension://abcdefghijklmnopabcdefghijklmnop"
