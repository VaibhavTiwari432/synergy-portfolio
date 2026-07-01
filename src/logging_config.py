"""
src/logging_config.py — structured logging + request-id correlation. OWNER: CE.

Audit Track 4. `configure_logging()` installs one stderr handler whose format is
controlled by SAF_LOG_FORMAT (json [default] | text) and level by SAF_LOG_LEVEL
(default INFO). JSON lines carry ts / level / logger / msg and — inside an API
request — the request_id set by the observability middleware via `request_id_var`
(None elsewhere, e.g. the worker). Idempotent and dependency-free (stdlib only).
"""

from __future__ import annotations

import contextvars
import json
import logging
import os
import sys
import time

#: set per-request by src/api/observability.py; read by the JSON formatter so
#: every log line emitted while handling a request is correlatable.
request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_id", default=None
)


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        ts = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created))
        payload: dict = {
            "ts": f"{ts}.{int(record.msecs):03d}Z",
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        rid = request_id_var.get()
        if rid:
            payload["request_id"] = rid
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


_configured = False


def configure_logging(level: str | None = None) -> None:
    """Install the root handler once. Safe to call from app + worker startup."""
    global _configured
    if _configured:
        return
    fmt = os.environ.get("SAF_LOG_FORMAT", "json").lower()
    lvl = (level or os.environ.get("SAF_LOG_LEVEL", "INFO")).upper()

    handler = logging.StreamHandler(sys.stderr)
    if fmt == "text":
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)-5s %(name)s %(message)s")
        )
    else:
        handler.setFormatter(JsonLogFormatter())

    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(lvl)
    # httpx INFO request lines include full URLs; Gemini keys are query params.
    # Keep provider failures in our own judge logs, but never emit secret-bearing URLs.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    _configured = True
