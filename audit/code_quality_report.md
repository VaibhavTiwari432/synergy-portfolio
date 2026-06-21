# Audit Track 6 - Code Quality & Maintainability

**Date:** 2026-06-21
**Lead:** Codex (extension surface) + Claude Code / CE (backend `src/`)
**Verdict:** PASS — extension seams (Codex) AND backend `src/` (CE) both complete.

## Extension Findings

| Item | Status | Notes |
|------|--------|-------|
| Dead imports | PASS | Touched extension files do not introduce imports. View modules are direct ES modules. |
| Magic numbers | FIXED | New timeout/poll values are named constants: `API_REQUEST_TIMEOUT_MS`, `TRIGGER_ANALYSIS_TIMEOUT_MS`, `MAX_POLL_ATTEMPTS`. |
| Global pollution | PASS | No new globals. Existing globals remain `SAFApiClient` and `SAFStorage` IIFE exports. |
| User-visible silent failure | FIXED | API timeout, analysis timeout, stuck polling, and missing user ref now produce bounded error envelopes or inline UI states. |
| Claim-language risk | PASS | No composite/overall/ranking copy added in touched extension code. |
| Formatting/syntax | PASS | `node --check` passes for touched JS. |

## Backend `src/` Findings (CE)

| Item | Status | Evidence / Fix |
|------|--------|----------------|
| Dead imports | FIXED | `pyflakes src/` found 9 unused imports — all removed (store.py json; ingest.py UUID; users.py count_rows_for_user; views.py TIER_CAVEATS; eventlog/queries.py Sequence; canonical.py datetime; estimator.py Protocol; judge/client.py JudgeParseError; scorer.py get_score_row). `pyflakes src/` now exits clean (0). |
| Type hints (routers + queries) | FIXED | AST scan found 21 unannotated params (the `pool=Depends()` DI idiom + 4 internal helpers); `queries.py` already fully typed. Annotated all route `pool` params (`asyncpg.Pool`) + the 4 helpers. AST scan now: **0 remaining**. |
| Magic numbers | PASS | Tunables already named env-sourced constants (POLL_INTERVAL, HEARTBEAT_INTERVAL, LEASE_TIMEOUT_SECONDS, PAGE_SIZE, …). |
| Comments on complex sections | PASS | CSL pipeline, scoring/claims, capture interception carry docstrings + rationale. |
| Structured logging / request id | DONE (Track 4) | `src/logging_config.py` JSON logs + per-request id; see ops_readiness_audit.md. |
| Worker heartbeat | DONE (Track 4) | `_heartbeat_loop` in scorer.py; see ops_readiness_audit.md. |
| Linters (black/flake8/pylint/ruff) | ⚠️ NOT IN TOOLCHAIN | None installed or in CI. Used `pyflakes` for this pass. Did NOT blanket-`black` (not installed; would be a massive unrelated diff). **Recommend adopting `ruff`** (pyflakes+isort+flake8+formatter) in dev deps + a CI step as a deliberate separate change. |

The items Codex flagged as open are now resolved here (type hints, dead imports)
or under Tracks 2/4 (request-id logging, heartbeat). The one open recommendation
is ruff-in-CI (non-blocking).

## Re-test

```powershell
node --check extension\utils\api_client.js
node --check extension\panel\views\chats.js
node --test tests\extension\api_client.test.js
node --test tests\extension\chats_view.test.js
```

Result: PASS.
