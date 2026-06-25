# SAF/ARI v3.21 — Core Engineering Synthesis Brief
## From the v3.21 specification into the running repo: cross-check, upgrades, the AI-psychology layer, the research data spine, and the agent self-exploration protocol

**Drop location:** repo root, beside `AGENT_REBUILD_BRIEF_v3.md`.
**Status:** synthesis brief — *not a rebuild*. It folds the v3.21 unified specification into the existing `synergy-portfolio` codebase by closing the gap between as-designed and as-built, never by re-architecting what already runs.
**Authoritative chain (unchanged):** `CLAUDE.md` (21 non-negotiables + v3/v3.1 addendum) and `INTERFACES.md` win on *behaviour and signatures*; the ADR log + `DISCREPANCY.md` win on *resolved decisions*; `SAF_ARI_v3.21_Unified_Master_Specification.md` wins on *scientific correctness*; **this brief wins only on sequencing** — what to build next and in what order. Where this brief appears to contradict a non-negotiable, the non-negotiable wins and the contradiction is a bug in this brief.

---

## PART 0 — HOW TO READ THIS BRIEF

### 0.1 What this brief is, in one paragraph

The repo already implements the full four-layer stack end-to-end: ingestion → event log → parallel TRAIT + STATE channels → precision merge → aggregation → dynamics → sustainability → claims gate → persisted `ScoreResponse`, plus a failure-isolated CSL layer and a research-grade persistence tier (provenance columns, neuron-firing matrix, per-turn state strip, literal judge output, CSL/question-quality/reliance artifacts). The calibration ratchet holds at **MAE ≈ 0.25 / 100% coverage** on the n=26 gold corpus. This brief does five things and only five: **(1)** audits every component for *as-built quality vs v3.21 intent*; **(2)** specifies the upgrades that close real gaps, each rung-tagged and freeze-checked; **(3)** makes the **AI-psychology layer** a first-class, wired part of scoring (it currently exists as modules that are only partially fed into the score); **(4)** completes the **research data spine** so nothing that matters for later validation is ever dropped; **(5)** installs an **agent self-exploration protocol** so the coding agents can discover and propose good engineering by themselves, safely, inside the existing governance.

### 0.2 The binding constraints (pointer, not restatement)

Every task in this brief inherits the 21 non-negotiables in `CLAUDE.md` and the v3/v3.1 addendum verbatim. The five that govern almost every decision here:

- **#1 Ontology freeze** — 107 neurons, 8 dimensions, 4 pillars. New *fields* on the contract table are allowed; new *items* are not. This is why every upgrade below is a field, a method, a gate, or a persistence change — never a new construct.
- **#2 No score multipliers for state** — state conditions evidence **precision (CI width)** only; `merge()`'s output value equals its input value for every dimension, always (R2, audit-tested). The AI-psychology layer obeys this without exception.
- **#8 CSPC is the sole owner of latent state** — the regime overlay is rules only; the word "surrender" never leaves the CSPC modules (CI greps for it).
- **#12 Absent ≠ zero** — `STRUCTURAL_NA` / `INSUFFICIENT_SAMPLE` / `MEASUREMENT_SATURATED` / genuine score are four distinct labels, never collapsed.
- **#14 Every emitted claim carries exactly one rung**; nothing is presented above it. **#2 of the addendum: no pilot fitting** on the 26 gold chats — they are a pilot/regression set.

### 0.3 The map: v3.21 four-layer stack → actual modules

