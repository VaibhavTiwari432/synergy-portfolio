
# TEAM.md — Multi-Agent Build Coordination
**The single source of truth for who builds what, in what order, against which contracts.**
Every agent reads this file at the start of every work session, before writing any code.

---

## 0. The team

| Agent | Role | What they own | Why |
|---|---|---|---|
| **Claude Code** | **Chief Engineer** | Contracts, architecture, DB layer, worker, all API routers, panel UI, portfolio, code review, discrepancy resolution | Strongest at cross-module reasoning; owns everything where a mistake corrupts downstream users |
| **Codex Plus** | **Junior Dev A** | Scope A: all trait/state/dynamics leaf modules. Scope B extension leaves: content.js, utils/storage.js, utils/payload_builder.js, panel.css | Good at bounded, contract-driven implementation |

> **Team change 2026-06-12:** Antigravity left the team.
> **Team update 2026-06-14:** Scope B build started. Codex owns the three extension
> leaf JS files and panel.css (bounded, selector-driven). CE owns manifest.json,
> background.js, utils/api_client.js, panel.html/js, portfolio view, all
> DB/worker/API code. Same rule: no two agents ever edit the same file.

**The one rule that makes this work:** *Junior devs build leaf modules against frozen contracts. The Chief Engineer owns every file that more than one module depends on.* No two agents ever edit the same file in the same session.

---

## 1. The dependency truth (read before assigning anything)

The framework is NOT a linear pipeline. State and trait run **in parallel** off the event log:

```
                    ┌──────────────────┐
                    │  EVENT LOG       │  ← everything reads from here
                    └────────┬─────────┘
                  ┌──────────┴───────────┐
                  ▼                      ▼
         ┌─────────────────┐   ┌──────────────────┐
         │ STATE channel   │   │ TRAIT channel    │   ← THESE TWO ARE INDEPENDENT
         │ (CSPC proxies)  │   │ (ARI extraction) │     build in parallel
         └────────┬────────┘   └────────┬─────────┘
                  └──────────┬───────────┘
                             ▼
                  ┌──────────────────────┐
                  │ PRECISION MERGE       │  ← state widens trait CI here
                  │ (Chief Engineer only) │     ONLY meeting point
                  └──────────┬───────────┘
                             ▼
                  ┌──────────────────────┐
                  │ AGGREGATION → v2.2    │
                  │ → SUSTAINABILITY      │
                  │ → CLAIMS GATE         │
                  └──────────────────────┘
```

**CSPC is NOT computed before ARI.** They are siblings. State only conditions trait *precision* (CI width), never trait score value. This is why two agents can build state and trait simultaneously.

---

## 2. Build order — contracts first, then parallel, then merge

### STAGE 0 — Chief Engineer ONLY (everyone else waits)
Nothing else starts until these are frozen and committed.

- [x] `contracts/schemas.py` — `Event`, `CanonicalSession`, `PartnerModel`, `DimensionScore`, `StateVector`, `ScoreResponse` (all Pydantic v2) — v1.0.0
- [x] `contracts/contract_table.yaml` — carried forward, verified loads (107 neurons, per-dim counts green)
- [x] `contracts/claims_table.yaml` — tier × permitted/forbidden (+ `probe_schema.yaml`)
- [x] `contracts/event_taxonomy.py` — the 6 frozen event types as constants (+ N-FIRE, window k=3, cell gate ≥3)
- [x] `contracts/intent_tags.py` — the 10 intent tags as constants
- [x] `INTERFACES.md` — the function signature every leaf module must implement (see §4) — v1.0.0
- [x] Skeleton repo (all dirs, empty `__init__.py`, failing-stub tests — 43 xfail stubs in `tests/unit/test_stage1_stubs.py`)

**Gate:** ✅ PASSED 2026-06-12 — schemas import cleanly (15 contract tests green), `INTERFACES.md` published. Stage 1 is open: Codex may start (see `AGENT_KICKOFF.md`).

### STAGE 1 — Parallel build (Codex ∥ Chief Engineer)
Disjoint files. No overlaps.

