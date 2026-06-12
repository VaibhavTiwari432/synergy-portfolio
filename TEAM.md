# TEAM.md — Multi-Agent Build Coordination
**The single source of truth for who builds what, in what order, against which contracts.**
Every agent reads this file at the start of every work session, before writing any code.

---

## 0. The team

| Agent | Role | What they own | Why |
|---|---|---|---|
| **Claude Code** | **Chief Engineer** | Contracts, architecture, the merge/precision layer, the claims engine, all integration, code review, discrepancy resolution | Strongest at cross-module reasoning, the parts where a mistake corrupts everything downstream |
| **Codex** | **Junior Dev A** | Self-contained, well-specified modules with clear inputs/outputs (extractors, classifiers, metric functions) | Good at bounded, contract-driven implementation |
| **Antigravity** | **Junior Dev B** | Self-contained modules in parallel with Codex (different files, never the same) | Good at bounded implementation; runs parallel to Codex |

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

**Gate:** ✅ PASSED 2026-06-12 — schemas import cleanly (15 contract tests green), `INTERFACES.md` published. Stage 1 is open: Codex and Antigravity may start (see `AGENT_KICKOFF.md`).

### STAGE 1 — Parallel build (Codex ∥ Antigravity ∥ Chief Engineer)
All three work simultaneously. Each owns disjoint files. No overlaps.

**CODEX builds (trait-side leaf modules):**
- [ ] `src/trait/tagger.py` — intent tagger (10 tags) → implements `tag_turns(session) -> list[TurnTags]`
- [ ] `src/trait/phase_classifier.py` → `classify_phases(session) -> list[Phase]`
- [ ] `src/trait/extractors/per_dimension/*.py` — deterministic extractors, one file per dimension
- [ ] `src/aggregate/normalize.py` → `normalize_counts(raw) -> NormalizedScores`
- [ ] Unit tests for each of the above

**ANTIGRAVITY builds (state-side + dynamics leaf modules):**
- [ ] `src/state/load_classifier.py` → `classify_load(session) -> list[LoadLabel]`
- [ ] `src/state/epistemic_classifier.py` → `classify_epistemic(session, tags) -> list[float]`
- [ ] `src/state/metacog_classifier.py` → `classify_metacog(session, tags) -> MetacogResult`
- [ ] `src/state/tomer_slope.py` → `tom_slope(session) -> float`
- [ ] `src/dynamics/transitions.py` — the 5 frozen transition metrics → `compute_transitions(eventlog) -> TransitionMetrics`
- [ ] `src/dynamics/overlay.py` — regime overlay (rules only) → `regime_overlay(eventlog) -> RegimeResult`
- [ ] Unit tests for each of the above

**CHIEF ENGINEER builds (the spine + everything multi-module):**
- [ ] `src/ingestion/adapters/*.py` — all adapters (Claude, ChatGPT, plaintext)
- [ ] `src/ingestion/canonical.py` — canonical session builder
- [ ] `src/eventlog/*.py` — schema, writer, queries (the substrate everyone reads)
- [ ] `src/trait/judge/*.py` — the Gemini judge (highest-risk, most expensive to get wrong)
- [ ] `src/trait/evidence.py` — EC provenance + theater check
- [ ] `src/state/estimator.py` — StateEstimator interface + ProxyEstimator (assembles Antigravity's classifiers)
- [ ] `src/aggregate/softmin.py` — soft non-compensatory aggregation
- [ ] `src/aggregate/gates.py` — scorability + state validity gates
- [ ] **`src/merge/precision.py`** — THE precision-weighting merge (state CI → trait). Single most important file.
- [ ] `src/dynamics/reactions.py` — E→R signatures + Dirichlet pooling (depends on eventlog + tags)
- [ ] `src/sustainability/*.py` — debt tracker, EWMA, λ stub
- [ ] `src/claims/*.py` — rungs, tier engine, report
- [ ] `src/api/*.py` — FastAPI app + routes
- [ ] `calibration/runner.py` — the MAE ratchet

### STAGE 2 — Integration + ratchet (Chief Engineer, juniors on standby for fixes)
- [ ] Wire all leaf modules into the pipeline
- [ ] Run calibration → **overall MAE ≤ 0.2994 gate**
- [ ] Contract tests (tier gating, forbidden words, rung tags)
- [ ] If a leaf module fails its contract → file a discrepancy (§5), assign back to its owner

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
| `src/state/{load,epistemic,metacog}_classifier.py`, `tomer_slope.py` | Antigravity | Only CE |
| `src/dynamics/{transitions,overlay}.py` | Antigravity | Only CE |
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
# src/state/load_classifier.py  — OWNER: Antigravity
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
- When Claude Code is throttled: the Chief Engineer's *current* task pauses, but Codex + Antigravity keep building leaf modules against the already-frozen contracts (this is why Stage 0 must finish first — it unblocks days of parallel junior work).
- When a junior is throttled: its tasks wait; the other junior + Chief Engineer continue. Leaf modules are independent, so one stalling never blocks another.
- **Never** have a throttled agent's work picked up by another agent mid-file. Ownership is fixed. A stalled task waits for its owner or gets formally reassigned by the Chief Engineer in `TEAM.md` (with the file moved in the ownership map).

**The unlock:** because everything is contract-driven and file-isolated, total throughput ≈ sum of all three agents' available capacity, not the bottleneck of any one. That is the entire point.

---

## 8. Definition of done (v1 — full technical implementation, extension debated later)

- [ ] All Stage 0 contracts frozen
- [ ] All Stage 1 leaf modules built + unit-green (Codex + Antigravity)
- [ ] All Stage 1 spine modules built (Chief Engineer)
- [ ] Pipeline integrated end-to-end on the 28 gold chats
- [ ] **Overall MAE ≤ 0.2994** (the ratchet)
- [ ] CSPC proxies produce state strips on all 28 chats
- [ ] v2.2 dynamics (FTM, 5 metrics, overlay) compute on all 28 chats
- [ ] Sustainability layer produces debt flags + S_human on all 28 chats
- [ ] Claims engine rung-tags everything; forbidden-word + tier contract tests green
- [ ] `POST /v1/sessions` + `GET /v1/sessions/{id}/score` return a full valid response

**Not in v1 scope (debate later):** browser extension, portfolio UI, self-rating collection, feedback loop, multi-store sync. The API is the deliverable. It runs on the 28 chats and proves the framework computes.

---

*Chief Engineer (Claude Code) owns this file. Start at Stage 0. Freeze contracts. Publish INTERFACES.md. Then unleash the juniors in parallel.*
