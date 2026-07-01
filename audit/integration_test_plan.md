# Audit Track 3 - Integration Seams

**Date:** 2026-06-21
**Lead:** Codex
**Scope:** extension <-> backend contracts, UI failure states, smoke coverage
**Verdict:** PASS for Codex-owned extension seams after fixes below. Backend/ops-only validation remains tracked in Tracks 2 and 4.

## Findings

| # | Item | Status | Evidence / Fix |
|---|------|--------|----------------|
| 1 | Missing `USER_REF` fails gracefully | FIXED | `extension/utils/api_client.js` now returns `{ok:false,error:"user_ref_required",status:0}` before `fetch` for every user-scoped helper. Test: `tests/extension/api_client.test.js`. |
| 2 | Network failure / hanging requests | FIXED | `api_client.js` now wraps HTTP calls in `AbortController` with `API_REQUEST_TIMEOUT_MS`. Timeout maps to the existing `{ok:false,error:"api_unreachable",status:0}` envelope. |
| 3 | Background analysis never replies | FIXED | `triggerAnalysis()` now has `TRIGGER_ANALYSIS_TIMEOUT_MS` and resolves `{ok:false,error:"analysis_timeout"}` instead of hanging. |
| 4 | Version mismatch / missing routes | PASS | View modules check `result.ok` and render inline errors/retry affordances. Settings/Profile/Portfolio/Projects all use optional API presence checks before calling. |
| 5 | Data-shape drift | PASS WITH WATCH | Views use optional chaining and fallback defaults for current contracts (`summary`, `profile_radar`, `feedback_given`, project conflict `detailData`). Future split fields such as `profile_radar_past/_present` should be additive. |
| 6 | Polling stuck forever | FIXED | `chats.js` now caps polling with `MAX_POLL_ATTEMPTS`; stuck pending/scoring rows become retryable failed rows with inline status. |
| 7 | Rapid Analyse clicks | FIXED | `chats.js` now tracks `analysingChatIds` and disables/dedupes per-chat Analyse while a request is in flight. |
| 8 | Feedback submit failure | PASS | `detail.js` re-enables feedback controls and shows inline error on failure. No `alert()`. |
| 9 | Project conflict shape | PASS | S8 uses `result.detailData.current_version`, refreshes project, and shows retry inline. |

## Smoke Test Script

Run from repo root after backend is up:

```powershell
.\scripts\smoke_scope_c.ps1 -BaseUrl http://localhost:8000 -ApiKey $env:SAF_API_KEY -UserRef saf-smoke
```

The script checks:
- `/v1/health`
- `GET/PATCH /v1/users/{uid}/settings`
- `GET /v1/users/{uid}/chats`
- `GET /v1/users/{uid}/portfolio`
- `GET /v1/users/{uid}/projects`

## Extension Manual Smoke

1. Load the unpacked extension from `extension/`.
2. Open a supported ChatGPT/Claude tab.
3. Open the SAF FAB.
4. Settings: set/verify user ref, toggle Auto-analyse and Data opt-in, verify inline save/error status.
5. Chats: click Analyse twice rapidly on the same row; only one request should be sent and the row should remain controlled.
6. Disable backend/network and retry Analyse; the row should show an inline failure and become retryable.
7. Profile: verify read-only username, join date fallback, scored count, streak, and disabled account link.
8. Projects: select a project, add chats, and verify inline conflict/not-found handling remains intact.

## Re-test

```powershell
node --check extension\utils\api_client.js
node --check extension\panel\views\chats.js
node --test tests\extension\api_client.test.js
node --test tests\extension\chats_view.test.js
```

Result: PASS.