**CODEX builds (all leaf modules — trait + state + dynamics):**
- [x] `src/trait/tagger.py` — intent tagger (10 tags) → `tag_turns(session) -> list[TurnTags]` (33 tests)
- [x] `src/trait/phase_classifier.py` → `classify_phases(session, tags) -> list[Phase]` (18 tests)
- [x] `src/trait/extractors/per_dimension/*.py` — 8 files; 9 deterministic neurons (AL-08, PR-02/05/07/14, EC-06/07/09, ES-01); CS/CD/AUI/CA structurally empty per contract table (20 tests incl. contract-fix coverage)
- [x] `src/aggregate/normalize.py` → `normalize_counts(...) -> NormalizedScores` (6 tests)
- [x] `src/state/load_classifier.py` → `classify_load(session) -> list[LoadLabel]` — relative-z, never absolute
- [x] `src/state/epistemic_classifier.py` → `classify_epistemic(session, tags) -> list[float]`
- [x] `src/state/metacog_classifier.py` → `classify_metacog(session, tags) -> MetacogResult` (surrender = 3+ accept-run)
- [x] `src/state/tomer_slope.py` → `tom_slope(session) -> (series, slope|None)` (14 tests for the four state leaves)
- [x] `src/dynamics/transitions.py` — the 5 frozen transition metrics, cell-gated
- [x] `src/dynamics/overlay.py` — regime overlay (rules only; no CSPC vocabulary) (12 tests for the two dynamics leaves)
- [x] Unit tests for each of the above

