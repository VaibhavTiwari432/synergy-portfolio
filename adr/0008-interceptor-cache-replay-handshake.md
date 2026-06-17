# ADR-0008 — Interceptor cache-and-replay handshake (close the document_start/document_idle race)

- **Status:** Accepted
- **Date:** 2026-06-17
- **Decider:** Chief Engineer; implementation directly authorized by project lead
- **Resolves:** DISCREPANCY D-016
- **Extends:** ADR-0007 / D-015 §1 — adds two messages to the `saf-capture`
  postMessage protocol (`ready-ping`, and a `source_: "cache_replay"` label on a
  replayed `conversation_json`). The §1 shape, origin/source guards, and the §2
  active-path walk are unchanged.

## Context — the race ADR-0007 left open

ADR-0007 made MAIN-world conversation-JSON interception the primary capture path:
`interceptor.js` injects at `run_at: "document_start"` and patches `fetch`/`XHR`
immediately; `content.js` (isolated world) injects at `run_at: "document_idle"`
and attaches its `saf-capture` listener only **after** the asynchronous consent
(onboarding) check passes.

For a conversation already open when the extension loads (the common case: user
installs the extension, then opens the panel on the chat already on screen), the
page fetches `/backend-api/conversation/<id>` at document_start — before the
isolated-world listener exists. `window.postMessage` is **not buffered**, so that
first-load payload is delivered to zero listeners and lost. Capture then degrades
to the demoted DOM scroll-probe (`capture_complete: null` → legacy role-balance
gate): exactly the low-fidelity path ADR-0007 set out to retire, hit on the very
first conversation a new user sees. SPA navigations re-fetch and are caught; only
the **initial** load races. Filed as D-016.

## Decision

Add a one-shot cache-and-replay handshake across the world boundary.

**interceptor.js (MAIN world):**
1. Cache every valid `/backend-api/conversation/` payload in
   `cachedConversationPayload` (latest wins).
2. Post it immediately as before — the normal SPA-nav path where content.js is
   already listening and does not race. Unchanged behaviour.
3. Listen for `{ source: "saf-capture", kind: "ready-ping" }` (origin-guarded). On
   a ping, if the cache is non-empty, re-post it **once** with
   `source_: "cache_replay"`, then clear the cache (so a later ping never replays a
   stale tree).

**content.js (isolated world):** after the consent check passes (inside
`enableCapture`), `postMessage` a `ready-ping`, then attach the normal
`saf-capture` listener. `postMessage` delivery is asynchronous, so the listener is
in place before any replay can arrive; ordering is race-free.

The replayed payload carries `source_: "cache_replay"` purely so the fix's
effectiveness (rescued-from-cache vs. arrived-live) is measurable downstream. The
consumer (`activePathFromMapping` → `SAF_CAPTURE_READY` → ingest) treats a replay
identically to a live capture — same completeness proof, same `family:"openai"`
guard, same server gate. No new trust surface: the replay only re-sends data the
page already fetched for itself, back to the same origin.

## Consequences

- A conversation open at install time now gets high-fidelity interception instead
  of the DOM fallback. The scroll-probe remains, correctly, the secondary path for
  the genuinely un-interceptable cases (no fetch occurred during the session).
- The `saf-capture` protocol gains two messages; D-015 §1's "ignore unknown kinds"
  rule already makes both directions forward-compatible (content.js ignores
  non-`conversation_json` kinds; interceptor ignores non-`ready-ping` kinds), so no
  consumer breaks.
- Replays are bounded to one per ping and content.js sends one ping per
  `enableCapture`, so there is no replay storm and no loop (a replayed
  `conversation_json` is not a `ready-ping`).
- Tested in `tests/extension/interception_race.test.js`: a pre-cached conversation,
  interceptor at document_start, controller brought up at document_idle → the
  payload arrives labelled `cache_replay` and is ingested as `capture_method:
  "interception"`; a second ping is proven a no-op.

## Alternatives rejected

- **Attach the listener earlier (move content.js to document_start / before
  consent).** Violates consent gating — we must not listen for transcript data
  before the onboarding/consent check passes. Rejected.
- **Buffer in content.js and poll.** D-016 explicitly forbade a content-side
  polling workaround; the authoritative cache lives where the data is captured
  (MAIN world), and a handshake is O(1) vs. a polling loop. Rejected.
