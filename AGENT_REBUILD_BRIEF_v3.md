# SAF/ARI Rebuild Brief — v3 (Multi-Agent Integrated)
**The single mission file. Drop in repo root. All three agents read this first.**

**Version:** 3.0 — full-framework technical implementation, multi-agent build structure integrated.
**Scope A (NOW):** the chat analyser — full v2.2 framework computing end-to-end as an API, calibrated on the 28 gold chats. **Scope B (LATER, decisions locked in §9):** browser extension + portfolio. Scope B is debated after Scope A ships.
**Authoritative spec:** `SAF_ARI_Final_Master_Compilation_v2_2.md` (uploaded, read end-to-end). v2.1 / v2 / v1 docs are working history; where they conflict, v2.2 wins. Where this brief conflicts with the spec: **this brief wins on scope** (what to build now), **the spec wins on correctness** (how it must behave).
**Team files:** `TEAM.md` (task board + ownership), `INTERFACES.md` (frozen signatures — Chief Engineer authors in Stage 0), `DISCREPANCY.md` (conflict log), `AGENT_KICKOFF.md` (role prompts), `CLAUDE.md` (non-negotiables, §8 verbatim).

---

## 0. Mission

Implement the **entire SAF/ARI v2.2 measurement framework in code** as a Python API:
ingest a chat (Claude or ChatGPT, export or plaintext) → universal event log → parallel STATE (CSPC proxies) + TRAIT (ARI 8-dim) channels → precision merge → aggregation → v2.2 interaction dynamics → sustainability layer → claims-gated response.

**Proof of done:** the pipeline runs on all 28 gold chats, the calibration ratchet holds (overall MAE ≤ 0.2994), every framework component either computes for real or exists as a correctly rung-tagged stub, and `POST /v1/sessions` → `GET /v1/sessions/{id}/score` returns the full response schema. No UI. No extension. The API **is** the deliverable.

---

## 1. The team

| Agent | Role | Owns | Why |
|---|---|---|---|
| **Claude Code** | **Chief Engineer (CE)** | Contracts, event log, ingestion, judge, precision merge, aggregation core, claims engine, API, integration, discrepancy resolution | The parts where a mistake corrupts everything downstream |
| **Codex** | **Junior Dev A** | Trait-side leaf modules (tagger, phase classifier, extractors, normalize) | Bounded, contract-driven implementation |
| **Antigravity** | **Junior Dev B** | State-side + dynamics leaf modules (CSPC proxy classifiers, transition metrics, overlay) | Bounded implementation, parallel to Codex |

**The one rule:** juniors build leaf modules against frozen contracts; the CE owns every file more than one module depends on. **No two agents ever edit the same file.** A junior that hits a blocker files it in `DISCREPANCY.md` and moves to another unblocked task — it never silently works around a problem and never edits a contract.

**The dependency truth (drives the whole split):** STATE and TRAIT are **siblings**, computed in parallel from the event log. CSPC is **not** computed before ARI. They meet at exactly one point — `src/merge/precision.py` (CE-owned) — where state conditions trait evidence **precision** (CI width), never trait score value.

```
              EVENT LOG  ← everything reads from here
             ┌────┴─────┐
        STATE channel   TRAIT channel      ← independent; built in parallel
        (Antigravity)   (Codex + CE judge)
             └────┬─────┘
        PRECISION MERGE (CE only — the only meeting point)
                  ↓
        AGGREGATION → v2.2 DYNAMICS → SUSTAINABILITY → CLAIMS GATE → API
```

---

## 2. Phase 0 — repository reset (CE, before anything else)

### 2.1 Preserve

| Asset | New location | Why |
|---|---|---|
| 28 gold chats + per-chat rationales + metadata | `data/gold/` (live) | The regression suite — only ground truth |
| `contract_table.yaml` (107 neurons) | `contracts/contract_table.yaml` (live) | Core ontology |
| `neurons_v6.json` | `contracts/neurons_v6.json` (live) | Core ontology |
| Judge prompt v1.3 | `legacy/judge_prompt_v1.3.md` | Baseline to beat; anchor examples reusable |
| Calibration v1.3 MAE table | `legacy/calibration_baseline_v1.3.md` | The ratchet numbers |
| ADRs 0003–0012 | `legacy/adr_v1/` | Rejected ideas stay visibly rejected |

