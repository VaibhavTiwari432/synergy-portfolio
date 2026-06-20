# SAF/ARI v3.1 — Claude Code Upgrade Brief

**Builds on:** the v3 Claude Code brief (`SAF_ARI_v3_ClaudeCode_Upgrades.md`) and ChatClassifier v2 (108 tests; MAE ≈ 0.299; Gemini judge; `EqualWeightScorer` shipping; `GRMScorer`/CDM/KT stubbed). v3.1 is a **small point release** — most of it is governance/grounding; the buildable code is a focused set.
**Reference spec:** `SAF_ARI_v3.1_SpecDelta_over_v3.md` (changes V3.1-A … V3.1-F).
**Working discipline (unchanged):** short tasks; **explicit STOP-for-human-review** at phase boundaries; **surface open questions rather than deciding silently**; absent neurons → N/A, never zero; never collapse N/A-class states; quantile cuts frozen.
**Ontology:** FROZEN. No new neurons/dimensions/pillars/latent variables. Every phase is a new *field* on an existing neuron, a pre-registration artifact, or a governance gate.

---

## Phase-ordering principle
**BUILD NOW (freeze-compliant fields/gates):** P1 (Brier field), P2 (relational-AI signatures), P4 (iatrogenic gate), P6 (§8.3 guard).
**ARTIFACT NOW / FITTING STUBBED (data-gated):** P3 (causal DAG pre-reg + estimation stub), P5 (A/B disclosure scaffold; analysis data-gated).
**Do not fit any model on the 26 gold chats.** Pilot, not training data. **Do not run causal discovery on the pilot corpus** (spec §14.1).

---

## P1 — Brier-score metacognitive-calibration field (spec V3.1-A) `[BUILD NOW]`
- **Goal:** add a strictly proper scoring rule over probabilistic self-assessments, feeding the calibration gap alongside the existing calibration slope.
- **Files:** `inference/calibration.py` (extend), `model/neuron_fields.py` (register new field on CA-08).
- **Interface:**
  `brier_score(self_assessments:list[{prob:float, outcome:0|1}]) -> float|None` (mean squared (prob − outcome); lower better; `None` if no realized outcome is observable in-session).
  Extend the calibration-gap output: `{calibration_slope, brier:float|None, n_scored:int}`.
- **Rules:** feeds **CA-08** evidence and the calibration-gap metric, **alongside** (not replacing) the slope (§5.8d). The self-rating widget continues to feed **only** the calibration gap, **never** behavioral scores. Returns N/A (never zero) when no in-session outcome exists to score against.
- **Acceptance:** on a fixture where stated confidences match outcomes, Brier ≈ 0; on a confidently-wrong fixture, Brier ≈ 1; both over- and under-confident fixtures score worse than calibrated ones; field attaches to CA-08 without changing the neuron count; the no-outcome path returns N/A; existing 108 tests pass.
- **STOP for human review** of how Brier and the slope combine in the reported calibration gap (do not silently pick a weighting).

---

## P2 — Relational-AI-psychology signature extractor (spec V3.1-D) `[BUILD NOW]`
- **Goal:** extract attachment/anthropomorphism/parasocial signatures from the transcript and feed them as **new evidence fields on existing CA neurons** — no new neuron.
- **Files:** `inference/relational_signatures.py`.
- **Interface:**
  `relational_signatures(chat) -> {over_deference:float, anthropomorphic_attribution:float, override_resistance:float, task_irrelevant_disclosure:float, mapping_note:str}`
  then attach (per the human-confirmed mapping): over_deference / failure-to-correct → **CA-15** (inverse); anthropomorphic_attribution → **CA-06**, **CA-13**; override_resistance → **CA-01**.
- **Open question (do NOT silently decide):** `task_irrelevant_disclosure` may have **no clean neuron home**. Emit it in the output with `mapping_note`, but **do not force it onto a neuron** — if review finds no home, it stays an unscored observation (never a new neuron).
- **Acceptance:** on fixtures, a transcript where the user never corrects a wrong AI claim raises `over_deference` and feeds CA-15 (inverse); a transcript treating the AI as a confidant raises `anthropomorphic_attribution`; neuron count unchanged; `task_irrelevant_disclosure` is reported but unattached pending review.
- **STOP for human review** of the signature→neuron mapping **and** the disposition of `task_irrelevant_disclosure` before wiring into scoring.

---

## P3 — Causal DAG pre-registration artifact + estimation stub (spec V3.1-B) `[ARTIFACT NOW / STUB]`
- **Goal:** materialize a **frozen causal hypothesis** over existing nodes so future analysis is confirmatory; lay the estimation interface that raises until data exists.
- **Files:** `validation/causal/dag_hypothesis.py` (the frozen artifact), `validation/causal/estimate.py` (stub).
- **Interface:**
  `build_causal_dag() -> CausalDAG` — nodes = existing 8 dimensions + 4 CSPC states + sustainability observables (λ, retention stability); edges = hypothesized directions (AL upstream → orchestration/agency gate generative dims → EC+CS guard the explanation trap → longitudinal-sink dims → future θ/transfer). Frozen + hashed so revisions are explicit.
  `validate_dag_acyclic(CausalDAG) -> bool`.
  `estimate_causal_effects(longitudinal_data, dag) -> CausalEffectReport` → `raise NotImplementedError("data-gated: requires reliable instrument + longitudinal corpus + EFA (spec §14.1/§14.2); causal-discovery fitting on the pilot corpus is rejected")`.
