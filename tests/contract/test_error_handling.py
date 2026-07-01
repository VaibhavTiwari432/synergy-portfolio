"""Audit Track 2 — safe error handling (no DB; runs in CI).

Proves the observability layer: unhandled exceptions become a generic 500 (no
traceback / internal detail in the body) with a correlation request id; a
DB-connection failure at request time becomes a 503, not a 500; every response
carries X-Request-ID and a client-supplied id is echoed.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from src.api.main import create_app
from src.api.observability import _is_db_unavailable
from src.api.store import SessionStore


def _client() -> TestClient:
    app = create_app(store=SessionStore(":memory:"))

    async def _boom():
        raise ValueError("INTERNAL detail that must never reach the client")

    async def _db_down():
        raise ConnectionError("postgres connection lost mid-request")

    app.add_api_route("/_test/boom", _boom, methods=["GET"])
    app.add_api_route("/_test/dbdown", _db_down, methods=["GET"])
    # raise_server_exceptions=False → return the handler's 500 instead of re-raising
    return TestClient(app, raise_server_exceptions=False)


def test_unhandled_exception_is_generic_500_with_request_id():
    client = _client()
    r = client.get("/_test/boom")
    assert r.status_code == 500
    body = r.json()
    assert body["error"] == "internal_server_error"
    assert body["request_id"]
    assert r.headers.get("X-Request-ID")
    # no internal leakage: message / type / traceback never in the body
    assert "INTERNAL detail" not in r.text
    assert "ValueError" not in r.text
    assert "Traceback" not in r.text


def test_db_connection_failure_maps_to_503_not_500():
    client = _client()
    r = client.get("/_test/dbdown")
    assert r.status_code == 503
    assert r.json()["error"] == "database_unavailable"
    assert r.headers.get("X-Request-ID")


def test_request_id_present_on_success_and_client_value_echoed():
    client = _client()
    r = client.get("/v1/health")
    assert r.status_code == 200 and r.headers.get("X-Request-ID")
    r2 = client.get("/v1/health", headers={"X-Request-ID": "trace-abc-123"})
    assert r2.headers.get("X-Request-ID") == "trace-abc-123"


def test_db_unavailable_detector_matches_asyncpg_connection_errors():
    # name/module-based detection without importing asyncpg (CI-minimal safe)
    class ConnectionDoesNotExistError(Exception):
        pass
    ConnectionDoesNotExistError.__module__ = "asyncpg.exceptions"

    class SomeLogicError(Exception):
        pass
    SomeLogicError.__module__ = "src.worker.scorer"

    assert _is_db_unavailable(ConnectionDoesNotExistError("gone")) is True
    assert _is_db_unavailable(ConnectionError("gone")) is True
    assert _is_db_unavailable(OSError("socket")) is True
    assert _is_db_unavailable(SomeLogicError("bug")) is False
    assert _is_db_unavailable(ValueError("bug")) is False
