# Deployment Readiness Checklist - Scope-C + Extension

**Date:** 2026-06-21 | **Branch:** `chore/deploy-readiness-audit` -> `main`
**Process:** CE led Tracks 1/2/4 + backend share of 6; Codex led Track 3 + extension share of 6, then closed Track 5.

| Track | Area | Owner | Verdict | Evidence | Commit(s) |
|-------|------|-------|---------|----------|-----------|
| 1 | Security & Credentials | CE | **PASS** | `audit/security_audit_findings.md` | `1f8d206` |
| 2 | Error Handling & Observability | CE | **PASS** | `audit/error_handling_audit.md` | `3ff8fda` |
| 3 | Integration Seams | Codex | **PASS** | `audit/integration_test_plan.md`, `scripts/smoke_scope_c.ps1` | `87418b8` |
| 4 | Deployment & Operations | CE | **PASS** | `audit/ops_readiness_audit.md` | `ff074cd` |
| 5 | Test Coverage & Gaps | Codex | **PASS** | `audit/test_gaps_audit.md`, `audit/track5_test_spec.md` | `87418b8` + Track 5 closeout commit |
| 6 | Code Quality | Both | **PASS** | `audit/code_quality_report.md` | `4a48778`, `87418b8` |

## Ship Gate
- [x] Security Track 1 - findings + retest (credentials never logged; fixtures obfuscated)
- [x] Error-handling Track 2 - generic 500 + 503, request id, worker recovery; findings + tests
- [x] Integration Track 3 - api_client/chats hardening + extension tests (Codex)
- [x] Ops Track 4 - deploy automation, startup env/DB checks, health, heartbeat, JSON logs, rollback
- [x] Code-quality Track 6 - dead imports removed, routers/queries typed, extension IIFE-clean
- [x] Extension: request timeout, missing-user-ref guard, Analyse timeout/dedupe/stuck-poll
- [x] Automated deploy script exists - `deploy.ps1` / `deploy.sh`
- [x] Smoke script automated - `scripts/smoke_scope_c.{ps1,sh}`
- [x] Ops troubleshooting - structured JSON logs + request id + `/v1/health` db + worker heartbeat
- [x] Track 5 remaining - worker concurrency, malformed-input validation, version-mismatch contract (Codex)
- [x] Extension E2E integration - IPv6 localhost normalization, toolbar->modal flow, 127.0.0.1 host permission (`ca7e058`)
- [ ] Deploy script verified in target env + smoke run against live backend (at staging deploy)

## Track 5 - completed closeout
- Covered before closeout: **409 conflict** (`test_scope_c_projects.py::test_update_project_optimistic_concurrency`); **cascading deleteUser** (`test_scope_c_projects.py`, `test_evidence_persistence.py`); **worker stuck-row recovery** (`test_worker_recovery.py`, CE Track 2).
- Added by Codex: **worker concurrency** (`test_worker_recovery.py::test_concurrent_workers_claim_and_finalize_once`), **malformed input validation** (`tests/contract/test_scope_c_validation.py`), and **data-shape/version tolerance** (`tests/extension/detail_view_shape.test.js`).

## Current Codex extension fixes (Track 3 / 6 / 5)
- `extension/utils/api_client.js`: HTTP timeout, `triggerAnalysis` timeout, `user_ref_required` guard.
- `extension/panel/views/chats.js`: polling cap + rapid-Analyse dedupe.
- `tests/extension/api_client.test.js`: integration-seam regressions and feedback thumb mapping.
- `tests/extension/detail_view_shape.test.js`: renderer tolerance for extra/missing score fields.
- `tests/contract/test_scope_c_validation.py`: malformed Scope-C validation matrix.
- `tests/integration/test_worker_recovery.py`: worker concurrency finalization guard.
- `scripts/smoke_scope_c.ps1`: Scope-C backend smoke automation.

## Post-audit E2E integration fixes (extension) - `ca7e058`
Real bugs found during end-to-end testing on Windows 11; uncommitted code shipped broken without these.
- **A. IPv6 normalization** (`extension/utils/api_client.js`): Windows resolves `localhost` to IPv6 `::1` first, but the dev server binds IPv4 `127.0.0.1` only -> fetches failed silently as `api_unreachable`. Fetch URL now forces loopback host (`localhost`/`::1`) to `127.0.0.1`; stored/displayed endpoint untouched.
- **B. Broken toolbar popup** (`extension/manifest.json`): `action.default_popup` pointed at `panel/panel.html`, which is a template-only shadow-DOM fragment (no `<script>`/`<body>`) -> clicking the toolbar icon opened a blank popup. Removed `default_popup`; added `http://127.0.0.1/*` host permission.
- **C. Toolbar click handler** (`extension/background.js`): added `chrome.action.onClicked` -> opens the in-page modal on supported tabs (ChatGPT/Claude), opens ChatGPT elsewhere, and self-heals (tab reload) if the content script is not yet injected.
- **D. Modal relay** (`extension/injected_icon.js`): handles `SAF_OPEN_MODAL` to toggle the modal; build stamp bumped to `0.5.1-toolbar-open` for load verification.
- Validation: `node --check` clean on all four files; `manifest.json` parses; normalization unit-verified (`localhost->127.0.0.1`, remote URLs untouched). Requires extension reload at `chrome://extensions` (manifest changed).

## Verification snapshot
- Backend full suite (CI path): **556 passed, 30 skipped**; DB extras pass under `PHASE1_GATE=1`.
- Extension JS suites: pass (`node --test`).
- Track 5 closeout retest on 2026-06-21: `tests/extension/*.test.js` -> 57 passed; `extension/tests/*.test.js` -> 29 passed; `tests/contract/test_scope_c_validation.py` -> 10 passed; `PHASE1_GATE=1 tests/integration/test_worker_recovery.py` -> 4 passed.
- `pyflakes src/` clean; CI forbidden-word gate clean; deploy/smoke scripts pass `bash -n` / PowerShell tokenize.

---

**Deployment-ready: YES (Tracks 1-6 PASS; final live-environment deploy/smoke still pending staging).**

Recommended sequence: merge -> deploy to staging via `deploy.{ps1,sh}` (migrate 011->013 + restart + smoke) -> production.
