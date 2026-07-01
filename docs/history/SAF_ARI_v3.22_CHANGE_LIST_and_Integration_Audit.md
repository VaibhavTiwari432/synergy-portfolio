# SAF/ARI v3.22 — Change List & Integration Audit

**Author basis:** direct inspection of branch `feat/v3.22-twelve-upgrades` @ `2a44045`
**Status of this doc:** proposal for triage — every item carries a rung and a stop gate
**Supersedes nothing.** Reorders `specs/v3.22/AUDIT_FINDINGS_AND_REMEDIATION.md` sequencing; see §6.

---

## 1. The integration gap (the finding the existing audit does not cover)

The existing v3.22 audit checks whether the twelve upgrade *modules* are internally correct. It does not check whether they are **wired into the live scoring path**. They are not. The live orchestrator `src/api/pipeline.py::score_session_with_artifacts` still runs the v3.21 stack.

**Wiring audit (refs in `src/api` + `src/worker`, the live path):**

| # | Upgrade | File present | Wired to live path | Internally correct | Net state |
|---|---------|:---:|:---:|:---:|---|
| 1 | Cascaded Selective Eval | ✓ `judge/cascade_eval.py` | ✗ (live=0) | — | dead module |
| 2 | Per-criterion judge | ✓ `judge/per_criterion.py` | ✗ (live=0) | ✗ rubric 15/107 | dead + incomplete |
| 3 | Active learning | ✓ `calibration/active_learning.py` | n/a (offline) | check | offline-only (ok) |
| 4 | Human IRR ceiling | spec-only | ✗ | — | doc-only |
| 5 | Tobit EC | ✓ `extractors/.../ec_tobit.py` | ✗ (live uses `ec.py`) | ⚠ no convergence handling | dead module |
| 6 | CH/COMP Explanation Trap | spec-only | ✗ | — | doc-only |
| 7 | Two-table event log | ✓ `eventlog/schema.py` | ✗ (live uses single log) | check | dead schema |
| 8 | DIF governance rule | spec-only | n/a (governance) | — | doc-only (ok) |
| 9 | IRT/GRM judge diagnostics | ✓ `csl/validation/judge_irt.py` | ✗ (src_refs=0) | ✗ unstable at n=1 | dead + broken |
| 10 | Process-mining conformance | ✓ `csl/analytics/conformance.py` | ✗ (src_refs=0) | ✗ naive seq match | dead + broken |
| 11 | Noorani (Tier-3 target) | spec-only | n/a (register) | — | doc-only (ok) |
| 12 | BCS (Baseline Capability Spec) | ✓ + `lpa_archetype_discovery` | partial | ✗ LPA hash metric; BCS YAML | broken |

**Consequence:** executing the existing remediation plan in full (port 92 neurons, fix IRT, fix κ^H, fix conformance, fix LPA) would leave every emitted score **unchanged**, because none of those modules are on the scoring path. The plan has no integration step.

**Live path today (`score_session_with_artifacts`):**
`tag_turns` (regex) → `classify_phases` → `_run_extractors` (sparse deterministic) → `judge.score_session` (**single joint 8-dim call**, `prompt.py:6`) → `_profile_from_judge` (`value = js.score`, "the judge owns value") → state channel → `merge` (precision) → `gate_dimension` → `compute_composite` → CSL artifact. `fluent_incompetence` is `=None` (line ~493).

---

## 2. Pipeline hindrances, by stage

