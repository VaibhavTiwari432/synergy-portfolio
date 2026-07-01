# Audit Track 1 — Security & Credentials

**Date:** 2026-06-21 · **Lead:** Claude Code (CE) · **Scope:** backend + extension + fixtures
**Verdict:** PASS (1 fix applied; 2 documented accepted-risks; 1 hardening deferred to Track 2)

| # | Item | Status | Evidence / Fix |
|---|------|--------|----------------|
| 1 | API key never in logs / tracebacks / error responses | ✅ PASS | `auth.py` uses `hmac.compare_digest` (constant-time); 401/503 bodies are generic and never echo the supplied key. No `X-API-Key` value logged anywhere in `src/`. |
| 2 | Extension storage encryption | ⚠️ ACCEPTED RISK | `chrome.storage.local` is **not** encrypted at rest (plaintext on the user's own disk). Standard for MV3 extensions; the stored API key authorizes only the user's own localhost backend. Documented; no code change. See "Accepted risks" below. |
| 3 | Env vars (`SAF_API_KEY`/`GEMINI_API_KEY`/`OPENAI_API_KEY`) never logged | ✅ PASS | `grep -rniE "log.*(api_key\|secret\|token\|password)" src/` → no key logging. Worker `self_rater.py:163` explicitly logs the exception **class name only**, never the key. |
| 4 | `DATABASE_URL` never in error messages | ✅ PASS | Only reference: `connection.py:48` logs `DATABASE_URL.split("@")[-1]` — host/db **after** `@`, so `user:password` (before `@`) is never logged. |
| 5 | Extension validates backend before storing creds | ⚠️ MINOR | No OAuth flow; creds come from user onboarding input. `SAF_PANEL_SAVE_SETTINGS` stores then runs `_updateHealth()` to reflect validity. Can't validate a key without a call; acceptable. Documented. |
| 6 | Test fixtures obfuscated (won't trip scanners) | ✅ FIXED | Was: only the Slack fixture split; OpenAI/OpenRouter/AWS/Google/GitHub were contiguous literals. **Fix:** all 6 fixtures in `tests/unit/test_secret_guard.py` now split into concatenated literals (runtime value unchanged → `scrub_secrets` still tested). Verified no contiguous token remains; test 9/9. |
| 7 | 500 errors don't leak internals | ✅ PASS (see Track 2) | `create_app` does **not** set `debug=True`, so FastAPI returns a generic `Internal Server Error` body with **no traceback**. Tracebacks go to server logs only. *Gap (→ Track 2):* no request-ID correlation on 500s; recommend a global handler that returns `{error, request_id}`. |
| 8 | Credential-at-rest in corpus (Track 0 / D-019) | ✅ PASS (pre-existing) | `scrub_secrets()` strips by key-name AND value-shape before every DB write; per-user OpenAI key no longer collected; migration 004 purged historical keys. |

## Fix applied
- `tests/unit/test_secret_guard.py` — split all 6 example-token fixtures so no
  contiguous token literal exists in source (push-protection / secret-scanner
  safe), runtime values unchanged. Test: **9 passed**.

## Accepted risks (documented, no code change)
- **Extension `chrome.storage.local` is unencrypted.** Mitigations in place: the
  API key is for the user's own (typically localhost) backend; never synced; never
  logged. If a hardened posture is ever required, options are (a) prompt for the
  key per session instead of persisting, or (b) a host-app-managed secret. Not
  blocking for the current deployment model.
- **No pre-store credential validation** in the extension (no auth provider to
  validate against). The post-save health check surfaces an invalid key as a red
  health badge.

## Deferred to Track 2 (observability)
- Add a global exception handler returning a generic message **+ a request ID**,
  and confirm via test that an unhandled exception yields `500` with no traceback.

## Re-test
- `pytest tests/unit/test_secret_guard.py -q` → **9 passed**.
- `grep` for contiguous token literals → none.
- Auth / logging / DB-URL findings verified by source inspection (citations above).

**Track 1: PASS** — one fix applied + re-tested; residual items are documented
accepted-risks or carried to Track 2.
