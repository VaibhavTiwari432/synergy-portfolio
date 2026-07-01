# SAF/ARI v3 — Claude Code Upgrade Brief

**Builds on:** ChatClassifier v2 (108 passing tests; overall MAE ≈ 0.299, threshold ≤ 0.375; EC-dimension MAE the known weak spot; Gemini LLM judge in the extraction pipeline; `EqualWeightScorer` shipping, `GRMScorer` interface-only/stubbed).
**Reference spec:** `SAF_ARI_v3_SpecDelta_over_v2.2.md` (V1–V16). This brief implements the *buildable-now* subset and lays correct interfaces for the *data-gated* subset.
**Working discipline (unchanged):** short, precise tasks; **explicit STOP-for-human-review** at each phase boundary; **surface open questions rather than making silent architectural decisions**; never collapse N/A-class states; absent neurons are N/A, never zero; quantile cuts are **frozen, never recomputed**.
**Ontology:** FROZEN. Do not add neurons, dimensions, pillars, or latent-state variables. Every phase below operates over the existing 107→8→4 structure.

---

## Phase-ordering principle — what is buildable now vs data-gated

**BUILD NOW (no new data required):** P0 (security), P1 (saturated state), P2 (judge protocol), P3 (G-study harness — build now, *run* when ≥30 subjects), P4 (Q-matrix formalization + G-DINA validation *stub*), P5 (EIG question features), P6 (reporting layer), P11 (reliance-metric extractor where the transcript supports it).

**STUB / SKELETON ONLY (data-gated — build the interface, do not fit):** P7 (CDM backend), P8 (retention-stability fitter — skeleton; runs when probes exist), P9 (KT sustainability backend), P10 (drift/invariance — build the scheduler + test; *run* when longitudinal/anchor data exists).

Each phase tags its gate. **Do not fit any model on the 26 gold chats.** They are a pilot, not training data (spec §F2).

---

## P0 — Security remediation (do this first) `[BUILD NOW — P0/critical]`
- **Goal:** remove the OpenAI API key sitting in `telemetry.metadata` (JSONB).
- **Action:** (1) rotate/revoke the exposed key immediately at the provider; (2) write a migration that scrubs the key from all existing `telemetry.metadata` rows; (3) add a write-time guard / schema check that rejects any secret-shaped value in `telemetry.metadata`; (4) move credentials to the secrets manager / env, never the DB.
- **Acceptance:** no row in `telemetry.metadata` contains a credential; a unit test asserts the write-time guard rejects a secret-shaped payload; the old key is confirmed revoked.
- **STOP for human review** before deleting/altering production rows.

---

## P1 — `MEASUREMENT_SATURATED` censored-reporting state (spec V3) `[BUILD NOW]`
- **Goal:** add the third N/A-class state for instrument saturation, with right-censored ("≥ X") reporting; never report "= max".
- **Files:** `scoring/scorability.py` (extend), `scoring/scorer.py` (emit censoring flag), `reporting/labels.py` (new label).
- **Interface (extend the existing scorability return):**
  `scorability(matrix, dim, tau=3) -> {scorable: bool, na_reason: Literal["structural","insufficient_sample"]|None, saturation: Literal["none","ceiling","floor"], n_items: int}`
  and in the scorer output add `censored: {state: Literal["none","SATURATED_HIGH","SATURATED_LOW"], bound: float|None}`.
- **Saturation rule (EqualWeightScorer):** flag `ceiling` when the dimension's applicable items are all at max valence-normalized ordinal (and ≥ tau of them); `floor` symmetrically. For the future GRM backend, flag saturation when `SE(θ)` exceeds a threshold at the extreme of the information function (leave a `# TODO(GRM)` hook).
- **Reporting:** a saturated dimension renders as `≥ X (instrument saturated)` / `≤ X`, never a point value; it is a **distinct label** from `STRUCTURAL_NA`, `INSUFFICIENT_SAMPLE`, and from genuine low/high scores.
- **Acceptance:** a crafted fixture with all-max items returns `SATURATED_HIGH` and a bound, not `100`; the four states (`structural`, `insufficient_sample`, `saturated`, genuine score) are never collapsed in any output path; existing 108 tests still pass.
- **STOP for human review** of the saturation thresholds before wiring into reports.

