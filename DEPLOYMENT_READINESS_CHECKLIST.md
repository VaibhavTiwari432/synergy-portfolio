# Deployment Readiness Checklist — Scope-C + Extension

**Date:** 2026-06-21 · **Branch:** `chore/deploy-readiness-audit` → `main`
**Process:** CE led Tracks 1/2/4 + backend share of 6; Codex led Track 3 + extension share of 6, leading Track 5.

| Track | Area | Owner | Verdict | Evidence | Commit(s) |
|-------|------|-------|---------|----------|-----------|
| 1 | Security & Credentials | CE | **PASS** | `audit/security_audit_findings.md` | `1f8d206` |
| 2 | Error Handling & Observability | CE | **PASS** | `audit/error_handling_audit.md` | `3ff8fda` |
| 3 | Integration Seams | Codex | **PASS** | `audit/integration_test_plan.md`, `scripts/smoke_scope_c.ps1` | `87418b8` |
| 4 | Deployment & Operations | CE | **PASS** | `audit/ops_readiness_audit.md` | `ff074cd` |
| 5 | Test Coverage & Gaps | Codex | **PARTIAL** | `audit/test_gaps_audit.md` (gap list below) | `87418b8` (+ pending) |
| 6 | Code Quality | Both | **PASS** | `audit/code_quality_report.md` | `4a48778`, `87418b8` |

## Ship Gate
- [x] Security Track 1 — findings + retest (credentials never logged; fixtures obfuscated)
- [x] Error-handling Track 2 — generic 500 + 503, request id, worker recovery; findings + tests
- [x] Integration Track 3 — api_client/chats hardening + extension tests (Codex)
- [x] Ops Track 4 — deploy automation, startup env/DB checks, health, heartbeat, JSON logs, rollback
- [x] Code-quality Track 6 — dead imports removed, routers/queries typed, extension IIFE-clean
- [x] Extension: request timeout, missing-user-ref guard, Analyse timeout/dedupe/stuck-poll
- [x] Automated deploy script exists — `deploy.ps1` / `deploy.sh`
- [x] Smoke script automated — `scripts/smoke_scope_c.{ps1,sh}`
- [x] Ops troubleshooting — structured JSON logs + request id + `/v1/health` db + worker heartbeat
- [ ] **Track 5 remaining** — worker concurrency, malformed-input validation, version-mismatch contract (Codex)
- [ ] Deploy script verified in target env + smoke run against live backend (at staging deploy)

## Track 5 — remaining gap list (Codex, before merge)
- ✅ already covered: **409 conflict** (`test_scope_c_projects.py::test_update_project_optimistic_concurrency`); **cascading deleteUser** (`test_scope_c_projects.py`, `test_evidence_persistence.py`); **worker stuck-row recovery** (`test_worker_recovery.py`, CE Track 2).
- ⏳ still needed (3–4 tests, same branch):
  1. **Worker concurrency** — two workers cannot both finalize the same score row (claim/lease under contention).
  2. **Malformed input validation** — routers return 422 for bad bodies (invalid `match_rating`, negative `turn_index`, unknown dimension, over-long fields).
  3. **Data-shape / version mismatch** — a response gaining fields still parses (optional-chaining contract); removed/renamed field caught.

## Current Codex extension fixes (Track 3 / 6)
- `extension/utils/api_client.js`: HTTP timeout, `triggerAnalysis` timeout, `user_ref_required` guard.
- `extension/panel/views/chats.js`: polling cap + rapid-Analyse dedupe.
- `tests/extension/api_client.test.js`: integration-seam regressions.
- `scripts/smoke_scope_c.ps1`: Scope-C backend smoke automation.

## Verification snapshot
- Backend full suite (CI path): **556 passed, 30 skipped**; DB extras pass under `PHASE1_GATE=1`.
- Extension JS suites: pass (`node --test`).
- `pyflakes src/` clean; CI forbidden-word gate clean; deploy/smoke scripts pass `bash -n` / PowerShell tokenize.

---

**Deployment-ready: YES (Tracks 1–4 PASS; Track 3 PASS; Track 6 PASS; Track 5 PARTIAL pending Codex).**

Recommended sequence: land Track 5's 3 remaining tests green on this branch →
merge → deploy to staging via `deploy.{ps1,sh}` (migrate 011→013 + restart + smoke) → production.