| Stage | File | Hindrance | Symptom it causes |
|------|------|-----------|-------------------|
| Tagging | `trait/tagger.py` | EXTRACT patterns over-broad (line 46 matches almost any question); generative/active patterns narrow | CSPC passive; sparse NeuronMatrix |
| State (metacog) | `state/metacog_classifier.py:46` | untagged turn → PASSIVE (violates absent≠zero) | CSPC passive (artifact, not measured) |
| Trait value | `judge/client.py` + `judge/prompt.py` | one joint call scores all 8 dims → halo; dimension-grain, not neuron-grain | 8-dim cluster high & similar; CD pure single-call variance |
| Value assembly | `pipeline.py::_profile_from_judge` | `value=js.score`; deterministic firings discarded into `raw_counts` | discriminating signal thrown away |
| Aggregation | `aggregate/softmin.py` | within-pillar weighted mean dilutes a low dim against its high pillar-mate (EC/CS at 1.5×) before soft-min; `SOFTMIN_P=-2` mild | high-ARI bias; a dim crashing barely dents composite |
| Gate | `aggregate/gates.py` | scorability ≥4/8; `N_EFF_TAU=1.0` | composite withheld ("pause") on thin sessions |
| Flags | `pipeline.py` line ~493 | `fluent_incompetence=None` (never computed) | the catching gate is off |
| CSL human side | `csl/projection.py` | needs neuron-grain; judge is dimension-grain → starves | C5/C7 N/A; levels rest on 0–2 firings |
| CSL contrast | `csl/ai_side_extractor.py` | broad-regex turn-prevalence (dense) vs sparse human control | human% mechanically low; verbose AI wins denominator |
| CSL precision | `csl/ownership.py:166` | `human_weighted = pi_s × control` → passive state (artifact) attenuates the human point estimate | low CSL% compounded |
| EC | `extractors/.../ec.py` | point value; off-screen verification censored | EC MAE=0.41, permanently flagged |

---

## 3. Change list — dependency-sequenced (do in this order)

Rungs: **D** DESIGNED · **M** MEASURABLE · **V** VALIDATED. Stop gates marked ⛔.

### WAVE A — Make the value path discriminate
*Fixes symptom 1 (uniform dims) + CD variance + CSL human-side starvation in one pass.*