---

## P2 — Judge non-determinism protocol (spec V2, A2) `[BUILD NOW]`
- **Goal:** stop treating the Gemini judge as deterministic; bound and log its variance; re-judge only near quadrant boundaries (stratified).
- **Files:** `inference/judge_runner.py` (N-replication wrapper), `inference/boundary.py` (boundary-band detector), `pipeline/provenance.py` (version pinning).
- **Interface:**
  `judge_score(chat, neuron_subset, *, n_replications:int=1) -> {scores, mean, sd, raw_outputs:list, judge_config:{model_id, version, params}}`
  `needs_rejudge(score_result, boundary_band:float) -> bool` (True iff the synergy–sustainability quadrant assignment is within `boundary_band` of a boundary).
- **Stratified flow:** score once → if `needs_rejudge` → re-run with `n_replications=N` (config, default 5) → report mean ± sd. Interior chats stay single-pass.
- **Tier-A hardening (same phase):** fix Python hash-seed nondeterminism (`PYTHONHASHSEED=0` in the pipeline entrypoint) and any async-ordering nondeterminism in mechanical-feature extraction; assert quantile cuts are loaded frozen, never recomputed at scoring time.
- **Acceptance:** same chat scored twice with `n_replications=1` on a hardened Tier-A path is bit-identical for mechanical features; the judge wrapper returns `sd > 0` across replications on a boundary fixture and logs `judge_config`; a frozen-cuts assertion fails loudly if cuts are recomputed.
- **STOP for human review** of `boundary_band` and `N` before enabling re-judging in batch.

---

## P3 — Generalizability-study harness (spec V1, A1) `[BUILD NOW; RUN when ≥30 subjects]`
- **Goal:** the K-replication study as a crossed `subject × judge-replication × occasion` G-study; estimate variance components; project K via a D-study; report the **absolute Φ** coefficient and the **quadrant flip rate**.
- **Files:** `validation/gtheory/gstudy.py`, `validation/gtheory/dstudy.py`.
- **Interface:**
  `run_gstudy(scores_long_df) -> {variance_components:{subject, judge_rep, occasion, interactions...}, phi_absolute, g_relative, residual_share}`
  `run_dstudy(variance_components, k_grid:list[int]) -> {k: phi_absolute}` (projects dependability vs number of judge-replications).
- **Notes:** report the **absolute Φ** (criterion-referenced), not the relative G-coefficient (ranking) — ranking is prohibited. Add `quadrant_flip_rate(replications)` as the decision-relevant reliability number.
- **Acceptance:** on a synthetic crossed dataset with known variance, components recover within tolerance; the D-study curve is monotone non-decreasing in K; a guard refuses to *report estimates* (vs design) when `n_subjects < 30` and instead emits `"under-powered: design fixed, estimates pending"`.
- **STOP for human review** before running on real data (and only once n ≥ 30 diverse subjects).

---

## P4 — Q-matrix formalization + G-DINA validation stub (spec V4, B1) `[FORMALIZE NOW; VALIDATE = STUB, data-gated]`
- **Goal:** materialize the existing 107→8 neuron→dimension map as a formal **Q-matrix** (107 × 8 binary), and lay the G-DINA validation interface that will later *test* whether each neuron loads on its assigned dimension.
- **Files:** `model/qmatrix.py` (build + validate the Q-matrix object from `contract_table.yaml`), `validation/cdm/gdina_validate.py` (interface only).
- **Interface:**
  `build_qmatrix(contract_table) -> QMatrix` (rows = 107 neurons, cols = 8 dimensions; entry 1 iff neuron loads on dimension).
  `qmatrix_sanity(QMatrix) -> {has_identity_submatrices: bool, each_attribute_measured: bool, n_single/double/triple_attribute_items}` (CDM identifiability preconditions — see spec V6/§8.1).
  `validate_qmatrix_gdina(responses, QMatrix) -> ItemAttributeFitReport`  # `raise NotImplementedError("data-gated: requires classification corpus")`
