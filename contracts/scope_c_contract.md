# Scope-C Contract — Projects · Sessions · Portfolio Acknowledgement

**Status:** FROZEN v1.0 — 2026-06-20
**Owner:** Chief Engineer (CE). Codex builds UI against these shapes; CE owns the
DB + routes that fulfil them.
**Resolves:** DISCREPANCY D-012 (the part left OPEN after the subject layer was
frozen under D-013).
**Binds:** CLAUDE.md 21 non-negotiables + v3/v3.1 addendum; TEAM.md ownership;
CODEX_AGENT_UI.md (S8/S9 build against this contract).

> **Freeze rule.** This document is additive-only. Fields may be *added* to a
> response; existing field names, types, identifier shapes, and endpoint paths do
> not change without a new version (`v1.1`, …) and a re-read notice in
> DISCREPANCY.md. Codex may build against every shape below today.

---

## 0. What this freezes (and what it does not)

Freezes: the **identity model** (`project_id`, `saf_session_id`), the
**project/session/portfolio-ack data model**, the **endpoint signatures**, the
**response envelopes**, and the **scalability invariants** (pagination,
concurrency, idempotency, deletion propagation).

Does **not** decide: which artifact blobs (`csl` / `question_quality` /
`reliance`, now persisted per migration 011) get surfaced on which route — that
is a separate field-exposure decision. They exist and are queryable; no route
returns them yet.

---

## 1. Identity model (FROZEN)