### 2.2 Delete
Everything else (old TS monorepo, old Python v1, old tests/configs). Tag `v1-final` in git first.

### 2.3 The MAE ratchet (release gate)
New pipeline must reach **overall MAE ≤ 0.2994** on the same 28 chats (per-dim target ≤ 0.375). EC tracked separately — its 0.41 is a **data** problem (insufficient high-band examples), not a prompt problem; do not burn cycles prompt-tuning EC. A rewrite that scores worse than v1 is a regression, not progress.

---

## 3. Framework → code requirements (condensed; spec section pointers in brackets)

The deep theory is in the uploaded spec files. This section is what each module must DO.

### 3.1 Ontology — frozen, implement exactly [spec §2–3, App. C/D]
**107 neurons → 8 dimensions → 4 pillars. No additions of any kind.** Neurons score 0.0–1.0; absent = `N/A`, never 0. EC×1.5 / CS×1.5 weighting in aggregation.

| AL 13 | PR 15 | **EC 14** | ES 14 | **CS 11** | CD 11 | AUI 12 | CA 17 |
|---|---|---|---|---|---|---|---|
| Engage | Engage | Manage · top wt | Manage | Create · top wt | Create | Design | Design |

### 3.2 Claims charter [spec §0.2]
Every emitted field carries exactly one rung: `DESIGNED` / `MEASURABLE` / `VALIDATED` / `ASPIRATIONAL`. Enforced structurally in the response schema — the report generator cannot emit above a field's rung. Nothing in v1 is VALIDATED (no probe data yet); say so.

### 3.3 Universal event log — the substrate [spec §5.9a]
Append-only, ordered, provenance-tagged. All adapters normalize into `CanonicalSession`; the event log materializes from it; **nothing downstream reads raw source formats.**

```python
Event: { t, event_type, actor: "human"|"ai"|"system", payload_ref,
         confidence: float, provenance: "displayed"|"implied", metadata: dict }
```
**Frozen taxonomy (6):** `E-ERR`, `E-CONTRA`, `E-CONFUSE`, `E-FRICTION`, `E-CORRECT`, `E-OVERREACH`. Plus `N-FIRE` for neuron firings.

### 3.4 Ingestion (Scope A adapters)
`ClaudeExportAdapter`, `ChatGPTExportAdapter` (conversations.json), `PlaintextAdapter`. All → `CanonicalSession`. Tier 1 (no telemetry). Extension adapters are Scope B.