- **Acceptance:** `build_qmatrix` reproduces the documented per-pillar neuron counts (AL 13, PR 15, EC 14, ES 14, CS 11, CD 11, AUI 12, CA 17 = 107); `qmatrix_sanity` flags whether identity submatrices exist (identifiability precondition); the G-DINA validator is present as a typed stub that raises until data exists.
- **STOP for human review** of the Q-matrix once built — this is the artifact that converts the neuron→dimension assignment from assumption to testable hypothesis; a human must confirm the loadings before it becomes canonical.

---

## P5 — EIG question-quality feature extractor (spec V9, C3) `[BUILD NOW]`
- **Goal:** score the human's prompts for question quality and feed the result into **existing** PR/AL/EC neurons (no new dimension); also emit a per-session question-complexity summary for the longitudinal layer.
- **Files:** `inference/question_quality.py`.
- **Interface:**
  `score_questions(chat) -> {per_turn:[{turn_id, eig_proxy:float, graesser_type:str, bloom_tier:int, specificity:float}], session_summary:{mean_complexity, complexity_trend, originality}}`
  Then map these features into the existing neuron evidence stream for PR/AL/EC (do **not** create new neurons; add as new *evidence fields* on existing ones, per the freeze).
- **Notes:** `eig_proxy` is an expected-information-gain-style heuristic over the question given prior context (document the approximation; it is one feature among several, not ground truth). `graesser_type` uses the Graesser & Person question taxonomy; `bloom_tier` uses the Bloom mapping already in project files.
- **Acceptance:** on fixtures, higher-tier questions (synthesis/evaluation) yield higher `eig_proxy`/`bloom_tier`; the features attach to PR/AL/EC evidence without altering the neuron count; `session_summary.complexity_trend` is computable across a multi-turn fixture.
- **STOP for human review** of which exact neurons each feature feeds (PR vs AL vs EC) before wiring — surface this mapping as an open question rather than deciding silently.

---

## P6 — Reporting layer: three views, never-collapse, saturated state (spec V3/G8) `[BUILD NOW]`
- **Goal:** implement the three view contexts keyed to the ID hierarchy, with the never-collapsible epistemic footer and the new saturated state surfaced correctly.
- **Files:** `reporting/views.py`, `reporting/footer.py`.
- **Interface:**
  `render_chat_view(saf_session_id)`, `render_project_view(project_id)`, `render_portfolio_view(subject_id)` — Portfolio View gated behind a **one-time acknowledgement screen**; an **always-visible, never-collapsible epistemic footer** on every view.
- **Never-collapse rule (enforced in code):** `STRUCTURAL_NA`, `INSUFFICIENT_SAMPLE`, `MEASUREMENT_SATURATED`, and genuine low scores render as **four distinct labels** — a single "Focus area" bucket is prohibited. Add a test that fails if any two are mapped to the same label.
- **Comparisons:** only user-vs-user-previous (personal baselines); **no population comparison, no leaderboard** (assert in code).
- **Theater-rate (TR) panel:** population-level theater-rate dashboard (share of sessions with null downstream behavioral change), per Grok G8.
- **Acceptance:** the four states render distinctly; Portfolio View is unreachable without the acknowledgement; the footer cannot be collapsed; a test asserts no population-ranking code path exists.
- **STOP for human review** of the footer copy and the acknowledgement-screen wording.

---

