# Audit Track 2 — Error Handling & Observability

**Date:** 2026-06-21 · **Lead:** Claude Code (CE) · **Verdict:** PASS (fixes applied + tested)

| # | Item | Status | Evidence / Fix |
|---|------|--------|----------------|
| 1 | 500 errors don't expose internals; generic body + request id | ✅ FIXED | New `src/api/observability.py`: global `@app.exception_handler(Exception)` returns `{"error":"internal_server_error","request_id":…}`, full traceback to log ONLY. `X-Request-ID` on every response (generated or echoed from the client). Wired in `create_app`. |
| 2 | DB unreachable → 503, not 500 | ✅ FIXED | Same handler maps connection-class errors (`ConnectionError`/`OSError`/`TimeoutError` + asyncpg connection errors by module+name) to **503 `database_unavailable`**. Startup-time DB-down already → 503 via `_require_pool`. |
| 3 | Worker stuck-row recovery (LEASE_TIMEOUT) | ✅ TESTED | `reset_expired_scoring_leases` reclaims a `scoring` row whose lease exceeded `LEASE_TIMEOUT_SECONDS` back to `pending` (single CTE + audit row, `FOR UPDATE SKIP LOCKED`). New tests prove an expired lease IS reclaimed and a fresh lease is NOT. |
| 4 | `capture_complete=false` handling | ✅ TESTED | `upsert_chat` runs `capture_completeness_error` → raises `ValueError` → **422** at the ingest router; the row never enters `pending`. Test asserts rejection + nothing persisted. (Migration-007 CHECK backstops at rest.) |
| 5 | Async failure (triggerAnalysis timeout) surfaces to UI | ✅ (Track 3) | Backend side (this track): failures return a clean 500/503 + request id, never a hang. UI surfacing (timeout → "Analysis failed", no silent hang) is **Codex Track 3** (`87418b8`: api_client timeouts + chats.js error states). Cross-referenced. |
| 6 | CI logging context on failures | ✅ PASS | pytest default shows per-assertion state; new tests assert concrete values (status, body keys, header) so a regression prints what differed. |

## Fixes applied
- `src/api/observability.py` (new) + wired into `src/api/main.py create_app`:
  request-id middleware + generic-500 handler + DB-down→503 handler. **No
  traceback or internal detail ever reaches the response body.**

## Tests added
- `tests/contract/test_error_handling.py` (no DB, runs in CI) — 4 tests:
  generic 500 + request id + **no leakage** (`ValueError`/message/`Traceback`
  absent from body); `ConnectionError` → 503; request-id present on success +
  client value echoed; `_is_db_unavailable` detector (asyncpg name/module match
  vs logic errors).
- `tests/integration/test_worker_recovery.py` (PHASE1_GATE) — 3 tests: expired
  lease reclaimed; fresh lease untouched; incomplete capture rejected at ingest.

## Re-test
- `pytest tests/contract/test_error_handling.py` → **4 passed**.
- `PHASE1_GATE=1 pytest tests/integration/test_worker_recovery.py` → **3 passed**.
- Full suite (CI path): **553 passed, 30 skipped**; forbidden-word gate clean.

## Carried to Track 4
- Full **structured (JSON) logging** with level + timestamp + request id on every
  log line (this track adds the request id + correlation; Track 4 makes the log
  *format* structured and ops-searchable).
- App **startup env/DB validation** (fail-loud) and **worker heartbeat**.

**Track 2: PASS** — error paths now fail safe (generic 500 / correct 503), the
worker self-heals stuck rows, incomplete captures are rejected, and every path is
tested.