**`PartnerModel` is a required schema field from Stage 0:** `{ family: "anthropic"|"openai"|"google"|"unknown", model_id, era_key: "YYYY-MM" }`. The judge family must differ from the partner family (non-negotiable #20). **Known caveat to ADR:** gc-003 has a Gemini partner; the v1 build judged it with Gemini (same-family). Record this as a flagged exception in ADR-000x; exclude or down-weight gc-003 in judge-family-sensitive analyses.

### 3.5 CSPC state proxies — what ships [spec §4, §9.1; full HGF deferred D1]
Behind a `StateEstimator` interface (`ProxyEstimator` now, `HGFEstimator` later):
- **L_t load:** per-turn `LOW_LOAD / HIGH_ICL / HIGH_ECL / FATIGUE` (prompt-length trajectory, vocab complexity delta, fragmentation).
- **E_t epistemic:** −1..+1 extractive↔generative from intent tags; session mean + half-to-half slope.
- **M_t metacog:** `ACTIVE / PASSIVE / SURRENDER` — surrender = accept-run ≥ 3 consecutive flat accepts; emit `surrender_detected` + onset turn.
- **ToM slope:** trajectory of theory-of-mind signatures in prompts.
- **A_t (Tier-2 only — stub in Scope A):** schema present; needs telemetry.
**State validity gate:** M_t collapse → `state_compromised: true` → widen all trait CIs; never suppress scores, suppress confidence and report the caveat.

### 3.6 Trait pipeline [spec §6, §7; H13 dimension-grain]
1. **Intent tagger** (Codex): 10 tags — `VERIFY, EXTRACT, INJECT_CONTEXT, OVERRIDE, SELF_AUDIT, DELEGATE, SCAFFOLD, PIVOT, DECOMPOSE, ACCEPT_FLAT`.
2. **Phase classifier** (Codex): `explore / refine / extract / evaluate` per turn.
3. **Deterministic extractors** (Codex): one file per dimension; unambiguous signals first (accept-run → AUI; VERIFY rate → EC; SELF_AUDIT presence, etc.).
4. **LLM judge** (CE): **Gemini 2.5 Flash** (OpenRouter fallback), temp 0.1, 3 retries; **dimension-grain** structured JSON — `{dim: {score, confidence, evidence_turns[], tom_tag}}`. Rewrite v1.3 prompt to dimension grain; reuse its anchor examples only. All-fail → `N/A` + `judge_unavailable: true`. EC gets `low_calibration_confidence: true` until corpus grows.
5. **EC provenance** (CE): tag evidence `displayed` (full precision) vs `implied` (reduced); **theater check** — a "verification" with zero downstream delta increments `theater_counter` and discounts EC precision.
6. **ES event-triggered** [v2.1]: score only when ethics-relevant trigger events exist; else structural `N/A` ("no_ethics_events_detected"). Never always-on.

### 3.7 Aggregation [spec §3.6, §7.6]
- **n_eff gate** τ=1 (config): under-sampled dimension → `INSUFFICIENT_SAMPLE`, raw counts retained, no ratio.
- **Count normalization:** fired ÷ applicable opportunities, standardized per dimension (CA-17 gets no structural edge over AUI-12).
- **Soft non-compensatory composite:** penalized power-mean across pillars × validity gates (scorability: ≥4/8 dims valid; state validity). A genuine hollow dimension can't be averaged away; one `INSUFFICIENT_SAMPLE` doesn't erase the rest.
- **Precision merge (CE — `src/merge/precision.py`):** state → trait CI width only. No multipliers, ever (R2).

### 3.8 v2.2 interaction dynamics [spec §5.9b–d]
All computed **only from the event log**; an audit test asserts no new latent variables exist anywhere.
- **E→R signatures:** response classes `VERIFY_CHALLENGE / SYNTHESIZE / CONSTRAIN / ACCEPT_FLAT / DISENGAGE / DELEGATE_MORE`; per-user π(r|e) with Dirichlet partial pooling; **per-cell n_e gating** (insufficient events → `N/A`, never a probability from 1 event).
- **Friction Transition Matrix:** P(VERIFY|E-FRICTION), P(ACCEPT_FLAT|E-FRICTION), P(DISENGAGE|E-FRICTION) — cell-gated.
- **Five frozen transition metrics:** verify_after_error_rate; constraint_before_generation_rate; prediction_before_answer_rate; accept_run_max/mean; revision_after_output_rate.
- **Regime overlay (Antigravity):** RULES ONLY — `generative / extractive / verification / drift / accept_run`; occupancy shares + session strip. `accept_run` is **never** labeled "surrender" (that's a CSPC construct). No probabilities, no latent model — CSPC is sole owner of latent state.
- **Partner reliability map (CE):** era-keyed schema + back-test hook, scaffold only; data captured via PartnerModel from day one.
- **Micro-probes:** event types in log + exposure-randomizer stub; delivery is Scope B+.

### 3.9 Sustainability layer [spec §5.2–5.3.1] — resolved position
- **Ŝ_human (the §5.3.1 embedded estimator — both bugs resolved):** partition human turns into A-turns ("continue/ok/go on") vs S-turns (specific constraint/correction/stopping rule). Segment AI spans into `T_redundant` (semantically redundant via cosine sim to established content; boilerplate; superseded) vs `T_floor`. Then **Ŝ_human = (r_auto − r_steer) × T_steered_out**. No κ multiplier (bug 2 fix). No counterfactual double-run (bug 1 fix — A-turns are the embedded baseline). Cache multiplier: linear first. Rung: `DESIGNED→MEASURABLE`; falsifiability contract in the contract table ("must correlate with 48h probe at r>0.3 or be revised").
- **Debt EWMA:** modes `erosion` (declining slope) / `flat_floor` (never built) / `none`; α=0.3; single session → `INSUFFICIENT_HISTORY`, never a debt score.
- **λ:** stub — value `null`, rung `DESIGNED`, "requires multi-session + probe."
- **Retention probe:** schema in `contracts/probe_schema.yaml` only; generative-recall formats (free recall / application / teach-back), recognition excluded. No delivery in Scope A.

### 3.10 Tier + claims gating [spec §9; claims_table.yaml]
Tier auto-detected from payload. Scope A inputs are all **Tier 1** (transcript only, no telemetry):
- Max rung MEASURABLE. **Forbidden at Tier 1:** the word "synergy" in any user-facing field; sustainability *statements* (flags-as-inference only); competence-vs-surrender discrimination; direct cognitive-load claims (proxy language).
- Forbidden everywhere: leaderboards; bare composite without CI+rung; raw "Cognitive Debt Score"; "surrender"/"dependent" as user-facing labels; bare composite/rank/debt to `is_minor: true`.
- Contract tests prove a Tier-1 payload cannot elicit a Tier-2+ claim through any API path; forbidden-word tests run in CI.

---

## 4. Architecture

**Stack:** Python 3.12+ · FastAPI · Pydantic v2 · SQLite→Postgres-ready (SQLAlchemy) · `google-generativeai` (judge) · `sentence-transformers` (semantic distance) · pytest.

### 4.1 Repo layout (team files at root)
```
saf-brain/
├── AGENT_REBUILD_BRIEF_v3.md      ← this file
├── CLAUDE.md                      ← §8 verbatim
├── TEAM.md  INTERFACES.md  DISCREPANCY.md  AGENT_KICKOFF.md
├── contracts/
│   ├── schemas.py                 ← Event, CanonicalSession, PartnerModel,
│   │                                DimensionScore, StateVector, ScoreResponse
│   ├── event_taxonomy.py  intent_tags.py
│   ├── contract_table.yaml  neurons_v6.json
│   ├── claims_table.yaml  probe_schema.yaml
├── data/gold/                     ← 28 chats + rationales (regression suite)
├── legacy/                        ← judge_prompt_v1.3, calibration baseline, adr_v1/
├── src/
│   ├── ingestion/  adapters/{claude_export,chatgpt_export,plaintext}.py  canonical.py
│   ├── eventlog/   schema.py  writer.py  queries.py
│   ├── state/      estimator.py  proxy.py  load_classifier.py
│   │               epistemic_classifier.py  metacog_classifier.py  tomer_slope.py
│   ├── trait/      tagger.py  phase_classifier.py  extractors/per_dimension/
│   │               judge/{client,prompt,parser}.py  evidence.py
│   ├── merge/      precision.py           ← THE meeting point (CE only)
│   ├── aggregate/  normalize.py  softmin.py  gates.py
│   ├── dynamics/   reactions.py  transitions.py  overlay.py  reliability_map.py
│   ├── sustainability/  debt_tracker.py  ewma.py  lambda_proxy.py  probe_schema.py
│   ├── claims/     rungs.py  tier_engine.py  report.py
│   └── api/        main.py  routes/{sessions,scores,trajectory,internal}.py
│                   middleware/auth.py
├── calibration/    gold_loader.py  runner.py   ← MAE ratchet (CI gate)
├── adr/            ← new ADRs from 0001
└── tests/          regression/  unit/  property/  contract/  integration/
```

### 4.2 API surface (Scope A)
```
POST /v1/sessions        { source, payload, user_ref?, partner_model? } → { session_id, detected_tier, event_count }
GET  /v1/sessions/{id}/score → full ScoreResponse:
     tier · profile{8 dims: value|INSUFFICIENT_SAMPLE|N/A, ci, n_eff, rung}
     composite{value|null, gates_passed, state_compromised_caveat, rung}
     state_strip[] · state_validity{} · flags{fluent_incompetence, debt_flag,
     accept_run_*, theater_counter} · reaction_signatures{ftm, transition_metrics}
     regime_overlay{occupancy, strip} · sustainability{s_human_hat, debt_ewma, lambda}
     report{observed[], inferred[], hypothesized[], tier_caveat}
GET  /v1/users/{ref}/trajectory      (multi-session; INSUFFICIENT_HISTORY on 1)
POST /v1/calibration/run             → { overall_mae, per_dim_mae, ratchet_passed }
GET  /v1/health   GET /v1/contracts
```
API-key auth from day one (simple header).

---

## 5. Multi-agent build plan

### STAGE 0 — CE only. Everyone else waits.
- [ ] `contracts/schemas.py` — all six core schemas (Pydantic v2), incl. `PartnerModel`
- [ ] `contracts/{event_taxonomy,intent_tags}.py` — frozen constants
- [ ] `contracts/claims_table.yaml` — tier × permitted/forbidden (per §3.10)
- [ ] Verify `contract_table.yaml` + `neurons_v6.json` load
- [ ] **`INTERFACES.md`** — exact signature for every leaf module, owner-tagged; the precision-merge input contract; what each module may/may not import
- [ ] Repo skeleton (all dirs, `__init__.py`, failing-stub tests), CI with calibration ratchet stub
- [ ] ADR-0001 (reset + preservation), ADR-0002 (gc-003 Gemini-partner judge-family caveat)
**Gate:** schemas import clean; INTERFACES.md committed. Then release the juniors.

### STAGE 1 — Parallel (Codex ∥ Antigravity ∥ CE). Disjoint files. Unit tests beside each module.

**CODEX (trait leaves):**
- [ ] `src/trait/tagger.py` — 10 intent tags
- [ ] `src/trait/phase_classifier.py`
- [ ] `src/trait/extractors/per_dimension/*.py` — 8 files
- [ ] `src/aggregate/normalize.py`

**ANTIGRAVITY (state + dynamics leaves):**
- [ ] `src/state/load_classifier.py` · `epistemic_classifier.py` · `metacog_classifier.py` · `tomer_slope.py`
- [ ] `src/dynamics/transitions.py` (5 frozen metrics) · `overlay.py` (rules only; no "surrender")

**CHIEF ENGINEER (spine):**
- [ ] `src/ingestion/*` (3 adapters + canonical) → first integration target: 28 gold chats round-trip losslessly into the event log
- [ ] `src/eventlog/*` (property tests: ordered, append-only)
- [ ] `src/trait/judge/*` (dimension-grain rewrite of v1.3) + `evidence.py` (provenance + theater)
- [ ] `src/state/estimator.py` (interface + ProxyEstimator assembling Antigravity's classifiers)
- [ ] `src/merge/precision.py` · `src/aggregate/{softmin,gates}.py`
- [ ] `src/dynamics/reactions.py` (E→R + Dirichlet + cell gating) · `reliability_map.py` (scaffold)
- [ ] `src/sustainability/*` (Ŝ_human, EWMA, λ stub, probe schema)
- [ ] `src/claims/*` · `src/api/*` · `calibration/runner.py`

### STAGE 2 — Integration + ratchet (CE; juniors on standby for discrepancy fixes)
- [ ] Wire leaves into the pipeline; full run on 28 gold chats
- [ ] **Gate A:** overall MAE ≤ 0.2994 (per-dim ≤ 0.375; EC tracked separately)
- [ ] **Gate B:** contract tests (tier gating, rung tags, forbidden words, minor protection) green
- [ ] **Gate C:** synthetic-fixture proofs — precision moves CIs not scores; state_compromised reported as caveat; EWMA modes fire correctly; FTM cells N/A on sparse events; no-latent-variable audit green
- [ ] **Gate D:** end-to-end `POST → GET score` returns full valid ScoreResponse on a fresh chat
- Leaf failures → file in `DISCREPANCY.md`, assign to owner; CE never silently patches a junior's module.

### Coordination rules (binding)
- **Ownership map:** `TEAM.md` §3 is authoritative. Never edit a file you don't own; need a change → `DISCREPANCY.md`.
- **Leaf isolation:** leaves import ONLY from `contracts/`; read events only via `eventlog/queries.py`; never call the judge; never import another leaf.
- **Discrepancies:** only the CE resolves; contract changes bump a version note and require juniors to re-read.
- **Session ritual:** sync → read TEAM.md board → read DISCREPANCY.md → read your INTERFACES.md entries → build owned files only → tests green → check the box → commit `[AGENT] file: what + test count`.
- **Throttle routing:** CE throttled → juniors continue (contracts already frozen — that's why Stage 0 is first). A junior throttled → its tasks wait; nobody picks up another agent's open file mid-edit; reassignment only by CE via TEAM.md ownership change.

---

## 6. Definition of done (Scope A)
All Stage 0–2 boxes checked; all four Stage-2 gates green; pipeline produces, for every gold chat: 8-dim profile + composite (gated), state strip + validity, flags, FTM + 5 transition metrics, regime overlay, Ŝ_human + debt mode, rung-tagged report. **Then** we debate Scope B.

---

## 7. S_human — resolved position (read before building `debt_tracker.py`)
Bug 1 (unobservable counterfactual) → solved by the within-conversation baseline: A-turns expose the model's intrinsic redundancy `r_auto`; no double-run. Bug 2 (κ double-counts ability) → solved by dropping κ; formula is pure `(r_auto − r_steer) × T_steered_out`. Any future credibility weighting is a separate normative parameter via ADR, `ASPIRATIONAL` until validated. Cache multiplier linear first. IRT integration NOT in Scope A.

---

## 8. Non-negotiables (copy verbatim into `CLAUDE.md`; all agents bound)
1. **Ontology freeze:** exactly 107 neurons, 8 dims, 4 pillars. Fields may be added to the contract table; items may not.
2. **No score multipliers for state.** State → evidence precision (CI width) only. (R2)
3. **Never claim "true synergy" from transcripts** (Tier 1–2). (R3)
4. **"synergy" never appears in Tier-1 user-facing output.**
5. **"surrender" never appears in regime-overlay output** (CSPC construct only).
6. **No leaderboards / population ranking / bare composite without CI + rung.**
7. **No raw "Cognitive Debt Score"** — measured quantities + inference language only.
8. **CSPC is sole owner of latent state.** Overlay is rules only; no second latent model.
9. **Full HGF deferred.** ProxyEstimator behind the StateEstimator interface.
10. **Self-ratings never used raw** — Dawid–Skene corrected only. (Scope B concern; rule stands.)
11. **Latency thresholds personal + relative** (~1.5 SD vs rolling baseline). Never absolute.
12. **Absent ≠ zero.** N/A or INSUFFICIENT_SAMPLE.
13. **Ecology and laboratory data pools never merge.**
14. **Every emitted claim carries exactly one rung;** nothing presented above it.
15. **Minor protection:** no bare composite / peer rank / debt score to `is_minor: true`.
16. **Data dignity:** minimization; deletion propagates to derived features.
17. **Rejected ideas stay rejected:** Cognitive Primitive Layer, two-pass EC, multipliers, transcript true-synergy, second latent model → read `legacy/adr_v1/` + spec §14, write an ADR, stop for approval.
18. **MAE ratchet ≤ 0.2994** is a release gate.
19. **EC is a data problem.** Do not prompt-tune past v1.3's lesson; the fix is 40+ high-band gold chats.
20. **Judge family ≠ partner family.** Gemini judge for Claude/ChatGPT partners; if a Gemini-partner chat is scored, flag it (see ADR-0002 / gc-003 caveat). Never an Anthropic model as judge.
21. **(Team) Never edit a file you don't own; never silently work around a blocker** — `DISCREPANCY.md` or nothing.

---

## 9. Scope B — locked decisions, build later (recorded so nothing is lost)
- **Extension:** Chrome MV3 on Claude.ai + ChatGPT; live capture → Tier 2 (timestamps, dwell, copy-paste); collector-bag one-by-one selection + bulk/project select.
- **Two-store model:** local-first display (`chrome.storage.local` cache + outbox) / server-persisted truth (metrics + cleaned dataset + trajectory). Trajectory is server-computed, pulled — it is the retention centerpiece and the moat.
- **Consent:** single conditional-use package in the required format (text → cleaned dataset → scoring → self-rating → feedback) or fully-functional local-ephemeral mode. Minors: guardian consent gate before any storage; stricter retention; `is_minor` set conservatively.
- **Per-chat partner self-rating** as second annotator (async, batched, Dawid–Skene, provenance-tagged). **Post-score user feedback** (agree/partial/disagree per dim + free text) as calibration signal, trust loop, and gold-candidate filter — never a live score override.
- **Portfolio (Tier-1 view):** profile *shape* (radar), strengths-first, ONE next habit, Past→Present→Trend with uncertainty band, archetype label, session rhythm strip. Dimension values only under a "research data" toggle. All §8 suppressions apply.
- **Open before Scope B:** guardian-consent mechanism (DPDP); cleaned-dataset retention policy (adult vs minor); self-rating call path (user's own API key vs in-session); bulk self-rating cost ceiling.

---

*First action — Chief Engineer: Phase 0 reset (tag `v1-final`, preserve per §2.1, delete per §2.2, ADR-0001/0002), then Stage 0 (freeze contracts, publish INTERFACES.md). Then release Codex and Antigravity per `AGENT_KICKOFF.md`. The ratchet decides when we're done.*
