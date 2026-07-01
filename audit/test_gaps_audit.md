# Audit Track 5 - Test Coverage & Gaps

**Date:** 2026-06-21
**Lead:** Codex assist
**Verdict:** PASS. Codex-owned Track 5 gaps are covered by extension, contract, and PHASE1-gated integration tests.

## Added Tests

`tests/extension/api_client.test.js`

Coverage:
- User-scoped helpers fail locally when `userRef` is missing and do not call `fetch`.
- Configured endpoint and `X-API-Key` are used, while warnings do not leak the key.
- Network timeout resolves as `api_unreachable`.
- `triggerAnalysis()` resolves as `analysis_timeout` when the background listener never replies.
- `submitFeedback({ type: 'thumb' })` maps to a valid backend body when no value is supplied.

`tests/extension/chats_view.test.js`

Coverage:
- Rapid Analyse clicks are deduped while a request is in flight.
- Stuck pending/scoring chats stop polling and become retryable failed rows.

`tests/extension/detail_view_shape.test.js`

Coverage:
- Detail rendering ignores extra future response fields.
- A scored dimension with missing optional CI falls back to `+/-?` without throwing.

`tests/contract/test_scope_c_validation.py`

Coverage:
- Feedback rejects invalid `match_rating`, negative `turn_index`, over-long comments, unknown dimensions, and invalid dimension scores with 422.
- Project creation rejects blank and over-length names with 422.
- Project PATCH rejects missing `If-Match` with 428 and malformed `If-Match` with 422.

`tests/integration/test_worker_recovery.py`

Coverage:
- Two concurrent workers claim the same pending chat exactly once.
- `mark_scored` finalizes once; the second finalization attempt returns 0.
- The chat ends `scored` with exactly one score row.

## Existing Coverage Confirmed

- Payload builder tests exist under both `extension/tests/` and `tests/extension/`.
- Content/interceptor/storage tests exist under `tests/extension/`.
- Scope-C backend integration coverage exists in `tests/integration/test_scope_c_projects.py`, including settings defaults/partial updates, optimistic 409 conflict handling, and cascade delete coverage.
- Worker stuck-row lease recovery is covered in `tests/integration/test_worker_recovery.py`.

## Remaining Gaps

| Gap | Owner | Status |
|-----|-------|--------|
| Worker stuck-row lease recovery test | CE | COVERED |
| Two-worker same-row concurrency test | Codex | COVERED |
| API malformed input matrix beyond current project/settings cases | Codex | COVERED |
| Browser-level extension flow test with a real MV3 runtime | Codex/CE | OPEN |
| Settings/Profile DOM tests for closed-shadow modal wiring | Codex | DEFERRED; current harness has no DOM runner/package. |

## Re-test

```powershell
node --test tests\extension\api_client.test.js
node --test tests\extension\chats_view.test.js
node --test tests\extension\detail_view_shape.test.js
pytest tests\contract\test_scope_c_validation.py -q
$env:PHASE1_GATE='1'; pytest tests\integration\test_worker_recovery.py -q; Remove-Item Env:\PHASE1_GATE
```

Track 5 closeout retest: PASS locally on 2026-06-21:
- `node --test tests\extension\api_client.test.js tests\extension\detail_view_shape.test.js` -> 6 passed.
- `node --test tests\extension\*.test.js` -> 57 passed.
- `node --test extension\tests\*.test.js` -> 29 passed.
- `pytest tests\contract\test_scope_c_validation.py -q` -> 10 passed.
- `PHASE1_GATE=1 pytest tests\integration\test_worker_recovery.py -q` -> 4 passed.
