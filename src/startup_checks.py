"""
src/startup_checks.py — fail-loud environment + DB validation. OWNER: CE.

Audit Track 4. A misconfigured deploy should announce itself at startup, not
silently serve 503s. These helpers LOG loudly (CRITICAL for missing required
vars) and the caller decides whether to also hard-fail. Secret VALUES are never
logged — only which names are present/absent.
"""

from __future__ import annotations

import logging
import os

log = logging.getLogger("saf.startup")


def check_env(*, component: str, required: list[str], optional: list[str] | None = None) -> list[str]:
    """Log presence/absence of env vars (names only). Returns the missing
    REQUIRED names so the caller can hard-fail if it chooses."""
    optional = optional or []
    missing = [name for name in required if not os.environ.get(name)]
    present = [name for name in required + optional if os.environ.get(name)]

    if present:
        log.info("[%s] env present: %s", component, ", ".join(sorted(present)))
    for name in optional:
        if not os.environ.get(name):
            log.warning("[%s] optional env not set: %s", component, name)
    if missing:
        log.critical(
            "[%s] MISSING REQUIRED ENV: %s — the service is misconfigured",
            component, ", ".join(missing),
        )
    return missing


async def check_db(pool) -> bool:
    """Verify the pool can run a trivial query. Logs the verdict; returns bool."""
    if pool is None:
        log.critical("[db] no connection pool — Postgres unreachable at startup")
        return False
    try:
        await pool.fetchval("SELECT 1")
        log.info("[db] connectivity OK")
        return True
    except Exception as exc:  # connectivity probe — never raise out of startup
        log.critical("[db] connectivity FAILED: %s: %s", type(exc).__name__, exc)
        return False