| v3.21 layer | Spec object | Where it lives in the repo | As-built reality |
|---|---|---|---|
| **Layer 1 — ARI** (trait) | 107 → 8 → 4, IRT/GRM | `src/trait/extractors/per_dimension/*.py` (8) + `src/trait/judge/*` + `src/aggregate/*` | Judge owns dimension value; 9 deterministic neurons live as evidence; EqualWeight/normalize aggregation; GRM is interface-stubbed |
| **Layer 2 — CSPC** (state) | 4D HGF, C→A→M cascade | `src/state/{load,epistemic,metacog,tomer_slope}_classifier.py` + `src/state/estimator.py` + `src/merge/precision.py` | 4 proxy classifiers live behind `StateEstimator`; per-turn π_t computed + persisted; full HGF deferred (#9) |
| **Layer 3 — CSL** (work) | ACF crosswalk, ownership, emergence | `csl/{crosswalk,projection,ai_side_extractor,ownership,emergence,report}.py` | Fully implemented & failure-isolated; emergence judge confirmer **abstains** pending ICC (ADR-0011) |
| **Layer 4 — outcome** | retention probe, λ, true synergy | `src/sustainability/{lambda_proxy,probe_schema}.py` + `contracts/probe_schema.yaml` | Correctly stubbed (DESIGNED); λ + true synergy gated on multi-session + probe data |
| **The Wall** | process↔outcome boundary | `src/claims/{rungs,tier_engine,report}.py` | Enforced: tier engine strips claims above a tier's rung; forbidden-word gate live |
| **Research spine** | store everything reproducible | `src/provenance.py` + migrations 005/006/008/011 + `src/worker/scorer.py` persistence | Strong: provenance columns, neuron_firings, turn_state, judge_runs, artifact blobs |

> **The headline finding of the audit.** The architecture is excellent and the discipline is real. The gap between v3.21-on-paper and the repo is **not architectural** — it is (a) *thin coverage* of the deterministic-evidence and AI-psychology channels, (b) a handful of *unwired* psych signals that compute but don't yet reach the score as evidence, (c) *research-data completeness* (a few high-value signals are computed and discarded), and (d) the *absence of a self-improvement loop*. None of the four requires touching the ontology, the claims ladder, or the Wall.

---

## PART 1 — THE SYNTHESIS THESIS

### 1.1 What "bringing v3.21 into the current work" actually means

v3.21 added **no new ontology**. It consolidated the lineage and sharpened a small set of mechanisms (the embedded T-reduction estimator, the fitted retention curve, the five AI-psychology precision conditioners, the CSL ownership-as-control formulation, the never-collapse fourth state). Every one of those either already exists in the repo or maps to an additive field/method. So the synthesis is **convergence work, not construction work**: bring the running instrument up to the precision the spec describes, and make sure the data it produces can carry the program to the only rung that matters next — **VALIDATED** — when the retention probe lands.

### 1.2 The five engineering workstreams (the spine of this brief)

| WS | Name | One-line goal | Touches |
|---|---|---|---|
| **WS-1** | **Evidence depth** | Raise deterministic-neuron coverage and route every approved psych signal into the score *as evidence/precision* | trait extractors, evidence.py, precision.py |
| **WS-2** | **AI-psychology layer** | Make the five precision conditioners + reaction signatures first-class, wired, and Goodhart-safe | state/, dynamics/, trait/reliance & question_quality |
| **WS-3** | **Research data spine** | Persist everything that matters for later validation; never drop a computed signal of research value | provenance, migrations, worker persistence, an export view |
| **WS-4** | **Self-exploration loop** | A safe protocol + harness for agents to discover and propose good engineering by themselves | a discovery harness, PROPOSAL register, CI |
| **WS-5** | **Engineering excellence** | Codify and CI-enforce the quality bar the framework's integrity depends on | tests, CI gates, determinism, docs/ADRs |

Each workstream is audited in Part 2, specified in Parts 3–6, and sequenced in Part 7. The two open-product discrepancies that block live data flow (**D-015** capture bridge, **D-022** `is_minor` threading) are folded into the sequence in Part 8.

### 1.3 The non-negotiable engineering posture

Three postures carry through everything below, because they are what separate this instrument from "an LLM rating a chat":

1. **Evidence, never verdict.** Every new signal enters as *evidence with a provenance tag and a precision*, weighted into a Bayesian-style update — never as a value the model asserts. The discipline that `merge()` already enforces for state (value-in == value-out, only CI changes) is the template for the entire AI-psychology layer.
2. **Capture now, condition later.** Research-relevant signals are *recorded* the moment they are computable and *gated from conditioning live scores* until their validity gate clears. This is how the program earns the right to its claims without ever asserting them early.
3. **Discovery is bounded by the freeze.** Agents are actively encouraged to find and propose improvements — but the four red lines (no new construct, no score multiplier, no Wall crossing, no contract edit without sign-off) are hard stops that route to a human, every time.

---

## PART 2 — THE CROSS-CHECK: COMPONENT-BY-COMPONENT AUDIT

Legend — **Status:** ✅ live & sound · 🟡 live but thin/partial · 🟦 correctly stubbed (data-gated) · 🔴 missing/blocked. **Quality** is an engineering grade against the framework's own bar (A = exemplary, B = solid, C = works but under-built). **Rung** is the highest rung the component's *output* may currently claim.

### 2.1 Ingestion & capture

| Component | Status | Quality | Rung | Upgrade needed |
|---|---|---|---|---|
| `interceptor.js` (MAIN-world fetch/XHR capture + cache-replay, ADR-0008) | ✅ | A | — | None; the field-presence runtime assertion (D-015 §CE) is the right early-warning. |
| `content.js` active-path walk (`activePathFromMapping`) + payload pass-through | 🟡 | B | — | **D-015 is the single most important live gap.** The CE spine is built; the Codex bridge (§1–§9 of D-015) is the blocker. Until it lands, long virtualized threads degrade to the scroll-probe fallback. **Resolve first.** |
| Ingest validation (role-balance, `content_hash` re-queue, completeness CHECK constraint) | ✅ | A | — | None. The DB-level `capture_complete=true ⇒ captured≥expected` CHECK is exactly the belt-and-suspenders the framework wants. |
| Adapters (`claude_export`, `chatgpt_export`, `gold_json`, `plaintext`) | ✅ | A | — | None. |

### 2.2 Event log — the substrate

| Component | Status | Quality | Rung | Upgrade |
|---|---|---|---|---|
| `src/eventlog/{schema,writer,queries}.py` — append-only, ordered, 6-event taxonomy + N-FIRE | ✅ | A | MEASURABLE | None structurally. The order-preserving log is the substrate for every sequence signal; it is correctly the *only* read surface for leaves. **WS-3** adds nothing here except ensuring the full log is persisted per chat (migration 008 already does this). |

### 2.3 Trait channel (ARI)

| Component | Status | Quality | Rung | Upgrade |
|---|---|---|---|---|
| 8 deterministic extractors (`per_dimension/*.py`) | 🟡 | B− | MEASURABLE | **Only 9 of 107 neurons fire deterministically** (AL-08, PR-02/05/07/14, EC-06/07/09, ES-01); CS/CD/AUI/CA are structurally empty per the contract table. This is *correct* (the judge covers inferential neurons) but thin. **WS-1 task:** add deterministic extractors for the unambiguous neurons the contract table marks `deterministic` but that aren't yet implemented, one PR per dimension, each landing as **evidence enrichment only** (raw counts ride on the `DimensionScore`; the judge keeps the value — the v1.3 "one variable at a time" lesson). |
| LLM Judge (`trait/judge/*`, Gemini 2.5 Flash, temp 0.1, 3 retries, dimension-grain) | ✅ | A | MEASURABLE | Sound. The OpenRouter OpenAI-family fallback for Gemini-partner chats (#20, ADR-0002) is correctly wired. **One upgrade (WS-2/WS-5):** the **stratified re-judge** (ADR-0009 `replication.py`) should fire on quadrant-boundary chats by default in calibration runs, reporting mean ± SD. |
| EC evidence + theater (`trait/evidence.py`) | ✅ | A | MEASURABLE | The `displayed`/`implied` provenance tags + `theater_counter` → CI widening is a textbook implementation of the v3.21 §6.10 spec. **WS-1:** add the **calibration-slope $\hat{s}$** field (acceptance-vs-claim-risk) once the claim-risk classifier seed lands; until then, leave as N/A — do not fabricate. |
| EC calibration (MAE ≈ 0.41) | 🟡 | — | MEASURABLE | **Not a code problem (#19).** The fix is 40+ high-band verifier-rich gold chats (the §8.3 archetype quota). Do **not** prompt-tune past v1.3's lesson. **WS-3 supports this** by making the gold-corpus archetype labels queryable so the quota gap is visible. |

### 2.4 State channel (CSPC)

| Component | Status | Quality | Rung | Upgrade |
|---|---|---|---|---|
| `load_classifier.py` (relative-z, 1.5 SD, never absolute — #11) | ✅ | A | MEASURABLE | None; the personal-baseline correction is in code, not just spec. |
| `epistemic_classifier.py` (−1..+1 extractive↔generative) | ✅ | B | MEASURABLE | Sound. **WS-2:** feed the **predictive-interaction-entropy** prior (session prompt-entropy) as context on $E_t$'s meaning (not its value). |
| `metacog_classifier.py` (ACTIVE/PASSIVE/SURRENDER, accept-run ≥3) | ✅ | A | MEASURABLE | Sound and correctly the *sole* owner of "surrender". **WS-2** layers the **JAF/Weight-of-Advice reliance event** as additional $M_t$ evidence (via reliance_metrics, already computed). |
| `tomer_slope.py` (ToM-signature trajectory) | ✅ | B | MEASURABLE | Sound. |
| `estimator.py` (`ProxyEstimator` behind `StateEstimator`; per-turn π_t persisted) | ✅ | A | MEASURABLE/DESIGNED | Exemplary. The interface seam for the future `HGFEstimator` (#9) is exactly right. Full HGF stays **DESIGNED/data-gated**. |
| `merge/precision.py` (THE meeting point; value-in == value-out) | ✅ | A | — | The single best-engineered module in the system. It is the template for WS-2. Do not touch its contract; *extend through it*. |

### 2.5 Aggregation

| Component | Status | Quality | Rung | Upgrade |
|---|---|---|---|---|
| `aggregate/normalize.py` (fired ÷ applicable, neuron-count standardized) | ✅ | A | MEASURABLE | None; deterministic ratio (D-017 confirmed no quantile cuts to freeze). |
| `aggregate/softmin.py` (penalized power mean, non-compensatory) | ✅ | A | MEASURABLE | Sound. |
| `aggregate/gates.py` (scorability ≥4/8 dims + state validity) | ✅ | A | MEASURABLE | Sound. |
| `aggregate/saturation.py` (`MEASUREMENT_SATURATED`, censored ≥τ, ADR-0010) | ✅ | A | MEASURABLE | The fourth never-collapse state is correctly implemented and live-tested. |

### 2.6 Dynamics (the interaction-physics layer)

| Component | Status | Quality | Rung | Upgrade |
|---|---|---|---|---|
| `dynamics/transitions.py` (5 frozen metrics, cell-gated) | ✅ | A | MEASURABLE | Sound; every cell gated on `MIN_EVENTS_PER_CELL`. |
| `dynamics/overlay.py` (RULES ONLY, no latent model, no "surrender") | ✅ | A | MEASURABLE | Exemplary discipline (CI greps for the forbidden word). |
| `dynamics/reactions.py` (E→R signatures, Dirichlet partial pooling, Friction Transition Matrix) | ✅ | A | MEASURABLE | This *is* the v3.21 §6.11 reaction layer — the most trait-like psych signal. **WS-2/WS-3:** ensure the full `ReactionSignatures` (per-event π(r|e)) is persisted for research, not just summarized. |
| `dynamics/reliability_map.py` (era-keyed partner reliability, schema only) | 🟦 | B | DESIGNED | Correctly empty (shipping invented numbers is worse than none). **WS-2:** seed from benchmark priors via ADR when the claim-risk classifier lands; back-test hooks already exist. |

### 2.7 Sustainability (Layer 4 + λ)

| Component | Status | Quality | Rung | Upgrade |
|---|---|---|---|---|
| `sustainability/debt_tracker.py` (`s_human_hat`: r_auto/r_steer, A/S-turn partition) | 🟡 | B | DESIGNED | The embedded T-reduction estimator is present as `SHumanHat{value, r_auto, r_steer, t_steered_out}`. **WS-3:** persist the **per-turn A/S partition** and the `ΔR = r_auto − r_steer` series so the falsification condition (§6.5.1: drop the metric if ΔR≈0 across users) is testable later. Stays DESIGNED. |
| `sustainability/ewma.py` (debt EWMA, flat-floor vs erosion modes) | 🟡 | B | MEASURABLE | Single-session today (reports `INSUFFICIENT_HISTORY`); the two `DebtMode`s exist in schema. **WS-3:** the cross-session trajectory needs the multi-session store (Part 4.4). |
| `sustainability/lambda_proxy.py` + `probe_schema.yaml` | 🟦 | A | DESIGNED | Correctly stubbed. λ, true synergy, validated ownership all wait for the probe. **Do not un-stub** (addendum #3). |

### 2.8 CSL (the cognitive-work layer)

| Component | Status | Quality | Rung | Upgrade |
|---|---|---|---|---|
| `csl/crosswalk.py` + `acf_crosswalk.yaml` (frozen, fail-loud) | ✅ | A | — | None. |
| `csl/projection.py` (NeuronMatrix → 7 ACF levels, re-projection not re-extraction) | ✅ | A | MEASURABLE | Non-circularity guarantee correctly implemented. |
| `csl/ai_side_extractor.py` (displayed AI contribution per level) | ✅ | B | MEASURABLE | Sound; the orthogonal channel. |
| `csl/ownership.py` (control-not-attribution, CSPC precision-weighted, never a session scalar) | ✅ | A | DESIGNED | Excellent; flagged `uncertified_pending_icc` until Phase 3.2. |
| `csl/emergence.py` (bilateral novelty + fused dependency + reframing; judge confirmer abstains) | 🟡 | A | MEASURABLE→ASPIRATIONAL | Fully built; **0 reportable until the emergence judge is wired + ICC-certified** (ADR-0011). The lexical-embedder fallback + frozen-threshold artifact (D-018) is the right pattern. **WS-2:** wire the judge confirmer behind the same interface; keep emergence-as-proof at ASPIRATIONAL. |
| `csl/report.py` (3-panel: stack / emergence ribbon / ARI-alignment strip) | ✅ | A | MEASURABLE | Sound; ARI dots never averaged into contribution bars. |
| `csl/analytics/{flow,bottleneck,orchestration}.py` | 🟡 | B | MEASURABLE | The Tier-1 analytics from §5.6. **WS-3:** persist their outputs; ensure bottleneck stays task-conditioned (a "bottleneck" may be appropriate delegation). |

### 2.9 AI-psychology modules (already present — the WS-2 core)

| Component | Status | Quality | Rung | Upgrade |
|---|---|---|---|---|
| `trait/question_quality.py` (EIG proxy, Graesser type, Bloom tier; D-020 approved evidence map) | ✅ | A | MEASURABLE | Wired **evidence-only** into PR-01/PR-03/PR-11 + EC-01 (verification/expectational only). The session complexity-summary is a longitudinal observable. **WS-3:** persist `mean_complexity` / `complexity_trend` / `originality` per session — this is a candidate **sustainability** signal (§6.13). |
| `trait/reliance_metrics.py` (Weight-of-Advice proxy + switch_fraction; D-021 → EC-11 evidence-only) | ✅ | A | DESIGNED | Borrowed-and-validated (VALIDATED in source field, DESIGNED for SAF). `appropriate_reliance` correctly data-gated to None. **WS-2:** route the behavioral reliance signal as $M_t$/EC-11 evidence precision; **WS-3:** persist the per-episode WoA series. |
| The other three conditioners (grounding, vigilance pattern, Dawid–Skene sycophancy) | 🔴 | — | DESIGNED | **Not yet modules.** WS-2 adds them as precision conditioners (Part 3). Dawid–Skene is the immediate reliability win (self-rating de-biasing). |

### 2.10 Claims engine & the Wall

| Component | Status | Quality | Rung | Upgrade |
|---|---|---|---|---|
| `claims/{rungs,tier_engine,report,footer,views}.py` (rung tagging, tier gating, forbidden-word enforcement) | ✅ | A | — | Excellent. The report generator structurally cannot emit above a field's rung. **D-022 gap:** `is_minor` defaults False on the live worker path — minor protection is *unenforced* there. **Fold into WS-3 + Part 8.** |

### 2.11 Persistence / research spine (the WS-3 core)

| Persisted artifact | Table / column | Status | Gap |
|---|---|---|---|
| Full `ScoreResponse` + provenance columns | `scores` (framework/schema/contract/git_sha/judge_model) | ✅ A | None; provenance is queryable columns, not a blob — correct. |
| Literal judge output + model identity | `judge_runs` (migration 005) | ✅ A | None. |
| Per-neuron firing matrix (NULL=N/A, 0.0=observed-0-of-N) | `neuron_firings` (005) | ✅ A | None; the absent≠zero semantics are enforced at the row level. |
| Per-turn state strip + per-turn π_t | `turn_state` (006) | ✅ A | None. |
| CSL / question-quality / reliance artifacts | `score_artifact_blobs` (011) | ✅ B | Stored as blobs; fine for now. **WS-3:** add a thin queryable index for the research-relevant scalars (emergence_count, mean_complexity, WoA) so cohort queries don't parse blobs. |
| Opaque subject mapping | `subjects` (006, random UUID, cascade delete) | ✅ A | None; the no-PII-derived-id precedent is correct (DPDP, #16). |
| Raw transcript + capture event log | `raw_chats`, capture log (008) | ✅ A | Retention window honored; deletion propagates. |
| **Session intent at score-time** | — | 🔴 | **Track 3 of D-013, deferred.** High research value (interpretation conditioning). **WS-3 task.** |
| **A/S-turn partition + ΔR series** (S_human) | — | 🔴 | Computed inside `s_human_hat` but not persisted. **WS-3 task.** |
| **Gold-corpus archetype labels** | `data/gold/metadata.json` | 🟡 | Present but not surfaced as a queryable corpus-coverage view (needed for the §8.3 quota + the twin gate). **WS-3 task.** |
| **The frozen anchor-set re-score schedule** (drift detection) | — | 🔴 | §8.6 needs a fixed anchor set re-scored on schedule to separate judge drift from subject change. **WS-3 task (a CI/cron job + a `drift_runs` table).** |

### 2.12 Infrastructure (DB / worker / API / extension)

| Component | Status | Quality | Notes |
|---|---|---|---|
| Postgres + Alembic (13 migrations) | ✅ A | Clean migration history; security migration 004 (OpenAI-key purge) + the value-shape secret guard (D-019) are correct. |
| Worker (`src/worker/scorer.py`, lease watchdog, content-hash re-queue) | ✅ A | Atomic claim, lease recovery, supersede-safe finalize. Exemplary. |
| API (`src/api/*`, FastAPI, key auth, Scope-C projects) | ✅ A | Keyset pagination, optimistic concurrency, idempotency keys (scope_c_contract). |
| Extension (interceptor + panel + 5 views) | 🟡 B | Capture path strong; **D-015 bridge** is the live gap; D-023/D-024/D-026 are UI polish (feedback recall, past/present radar, account link). |
| CI (`.github/workflows/ci.yml`) | ✅ B | **WS-5** adds the determinism, four-state, R2-audit, forbidden-word, and rung-violation gates as named jobs. |

---

## PART 3 — THE AI-PSYCHOLOGY ENGINEERING LAYER (WS-2)

This is the explicit ask — *engineering must include AI-psychological insights* — made concrete. The principle is absolute and worth stating before the mechanisms: **every psychological signal enters as evidence precision or as a context tag on a signal's meaning. None of them ever becomes a score multiplier or a value the model asserts (#2, R2).** The template is `merge/precision.py`: value-in equals value-out; only the credible interval moves.

### 3.1 The five precision conditioners — each as a wiring task

Each conditioner is a *distributed pattern across many turns* (which is why it is Goodhart-resistant) and each routes to an existing module. None adds a neuron (#1).

| # | Conditioner | Psychology | Module (new or existing) | Enters scoring as | Status |
|---|---|---|---|---|---|
| C1 | **Judge-Advisor / Weight-of-Advice** | Yaniv & Kleinman; Sniezek & Buckley — reliance as a continuous, calibrated shift toward advice | `trait/reliance_metrics.py` (exists) | A reliance-event series conditioning **EC/AUI evidence precision** and feeding $M_t$; high WoA + no scrutiny ⇒ lower EC-11 precision | 🟡 wired evidence-only; **route to precision (WS-2)** |
| C2 | **Conversational grounding** | Clark & Brennan — initiation / grounding / **repair**; repair turns are richer evidence | new: `trait/grounding.py` (leaf, Codex) | Classifies each human turn's grounding function; **repair turns raise EC/CA evidence precision** | 🔴 add as a leaf behind the `INTERFACES.md §1` pattern |
| C3 | **Epistemic vigilance** | Sperber & Mercier — justification requests, source probing, prior-expression; a distributed signal hard to fake | new: `trait/vigilance.py` (leaf, Codex) | The vigilance *pattern* conditions EC/CA precision; never a per-turn score | 🔴 add as a leaf |
| C4 | **Dawid–Skene sycophancy correction** | Dawid & Skene — two biased raters, unknown truth → EM-recover the latent label + per-rater bias | new: `calibration/dawid_skene.py` (CE) | A **required preprocessing gate** on dual annotations + the self-rating; de-biases the judge's elaborated-over-terse tilt; calibrates CSL origin tags | 🔴 **immediate reliability win**; the self-rating already exists (`worker/self_rater.py`) and is consumed only as the calibration gap — keep it that way |
| C5 | **Predictive interaction entropy** | Shannon — prompt-entropy over the session; low entropy over a long session = cognitive narrowing | extend `state/epistemic_classifier.py` (Antigravity/CE) | A PR/CD **context prior on the *meaning* of a firing**, reported with CIs — not the score | 🔴 add as a context field |

**Wiring rule for all five (the one that keeps them honest):** a conditioner produces a *precision multiplier on the evidence term*, which `merge/precision.py` (or its evidence-side analogue) folds into the CI — it never produces a multiplier on the *score*. Concretely, the evidence a neuron contributes enters the dimension posterior with weight ∝ π(context); low π widens the CI and moves the posterior less. The audit test for WS-2 is the same as R2: **for any conditioner, score value out == score value in; only CI changes.**

### 3.2 The relational-AI and behavioral-economics evidence fields

v3/v3.1 grounded several existing CA/AUI/EC neurons in relational-AI psychology (attachment, anthropomorphism, parasocial deference) and behavioral economics (present bias, prospect theory — *why* users surrender). Per addendum #6, these are **evidence fields only**: a relational-AI signature may map to an existing CA neuron *after human review of a clean mapping*; task-irrelevant disclosure remains an **unscored observation**. **WS-2 task:** add a `relational_signatures` evidence extractor that flags the patterns and persists them, but routes to a CA neuron's evidence *only* through the D-020/D-021 human-approved-map pattern — never auto-wired.

### 3.3 The state cascade as the psychological mechanism

The $C_t \to A_t \to M_t$ cascade (extraneous-load spike → affective dysregulation → metacognitive shutdown) is the mechanistic signature of surrender forming in real time (Shaw & Nave System-3 account). In the repo, `metacog_classifier.py` owns surrender and `estimator.py` computes cascade flags. **WS-2 task (DESIGNED, not shipped):** keep the **$A_t$ degradation branch pre-registered** — if text-derived affect fails the identifiability test, the cascade re-estimates as the direct $C_t \to M_t$ path. No permitted claim depends on $A_t$. The `StateVector.a_t` field and `cascade_flags` already exist to carry this.

### 3.4 The event-conditioned reaction layer (the most trait-like psych signal)

`dynamics/reactions.py` already implements the v3.21 §6.11 layer: for each of the six trigger events, the first substantive human response is classified and π(r|e) estimated with Dirichlet partial pooling, every cell gated on event count. The flagship is the **Friction Transition Matrix** — P(VERIFY | E-FRICTION) vs P(ACCEPT-FLAT/DISENGAGE | E-FRICTION) — the single contrast with the strongest prior claim to predicting the deferred probe. This is psychology done as engineering: *what a person does when something happens* is closer to who-they-are-as-a-collaborator than any base rate. **WS-3 task:** persist the full π(r|e) matrix per session (it is currently summarized into the response); it is the highest-value research artifact the dynamics layer produces.

---

## PART 4 — THE RESEARCH DATA SPINE (WS-3)

The explicit ask — *store the output of everything that matters for further research*. The repo already has a strong recoverability tier (Part 2.11). This workstream completes it. The governing principle is **capture-don't-condition (#addendum):** record every research-relevant signal the moment it is computable; gate its *use in live scoring* until its validity gate clears.

### 4.1 The invariant: every score reproducible after the transcript purges

This is already largely true (provenance columns + neuron_firings + turn_state + judge_runs). The completion criterion: **given a `scores` row and its sibling artifact rows, the full `ScoreResponse` can be reconstructed and re-explained without the raw transcript.** WS-3's job is to close the three holes where a research-relevant signal is computed and then dropped.

### 4.2 What to add — all additive, all freeze-safe

| Add | Where | Why it matters for research | Rung |
|---|---|---|---|
| **`session_intent`** (Learning/Execution/Exploration/Brainstorming/Delegation/Emotional-support) classified at score-time | new column on `scores` + `trait/intent_classifier.py` already exists for tier; persist the label | Interpretation conditioning (§7.3); needed to ever stratify outcomes by task type. Track 3 of D-013. | MEASURABLE (noisy — surface confidence) |
| **A/S-turn partition + ΔR series** | new artifact rows keyed by chat | The falsification data for S_human (§6.5.1: drop if ΔR≈0 across users). Without it, the metric can never be tested. | DESIGNED |
| **Full π(r|e) reaction matrix** | promote from response-summary to a persisted artifact | The reaction-signature layer is the strongest predictor candidate for the probe (§8.9.3). | MEASURABLE |
| **Question-complexity longitudinal trio** (`mean_complexity`, `complexity_trend`, `originality`) | index from the question_quality blob | A candidate **sustainability** observable (§6.13) — the npj-Science-of-Learning corroboration that question sophistication tracks knowledge. | MEASURABLE |
| **WoA per-episode series** | index from the reliance blob | The appropriate-reliance trajectory; feeds the calibration-slope when the claim-risk classifier lands. | DESIGNED |
| **Gold-corpus coverage view** (archetype × language × twin-pair cells) | a read view over `data/gold/metadata.json` | Makes the §8.3 quota gap and the twin-gate readiness *visible* — the EC fix and the §8.9.5 gate both depend on it. | — |
| **`drift_runs`** (frozen anchor set re-scored on schedule) | new table + a CI/cron job | §8.6: separates **judge drift** (instrument moved) from **subject change** (person moved). Without a fixed anchor re-score, drift is invisible. | MEASURABLE |
| **The deferral register as data** | `contracts/deferral_register.yaml` + a loader | Survives external proposals with epistemic tags + reinstatement triggers (the governance artifact the spec mandates); also the *output sink* for the WS-4 self-exploration protocol. | — |

### 4.3 The principle made operational — three storage tiers

- **Tier R0 — reproducibility (must never drop):** provenance, neuron_firings, turn_state, judge_runs, the event log. *Already complete.*
- **Tier R1 — research signals (capture now, gate use):** session_intent, A/S partition, reaction matrix, question-complexity trio, WoA series, relational signatures. *Persist as artifacts; never condition a live score until validated.*
- **Tier R2 — validation infrastructure (the program's future):** the gold coverage view, `drift_runs`, the deferral register, and — when it exists — the retention-probe table (`probe_schema.yaml` is the contract). *The substrate that moves the instrument from MEASURABLE to VALIDATED.*

### 4.4 The multi-session store (the unlock for λ and erosion debt)

The debt EWMA and λ are single-session-blind today because there is no per-subject session sequence assembled. The `subjects` table (opaque `subject_id`, migration 006) is the key; **WS-3 task:** a `subject_sessions` read path that assembles a subject's scored sessions in order, feeding the cross-session debt trajectory and the eventual λ estimate. This stays **DESIGNED** for λ and **MEASURABLE** for the descriptive debt trajectory until the probe validates the outcome interpretation. No pilot fitting (#addendum-2).

---

## PART 5 — THE AGENT SELF-EXPLORATION PROTOCOL (WS-4)

The explicit ask — *the brief must include self-exploration and let agents find good things to introduce by themselves.* This is the most novel workstream, and it has to be designed so that "agents improving the framework on their own" never becomes "agents drifting the framework." The protocol below makes discovery a first-class, encouraged activity **bounded by four hard red lines that always route to a human.**

### 5.1 The shape of it

Self-exploration is a **three-stage loop** that fits the existing governance (`DISCREPANCY.md`, the ADR log, the deferral register) rather than inventing a parallel one:

```
   DISCOVER ──────────────▶ PROPOSE ──────────────▶ TRIAGE
 (agent runs the          (agent files a           (CE or human adjudicates;
  Discovery Pass;          PROPOSAL entry;           one of three verdicts;
  harness surfaces         freeze-checked,           red-line proposals ALWAYS
  candidates)              rung-tagged, evidenced)   stop for human sign-off)
        ▲                                                     │
        └─────────────────── REINSTATEMENT TRIGGER ◀──────────┘
              (deferred proposals carry a condition that re-surfaces them)
```

### 5.2 Stage 1 — DISCOVER: what an agent is *encouraged* to look for

At the start of a work session (and via the automated harness in §5.6), an agent runs the **Discovery Pass** — a fixed checklist of questions that reliably surface good engineering. The green-list domains where self-improvement is actively wanted:

1. **Unwired evidence.** Is there a signal that *computes* but doesn't reach the score as evidence? (e.g. a deterministic neuron the contract table marks `deterministic` but no extractor fires; a psych conditioner that produces a value nobody consumes.)
2. **Dropped research data.** Is a research-relevant signal computed and then discarded before persistence? (the WS-3 holes are exactly these.)
3. **Determinism risk.** Does any path produce a different output on re-run of the same input? (un-pinned ordering, un-frozen cuts, embedding batch variance.)
4. **Coverage gaps.** Does a leaf lack its three obligatory tests (happy path, empty session, absent≠zero)? Is a branch untested?
5. **Stub-ready-to-ship.** Is something stubbed whose *data gate has actually cleared*? (Almost never true yet — but the agent should check, not assume.)
6. **Provenance/audit completeness.** Can every emitted number be reproduced from persisted rows after a transcript purge? If not, what's missing?
7. **Docstring/ADR drift.** Does a module's behaviour no longer match its docstring or the ADR that authorized it?
8. **Performance & cost.** Is a judge call, embedding pass, or DB query doing redundant work? (cost discipline matters; see the Skill-TokenSaver line of work in project files.)

### 5.3 Stage 2 — PROPOSE: the safe format

An agent that finds something files a **PROPOSAL** — a new entry type in a `PROPOSALS.md` register (sibling to `DISCREPANCY.md`), using this template:

```
## P-NNN  [PROPOSED]  — <one-line title>
- Found by: <CE | Codex | discovery-harness>
- Date / git_sha: <when / sha>
- Domain: <one of the 8 Discovery Pass domains>
- Finding: <what, concretely — the file, the line, the gap>
- Evidence: <a failing test, a re-run diff, a dropped-signal trace, a coverage report>
- Proposed minimal change: <the smallest change that closes it>
- RUNG of the affected output: <DESIGNED | MEASURABLE | VALIDATED | ASPIRATIONAL>
- FREEZE CHECK (mandatory, all four):
    [ ] adds NO neuron / dimension / pillar / latent variable (#1)
    [ ] introduces NO score multiplier; state/psych stays precision-only (#2)
    [ ] crosses NO Wall (no outcome claim from transcript-only data)
    [ ] edits NO contract/schema without CE sign-off (#21)
- REJECTED-IDEAS CHECK: <confirm this is not a re-proposal of a §14/legacy-ADR rejected idea>
- Self-classification: <green-list autonomous | needs-CE-review | RED-LINE-needs-human>
- Status: PROPOSED
```

### 5.4 Stage 3 — TRIAGE: three verdicts, mirroring the framework's own discipline

Every proposal is triaged exactly the way the framework triages external ideas (§0.9): **genuine addition** (adopt), **already covered under a different name** (log + close), or **architecturally dangerous / out of scope** (defer to the register with a reinstatement trigger). The adjudicator is the CE for green-list items and a **human (project lead) for anything touching a red line.**

### 5.5 The four red lines (hard stops — an agent may NEVER self-adopt these)

These are non-negotiable and exist precisely because an autonomous agent optimizing locally is the *exact failure mode the framework studies in humans*. Any proposal that touches one of these is **auto-classified RED-LINE and routed to the project lead, no exceptions:**

1. **Ontology** — adding/merging/removing any neuron, dimension, pillar, or latent variable. (Lifting the freeze needs the corpus + EFA + the predictive-validity gate, not an agent's judgment.)
2. **Score semantics** — turning any state/psych/CSL signal into a multiplier on a score value, or letting the judge emit unbounded scores. Precision-only, always.
3. **The Wall** — making any sustainability/synergy/λ/ownership claim from transcript-only data, or un-stubbing λ / true synergy / the retention curve before probe data exists.
4. **Contracts** — editing `contracts/schemas.py`, `contract_table.yaml`, `claims_table.yaml`, `INTERFACES.md`, or any frozen artifact without CE sign-off (and a re-read by affected owners).

### 5.6 The discovery harness (automation that surfaces candidates)

A CI job (`.github/workflows/discovery.yml`, non-blocking) runs the Discovery Pass mechanically each night and on each PR, emitting candidate findings for an agent to triage — turning self-exploration from "remember to look" into "the gaps come to you":

- **Unwired-evidence scan:** diff the contract table's `deterministic` neurons against the neurons any extractor actually fires → list the unimplemented ones.
- **Dropped-signal scan:** assert every research-relevant computed object in `ScoreRun` reaches a persisted row → flag any that don't.
- **Determinism probe:** score a fixture chat twice; byte-diff the `ScoreResponse` (minus timestamps) → fail-loud on drift.
- **Coverage probe:** flag any leaf missing its three obligatory tests.
- **Provenance probe:** reconstruct a fixture score from persisted rows alone → flag any field that can't be rebuilt.
- **Rung-violation grep + forbidden-word grep:** any output asserted above its rung; any "surrender" outside the CSPC modules.

Each harness hit auto-drafts a `P-NNN [PROPOSED]` stub with the freeze-check pre-filled to the safe default (all boxes unchecked → needs review), so the agent triages rather than authors from scratch.

### 5.7 What "good" looks like (the reward function for self-exploration)

An agent is doing this well when its proposals: close a *real* gap backed by *evidence* (a failing test, a re-run diff, a dropped-signal trace — never a vibe); take the *smallest* change that closes it; preserve every non-negotiable; and *raise the research value or reliability* of the instrument without advancing any claim's rung. A proposal that adds capability the data doesn't yet support is **correctly rejected**, and the rejection is itself good engineering.

---

## PART 6 — THE "BEST ENGINEERING WORK" STANDARD (WS-5)

The ask — *check the best engineering work on our framework.* The repo already demonstrates most of this; WS-5 codifies it as an enforced bar so it cannot regress.

### 6.1 The eight engineering invariants (what integrity depends on)

1. **Determinism.** Same input → same output. No network/randomness without a fixed seed. (D-017/D-018 correctly scope this to live paths only.)
2. **Evidence, never verdict.** New signals enter as evidence + provenance + precision; `merge()`'s value-in==value-out is the law (R2).
3. **Absent ≠ zero.** Four distinct states, never collapsed (#12); enforced at the row level in `neuron_firings`.
4. **Provenance completeness.** Every score reproducible from persisted rows after the transcript purges (Part 4.1).
5. **Failure isolation.** A parallel layer (CSL) error never fails the core score; the worker degrades loudly, never silently.
6. **Rung-tagging.** Every emitted field carries exactly one rung; the report generator structurally cannot exceed it (#14).
7. **The partition.** State-diagnostic, competency-diagnostic, and AI-side channels stay disjoint — the non-circularity guarantee (§2.2).
8. **Ownership discipline.** No two agents edit the same file; contracts change only via CE + re-read (#21); blockers go to `DISCREPANCY.md`, never silent workarounds.

### 6.2 The definition-of-done for any change

A change is done when: it has unit tests beside the module (happy / empty / absent≠zero at minimum); it passes the MAE ratchet (≤ 0.2994 overall, ≤ 0.375 per-dim) if it touches the score path; it passes the determinism probe; it carries an ADR if it changed a resolved decision or a contract; its freeze-check is green; and its output's rung is correct and enforced.

### 6.3 The CI gates to add (named jobs)

The current `ci.yml` runs the suite. WS-5 adds, as named required jobs: **the MAE ratchet** (release gate); **the R2 audit** (merge value-in==value-out); **the determinism probe** (two-run byte-diff); **the four-state test** (the never-collapse labels); **the forbidden-word grep** ("surrender" outside CSPC); **the rung-violation check**; and **the discovery harness** (§5.6, non-blocking). The predictive-validity gate stays **load-bearing and non-configurable** (addendum #4) — no config may disable it or down-weight its margin.

---

## PART 7 — THE SEQUENCED EXECUTION PLAN

Ordered by dependency and leverage. Each task: owner, acceptance, gate. **STOP** markers are mandatory human-review points.

### Phase A — Unblock live data (prerequisite for everything that needs corpus growth)
1. **D-015 capture bridge** — Codex authors `content.js` §1–§9 active-path walk + `payload_builder.js` pass-through against the frozen D-015 contract; CE's spine is built. **Gate:** the interception-race test + a long virtualized thread captured as `capture_method:"interception"`, not the fallback. **(CE + Codex)**
2. **D-022 `is_minor` threading** — persist `is_minor` on `raw_chats`, thread through `_build_canonical_session` → `enforce()`. **Gate:** a minor-flagged chat never receives a bare composite/peer-rank/debt form (worker integration test). **(CE)** **STOP — minor-safety review before any minor-facing pilot.**

### Phase B — Evidence depth (WS-1)
3. Deterministic extractors for the contract-table `deterministic` neurons not yet implemented — one PR per dimension, **evidence-enrichment only** (judge keeps the value). **Gate:** each new firing appears in `neuron_firings`, never alters a `DimensionScore` value (R2). **(Codex)**
4. EC calibration-slope $\hat{s}$ field (behind the claim-risk classifier seed) — **stays N/A until the seed lands; no fabrication.** **(CE)**

### Phase C — AI-psychology layer (WS-2)
5. **Dawid–Skene gate** (`calibration/dawid_skene.py`) — the immediate reliability win; de-bias dual annotations + self-rating. **Gate:** the self-rating still feeds only the calibration gap, never a behavioral score. **(CE)** **STOP — confirm the de-biasing is calibration-only.**
6. **Grounding** (`trait/grounding.py`) and **vigilance** (`trait/vigilance.py`) leaves — repair/vigilance patterns → EC/CA evidence precision. **Gate:** R2 audit (value-in==value-out). **(Codex)**
7. **Predictive interaction entropy** — context prior on PR/CD firing *meaning*, reported with CIs. **(CE/Antigravity-pattern)**
8. **Route reliance (WoA) to precision** — currently evidence-only; route as $M_t$/EC-11 precision. **(CE)**
9. **Emergence judge confirmer** — wire behind the existing interface; **emergence-as-proof stays ASPIRATIONAL**; reportable count > 0 only after ICC certification (ADR-0011 → a follow-up ADR). **(CE)** **STOP — ICC certification before reportable emergence.**

### Phase D — Research data spine (WS-3)
10. Persist: `session_intent` (R1), A/S partition + ΔR (R1), full π(r|e) matrix (R1), question-complexity trio + WoA series (R1 index). **Gate:** the dropped-signal scan passes (every research object reaches a row). **(CE)**
11. `subject_sessions` read path → cross-session debt trajectory (MEASURABLE) + λ input (DESIGNED, **not fit** — addendum #2). **(CE)**
12. Gold-corpus coverage view + `drift_runs` table + nightly anchor re-score. **Gate:** drift run separates instrument drift from subject change on the anchor set. **(CE)**
13. `deferral_register.yaml` + loader (also the WS-4 sink). **(CE)**

### Phase E — Self-exploration + excellence (WS-4 + WS-5)
14. `PROPOSALS.md` register + the four-red-line freeze-check template. **(CE)**
15. `discovery.yml` harness (the six scans, non-blocking, auto-drafts P-NNN stubs). **(CE)**
16. CI gates: MAE ratchet, R2 audit, determinism probe, four-state, forbidden-word, rung-violation as named jobs. **(CE)**

### What stays DESIGNED / data-gated (do NOT build until the gate clears — addendum #3)
Full HGF; GRM/CDM/G-DINA fitting; causal-discovery fitting; KT sustainability; disclosure-effects analysis; drift/invariance *analysis* (the *runs* are collected in Phase D, the *analysis* waits for n); λ beyond the stub; true synergy; validated ownership. Each raises a clear data-gated error if invoked early.

---

## PART 8 — OPEN DISCREPANCIES, FOLDED IN

| Discrepancy | Where it sits | Action |
|---|---|---|
| **D-015** interceptor bridge | Phase A.1 | The live-capture unblocker; do first. |
| **D-022** `is_minor` on the live path | Phase A.2 | Minor-safety; STOP-gated before any minor pilot. |
| **D-023** feedback pre-population | UI polish, post-Phase-A | Ships submit-only now; read-path + model decision later. |
| **D-024** portfolio past/present radar | UI polish | Present-only now; the past window needs the `subject_sessions` store from Phase D.11 — **D-024 unblocks once D.11 lands.** |
| **D-026** account-management URL | UI polish | One-line swap when the web-app URL exists. |

---

## APPENDIX A — MODULE → LAYER → STATUS QUICK MAP

```
LAYER 1 ARI (trait)          status   LAYER 2 CSPC (state)         status
  trait/tagger.py              ✅A       state/load_classifier.py     ✅A
  trait/phase_classifier.py    ✅A       state/epistemic_classifier   ✅B
  trait/extractors/*.py (8)    🟡B-      state/metacog_classifier     ✅A
  trait/judge/*                ✅A       state/tomer_slope.py         ✅B
  trait/evidence.py (EC prov)  ✅A       state/estimator.py           ✅A
  aggregate/normalize.py       ✅A       merge/precision.py           ✅A  ← the template
  aggregate/softmin.py         ✅A
  aggregate/gates.py           ✅A     DYNAMICS
  aggregate/saturation.py      ✅A       dynamics/transitions.py      ✅A
                                         dynamics/overlay.py          ✅A
LAYER 3 CSL (work)                       dynamics/reactions.py        ✅A  ← psych signal
  csl/crosswalk.py             ✅A       dynamics/reliability_map.py  🟦B
  csl/projection.py            ✅A
  csl/ai_side_extractor.py     ✅B     LAYER 4 outcome
  csl/ownership.py             ✅A       sustainability/debt_tracker  🟡B
  csl/emergence.py             🟡A*      sustainability/ewma.py       🟡B
  csl/report.py                ✅A       sustainability/lambda_proxy  🟦A  ← keep stubbed
  csl/analytics/*              🟡B       sustainability/probe_schema  🟦A

AI-PSYCH (WS-2 core)                   CLAIMS / WALL
  trait/question_quality.py    ✅A       claims/{rungs,tier_engine,
  trait/reliance_metrics.py    ✅A         report,footer,views}.py    ✅A
  trait/grounding.py           🔴 add
  trait/vigilance.py           🔴 add   RESEARCH SPINE (WS-3)
  calibration/dawid_skene.py   🔴 add     provenance.py               ✅A
                                         migrations 005/006/008/011  ✅A
  * emergence: built; 0 reportable        + session_intent, A/S, π(r|e),
    until judge ICC-certified.             drift_runs, coverage view  🔴 add
```

## APPENDIX B — THE ADDITIVE SCHEMA DELTA (research spine, all freeze-safe)

All columns/tables are **additive**; none changes an existing contract field's meaning; none adds a neuron/dimension/latent variable.

| Object | Kind | Carries | Rung |
|---|---|---|---|
| `scores.session_intent` | column | the score-time intent label + confidence | MEASURABLE |
| `as_partition` | artifact rows | per-turn A/S class + `r_auto`/`r_steer`/ΔR | DESIGNED |
| `reaction_matrix` | artifact | full π(r\|e) per session | MEASURABLE |
| `qq_longitudinal` | index | mean_complexity / complexity_trend / originality | MEASURABLE |
| `woa_series` | index | per-episode Weight-of-Advice | DESIGNED |
| `relational_signatures` | artifact | flagged patterns (unscored unless human-mapped) | DESIGNED |
| `subject_sessions` | read path | ordered per-subject session sequence | — |
| `gold_coverage` | view | archetype × language × twin-pair cells | — |
| `drift_runs` | table | frozen-anchor re-score results on schedule | MEASURABLE |
| `deferral_register` | yaml + loader | deferred proposals + reinstatement triggers | — |
| `retention_probe` | table | per `probe_schema.yaml` — **when probe exists** | DESIGNED→VALIDATED |

## APPENDIX C — THE DISCOVERY PASS CHECKLIST (runnable each session)

```
[ ] Unwired evidence:    contract-table `deterministic` neurons − fired neurons = ?
[ ] Dropped signals:     every research object in ScoreRun → a persisted row?
[ ] Determinism:         fixture scored twice → byte-identical (minus timestamps)?
[ ] Coverage:            every leaf has {happy, empty-session, absent≠zero}?
[ ] Stub-ready:          any stub whose DATA gate actually cleared? (usually: no)
[ ] Provenance:          fixture score reconstructable from rows alone?
[ ] Doc/ADR drift:       module behaviour still matches its docstring + ADR?
[ ] Cost:                redundant judge/embedding/DB work?
→ Any hit: file P-NNN [PROPOSED] with the four-box FREEZE CHECK + evidence.
```

## APPENDIX D — THE GREEN / RED LISTS FOR AUTONOMOUS WORK

**GREEN (agent may implement after CE review, no human sign-off needed):** test coverage; determinism hardening; wiring an *already-approved* evidence field (D-020/D-021 pattern); research-data persistence completeness; docstring/ADR hygiene; performance/cost; harness scans.

**RED (always stop for the project lead):** anything touching the **ontology** (neurons/dimensions/pillars/latent variables); **score semantics** (multipliers, unbounded judge output); **the Wall** (outcome claims from transcript data; un-stubbing λ/true-synergy/probe-curve); **contracts** (`schemas.py`, `contract_table.yaml`, `claims_table.yaml`, `INTERFACES.md`).

---

*End of the SAF/ARI v3.21 Engineering Synthesis Brief. The architecture is sound and the discipline is real; the work ahead is convergence — evidence depth, the AI-psychology layer wired as precision, a complete research spine, and a bounded self-exploration loop — none of it touching the ontology, the claims ladder, or the Wall. The instrument is DESIGNED and MEASURABLE today; this brief is the engineering path that keeps it honest while the retention probe earns it the right to say VALIDATED.*
