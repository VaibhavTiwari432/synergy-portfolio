"""Audit Track 4 — ops readiness (no DB; runs in CI).

Proves the health endpoint reports liveness + a db readiness field, and the
fail-loud env validator reports missing required vars.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from src.api.main import create_app
from src.api.store import SessionStore
from src.startup_checks import check_env


def test_health_reports_status_and_db_readiness():
    client = TestClient(create_app(store=SessionStore(":memory:")))
    r = client.get("/v1/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["db"] in ("ok", "unavailable")  # readiness field present


def test_check_env_flags_missing_required(monkeypatch):
    monkeypatch.delenv("SAF_NONEXISTENT_REQUIRED_XYZ", raising=False)
    missing = check_env(component="test", required=["SAF_NONEXISTENT_REQUIRED_XYZ"])
    assert missing == ["SAF_NONEXISTENT_REQUIRED_XYZ"]

    monkeypatch.setenv("SAF_NONEXISTENT_REQUIRED_XYZ", "present")
    assert check_env(component="test", required=["SAF_NONEXISTENT_REQUIRED_XYZ"]) == []


def test_check_env_no_required_is_clean():
    assert check_env(component="test", required=[], optional=["DEFINITELY_UNSET_OPT"]) == []
