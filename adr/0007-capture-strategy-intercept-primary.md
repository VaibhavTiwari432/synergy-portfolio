# ADR-0007 — Capture strategy: conversation-JSON interception primary, scroll-probe demoted to fallback

- **Status:** Accepted
- **Date:** 2026-06-17
- **Decider:** Chief Engineer; strategy + option-2 split confirmed by project lead
- **Supersedes:** the "Long-chat fallback" / scroll-harvest approach added under
  D-014 (2026-06-17) as the *primary* completeness mechanism. That code is not
  deleted — it is demoted to a hardened secondary (see Decision §3).
- **Implements via:** D-015 (the content.js interface contract for Codex) + the
  CE spine (interceptor, manifest, ingest, completeness gate, migration, tests).

## Context — why the scroll-probe can never be complete

ChatGPT renders its message list **virtualized**: only the turns near the
viewport are mounted in the DOM at any instant; scrolling away unmounts them,
and long threads lazy-load older turns from the server only on scroll-up. So
`document.querySelectorAll` over `conversation-turn-*` containers
(`content.js:248 allCandidates`) returns the *visible window*, never the whole
conversation. The scroll-harvest in `captureFullConversationForManual`
(`content.js:397`, added under D-014) is the right instinct for a pure-DOM
strategy, but it is racing React's mount/unmount, re-deduping re-mounted nodes,
and is still bounded by whatever the server has paginated in. **Completeness was
never guaranteed by the rendered DOM**, so no amount of traversal polish makes it
reliable.

This is the root cause of the symptom under investigation (incomplete transcripts
reaching the scorer) — and it is the same disease as the D-014 finding (a 58-turn
row split 55 user / 3 assistant). The role-balance guards shipped under D-014
catch *gross* imbalance; they do **not** catch a transcript that is internally
balanced but silently truncated by virtualization.

## Decision

### 1. Promote conversation-JSON interception to the primary capture source

When the user opens a saved chat, ChatGPT's web app fetches the **complete**
conversation tree from its own backend. The content script shares the user's
session, so that payload is available to us. We do **not** replicate the call
(auth tokens / headers are fragile) — we **intercept the response the page
already makes**: patch `fetch`/`XHR` in the **MAIN world**, match the
conversation endpoint, and hand the parsed JSON across the isolated-world
boundary by `postMessage`. This fixes completeness *by construction* — the
payload is the whole tree regardless of scroll position.

MV3 trap, designed-around: content scripts run in an isolated world and do not
share the page's `window.fetch`, so the interceptor runs in a dedicated
`world: "MAIN"` content-script entry (`extension/interceptor.js`,
`run_at: "document_start"`). It is CE-owned (it touches no DOM selectors; it is
network plumbing, not a leaf). The isolated-world bridge that consumes the
`postMessage` lives in `content.js` and is Codex-owned (D-015).

### 2. It is a tree, not a list — take the active path only

Regenerations and edits create sibling branches in `mapping`. The displayed
conversation is the path from `current_node` walking parent pointers to the root,
reversed. **Flattening the whole mapping folds abandoned branches into the
transcript and corrupts the score** — so the bridge takes the active path only.
The exact walk is specified in D-015.

### 3. Demote the scroll-probe to a hardened fallback (do not delete it)

The scroll-harvest stays in `content.js` as the secondary path, for when
interception is unavailable (MAIN world not injected, a future platform with no
interceptable fetch, or the JSON shape unrecognised). It fires **only** when
interception has not produced a complete capture for the active conversation —
never alongside it. The D-014 fallback fixes (top-first pagination exhaustion,
`MutationObserver` running throughout, dedupe by stable id, stream-complete gate)
remain valid for that secondary role.

### 4. The completeness gate is what actually protects the corpus

Same philosophy as "no CI, no emission" and "consent gates everything": an
incomplete transcript that *looks* fine produces a confidently wrong ARI that
silently poisons the corpus. So completeness is made **checkable** and
incompleteness **blocks scoring**:

- The mapping yields an authoritative `expected_turn_count` (user+assistant
  messages on the active path, after visibility filtering).
- The capture carries `captured_turn_count` and a `capture_complete` boolean.
- `capture_complete` is true **iff** `expected_turn_count == captured_turn_count`
  (after dedupe reconciliation), the active path resolved fully from
  `current_node` to root, and the last turn is not mid-stream.
- **`false` vs `null` is load-bearing.** `false` = interception ran and is
  *proven* incomplete (→ quarantine). `null` = completeness *unknown* (the
  scroll-probe / dom-live fallback paths, which cannot prove completeness) → defer
  to the legacy role-balance gate so the fallback still ingests. A fallback path
  must NEVER set `false`, or every fallback capture would be permanently
  quarantined — the opposite of a hardened fallback.
- **`captured_turn_count` is server-derived, not client-trusted.** The gate uses
  `captured = len(turns)`, not the client's scalar — otherwise a payload could
  claim `captured == expected` while delivering a truncated `turns` array, and the
  DB CHECK (which compares two scalars, not a scalar to the JSONB array) would not
  catch it. A client `captured_turn_count` that disagrees with the delivered turns
  is a broken bridge → 422 `captured_count_mismatch`. The worker re-derives from
  the stored turns too. **Honest limitation:** `expected_turn_count` remains a
  bridge claim the server cannot independently verify (it never receives the raw
  mapping), so the `expected` half of the invariant rests on the bridge getting
  the active-path walk right; the server-derived `captured` is the half the server
  can enforce.