## P7 — CDM `ScorerBackend` (spec V4, B1) `[STUB — data-gated]`
- **Goal:** add CDM (DINA/DINO/G-DINA) as a classification backend implementing the existing `ScorerBackend` ABC, **complementary** to GRM (estimation). Interface only; do not fit.
- **Files:** `scoring/cdm_scorer.py`.
- **Interface:** implement `ScorerBackend` with `classify(items_for_dim, qmatrix) -> {attribute_profile:dict, slip, guess, posterior}`; `raise NotImplementedError("data-gated: CDM fit requires classification corpus (spec §F2/§F3)")` in the fit path.
- **Notes:** DINA = conjunctive/non-compensatory (the formal twin of `minimum-across-pillars`, §3.6); document this correspondence in the module docstring. CDM gives discrete α per dimension; GRM gives continuous θ — same frozen 8 dimensions, different question (classify vs estimate). Do not let one overwrite the other.
- **Acceptance:** the stub satisfies the `ScorerBackend` contract (swapping it in does not break calling code); the fit path raises the data-gated error; the docstring states the DINA↔§3.6 correspondence.

---

## P8 — Retention-stability fitter (spec V8, C2) `[SKELETON NOW; RUN when probes exist]`
- **Goal:** replace the binary 48-h retention gate with a fitted **stability** parameter (FSRS Difficulty–Stability–Retrievability, or half-life regression).
- **Files:** `sustainability/retention_stability.py`.
- **Interface:**
  `fit_stability(probe_events:list[{subject_id, skill, elapsed_hours, recalled:bool|score}]) -> {stability, difficulty, retrievability_curve}`
  `stability_trend(subject_id, skill) -> {slope, direction:Literal["rising","flat","falling"]}`.
- **Notes:** require ≥2 staggered probes ≥24 h apart (no sub-hour claims — FSRS has no short-term-memory model). Rising stability = capacity growth; falling = cognitive debt. Feed `stability` to P9 (KT) and to the §8.3 predictive-validity target.
- **Acceptance:** on synthetic probe data with a known decay, `fit_stability` recovers stability within tolerance; the fitter refuses (clear error) with <2 probes or sub-24-h spacing; `stability_trend` classifies rising/flat/falling correctly on synthetic series.
- **STOP for human review** before scheduling real probes (probe cadence + framing as "skill boosters" per the DPDP/consent posture).

---

## P9 — KT sustainability backend (spec V7, C1) `[STUB — data-gated]`
- **Goal:** interpretable knowledge-tracing backend (BKT/IKT with an **active forgetting parameter**), hosted in the existing HGF, tracking the across-session trajectory of the longitudinal-sink dimensions (AUI/CA). Interface only.
- **Files:** `sustainability/kt_tracer.py`.
- **Interface:** `update_trajectory(subject_id, dim, session_observations) -> {mastery_posterior, forgetting_rate, uncertainty}`; `raise NotImplementedError("data-gated: requires multi-session sequences per subject")` in the fit path.
- **Notes:** **interpretable tracer only — not deep DKT** (interpretability + existing embedding deferral). Must be uncertainty-preserving. The mastery trajectory is the *temporal readout of an existing dimension* — not a new construct (freeze audit §V-Audit). Consumes P8 stability as an observable.
- **Acceptance:** stub satisfies the interface; fit path raises the data-gated error; docstring states "interpretable, forgetting-on, HGF-hosted, no new construct."

---

## P10 — Drift / scalar-invariance scheduled re-scoring (spec V10, D1) `[BUILD scheduler NOW; RUN data-gated]`
- **Goal:** re-score the frozen anchor set on a fixed schedule and test **scalar invariance over time (ΔCFI)** to distinguish judge drift from subject change.
- **Files:** `validation/drift/anchor_rescore.py` (scheduler — build now), `validation/drift/invariance.py` (ΔCFI test — build now; runs when ≥2 anchor occasions exist).
- **Interface:**
  `rescore_anchor_set(anchor_chat_ids, schedule) -> occasion_scores` (build now; pins judge_config per occasion).
  `test_scalar_invariance(occasion_scores) -> {configural, metric, scalar, strict, delta_cfi, drift_alarm:bool}` (alarm = scalar invariance fails across occasions ⇒ instrument moved).
  `select_anchors_regdif(responses, group) -> anchor_items` (Reg-DIF; small-sample-friendly).
- **Acceptance:** the scheduler re-scores the anchor set and stores per-occasion `judge_config`; the invariance test returns a `drift_alarm` on a synthetic occasion-shift fixture; the test refuses (clear message) with <2 occasions.
- **STOP for human review** of the re-scoring schedule and the ΔCFI threshold for the drift alarm.