- **Notes:** name (in docstrings) the intended toolbox — potential outcomes, **longitudinal g-methods** for time-varying confounding, dynamic SEM, Bayesian change-point for model-era shifts — but **do not implement fitting**. The counterfactual probes (commitment 9) are the data source.
- **Acceptance:** `build_causal_dag` returns an acyclic graph over **only existing** nodes (a guard rejects any node not in the frozen ontology); the artifact is hash-stamped; the estimation function raises the data-gated error; a test asserts no PC/FCI/GES discovery routine runs against `dataset_role="pilot"`.
- **STOP for human review** of the DAG edge set before it is frozen as the pre-registered hypothesis — this is the artifact the eventual causal claims hang on.

---

## P4 — Iatrogenic-risk disclosure gate (spec V3.1-C) `[BUILD NOW]`
- **Goal:** gate summative disclosure of negative sustainability signals; extends the v3 reporting layer (P6).
- **Files:** `reporting/disclosure_gate.py`, integrate into `reporting/views.py`.
- **Interface:**
  `can_disclose_summative(signal, recipient_context) -> {allowed:bool, reason:str, route:Literal["summative","formative_only","support"]}`
  Allowed **only if all**: recipient is adult; consented; the rendering is formatively framed with an actionable next step; **never a bare negative verdict**; and no distress signal present. Minors / low-validation tiers → `formative_only`. Any distress signal → `support` (suppress summative; surface resources).
- **Rules:** a negative-autonomy/erosion/debt signal can **never** be shown to a minor; can **never** render as a bare verdict; distress always wins (routes to support, never to a score). Ties to P5 (the A/B study informs thresholds).
- **Acceptance:** minor context → `formative_only`; adult + consent + formative framing + next step → `summative`; any distress flag → `support` regardless of other fields; a bare-verdict render path is unreachable (test asserts every negative summative disclosure carries an actionable next step).
- **STOP for human review** of the distress-signal definition and the support-routing resources before enabling any summative disclosure.

---

## P5 — A/B disclosure-effects experiment scaffold (spec V3.1-F) `[SCAFFOLD NOW / ANALYSIS data-gated]`
- **Goal:** build the randomized-disclosure assignment + outcome-logging scaffold; pre-register the analysis; do not analyze yet.
- **Files:** `validation/experiments/ab_disclosure.py`.
- **Interface:**
  `assign_disclosure_condition(subject_id) -> Literal["no_disclosure","formative","summative_gated"]` (randomized; logged with seed).
  `log_outcome(subject_id, condition, behavior_metrics, wellbeing_signals)`.
  `analyze_disclosure_effects(...) -> raise NotImplementedError("data-gated: pre-registered; analysis runs post-corpus")`.
- **Notes:** pairs with the theater-rate (TR) dashboard (v3 P6) as the continuous Goodhart monitor. Pre-register **null results** as publishable (OSF, v3 V14). The `summative_gated` arm must route through P4's gate.
- **Acceptance:** assignment is randomized + reproducible from a logged seed; outcomes log both behavior and wellbeing; the analyzer raises the data-gated error; the `summative_gated` arm cannot bypass P4.
- **STOP for human review** of the experiment design + consent language before any live assignment.

---

## P6 — §8.3 predictive-validity gate guard (spec §14.1 rejection) `[BUILD NOW]`
- **Goal:** make it impossible to bypass or soften the §8.3 predictive-validity gate via a "construct-validity primacy" config.
- **Files:** `validation/gates/predictive_validity.py` (guard), config schema.
- **Interface / rule:** there is **no config flag** that disables or down-weights the §8.3 gate. The gate's requirement (CSPC-states model must beat the quality-only baseline at predicting the retention/stability target by the pre-specified margin) is **code-enforced**, not configurable. TR / construct-validity feedback may *inform* but never *override* the gate.
- **Acceptance:** a test asserts no code path sets `predictive_validity_gate.enabled = False` or scales its margin from config; an attempt to do so raises `"the predictive-validity gate is load-bearing and not configurable (spec §14.1)"`.
- **STOP for human review** only if a legitimate reason to parameterize the margin emerges — surface it as an open question, do not change the gate silently.

---

## Consolidated STOP-for-human-review points
1. **P1** — how Brier + slope combine in the calibration gap.
2. **P2** — signature→neuron mapping **and** the disposition of `task_irrelevant_disclosure`.
3. **P3** — the causal DAG edge set before it is frozen as the pre-registered hypothesis.
4. **P4** — the distress-signal definition and support-routing resources.
5. **P5** — A/B experiment design + consent language before live assignment.
6. **P6** — only if parameterizing the §8.3 margin is ever proposed.

---

## Data-gating summary

| Phase | Build now? | Runs/fits when… |
|---|---|---|
| P1 Brier field | ✅ full | immediately |
| P2 relational signatures | ✅ full (pending mapping review) | immediately |
| P3 causal DAG | 🟡 artifact + stub | estimation: reliable instrument + longitudinal + EFA; **fitting on pilot rejected** |
| P4 iatrogenic gate | ✅ full | immediately |
| P5 A/B disclosure | 🟡 scaffold | analysis: post-corpus + consent infra |
| P6 §8.3 guard | ✅ full | immediately |

**The rule above all (carried from v3, reinforced here):** do not fit on the 26 gold chats, and do not let any "construct-validity primacy" framing soften the §8.3 gate. Relevance is not scope; the gate is load-bearing.

*End of v3.1 Claude Code upgrade brief.*
