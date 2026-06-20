# Audit Track 4 — Deployment & Operations

**Date:** 2026-06-21 · **Lead:** Claude Code (CE) · **Verdict:** PASS (fixes applied + tested)

| # | Item | Status | Evidence / Fix |
|---|------|--------|----------------|
| 1 | Single end-to-end deploy script (migrate → restart → smoke) | ✅ ADDED | `deploy.ps1` (Windows) + `deploy.sh` (Unix): validate env → `alembic upgrade head` → restart (via `SAF_RESTART_CMD` or interactive prompt) → smoke. Aborts on first failure. |
| 2 | Startup env validation (fail loud if `SAF_API_KEY` missing) | ✅ ADDED | `src/startup_checks.check_env` logs **CRITICAL** for missing required vars (names only, never values); wired into the API lifespan (`required=["SAF_API_KEY"]`) and the worker. Preserves the documented fail-closed-503 design; ops sees a loud startup log. |
| 3 | DB health check on startup | ✅ ADDED | `check_db()` runs `SELECT 1` after `init_pool()` and logs OK/FAILED. Wired into API lifespan and worker `run()`. |
| 4 | Health endpoint reflects DB readiness | ✅ ADDED | `GET /v1/health` now returns `{"status":"ok","db":"ok"|"unavailable"}` (liveness + readiness), no auth — pollable by a load balancer / ops. |
| 5 | Worker heartbeat / liveness | ✅ ADDED | `_heartbeat_loop` logs `[WORKER] heartbeat <ts>` every `WORKER_HEARTBEAT_SECONDS` (default 30) and, if `WORKER_HEARTBEAT_FILE` is set, writes a UTC timestamp to it. Runs in the worker's `asyncio.gather`. |
| 6 | Structured logging (JSON + ts + level + request id) | ✅ ADDED | `src/logging_config.configure_logging()` installs a JSON formatter (`SAF_LOG_FORMAT=json` default, `text` opt-out; `SAF_LOG_LEVEL`). Carries ts/level/logger/msg + the per-request `request_id` (contextvar set by the Track-2 middleware). Called at API + worker startup. |
| 7 | Smoke tests automated (not manual) | ✅ ADDED | `scripts/smoke_scope_c.ps1` (existing, Codex) + new `scripts/smoke_scope_c.sh` (curl): health, settings get/patch, chats, portfolio, projects. Invoked by the deploy scripts. |
| 8 | Rollback documented + reversible | ✅ PASS | `DEPLOY_RUNBOOK_scope_c.md` §6: app/worker redeploy prior commit; `alembic downgrade` reverses 013→012→011 (additive). ⚠️ never downgrade past 004 (credential purge — irreversible by design). |
| 9 | Metrics (Prometheus/StatsD) | ⚠️ RECOMMENDED (not added) | None today. Recommended next: request latency, error rate, queue depth (pending count), lease-recovery count. Request-id + structured logs give correlation now; metrics are a follow-up, not a ship blocker. |

## Files added / changed
- **new:** `src/logging_config.py`, `src/startup_checks.py`, `deploy.ps1`,
  `deploy.sh`, `scripts/smoke_scope_c.sh`, `tests/contract/test_ops_readiness.py`.
- **changed:** `src/api/main.py` (lifespan: configure_logging + env check + DB
  ping; `/v1/health` readiness), `src/api/observability.py` (set `request_id_var`
  for log correlation), `src/worker/scorer.py` (configure_logging + env/DB check +
  heartbeat), `tests/contract/test_api_contract.py` (health shape).

## Tests
- `tests/contract/test_ops_readiness.py` (CI, no DB) — 3 tests: health
  status+db-readiness field; `check_env` flags missing required; clean when none.
- Full suite (CI path): **556 passed, 30 skipped**. Deploy/smoke scripts pass
  `bash -n` and PowerShell tokenize.

## Recommended follow-ups (non-blocking)
- Prometheus/StatsD metrics (item 9).
- A `/v1/health/ready` vs `/v1/health/live` split if a k8s probe distinction is
  needed (current single endpoint already carries both signals).

**Track 4: PASS** — deployment is now scripted end-to-end, the app/worker fail
loud on misconfiguration, health + DB connectivity are observable, the worker has
a heartbeat, and logs are structured + request-correlated.
