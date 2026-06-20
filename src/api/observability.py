"""
src/api/observability.py — request IDs + safe error handling. OWNER: CE.

Audit Track 2. Three guarantees:
  - Every request carries an X-Request-ID (generated if the client didn't send
    one); it is echoed on the response and stamped into error logs for
    correlation.
  - An unhandled exception returns a GENERIC 500 — `{"error":
    "internal_server_error", "request_id": ...}` — and the full traceback goes
    to the server log ONLY, never the response body (no internal leakage).
  - A lost/unreachable Postgres connection AT REQUEST TIME maps to 503
    ("database_unavailable"), not a 500, so ops can tell "DB down" from "bug".

HTTPException (401/404/422/503 from routes) is handled by FastAPI's own handler
and is unaffected — only truly unhandled exceptions hit the handler here.
"""

from __future__ import annotations

import logging
import uuid

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from src.logging_config import request_id_var

log = logging.getLogger("saf.api")


def _is_db_unavailable(exc: BaseException) -> bool:
    """True when the exception means Postgres is unreachable (→ 503), as opposed
    to a logic/programming error (→ 500). Detected without a hard asyncpg import
    so this module stays importable in the minimal CI env."""
    if isinstance(exc, (ConnectionError, OSError, TimeoutError)):
        return True
    module = (type(exc).__module__ or "")
    name = type(exc).__name__
    if module.startswith("asyncpg") or module.startswith("postgres"):
        return any(
            token in name
            for token in (
                "ConnectionDoesNotExist",
                "CannotConnectNow",
                "ConnectionFailure",
                "InterfaceError",
                "TooManyConnections",
                "PostgresConnectionError",
                "ConnectionRejection",
            )
        )
    return False


def install_observability(app: FastAPI) -> None:
    @app.middleware("http")
    async def _request_id_mw(request: Request, call_next):
        rid = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        request.state.request_id = rid
        token = request_id_var.set(rid)  # correlate every log line for this request
        try:
            response = await call_next(request)
        finally:
            request_id_var.reset(token)
        response.headers["X-Request-ID"] = rid
        return response

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        rid = getattr(request.state, "request_id", None) or uuid.uuid4().hex
        if _is_db_unavailable(exc):
            log.warning("db_unavailable rid=%s %s: %s", rid, type(exc).__name__, exc)
            return JSONResponse(
                status_code=503,
                headers={"X-Request-ID": rid},
                content={"error": "database_unavailable", "request_id": rid},
            )
        # full traceback to the LOG only — never the response body
        log.error("unhandled_error rid=%s", rid, exc_info=exc)
        return JSONResponse(
            status_code=500,
            headers={"X-Request-ID": rid},
            content={"error": "internal_server_error", "request_id": rid},
        )
