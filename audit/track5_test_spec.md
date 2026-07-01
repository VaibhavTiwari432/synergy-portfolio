# Track 5 — remaining test spec (for Codex)

Commit to `chore/deploy-readiness-audit` before merge. DB-gated tests use the
existing pattern: `pytestmark = skipif(PHASE1_GATE != 1)`, the module `pool`
fixture, and `clean_user` (see `tests/integration/test_scope_c_projects.py`).

**Already covered — do NOT re-add:**
- 409 conflict → `test_scope_c_projects.py::test_update_project_optimistic_concurrency`
- cascading deleteUser → `test_scope_c_projects.py::test_subject_deletion_cascades_scope_c`, `test_evidence_persistence.py::test_delete_user_purges_subject_and_evidence`
- worker stuck-row recovery → `test_worker_recovery.py`

---

## 1. Worker concurrency — only one worker finalizes a score row
**Why:** two poll loops must not both score/finalize the same chat.
**Where:** `tests/integration/test_worker_recovery.py` (or a new `test_worker_concurrency.py`), PHASE1_GATE.
**Spec:**
- Ingest one chat (status `pending`).
- Concurrently call the claim path twice (e.g. `asyncio.gather` of two
  `claim_pending_batch(conn)` on two acquired connections, or two `mark_scored`
  with the same `content_hash`).
- Assert the chat is claimed/finalized **exactly once**: the second claim returns
  empty / `mark_scored` returns 0 (no double-score). Verify `scores` has one row
  and status ends `scored`.
- Reference the existing optimistic guard: `mark_scored` updates only when
  `status='scoring' AND content_hash NOT DISTINCT FROM $2`.

## 2. Malformed input → 422 (not 500)
**Why:** routers must reject bad bodies cleanly.
**Where:** `tests/contract/` with `TestClient` (no DB needed for pure-validation
422s from Pydantic; for handler-level 422s use PHASE1_GATE + a seeded user).
**Spec (each asserts `status_code == 422`):**
- `POST /v1/users/{u}/chats/{c}/feedback` with `{"match_rating":"maybe"}` → 422
  (allowed: yes/partial/no).
- feedback with `turn_index: -1` → 422; `comment` > 280 chars → 422; unknown
  dimension in `dimension_scores` → 422.
- `POST /v1/users/{u}/projects` with `{"name":""}` (blank) or name > 120 chars → 422.
- `PATCH /v1/users/{u}/projects/{id}` without `If-Match` → 428; bad `If-Match` → 422.
- (extension) `submitFeedback` mapping: a `{type:'thumb'}` with no value still
  produces a valid backend body, never a malformed POST.

## 3. Data-shape / version mismatch — old client tolerates new response
**Why:** when the backend adds fields (e.g. D-024's `profile_radar_past/_present`),
an older extension must not break.
**Where:** `tests/extension/` (JS) + an optional backend contract test.
**Spec:**
- JS: feed a renderer (e.g. `portfolio.js` / `detail.js`) a response **with extra
  unknown fields** → asserts it renders without throwing (optional chaining holds).
- JS: feed a response **missing an optional field** → asserts a graceful fallback
  (no `undefined`/`KeyError`-style crash), e.g. CI absent → `±?`.
- Backend (optional): assert `getPortfolio`/`getProject` responses still contain
  the **frozen** Scope-C keys (contract regression guard) so a removal is caught.

---

**Acceptance:** all new tests green under `PHASE1_GATE=1` (DB ones) and in CI
(no-DB ones); full backend suite still passes; then flip Track 5 → PASS in
`DEPLOYMENT_READINESS_CHECKLIST.md`.