- **A1 [M] Complete `judge/rubric_bank.py` 15 → 107 neurons.** Each rubric needs `title, dimension, anchors, negative_criteria, scale_levels`, and a score-level → [0,1] strength mapping (so `normalize.py` can consume judge neurons). *Blocks A2–A4 and all of Wave D.* (= existing audit Critical #1.)
- **A2 [M] Wire `per_criterion.score_all_neurons` (+ `cascade_eval` for cost control) into the trait channel,** replacing the single `judge.score_session` joint call in `_profile_from_judge`. *Depends: A1.*
- **A3 [M] Aggregate neuron-grain via `normalize.py`.** Feed judge per-neuron strengths into the same `firings` dict the deterministic extractors fill, so `value = normalize(judge_neurons ∪ deterministic_neurons)`. This unifies the two channels and stops discarding the deterministic signal into `raw_counts`. *Depends: A2.*
- **A4 [M] Route the unified NeuronMatrix into `csl/projection.project_to_acf`.** This is what populates the CSL human side — the direct fix for the shallow "who-drives-what" table (symptoms 3/4). *Depends: A3.*

⛔ **Gate A:** re-score the 4-run Chat4 corpus. Required: (i) CD cross-run range drops from 0.39 toward the 0.03–0.06 band; (ii) the 8 dims spread (no longer cluster 0.85–0.98); (iii) CSL levels C5/C7 populate instead of N/A. If (i)–(iii) fail, stop — the grain fix did not land.

### WAVE B — Fix the evidence/state layer
*Fixes symptom 2 (CSPC passive) + de-artifacts low CSL%.*

- **B1 [D] Rebalance the tagger / move past surface-only.** Narrow EXTRACT, broaden generative/active detection; preferably hybrid (regex prefilter + judge confirmation on ambiguous turns) so state is not surface-only (your point #4). Frozen-tag contract change → version bump.
- **B2 [M] `metacog_classifier.py`: add UNLABELED state.** Untagged turn → UNLABELED, not PASSIVE. Passivity becomes measured, not defaulted. Lifts the `pi_s` suppression of CSL human%.
- **B3 [D] Symmetrize the CSL contrast.** Either measure the AI side at control-grain (not turn-prevalence) or density-normalize human-vs-AI; reconsider `ownership.py:166` `pi_s × control` (state-conditioning the value, not just CI). Otherwise a verbose AI permanently wins the ownership denominator.

### WAVE C — Turn on stubbed gates/metrics
- **C1 [M] Compute `fluent_incompetence`** in `score_session_with_artifacts` (currently `=None`). Now feasible: PR-high ∧ verification-low ∧ attribution-gap-high ∧ generative-ratio<0.3, from Wave-A neuron evidence. *Depends: A.*
- **C2 [M] Wire `ec_tobit`** in place of `ec.py` point value (add convergence handling first — existing audit Item #6).
- **C3 [D] Route dynamics through the two-table event log** (`eventlog/schema.py`: Human Control-Signal / AI Action) instead of the single log.

### WAVE D — Segmentation, done right (your #1 — the synthesis, NOT segment-then-score)
- **D1 [D] CSPC as evidence-router + precision, not partition.** Run neuron-grain extraction **within** state-homogeneous windows (harvest CD/CS from generative bursts, EC from verification stretches), then **pool** per-segment firings into ONE session-level estimate with state-conditioned precision. Emit per-regime profiles as a descriptive overlay only.
- **D1-DONT:** do **not** emit independent per-segment composites. n_eff collapses (segments of 1–7 turns) → per-segment variance explodes and the scorability gate fails → *more* pauses. *Depends: A (neuron grain).*

### WAVE E — Validation/diagnostics (existing audit's "critical" items — but they do NOT touch live scores)
- **E1 [M→V] judge_irt:** Bayesian GRM, corpus-gated (n≥30). **E2 [M] kappa_efficiency:** Gaussian likelihood (Ŝ is continuous). **E3 [D] conformance:** pm4py token replay. **E4 [D] LPA:** proper categorical encoding + ARI agreement. **E5 BCS YAML** consistency.
- Sequencing note: these are validation infrastructure, not the scoring path. They change no emitted score. Do them after A–C unless a release gate explicitly needs a diagnostic.

---

## 4. Critical path

```
A1 (rubric 107) ─▶ A2 (wire per-criterion) ─▶ A3 (neuron aggregation) ─▶ A4 (CSL human side)
                                                                  │
                                            ⛔ Gate A (re-score Chat4)
                                                                  │
                                   ┌──────────────────────────────┼───────────────┐
                                   ▼                              ▼               ▼
                              C1 fluent_inc.              D1 segmentation     B1/B2/B3 state+CSL
```

A1 is the bottleneck for everything that moves a score. B-wave is parallelizable with A but its payoff (de-artifacting CSL%) only shows once A4 lands.

## 5. What NOT to do yet (discipline)
- Don't build per-segment composites (D1-DONT).
- Don't fit IRT/GRM/LPA/conformance for *score* purposes on 26 single-archetype chats — they are diagnostics; using them to condition scores crosses the corpus gate and contaminates calibration.
- Don't treat segmentation as a fix for the 26-corpus reliability problem — it needs *more* calibration data per regime, not less. Corpus growth (active learning, Item #3) remains the binding constraint.

## 6. Reorder vs the existing remediation plan
Existing plan: Day1 rubric → Day2 IRT → Day3 κ^H → Day4 conformance+LPA → Day5 BCS+Tobit → validate. This front-loads E-wave (diagnostics that change no score) and never wires the value path. Proposed reorder: **A1 → A2/A3/A4 (+Gate A) → C1/C2 → B → D**, with **E** moved after, since E alters no emitted number until A is in place.

---
*Rungs are claims about the change's current maturity, not its target. Nothing here is VALIDATED — validation is gated on a corpus that does not yet exist. File-ownership boundaries (CE / Codex / Antigravity) to be assigned per item before execution.*