**CHIEF ENGINEER builds (the spine + everything multi-module):**
- [x] `src/ingestion/adapters/*.py` — all adapters (Claude, ChatGPT, plaintext, + internal gold_json) — 26-chat lossless round-trip green
- [x] `src/ingestion/canonical.py` — canonical session builder
- [x] `src/eventlog/*.py` — schema, writer, queries (9 property tests: append-only, ordered, idempotent)
- [x] `src/trait/judge/*.py` — dimension-grain v2.0 (v1.3 anchors reused), Gemini + OpenRouter fallback, 16 tests
- [x] `src/trait/evidence.py` — EC provenance + theater check (7 tests)
- [x] `src/state/estimator.py` — StateEstimator interface + ProxyEstimator (assembles Codex's state classifiers; 6 tests)
- [x] `src/aggregate/softmin.py` — soft non-compensatory aggregation (4 pillars, p=−2)
- [x] `src/aggregate/gates.py` — n_eff τ=1 + scorability + state validity gates (11 tests with softmin)
- [x] **`src/merge/precision.py`** — THE precision-weighting merge (state CI → trait). 9 synthetic-fixture tests: values never move.
- [x] `src/dynamics/reactions.py` — E→R signatures + Dirichlet pooling + cell gating (+ `reliability_map.py` scaffold; 8 tests)
- [x] `src/sustainability/*.py` — Ŝ_human, EWMA, λ stub, probe schema (12 tests)
- [x] `src/claims/*.py` — rungs, tier engine, report (forbidden-word scan; minor protection; 14 tests)
- [x] `src/api/*.py` — FastAPI app + routes + auth (fails closed) + SQLite store (10 contract tests)
- [x] `calibration/runner.py` — the MAE ratchet (headline vs shadow per D-001; 7 tests)

### STAGE 2 — Integration + ratchet ✅ CLOSED 2026-06-12 (ADR-0006)
- [x] Leaf modules load into the pipeline (optional-import wiring resolves all 17; hard-wiring per D-003 = item below)
- [x] Hard-wire leaves: phases + extractors + normalize into the trait evidence path (D-003)
- [x] Run calibration → **Gate A: overall MAE ≤ 0.2994 AND coverage ≥ 80% of the headline pool** — ✅ PASSED with prompt v2.1: shadow 0.2368 (n=26), headline 0.2502 (n=23), coverage 100%/100%, all per-dim ≤ 0.375 (`calibration/results/stage2_final.json`)
- [x] Contract tests (tier gating, forbidden words incl. stem derivatives, rung tags, minor protection) — green (Gate B: 49 + 7 stem tests, explicit run)
- [x] Synthetic fixtures (precision/CI, state caveat, EWMA modes, FTM gating, no-latent audit) — green (Gate C: 60 tests, explicit run)
- [x] `POST /v1/sessions` → `GET /v1/sessions/{id}/score` full valid response — ✅ Gate D PASSED live (real Gemini judge, fresh non-gold 14-turn chat, 19/19 checks — `calibration/gate_d_smoke.py`)
- [x] Re-judge gc-003/016/018 via `openai_family_judge()` — ✅ DONE 2026-06-12 (D-005 resolved): openai/gpt-oss-120b:free via OpenRouter (zero-credit key → free OpenAI-family model); headline pool restored to n=26, MAE 0.2505, ratchet PASS (`stage2_rejudged.json`)
- [x] If a leaf module fails its contract → file a discrepancy (§5), assign back to its owner — done once (PR-02/PR-05/EC-07/EC-09 fixed by Codex, verified by CE)

### SCOPE B — Browser Extension + DB Layer (build started 2026-06-14)
Reference: `EXTENSION_BUILD_PROMPT.md` (read entirely before writing any file).
All 21 non-negotiables in CLAUDE.md remain binding for every line of Scope B code.

#### PHASE 1 — DB + Worker + Ingest endpoints ✅ CLOSED 2026-06-14 (CE)
- [x] `infra/docker-compose.yml` — Postgres 16, db=saf_brain, port=5432
- [x] `alembic/` — Alembic setup + migration 001 (four tables: raw_chats, telemetry, scores, feedback + all indexes + CASCADE constraints)
- [x] `src/db/connection.py` — async asyncpg pool with JSON/JSONB codecs registered
- [x] `src/db/queries.py` — all DB operations (upsert, claim, status update, cascade delete, count)
- [x] `contracts/self_rating_prompt.txt` — versioned self-rating prompt (v1.0)
- [x] `src/worker/scorer.py` — polling worker (3s interval, atomic claim, direct pipeline import, `python -m src.worker.scorer`)
- [x] `src/worker/self_rater.py` — async self-rater (1s delay, key-safe, skip-on-absent)
- [x] `src/api/routers/ingest.py` — POST /v1/ingest + GET /v1/users/{ref}/chats
- [x] `src/api/routers/users.py` — GET .../score, POST .../feedback, GET .../portfolio, DELETE /v1/users/{ref}
- [x] `src/api/main.py` — updated: lifespan (Postgres pool), Scope B routers included, Scope A unchanged
- [x] `tests/integration/test_phase1_gate.py` — G1–G5 gate tests (run with PHASE1_GATE=1)
- **Gate:** ✅ PASSED 2026-06-14 — G1–G5 all green (4/4), 348 total tests passed.
  PostgreSQL 17 installed natively (winget). DB: saf_brain on localhost:5432.
  `PHASE1_GATE=1 pytest tests/integration/test_phase1_gate.py -v`

#### PHASE 2 — Extension Core ✅ CLOSED 2026-06-14 (CE + Codex)
**CE builds:**
- [x] `extension/manifest.json` — MV3, host perms, tabs+alarms+storage+activeTab+scripting
- [x] `extension/background.js` — service worker: ingest, collector bag, health poll (1 min alarm), all panel message handlers
- [x] `extension/utils/api_client.js` — IIFE global `SAFApiClient`, all API calls, key-safe logging
- [x] `extension/panel/panel.html` — all views: onboarding-welcome, onboarding-setup, pending, main, portfolio, settings; Section 1 (data-order=1) always before Section 2 (data-order=2); no composite element; minor-guard dormant
- [x] `extension/panel/panel.js` — full panel logic: forbidden-word guard (_safeText), minor protection guard, report.observed→Section 1, report.inferred→Section 2, regime bar SVG, flag pills, radar SVG toggle, feedback form, portfolio view, settings, 5s pending poll

**CODEX builds:**
- [x] `extension/content.js` — MutationObserver, turn capture, telemetry, selector fallbacks, IIFE/SAFContentCapture
- [x] `extension/utils/storage.js` — IIFE/SAFStorage with OPENAI_API_KEY key name
- [x] `extension/utils/payload_builder.js` — IIFE/SAFPayloadBuilder, source/role normalisation
- [x] `extension/panel/panel.css` — styling (Codex, 795 lines, complete 2026-06-14)

**Key implementation details:**
- `background.js` uses `importScripts()` to load IIFE utils (classic service worker, not `"type":"module"`)
- `api_client.js` reads endpoint/key from `SAFStorage` on every call (user can change settings without reload)
- `openai_api_key` (matches `SAFStorage.STORAGE_KEYS.OPENAI_API_KEY`) passed in ingest `metadata` → worker reads `tel['metadata'].get('openai_api_key')` for self-rater
- Panel routes all API calls through background.js via `chrome.runtime.sendMessage`; panel never talks to API directly

**Gate:** Load unpacked extension on chat.openai.com. 10-turn real conversation. Verify ingest called, DB pending, worker scores, health_status="ok".

#### PHASE 3 — Panel UI Gate (NOT STARTED)
After `panel.css` complete:
- Open panel after a scored conversation
- Section 1 has text (strengths), Section 2 has text (growth nudge) — in that order
- Regime bar renders, health dot shows green, radar appears under toggle
- No forbidden words visible, no composite number anywhere
- "Analyse now" triggers capture + pending state

#### PHASE 4 — Portfolio + Feedback + Flywheel ✅ CLOSED 2026-06-14 (CE)
**CE builds:**
- [x] Portfolio view — built in Phase 2 (panel.js `_loadPortfolio`, panel.html `#view-portfolio`): radar means, archetype, trajectory direction, growth summary, session count, DESIGNED rung
- [x] Feedback prompt — built in Phase 2 (panel.html `#feedback-section`): once per scored chat, disappears on submit, 280-char limit, match_rating yes/partial/no
- [x] New chat notification — badge `…` (blue) + tooltip `"N turns saved · analysing…"` on successful ingest; badge `!` (red) on API error; badge cleared when panel opens
- [x] `extension/utils/self_rating_prompt.js` — IIFE/SAFSelfRatingPrompt: `PROMPT_TEMPLATE` (verbatim copy of `contracts/self_rating_prompt.txt`), `buildPrompt(transcript)`, `formatTurns(turns)` for transparency display

**Extension JS tests (27/27):**
```
node --test extension/tests/payload_builder.test.js extension/tests/self_rating_prompt.test.js
```
Covers: all source/role normalisation, turn filtering, family="openai" enforcement, forbidden-word absence, prompt template integrity.

**Gate:** 3+ real conversations analysed. Portfolio shows trajectory. Feedback works. Clear-all removes everything server-side and local.

---

## 3. File ownership map — NEVER edit a file you don't own

| Path | Owner | Anyone else edits? |
|---|---|---|
| `contracts/**` | Chief Engineer | NEVER |
| `INTERFACES.md`, `TEAM.md` | Chief Engineer | NEVER |
| `src/eventlog/**` | Chief Engineer | NEVER |
| `src/ingestion/**` | Chief Engineer | NEVER |
| `src/merge/**` | Chief Engineer | NEVER |
| `src/claims/**` | Chief Engineer | NEVER |
| `src/api/**` | Chief Engineer | NEVER |
| `src/trait/judge/**` | Chief Engineer | NEVER |
| `src/trait/tagger.py`, `phase_classifier.py`, `extractors/**` | Codex | Only CE, only to fix a filed discrepancy |
| `src/aggregate/normalize.py` | Codex | Only CE |
| `src/state/{load,epistemic,metacog}_classifier.py`, `tomer_slope.py` | Codex | Only CE |
| `src/dynamics/{transitions,overlay}.py` | Codex | Only CE |
| `src/aggregate/{softmin,gates}.py` | Chief Engineer | NEVER |
| `src/sustainability/**` | Chief Engineer | NEVER |
| `src/db/**` | Chief Engineer | NEVER |
| `src/worker/scorer.py` | Chief Engineer | NEVER |
| `src/worker/self_rater.py` | Chief Engineer | NEVER |
| `src/api/routers/**` | Chief Engineer | NEVER |
| `infra/**` | Chief Engineer | NEVER |
| `alembic/**` | Chief Engineer | NEVER |
| `extension/manifest.json` | Chief Engineer | NEVER |
| `extension/background.js` | Chief Engineer | NEVER |
| `extension/utils/api_client.js` | Chief Engineer | NEVER |
| `extension/panel/panel.html` | Chief Engineer | NEVER |
| `extension/panel/panel.js` | Chief Engineer | NEVER |
| `extension/content.js` | Codex | Only CE, only to fix a filed discrepancy |
| `extension/utils/storage.js` | Codex | Only CE |
| `extension/utils/payload_builder.js` | Codex | Only CE |
| `extension/panel/panel.css` | Codex | Only CE |
| `tests/**` next to a module | That module's owner | — |

**If you need a change in a file you don't own:** do NOT edit it. File a discrepancy in `DISCREPANCY.md` (§5). The owner makes the change.

---

## 4. The interface contract (how leaf modules stay compatible)

Every leaf module implements EXACTLY the signature in `INTERFACES.md`. It receives frozen schema types and returns frozen schema types. It does NOT:
- import from another leaf module (only from `contracts/`)
- reach into the event log writer (only read via `eventlog/queries.py`)
- invent its own data structures for things that have a schema

Example interface entry (Chief Engineer authors these in `INTERFACES.md`):
```python
# src/state/load_classifier.py  — OWNER: Codex
def classify_load(session: CanonicalSession) -> list[LoadLabel]:
    """One LoadLabel per human turn.
    LoadLabel ∈ {LOW_LOAD, HIGH_ICL, HIGH_ECL, FATIGUE}.
    Reads session.turns only. No event log writes. No judge calls."""
```

If the interface is ambiguous → ask the Chief Engineer in `DISCREPANCY.md` BEFORE coding, not after.

---

## 5. Discrepancy protocol — the common place to resolve conflicts

When ANY agent hits one of these, it stops and writes an entry in `DISCREPANCY.md`:
- a contract/schema seems wrong or insufficient
- two modules need data the interface doesn't pass
- a test fails because of another module's output
- an interface is ambiguous
- a non-negotiable seems to block a needed implementation

**Entry format (append to `DISCREPANCY.md`):**
```
## D-NNN  [OPEN]  — <one-line title>
- Raised by: <agent>
- File(s): <paths>
- Problem: <what's blocking, concretely>
- Proposed fix: <your suggestion, if any>
- Decision: <CHIEF ENGINEER fills this — the resolution>
- Status: OPEN → RESOLVED
```

**Resolution rules:**
- Only the **Chief Engineer (Claude Code)** marks a discrepancy RESOLVED and decides the fix.
- If the fix touches a contract → Chief Engineer updates the contract, bumps a version note, and tells both juniors to re-read.
- Juniors do NOT resolve their own discrepancies or work around them silently. A silent workaround is the one failure mode that breaks the whole team.
- The Chief Engineer reviews `DISCREPANCY.md` at the start of every session before writing new code.

---

## 6. Session ritual (every agent, every session)

1. `git pull` (or sync the workspace) — get the latest contracts.
2. Read `TEAM.md` §2 task board — what's mine, what's done, what's blocked.
3. Read `DISCREPANCY.md` — anything OPEN that affects me? (Chief Engineer: resolve them.)
4. Read `INTERFACES.md` for the exact signature of what I'm building.
5. Build ONLY my owned files. Write tests next to them.
6. Run my unit tests green before handing off.
7. Check the box in `TEAM.md` §2 + commit with a clear message: `[CODEX] tagger.py: 10 intent tags + 15 tests green`.
8. If blocked → `DISCREPANCY.md`, then move to another unblocked task.

---

## 7. Harnessing limits (the practical reason for three agents)

Each tool has usage limits. The point of three is to **keep building when one is throttled**, not to parallelize for its own sake.

**Limit-aware routing:**
- The **critical path** runs through the Chief Engineer (contracts, merge, judge, integration). Reserve Claude Code capacity for these — don't spend it on leaf modules a junior can do.
- When Claude Code is throttled: the Chief Engineer's *current* task pauses, but Codex keeps building leaf modules against the already-frozen contracts (this is why Stage 0 must finish first — it unblocks days of parallel junior work).
- When Codex is throttled: its tasks wait; the Chief Engineer continues on spine work. Leaf modules are independent, so one stalling never blocks another.
- **Never** have a throttled agent's work picked up by another agent mid-file. Ownership is fixed. A stalled task waits for its owner or gets formally reassigned by the Chief Engineer in `TEAM.md` (with the file moved in the ownership map).

**The unlock:** because everything is contract-driven and file-isolated, total throughput ≈ sum of both agents' available capacity, not the bottleneck of either one. That is the entire point.

---

## 8. Definition of done (v1 — full technical implementation, extension debated later)

- [x] All Stage 0 contracts frozen (v1.1.0)
- [x] All Stage 1 leaf modules built + unit-green (Codex)
- [x] All Stage 1 spine modules built (Chief Engineer)
- [ ] Pipeline integrated end-to-end on the 26 gold chats (ADR-0003: corpus is n=26) — pending hard-wiring (D-003) + live calibration run
- [ ] **Overall MAE ≤ 0.2994 with coverage ≥ 80%** (the ratchet + D-002 coverage gate)
- [ ] CSPC proxies produce state strips on all 26 chats (live run pending)
- [ ] v2.2 dynamics (FTM, 5 metrics, overlay) compute on all 26 chats (live run pending)
- [ ] Sustainability layer produces debt flags + S_human on all 26 chats (live run pending)
- [x] Claims engine rung-tags everything; forbidden-word + tier contract tests green
- [x] `POST /v1/sessions` + `GET /v1/sessions/{id}/score` return a full valid response (contract-tested with faked judge; live re-verify at Stage-2 close)

**Not in v1 scope (debate later):** browser extension, portfolio UI, self-rating collection, feedback loop, multi-store sync. The API is the deliverable. It runs on the 26 gold chats and proves the framework computes.

---

## 9. Uncommitted-tree authorship ledger (2026-06-17)

**Why this section exists:** the entire Scope B layer (Phases 1–4 above, all CLOSED)
AND the recoverability work (Tracks 0–2, `DISCREPANCY.md` D-013) are complete and
green in the working tree but were **never committed** — `git log` confirms no
Scope-B file (`src/db/queries.py`, etc.) exists on any ref. Before the closing
commits land, this ledger records **who authored what**, so attribution is correct
and no agent's work is silently folded into another's commit (#21). A CE audit
(2026-06-17) verified that **none of the recoverability Track 0–2 edits touched a
Codex-owned file** — the ownership boundary in §3 held throughout.

### Codex-authored, uncommitted (Scope B extension leaves + tests)
Built 2026-06-14 (Phase 2/4 board, §2), contract-driven against `EXTENSION_BUILD_PROMPT.md`:

| File | What it does | Why (source) |
|---|---|---|
| `extension/content.js` | MutationObserver turn capture, telemetry, selector fallbacks (IIFE `SAFContentCapture`) | Phase 2 leaf; selector-driven, bounded. **+ D-011 fix (2026-06-17):** zero-completed-pairs hard floor so forced "Analyse now" overrides timing but never the content floor. |
| `extension/utils/storage.js` | `SAFStorage` wrapper over chrome.storage | Phase 2 leaf. Note: still defines an `OPENAI_API_KEY` slot — harmless post-Track-0 (CE's `background.js` no longer sends it); slot removal is a future Codex cleanup, not a blocker. |
| `extension/utils/payload_builder.js` | `SAFPayloadBuilder`, source/role normalisation, family=openai enforcement | Phase 2 leaf. |
| `extension/panel/panel.css` | Panel styling (≈795 lines) | Phase 2 leaf. |
| `tests/extension/content.test.js` | content.js capture + D-011 regressions | Tests next to a Codex module → Codex-owned (§3). |
| `tests/extension/storage.test.js`, `tests/extension/payload_builder.test.js`, `extension/tests/payload_builder.test.js` | leaf-module tests | Codex-owned. |

Codex's other Scope-B contributions were **diagnoses, not code in CE files**: Codex
raised D-006/D-007/D-008/D-009/D-010 (live-capture requeue, analyse-now reporting
bugs, HTTP error labels); the fixes landed in CE-owned `background.js`/`panel.js`/
`queries.py` by CE. The one Codex *implementation* request from CE was D-011, above.

**D-011 review verdict (CE, 2026-06-17): RESOLVED.** The hard floor at
`content.js:487` precedes the `!force` debounce, matching the agreed semantic
("forced overrides timing, never minimum content"); 53 extension JS tests green
incl. the three forced-capture regressions. Marked RESOLVED in `DISCREPANCY.md`.

### CE-authored, uncommitted (everything else in the tree)
`src/db/**`, `src/worker/**`, `alembic/**`, `infra/**`, `src/api/routers/**`,
`src/provenance.py`, CE extension files (`manifest.json`, `background.js`,
`api_client.js`, `panel.html/js`, `injected_icon.js`, `self_rating_prompt.js`),
DB integration tests, calibration scripts — plus the recoverability deltas in
tracked files (`contracts/schemas.py`, `pipeline.py`, `precision.py`,
`estimator.py`, `parser.py`).

### Capture-strategy change (ADR-0007 / D-015, 2026-06-17) — split build, in progress
The scroll-probe cannot beat ChatGPT virtualization; primary capture moves to
MAIN-world conversation-JSON interception with a completeness gate. Option-2 split
(project lead): CE builds the spine, Codex authors the content.js bridge.

**CE-authored, uncommitted (this change):**
| File | What it does |
|---|---|
| `extension/interceptor.js` (new) | MAIN-world fetch/XHR patch; matches the conversation endpoint; postMessage `saf-capture` per D-015 §1; one-shot field-presence shape warning. Ships **unwired** — see release gate. |
| `extension/manifest.json` | unchanged for now — the MAIN-world activation stanza is **deferred to the joint bridge commit** (D-015 RELEASE GATE) so `main` never injects an interceptor with no consumer |
| `extension/utils/api_client.js` | carries structured (object) 422 `detail` → `detailData` + message |
| `extension/background.js` | short-circuits `capture_complete === false` before the network call |
| `src/api/routers/ingest.py` | 4 optional capture fields; structured-422 completeness quarantine |
| `src/db/queries.py` | `capture_completeness_error()` (false=block / null=defer) + 3 columns on `upsert_chat` |
| `alembic/versions/007_capture_completeness.py` (new) | columns + CHECK enforcing the invariant at rest |
| `src/worker/scorer.py` | worker double-check refuses to score incomplete rows |
| `tests/unit/test_capture_validation.py`, `tests/extension/interceptor.test.js` (new) | gate + interceptor coverage |

Verification (2026-06-17): 295 unit + 53 existing-extension + 6 interceptor JS +
11 integration (Phase-1 G1–G5, rescore R1–R6) green; migration 007 applied to dev
DB (head=007), CHECK confirmed rejecting `complete=true` with `captured<expected`.

**Codex scope (D-015 §1–§9, NOT yet built):** `extension/content.js` (consume the
`saf-capture` postMessage, walk the active path `current_node`→root, dedupe-merge
the live tail by stable key — never append-only, buffer-and-retry the mid-stream
tail, demote the scroll-probe to fire only when `capture_complete` is not proven)
and `extension/utils/payload_builder.js` (pass the four capture fields through).
Hand-off note for Codex: the `false`-vs-`null` distinction in §7 is load-bearing —
fallback paths set `null`, never `false`. Confirm the §3 VERIFY field names in a
live network tab before wiring.

### Commit-attribution plan (follows the existing `[Codex]`/`[CE]` precedent)
1. `[Codex]` commit — the reviewed extension leaves + tests above (D-011 resolved).
2. `[CE]` commit(s) — Scope B base, then recoverability Tracks 0–2, then the
   ADR-0007/D-015 capture spine (CE files above).
3. `[Codex+CE]` JOINT activation commit — D-015 content.js bridge + payload
   pass-through + the manifest MAIN-world stanza, landing together. This is the
   first commit where interception is live end-to-end; `main` never passes through
   an injected-but-unconsumed interceptor (D-015 RELEASE GATE).

---

*Chief Engineer (Claude Code) owns this file. Start at Stage 0. Freeze contracts. Publish INTERFACES.md. Then unleash the juniors in parallel.*
