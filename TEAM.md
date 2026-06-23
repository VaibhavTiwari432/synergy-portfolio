
# TEAM.md - Current v3/v3.1 Update Pointer

**Read this first:** the current v3/v3.1 framework update is appended at the end
of this file. It supersedes historical reset/team references only where it is
more specific about the current active update and ownership.

---

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

## 9. Authorship ledger — uncommitted and recently committed (updated 2026-06-17)

**Purpose:** tracks who authored what in this branch so attribution is correct and no
agent's work is silently folded into another's commit (non-negotiable #21). Section is
updated at the close of each CE session.

### Committed on this branch (newest first)

| Commit | Author | Files | What |
|---|---|---|---|
| `cd3d648` `[Codex]` | Codex | `extension/content.js`, `extension/utils/payload_builder.js` | DOM hardening (data-message-id selectors), scroll-progress notifications, location-change auto-capture, D-015 §7 snapshot fields, D-015 §8 payload pass-through |
| `7f10fdf` `[CE]` | CE | `adr/0007-*`, `extension/interceptor.js`, `DISCREPANCY.md`, `TEAM.md` | ADR-0007 + D-015 spec + release-gate doc; interceptor.js shipped dormant |
| `cc30e4e` `[CE]` | CE | all Scope B + recoverability files | Scope B Phases 1–4 + recoverability Tracks 0–2 (migrations 001–007, worker, API, extension, panel) |

### CE-authored, uncommitted (this session)

| File | What it does |
|---|---|
| `extension/background.js` | `_analyseProgress` map + `_setAnalyseProgress()`; `SAF_ANALYSE_PROGRESS` handler (stores progress from content.js scroll notifications); progress state threaded through the entire analyse-now flow (capturing → ingesting → scoring → complete/error); `SAF_PANEL_GET_STATUS` and `SAF_PANEL_OPEN` include `analysisProgress` |
| `extension/panel/panel.html` | Added `id="pending-stage-label"` to the pending view status span |
| `extension/panel/panel.js` | `_renderAnalysisProgress()`, `_startAnalysisProgressPoll()` (700 ms), `_stopAnalysisProgressPoll()`; `inert` attribute for hidden views (keyboard/AT isolation); pending view polls `SAF_PANEL_GET_STATUS` for real progress instead of synthetic fill |
| `extension/injected_icon.js` | **DEFERRED — excluded from this commit (see note below).** `radarSvg()` + `normaliseProfile()` (8-dim mini radar in score view); `renderProgress()` (replaces static "analysing…" with a live progress bar); `actionButtons()` + `wireMiniNav()` (Analyse / Portfolio / Settings row); CSS for radar, progress bar, action-button layout. This IS CE work, but the file also carries an unrelated non-CE UI-polish layer in the working tree; the whole file is held back so the two can be separated cleanly later. |
| `src/db/queries.py` | `_intent_tag()`, `derive_turn_event_log()`, `replace_capture_artifacts()` — writes per-turn rows to `event_log` (char_count + intent_tag) and `raw_transcripts` (full text + retention_flag) transactionally on every ingest |
| `src/api/routers/ingest.py` | Calls `replace_capture_artifacts()` after `upsert_chat`; accepts `raw_retention_flag` in `IngestRequest` |
| `alembic/versions/008_capture_event_log_raw_transcripts.py` (new) | Creates `event_log` and `raw_transcripts` tables (CASCADE on chat delete, UNIQUE(chat_id, turn_index)); already applied (head=008) |

Verification (this session): 52 JS + 299 Python unit + 36 integration (16 DB-skipped)
all green; `node --check` clean on all 5 modified JS files; migration 008 confirmed
applied to dev DB.

### Ownership reassignment — D-015 §1–§6 bridge (CE built Codex-scope files)

**2026-06-17, project-lead decision:** the D-015 content.js bridge (§1–§6) was
authored by **CE**, not Codex, by explicit project-lead direction. `extension/content.js`
and `extension/utils/payload_builder.js` remain **Codex-owned** in §3 going forward; this
is a one-off reassignment for the bridge build, not a permanent ownership transfer. Recorded
here per #21 so the `[CE]` attribution on Codex-owned files is intentional and visible, not a
silent boundary violation. Future edits to these two files revert to Codex ownership.

CE-authored bridge work, uncommitted (this session, on Codex-owned files):
| File | What CE built |
|---|---|
| `extension/content.js` | `activePathFromMapping(convo)` (§2 active-path tree walk, fail-closed, reusable for export backfill §9); `saf-capture` postMessage consumer (`handleWindowMessage`, origin+source guard §1); `ingestInterception`/`emitInterception` feeding the **unchanged** `SAF_CAPTURE_READY → payload_builder → ingest` contract; dedupe-merge of the DOM live tail by `role:message_id` (§6); buffer-and-retry on mid-stream tail (§4); `model_slug` → `partner_model.model_id` with `family:"openai"` kept hardcoded (§5); scroll harvest demoted to fallback (`capture_method:"scroll_probe"`, `capture_complete:null` — §7 false-vs-null) and only run when no complete interception exists for the conversation |
| `extension/utils/payload_builder.js` | (no change this session — §8 pass-through already committed in `cd3d648`) |
| `extension/manifest.json` (CE-owned) | MAIN-world `interceptor.js` stanza at `document_start` — the D-015 RELEASE-GATE activation switch; lands now because the bridge consumer exists |
| `tests/extension/active_path.test.js` (new) | 7 tests for `activePathFromMapping`; centerpiece is a forked-conversation fixture proving only the active branch (root→`current_node`) is returned |
| `extension/tests/payload_builder.test.js`, `tests/extension/content.test.js` | alignment fixes (Codex-owned tests): selector snapshot → `data-message-id` to match committed `cd3d648`; capture-fields §8 pass-through coverage. Kept, not discarded — they track committed behaviour, not abandoned DOM logic |

Race fix landed: **D-016 → RESOLVED (ADR-0008)** — `interceptor.js` (document_start) could
fire before `content.js` attached its listener (document_idle), losing the initial page-load
fetch. Fixed with a cache-and-replay handshake: `interceptor.js` caches every conversation
payload and replays it once on a `ready-ping` from `content.js` (labelled `source_:
"cache_replay"`); `content.js` sends the ping then attaches its listener the moment consent
passes. Covered by `tests/extension/interception_race.test.js` (2 tests). This touched CE-owned
`interceptor.js` and Codex-owned `content.js` (same bridge reassignment as above).

### Commit-attribution plan (remaining work)
1. `[CE]` commit (THIS commit) — `[CE] Activate D-015 network-intercept bridge + D-016
   race fix`. Contains: the bridge (content.js consumer, manifest activation stanza,
   active_path test), the D-016 race fix (interceptor.js cache-and-replay, content.js
   ready-ping, interception_race test, ADR-0008), the analyse-progress UI on
   background.js/panel.js/panel.html, per-turn persistence (queries.py/ingest.py/migration
   008), the aligned tests, and the TEAM.md/DISCREPANCY.md doc updates. This is the
   activation commit: interception is live end-to-end (race-free) and `main` never carries
   an injected-but-unconsumed interceptor (RELEASE GATE).
   **Excluded from this commit (held back in the working tree):**
   - `extension/panel/panel.css` — an unrelated UI-polish layer, Codex-owned, not CE work.
   - `extension/injected_icon.js` — carries CE radar/progress work AND the same non-CE
     UI-polish layer entangled in one file; deferred whole so the two can be split into a
     proper `[Codex]`/`[CE]` attribution later. (Background.js/panel.js progress code ships
     here and degrades gracefully without the mini-panel's consumption of it.)

---

*Chief Engineer (Claude Code) owns this file. Start at Stage 0. Freeze contracts. Publish INTERFACES.md. Then unleash the juniors in parallel.*
# TEAM.md - Current v3/v3.1 Framework Update

**Current status - 2026-06-18:** the active work is no longer the original reset
plan. Scope A is implemented, Scope B extension/DB/worker work exists, and the
next framework update is driven by:

- `SAF_ARI_v3_ClaudeCode_Upgrades.md`
- `SAF_ARI_v3.1_ClaudeCode_Upgrades.md`
- `SAF_ARI_v3_SpecDelta_over_v2.2.md`
- `SAF_ARI_v3.1_SpecDelta_over_v3.md`
- the new top section of `AGENT_REBUILD_BRIEF_v3.md`

Claude Code remains Chief Engineer and owns shared contracts, DB, worker, API,
claims/reporting, migrations, cross-module integration, and all governance
gates. Codex Plus owns only explicitly assigned leaf modules/extension leaves.
Antigravity references below are historical unless this file is intentionally
edited to reassign work.

**Active rule for v3/v3.1:** build freeze-compliant fields, gates, artifacts,
and data-gated stubs. Do not rebuild the repo, do not add ontology, and do not
fit on the pilot/gold chats.

---

## Open Codex tasks — v3.21 (added 2026-06-23 by CE)

### TASK C-001 — AI-psychology precision conditioners (grounding + vigilance)
- **Status:** READY (contract landed). Spec: `PROPOSALS.md` P-002. Interfaces:
  `INTERFACES.md` §1.4 `classify_grounding` + §1.5 `score_vigilance`.
- **⚠ RE-READ REQUIRED:** `contracts/schemas.py` bumped **SCHEMA_VERSION → 1.2.0**
  (D-027). New types `GroundingFunction` + `VigilanceResult`. Re-read the contract
  before writing any code.
- **Build (Codex-owned leaves):**
  - `src/trait/grounding.py` → `classify_grounding(session, tags) -> list[GroundingFunction]`
  - `src/trait/vigilance.py`  → `score_vigilance(session, tags) -> VigilanceResult`
  - Unit tests beside each: {happy path, empty-session, absent-≠-zero}.
- **Bounds (CLAUDE.md):** evidence for EC/CA **precision only** — never a score
  value (#2); no new neuron/dimension/pillar/latent (#1); import only from
  `contracts.*` + stdlib; deterministic; no judge, no event-log writes.
- **Not in this task (CE follow-up):** the merge-side wiring (REPAIR-fraction /
  vigilance-score → EC/CA CI-widening in `src/merge/precision.py`, R2-audited).
  The leaves land first; CE wires precision after review.

---