---

## P11 — Appropriate-reliance metric extractor (spec V12, E1) `[BUILD NOW where transcript supports]`
- **Goal:** compute the validated reliance metrics from the transcript where derivable; flag where they require the judge-advisor / tasklet design (not in a raw chat).
- **Files:** `inference/reliance_metrics.py`.
- **Interface:** `reliance_metrics(chat) -> {weight_of_advice:float|None, switch_fraction:float|None, appropriate_reliance:{over:float, under:float}|None, derivable:bool, note:str}` (return `None` + a note when the signal needs a controlled judge-advisor setup rather than a raw transcript).
- **Notes:** WoA = continuous shift toward AI advice; switch fraction = answer-change rate. These feed the EC dimension and the metacognitive calibration gap — **the self-rating widget feeds only the calibration gap, never the behavioral scores** (unchanged design rule). Appropriate-reliance over/under requires knowing whether the AI advice was correct — flag as `derivable:false` for raw chats lacking ground truth.
- **Acceptance:** on a fixture where the human revises toward AI advice, `weight_of_advice` and `switch_fraction` are computed; `appropriate_reliance` returns `None` with a note when correctness ground truth is absent.

---

## Cross-cutting: governance & metrics (spec V14/V15)
- **QWK alongside MAE:** add Quadratic-Weighted Kappa to the judge-vs-human-gold evaluation report (`evaluation/agreement.py`), reported beside the existing MAE. The EC weak spot should be examined in QWK (category-agreement) terms, not MAE alone.
- **Benchmark vs pilot guardrails (code-level):** tag the 26 gold chats as `dataset_role="pilot"` in metadata; any code path that would fit GRM/EFA/CDM on `dataset_role="pilot"` must refuse with `"pilot set is a validation anchor, not training data (spec §F2)"`. Separate the **8-dimension** and **107-neuron** annotation timelines as distinct dataset tags (`grain="dim8"` vs `grain="neuron107"`); the 107-neuron psychometric fits refuse on `dim8`-grain data.

---

## Consolidated STOP-for-human-review points
1. **P0** — before altering production telemetry rows.
2. **P1** — saturation thresholds before wiring into reports.
3. **P2** — `boundary_band` and `N` before batch re-judging.
4. **P3** — before any real-data G-study run (and only at n ≥ 30 diverse subjects).
5. **P4** — the built Q-matrix, before it becomes canonical (assumption → tested hypothesis).
6. **P5** — which neurons each EIG feature feeds (open question, not a silent decision).
7. **P6** — epistemic-footer copy + Portfolio-View acknowledgement wording.
8. **P8** — probe cadence + framing before scheduling real retention probes.
9. **P10** — re-scoring schedule + ΔCFI drift-alarm threshold.

---

## Data-gating summary

| Phase | Build now? | Runs/fits when… |
|---|---|---|
| P0 security | ✅ full | immediately |
| P1 saturated state | ✅ full | immediately |
| P2 judge protocol | ✅ full | immediately |
| P3 G-study harness | ✅ build | n ≥ 30 diverse subjects |
| P4 Q-matrix | ✅ build/formalize | G-DINA validate when classification corpus exists |
| P5 EIG features | ✅ full | immediately |
| P6 reporting | ✅ full | immediately |
| P7 CDM backend | ⛔ stub only | classification corpus (§F2/F3) |
| P8 retention fitter | 🟡 skeleton | ≥2 staggered unaided probes exist |
| P9 KT backend | ⛔ stub only | multi-session sequences exist |
| P10 drift/invariance | 🟡 scheduler+test | ≥2 anchor-rescore occasions exist |
| P11 reliance metrics | ✅ where derivable | tasklet metrics need judge-advisor design |

**The one rule above all:** do not fit any model on the 26 gold chats. They are a pilot/seed; treating them as training data or a benchmark is rung-inflation the framework's own discipline forbids.

*End of v3 Claude Code upgrade brief.*