| ID | Shape | Source of truth | Notes |
|----|-------|-----------------|-------|
| `subject_id` | random opaque UUID (`gen_random_uuid()`) | `subjects` table (migration 006) | Already frozen under D-013. Never derived from `user_ref` / PII (#16). |
| `project_id` | random opaque UUID (`gen_random_uuid()`) | `projects.id` (new) | **Server-minted.** The extension never invents a project id; `create` returns it. Follows the opaque-subject precedent. |
| `saf_session_id` | UUID | **alias of `raw_chats.id`** (`chat_id`) | **No new column, no mapping table.** `saf_session_id := raw_chats.id`. One canonical identity for a scored conversation. This is an *alias*, not an ID collapse — there is still exactly one source row. |
| `conversation_id` | provider string | `raw_chats.conversation_id` | Unchanged, back-compatible. Provider-side id (e.g. ChatGPT `/c/<id>`). |

**Why `saf_session_id` aliases `chat_id`:** the worker, scores, evidence, judge
audit, turn_state, and migration-011 artifacts are all keyed on `raw_chats.id`.
Minting a second per-analysis id would fork that identity and require a mapping
on every join. If re-score history as distinct sessions is ever needed, that is a
`v1.1` additive change (a `score_runs` child table), not a breaking one.

---

## 2. Data model (FROZEN shapes — CE implements as migration 012)

All tables: UUID PKs, `created_at timestamptz default now()`. Deletion of a
subject cascades to everything below it (#16 data dignity).

### 2.1 `projects`
```
id           uuid     PK   default gen_random_uuid()
subject_id   uuid     FK → subjects(subject_id) ON DELETE CASCADE   [INDEX]
name         text     NOT NULL  (1..120 chars, trimmed, no PII expectation)
description  text     NULL      (0..500 chars)
created_at   timestamptz NOT NULL default now()
updated_at   timestamptz NOT NULL default now()
archived_at  timestamptz NULL    (soft-delete marker; NULL = active)
version      integer  NOT NULL default 1   (optimistic concurrency)
```
Index: `(subject_id, archived_at, created_at desc, id)` — supports keyset
pagination of a subject's active projects.

### 2.2 `project_sessions` (many-to-many project ↔ scored chat)
```
project_id   uuid     FK → projects(id)     ON DELETE CASCADE
chat_id      uuid     FK → raw_chats(id)    ON DELETE CASCADE
added_at     timestamptz NOT NULL default now()
PRIMARY KEY (project_id, chat_id)
```
Index: `(chat_id)` — reverse lookup ("which projects is this chat in?").
A chat MAY belong to multiple projects. Assignment is idempotent (re-adding is a
no-op, not an error).

### 2.3 `portfolio_ack`
```
subject_id    uuid    FK → subjects(subject_id) ON DELETE CASCADE
scope         text    NOT NULL   ('portfolio' | 'project:<uuid>')
snapshot_hash text    NOT NULL   (sha256 of the canonical state the user acked)
acked_at      timestamptz NOT NULL default now()
PRIMARY KEY (subject_id, scope)
```
Acknowledgement is **state-scoped**: the user acks a *specific* portfolio
snapshot (by hash). When the underlying state changes, `snapshot_hash` no longer
matches → the UI knows there is unacknowledged change without storing the whole
state twice.

---

## 3. Cross-cutting invariants (FROZEN — apply to every endpoint)

These are the "scalable systems" guarantees. They are part of the contract, not
implementation detail.

1. **Auth.** Every route requires the API key (`require_api_key`), same as
   existing routes. Routes are keyed by `{user_ref}` in the path for parity with
   the current API; the server resolves `user_ref → subject_id` internally.
2. **Pagination = keyset, never offset.** List endpoints accept `?limit=` (default
   20, max 100) and `?cursor=` (opaque base64 of the last `(created_at,id)`).
   Response envelope:
   ```json
   { "items": [ ... ], "next_cursor": "<opaque|null>", "limit": 20 }
   ```
   `next_cursor: null` means the last page. Offset pagination is forbidden (it
   does not scale and double-counts under concurrent writes).
3. **Optimistic concurrency.** Mutable resources (`projects`) carry `version`.
   `PATCH`/`DELETE` MUST send `If-Match: <version>`. Mismatch → `409 Conflict`
   with `{ "error": "version_conflict", "current_version": N }`. No
   last-writer-wins.
4. **Idempotency.** `POST` creates accept an `Idempotency-Key` header. A repeat
   key within 24h returns the original result, not a duplicate. Required for the
   extension where a double-tap must not mint two projects.
5. **Deletion propagates (#16).** `DELETE /projects/{id}` removes the project and
   its `project_sessions` rows (NOT the chats). Deleting the subject (existing
   `DELETE /v1/users/{user_ref}`) cascades to `projects`, `project_sessions`,
   `portfolio_ack`. No orphan survives.
6. **Rung + CI on every emitted score (#6, #14).** Any dimension value carries a
   `ci` and the response carries a `rung`. Project aggregation is `rung:
   "DESIGNED"`. **No project-level composite/total/overall number is emitted** —
   per-dimension only, exactly like the per-chat profile.
7. **Four reporting states, never collapsed (#12).** A dimension is one of
   `scored` · `STRUCTURAL_NA` · `INSUFFICIENT_SAMPLE` · `MEASUREMENT_SATURATED`.
   Aggregation rule: `INSUFFICIENT_SAMPLE` when fewer than **3** scored sessions
   contribute to that dim; `STRUCTURAL_NA` when no session ever had it
   applicable; `scored` otherwise (mean + CI). Saturation propagates if every
   contributing session was saturated.
8. **Minor protection (#15).** If the subject is `is_minor`, no bare composite,
   peer rank, or debt score in any Scope-C response. (No peer rank exists anywhere
   regardless — personal baseline only.)
9. **Contract version echo.** Every Scope-C response includes
   `"contract_version": "scope-c/v1.0"` so clients can detect drift.

---

## 4. Endpoints (FROZEN signatures)

Base: all under the existing `require_api_key` dependency.

### 4.1 Projects

```
POST   /v1/users/{user_ref}/projects
         headers: Idempotency-Key (recommended)
         body:    { "name": str, "description": str|null }
         201 →    Project
         422 →    name empty / too long

GET    /v1/users/{user_ref}/projects?limit=&cursor=
         200 →    { items: [ProjectSummary], next_cursor, limit, contract_version }

GET    /v1/users/{user_ref}/projects/{project_id}
         200 →    ProjectDetail
         404 →    not found / not owned by this user_ref

PATCH  /v1/users/{user_ref}/projects/{project_id}
         headers: If-Match: <version>   (REQUIRED)
         body:    { "name"?: str, "description"?: str }
         200 →    Project (version incremented)
         409 →    version_conflict
         404 →    not found

DELETE /v1/users/{user_ref}/projects/{project_id}
         headers: If-Match: <version>   (REQUIRED)
         200 →    { "deleted": true, "sessions_unlinked": N }
         409 →    version_conflict
```

### 4.2 Project ↔ session assignment

```
POST   /v1/users/{user_ref}/projects/{project_id}/sessions
         body: { "chat_ids": [uuid, ...] }    (== saf_session_ids)
         200 → { "added": N, "skipped_already_present": M, "unknown": [uuid...] }
         (idempotent; unknown/not-owned chat_ids are reported, not fatal)

DELETE /v1/users/{user_ref}/projects/{project_id}/sessions/{saf_session_id}
         200 → { "removed": true }
```

### 4.3 Sessions (alias of the existing chat-score route)

```
GET    /v1/users/{user_ref}/sessions/{saf_session_id}
         == GET /v1/users/{user_ref}/chats/{chat_id}/score   (identical payload)
```
`saf_session_id` resolves to `raw_chats.id`. This is the Scope-C name for the
same resource; the existing `/chats/{chat_id}/score` route is unchanged and
remains valid. Codex may call either; prefer `/sessions/` for new S8/S9 code.

### 4.4 Portfolio acknowledgement

```
GET    /v1/users/{user_ref}/portfolio
         (existing route) — additively gains an "ack" block:
         "ack": { "acked": bool, "acked_at": iso|null, "snapshot_hash": str }
         and "snapshot_hash": str at top level (the hash of the current state).

POST   /v1/users/{user_ref}/portfolio/ack
         body: { "snapshot_hash": str }
         200 → { "acked": true, "acked_at": iso }
         409 → { "error": "stale_snapshot", "current_hash": str }
              (the state moved between GET and POST; client re-reads then re-acks)
```

---

## 5. Response schemas (FROZEN)

```jsonc
// Project (full)
{
  "project_id": "uuid",
  "name": "Q3 research",
  "description": "string|null",
  "version": 1,
  "created_at": "iso8601",
  "updated_at": "iso8601",
  "session_count": 7,
  "contract_version": "scope-c/v1.0"
}

// ProjectSummary (list item — no aggregation, cheap to page)
{ "project_id": "uuid", "name": "string", "session_count": 7,
  "updated_at": "iso8601" }

// ProjectDetail — project + aggregated radar (NO project total/composite)
{
  "project_id": "uuid",
  "name": "string",
  "version": 1,
  "session_count": 7,
  "profile_radar": {
    // one entry per ARI dimension (AL, PR, EC, ES, CS, CD, AUI, CA)
    "EC": { "state": "scored", "value": 0.71, "ci": [0.63, 0.79], "n": 6 },
    "ES": { "state": "INSUFFICIENT_SAMPLE", "value": null, "ci": null, "n": 1 },
    "AUI":{ "state": "STRUCTURAL_NA",       "value": null, "ci": null, "n": 0 }
    // ... MEASUREMENT_SATURATED uses { state, value:null, ci:null, bound }
  },
  "strengths": ["EC", "CS"],        // dims meaningfully above the subject baseline
  "watch": ["ES"],                  // dims below — framing is formative, not a verdict
  "rung": "DESIGNED",
  "contract_version": "scope-c/v1.0"
}
```

**Forbidden in every Scope-C response** (enforced at review): a single
project/portfolio composite number, any peer/population ranking, the word
"synergy", a bare "cognitive debt score", or a dimension value without `state`
and (when `scored`) a `ci`.

---

## 6. Build sequence after this freeze

1. **CE** — migration 012 (`projects`, `project_sessions`, `portfolio_ack`) +
   `queries.py` CRUD + the routers in §4. Mirrors the existing
   `users.py`/`ingest.py` patterns and the §3 invariants.
2. **CE** — once routes are live, `background.js` emits
   `SAF_PROJECTS_API_READY` (CODEX_AGENT_UI.md §7) and adds the
   `api_client.js` functions S8/S9 call.
3. **Codex** — builds S8 (Projects view) and S9 (Project detail) against the
   shapes above; until step 2 fires, the Projects nav stays disabled
   (already implemented).

Codex MAY start S8/S9 markup/styles now against these frozen shapes (with a local
fixture), but MUST NOT go live until `SAF_PROJECTS_API_READY`.

---

*End Scope-C Contract v1.0 (FROZEN). Amendments: bump version + DISCREPANCY note.*