- **Gate decision: quarantine, do not score.** When `capture_complete is False`,
  `/v1/ingest` returns **HTTP 422 with a structured body**
  (`{reason, capture_complete, expected_turn_count, captured_turn_count,
  message}`) so the extension badge shows "captured M of N", never "API
  unreachable" (cf. D-009); the row never enters `pending`. The worker repeats the
  check and marks any incomplete claimed row `failed` rather than scoring it, and
  a **DB CHECK constraint** (migration 007) forbids `capture_complete = true`
  whenever `captured_turn_count < expected_turn_count` — the invariant is enforced
  by the database, not trusted to ingest as the sole writer. This reuses the exact
  quarantine path D-014 established for imbalance. *A wrong score is worse than no
  score.* The 422 also gives a live "capture is broken" signal instead of
  discovering gaps weeks later — reinforced by a runtime field-presence assertion
  in the interceptor (a structured warning the first time a §3 VERIFY field is
  missing), so a ChatGPT shape change surfaces in hours.

### 5. Provenance + timestamp upgrade (bonus, lands on the recoverability work)

The intercepted JSON carries `model_slug` (the exact partner model id+version)
and real per-message `create_time`. Interception therefore upgrades the
`partner_model.model_id` and per-turn `timestamp_ms` fidelity that D-013's
provenance tracks were reconstructing from the DOM. The bridge populates these
from the JSON when present; the DOM remains the source only for the live-streamed
tail.

### 6. Backfill stays export-JSON; the live tail stays DOM

- **Backfill:** for chats the user never opens this session, the page never
  fetches them, so interception cannot see them. The user-downloaded
  `conversations.json` export remains the complete-by-construction backfill path,
  exactly as specced. The export file is itself an array of `mapping` trees, so it
  shares the **same active-path walk** as interception.
- **Live tail:** turns added *during* the session arrive by streaming and are
  always in the viewport (virtualization never drops the newest turns), so the
  existing pair-detection already has them. Division of labour: JSON mapping is the
  authoritative source for the history virtualization was hiding; the DOM supplies
  the freshly-streamed tail. **Reconcile by deduping into a Map keyed by a stable
  message key, never by assuming append-only** (D-015 §6): ChatGPT may or may not
  re-fetch the conversation mid-session, and dedupe is correct either way — the
  append-only assumption is a fragile optimisation not worth the correctness risk.
  The page's actual re-fetch behaviour is to be observed in the network tab during
  the first live test and recorded here as a footnote, so the next person knows
  what was seen rather than what was assumed.

## Ownership split (TEAM.md §3, option 2)

| Piece | Owner | File(s) |
|---|---|---|
| MAIN-world interceptor (patch fetch/XHR, match endpoint, postMessage) | **CE** | `extension/interceptor.js` (new) |
| Manifest MAIN-world entry | **CE** | `extension/manifest.json` |
| Background handler for new capture fields → ingest | **CE** | `extension/background.js` |
| Ingest schema + 422 quarantine on incomplete | **CE** | `contracts/schemas.py`, `src/api/routers/ingest.py` |
| Completeness columns + worker gate | **CE** | `alembic/` (migration 007), `src/db/queries.py`, `src/worker/scorer.py` |
| Tests (schema/ingest/worker/migration) | **CE** | `tests/...` next to CE modules |
| **Bridge: consume postMessage, walk active path, forward** | **Codex** | `extension/content.js` |
| **Carry the new completeness/method fields through** | **Codex** | `extension/utils/payload_builder.js` |
| **Fallback demotion (scroll-probe fires only when interception incomplete)** | **Codex** | `extension/content.js` |

CE's spine does not depend on the bridge being authored yet (it accepts the
fields whenever they arrive; absent fields degrade to the existing DOM/scroll
path). The bridge spec (D-015) is complete enough that Codex needs no mid-build
CE questions.

## VERIFY-IN-NETTAB (non-hallucination, non-negotiable spirit)

The exact conversation endpoint path (`/backend-api/conversation/{id}`) and the
`mapping` / `current_node` / `message.author.role` / `content.parts` /
`metadata.model_slug` / `create_time` field names are **ChatGPT internals that
shift over time**. They are flagged in D-015 as `VERIFY` and are defined in **one
place** (the const block at the top of `interceptor.js` and the field list in
D-015 §3). Neither CE nor Codex hardcodes these strings from memory: the project
lead confirms them in a live network tab before wiring. The architecture holds
regardless of the exact strings.

## Consequences

- Completeness becomes a property of the data source, not of traversal luck.
- One new failure mode to monitor: interception silently stops working if ChatGPT
  changes the endpoint/shape. The completeness gate turns that into a visible
  `capture_complete=false` / 422 spike rather than a silent corpus poison — but
  someone must watch for it (future: a capture-health metric, same family as the
  zero-turn alert).
- The scroll-probe code stays, carrying a small maintenance cost, justified as the
  no-MAIN-world / unknown-shape safety net.
- Additive schema/migration only (optional columns, like D-013's StateVector
  fields) — back-compatible with existing rows, which read as
  `capture_complete = NULL` (treated as "unknown, fall back to balance gate").
