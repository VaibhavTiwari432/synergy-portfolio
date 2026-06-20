# Audit Track 5 - Test Coverage & Gaps

**Date:** 2026-06-21
**Lead:** Codex assist
**Verdict:** PARTIAL PASS. Codex-owned extension integration tests added; backend worker/concurrency tests remain for Claude/CE.

## Added Tests

`tests/extension/api_client.test.js`

Coverage:
- User-scoped helpers fail locally when `userRef` is missing and do not call `fetch`.
- Configured endpoint and `X-API-Key` are used, while warnings do not leak the key.
- Network timeout resolves as `api_unreachable`.
- `triggerAnalysis()` resolves as `analysis_timeout` when the background listener never replies.

`tests/extension/chats_view.test.js`

Coverage:
- Rapid Analyse clicks are deduped while a request is in flight.
- Stuck pending/scoring chats stop polling and become retryable failed rows.

## Existing Coverage Confirmed

- Payload builder tests exist under both `extension/tests/` and `tests/extension/`.
- Content/interceptor/storage tests exist under `tests/extension/`.
- Scope-C backend integration coverage exists in `tests/integration/test_scope_c_projects.py`, including settings defaults/partial updates and cascade delete coverage.

## Remaining Gaps

| Gap | Owner | Status |
|-----|-------|--------|
| Worker stuck-row lease recovery test | Claude/CE | OPEN |
| Two-worker same-row concurrency test | Claude/CE | OPEN |
| API malformed input matrix beyond current project/settings cases | Claude/CE | OPEN |
| Browser-level extension flow test with a real MV3 runtime | Codex/CE | OPEN |
| Settings/Profile DOM tests for closed-shadow modal wiring | Codex | DEFERRED; current harness has no DOM runner/package. |

## Re-test

```powershell
node --test tests\extension\api_client.test.js
node --test tests\extension\chats_view.test.js
pytest tests\integration\test_scope_c_projects.py -q
```

Node extension test: PASS. Python integration test should be run in an environment with Postgres and async deps configured.
