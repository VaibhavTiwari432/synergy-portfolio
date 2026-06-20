# Deployment Readiness Checklist

**Date:** 2026-06-21
**Status:** NOT READY FOR PRODUCTION until all tracks below are PASS and re-tested.

| Track | Owner | Status | Artifact |
|-------|-------|--------|----------|
| 1. Security & credentials | Claude/CE | PASS | `audit/security_audit_findings.md` |
| 2. Error handling & observability | Claude/CE | OPEN | `audit/error_handling_audit.md` pending |
| 3. Integration seams | Codex | PASS | `audit/integration_test_plan.md` |
| 4. Deployment & operations | Claude/CE | OPEN | `audit/ops_readiness_audit.md` pending |
| 5. Test coverage & gaps | Codex assist | PARTIAL | `audit/test_gaps_audit.md` |
| 6. Code quality & maintainability | Both | PARTIAL | `audit/code_quality_report.md` |

## Ship Gate

- [x] Security Track 1 has pass/fail findings and retest.
- [ ] Error handling Track 2 has pass/fail findings, fixes, and retest.
- [x] Integration Track 3 has pass/fail findings, fixes, and extension tests.
- [ ] Ops Track 4 has deploy automation, health checks, and rollback validation.
- [ ] Track 5 backend/worker/concurrency gaps are closed or explicitly accepted.
- [ ] Track 6 backend lint/type/logging pass is complete.
- [x] Extension API requests have timeout behavior.
- [x] Extension missing-user-ref path is bounded and does not call malformed backend URLs.
- [x] Extension Analyse flow has timeout/dedupe/stuck-poll handling.
- [ ] Automated deploy script is verified in the target environment.
- [ ] Smoke script is run against a live backend and results are attached.

## Current Codex Fixes

- `extension/utils/api_client.js`: HTTP timeout, `triggerAnalysis` timeout, local `user_ref_required` guard.
- `extension/panel/views/chats.js`: polling cap and rapid Analyse dedupe.
- `tests/extension/api_client.test.js`: regression tests for integration seam behavior.
- `scripts/smoke_scope_c.ps1`: curl-style backend smoke automation for Scope-C routes.

## Final Sign-off Rule

Mark this checklist READY only after every OPEN/PARTIAL row above is resolved with:
1. Findings document.
2. Fix commits or explicit accepted-risk note.
3. Re-test command and result.
