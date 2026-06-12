# TEAM.md — Multi-Agent Build Coordination
**The single source of truth for who builds what, in what order, against which contracts.**
Every agent reads this file at the start of every work session, before writing any code.

---

## 0. The team

| Agent | Role | What they own | Why |
|---|---|---|---|
| **Claude Code** | **Chief Engineer** | Contracts, architecture, the merge/precision layer, the claims engine, all integration, code review, discrepancy resolution | Strongest at cross-module reasoning, the parts where a mistake corrupts everything downstream |
| **Codex Plus** | **Junior Dev A** | All leaf modules: trait-side (tagger, phase classifier, extractors, normalize) AND state/dynamics-side (state classifiers, transitions, overlay) | Good at bounded, contract-driven implementation |

> **Team change 2026-06-12:** Antigravity left the team. All its assignments
> (state + dynamics leaves) transferred to Codex Plus effective immediately.

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

### STAGE 2 — Integration + ratchet (Chief Engineer, Codex on standby for fixes)
- [x] Leaf modules load into the pipeline (optional-import wiring resolves all 17; hard-wiring per D-003 = item below)
- [ ] Hard-wire leaves: phases + extractors + normalize into the trait evidence path (D-003)
- [ ] Run calibration → **Gate A: overall MAE ≤ 0.2994 AND coverage ≥ 80% of the headline pool** (coverage gate per D-002: a chat with judge_unavailable or <4 valid dims is excluded from MAE and counted against coverage; low coverage fails the gate regardless of MAE)
- [x] Contract tests (tier gating, forbidden words incl. stem derivatives, rung tags, minor protection) — green (Gate B)
- [x] Synthetic fixtures (precision/CI, state caveat, EWMA modes, FTM gating, no-latent audit) — green (Gate C)
- [x] `POST /v1/sessions` → `GET /v1/sessions/{id}/score` full valid response — green in contract tests (Gate D; re-verify against live judge at close)
- [ ] Re-judge gc-003/016/018 via `openai_family_judge()` (D-001/D-003)
- [ ] If a leaf module fails its contract → file a discrepancy (§5), assign back to its owner — done once (PR-02/PR-05/EC-07/EC-09 fixed by Codex, verified by CE)

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

*Chief Engineer (Claude Code) owns this file. Start at Stage 0. Freeze contracts. Publish INTERFACES.md. Then unleash the juniors in parallel.*
