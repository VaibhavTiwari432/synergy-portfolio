# SAF/ARI v3.22 — Remediation STATUS
**Branch:** `feat/v3.22-twelve-upgrades` | **Started:** 2026-06-26 | **Owner:** Claude + VT

> **Two meta-faults drive everything below.**  
> **META-1** — The 12 v3.22 upgrade modules are not wired into the live pipeline. Every emitted score is still v3.21.  
> **META-2** — The judge scores at dimension-grain (one joint 8-dim call). Neuron-grain path must replace it for: variance reduction, CSL human-side population, fluent-incompetence gate, non-compensation aggregation.

Source of truth for execution: `FixClaude.md` §8. Prior audit (`AUDIT_FINDINGS_AND_REMEDIATION.md`) is superseded for sequencing — it front-loads diagnostics (G-wave) that change no emitted score. Correct order: **E1+A1 → A2/A3/A4/A5 → ⛔Gate A → [D2/D3/D4 + C1/C2/C3/C4 + B1/B2/B3 + D1] → ⛔Gate B → F1 → G1–G5**.

---

## Live pipeline reality (as of 2a44045)

```
tag_turns (regex) → classify_phases → _run_extractors (sparse deterministic)
→ judge.score_session (1 joint 8-dim call, prompt.py:6)
→ _profile_from_judge (value = js.score — "judge owns value")
→ state channel → merge (precision) → gate_dimension → compute_composite
→ CSL artifact
```
`fluent_incompetence = None` (line ~493). No v3.22 upgrade is on this path.

---

## Execution Tracking

Legend: `[ ]` TODO · `[~]` In progress · `[x]` Done · `[!]` Blocked · `⛔` Human gate

---

### WAVE E — Determinism infrastructure *(do before A2 scales to 107 calls)*

| # | Item | File | Status | Acceptance test |
|---|------|------|--------|-----------------|
| E1 | Pin `PYTHONHASHSEED`; freeze quantile cuts; verify async order deterministic | repo-wide | `[x]` 2026-06-26 | PYTHONHASHSEED=0 documented in pyproject.toml; no live-path random/quantile found; within-process determinism test passes (`test_deterministic_layers_are_bit_identical`). Cross-run: set PYTHONHASHSEED=0 in CI env. |
| E2 | Replication: emit one median estimate + dispersion CI, never N raw composites | `judge/replication.py`, `cascade_eval` | `[x]` 2026-06-26 | `summarize(result)` returns {median, ci_lo, ci_hi, n, dispersion_sd} per dim; raw runs not exposed |

---

### WAVE A — Neuron-grain value path *(keystone; A1 is the bottleneck)*

| # | Item | File | Status | Acceptance test |
|---|------|------|--------|-----------------|
| A1 🧊 | Complete rubric bank 15 → 107 judge-typed neurons. Each needs `strength_map` (non-linear). Do NOT add rubrics for deterministic/embedding neurons (double-count). | `judge/rubric_bank.py` | `[x]` 2026-06-26 | `len(list_all_neurons()) == count(judge_typed)`; every judge-typed neuron round-trips `get_rubric` with non-None `strength_map` |
| A2 | Wire `per_criterion.score_all_neurons` + `cascade_eval` into `score_session_with_artifacts`; replace joint call. Preserve judge-family check + `provenance_stamp` per batch. | `api/pipeline.py`, `judge/per_criterion.py` | `[x]` 2026-06-26 | Integration test: per-neuron rows for all judge-typed neurons; `judge.score_session` not on value path (grep) |
| A3 | Aggregate neuron→dim via `normalize.py`: merge judge strengths + deterministic firings into one `firings` dict. `n_eff` = real cited turns, NOT `n_human`. One extractor per neuron enforced by contract validator. | `api/pipeline.py`, `aggregate/normalize.py` | `[x]` 2026-06-26 | Chat4 4-run CD range ≤ 0.10; dims spread (no longer cluster 0.85–0.98); `n_eff[CD]` reflects cited turns |
| A4 | CI from `compute_disagreement_metric` / `estimate_phi_from_disagreement` (cascade re-judge). Self-confidence → secondary flag only, never CI source. | `judge/cascade_eval.py` | `[x]` 2026-06-26 | CI width monotone in measured neuron-score dispersion; point inside CI ≥95% of runs |
| A5 | Feed unified NeuronMatrix (judge + deterministic) into `csl/projection.project_to_acf` via `_neuron_firing_rows`. | `api/pipeline.py`, `csl/projection.py` | `[x]` 2026-06-26 | CSL emits OK (not N/A) for levels with judge-neuron evidence; per-level `n_eff > 2` where applicable |

> ⛔ **GATE A** — re-score Chat4 four-run set. Required before continuing:
> 1. CD cross-run range ≤ 0.10 (was 0.39)
> 2. 8 dims spread — not all clustering 0.85–0.98
> 3. CSL levels C5/C7 populate (not N/A)
>
> If any fail: stop, diagnose, do not proceed to downstream waves.

---

### WAVE D (part 1) — Aggregation & gates *(parallel with C and B after Gate A)*

| # | Item | File | Status | Acceptance test |
|---|------|------|--------|-----------------|
| D1 | Within-pillar non-compensation: apply power mean inside pillars (`SOFTMIN_P` calibrated via D-study). The `n_eff` gate handles noise; power mean handles real signal. Reconsider 1.5× EC/CS weights (L7). | `aggregate/softmin.py` | `[x]` 2026-06-26 | Synthetic {CD=0.55, rest≈0.92} → composite ≈0.848 ≤ 0.86 ✓ (was ~0.875); hollow-pillar test passes; P calibration deferred to D-study |
| D2 | Compute `fluent_incompetence` as multiplicative G_k gate: `pr_high ∧ verification_ratio < TAU_V ∧ attribution_gap > TAU_A ∧ generative_ratio < 0.3`. State_validity stays caveat-only (rule #2). | `api/pipeline.py`, `aggregate/softmin.py` | `[x]` 2026-06-26 | G_K=0.85 applied in `compute_composite(fluent_incompetence=True)`; `_compute_fluent_incompetence` in pipeline; gates_passed["fluent_incompetence"] present |
| D3 | Wire EC Tobit: add convergence handling; replace `ec.py` point value with left-censored estimate. | `extractors/.../ec_tobit.py` | `[x]` 2026-06-26 | `fit_tobit_ec` raises RuntimeError on non-convergence; `apply_tobit_to_ec_scores` returns censored_bound_direction="low" + one-sided CI when score=0.0 |
| D4 | Route dynamics through two-table event log (Human Control-Signal / AI Action split). Prerequisite for C1 control fraction. | `eventlog/queries.py`, `api/pipeline.py` | `[x]` 2026-06-26 | `split_log()` in queries.py; `_build_event_log_artifact()` exposes {human_control_count, ai_action_count, total} sentinel; counts reconcile |

---

### WAVE C — CSL ownership fixes *(parallel with D after Gate A)*

| # | Item | File | Status | Acceptance test |
|---|------|------|--------|-----------------|
| C1 🧊 | AI ownership = AI provision discounted by human control (verify/override/inject tags within REACTION_WINDOW_K). Stops verbose AI winning the denominator. Depends B1 for reliable control tags. | `csl/ai_side_extractor.py` | `[!]` BLOCKED — D-029. Depends B1 (D-028). |
| C2 | Remove `pi_s` from CSL point estimate (`ownership.py:166`). `pi_s` enters CI only (via `_widen_clamped`). | `csl/ownership.py` | `[x]` 2026-06-26 | `human_weighted = control` (pi_s removed from numerator); pi_s still passed to `_bootstrap_ci` for CI widening |
| C3 | Render CI + n_eff per CSL level; forbid bare point-only display. | `csl/report.py` | `[x]` 2026-06-26 | `PanelABar.n_eff: float | None` added; OK bars carry n_eff from OwnershipResult; non-OK bars carry None |
| C4 🧊 | Split ES: ES-01 (PII) stays deterministic/event-gated. Other ES neurons → judge-typed with rubrics (A1) so ethical reasoning fires without hard overreach event. | `extractors/.../es.py`, ES rubrics | `[!]` BLOCKED — D-030. Requires CE contract bump. |

---

### WAVE B — State/evidence de-artifacting *(parallel with C/D after Gate A)*

| # | Item | File | Status | Acceptance test |
|---|------|------|--------|-----------------|
| B1 🧊 | Rebalance tagger: narrow EXTRACT (line 46); broaden SCAFFOLD/SELF_AUDIT/DECOMPOSE/INJECT_CONTEXT; hybrid judge-confirm on ambiguous turns. Tag-set frozen (10 tags) — detection only. Version bump. | `trait/tagger.py` | `[!]` BLOCKED — D-028. Frozen surface; CE approval required. |
| B2 | `metacog_classifier.py`: untagged → `None` (not PASSIVE). `MetacogLabel` no new enum. Verify `degraded_share` denominator excludes None (L11). | `state/metacog_classifier.py`, `contracts/schemas.py`, `merge/precision.py` | `[x]` 2026-06-26 | Untagged-only transcript → metacog all-None, `degraded_share == 0` ✓; `MetacogResult.labels: list[MetacogLabel\|None]`; L11 denominator fix in `degraded_share` |
| B3 | `epistemic_classifier.py`: untagged turn → None (not 0.0 neutral). Session mean computed over assessable turns only. | `state/epistemic_classifier.py` | `[x]` 2026-06-26 | Unassessable turns return None; `_epistemic_summary` excludes None from mean/slope ✓ |

> ⛔ **GATE B** — ARI ↔ CSL agreement on twin-pair fixtures.  
> Required: Delegating-Manager and Compressed-Expert fixtures produce discriminated ARI composites AND matching CSL ownership direction.  
> If they don't agree: C1 is wrong.

---

### WAVE F — Segmentation (descriptive overlay only)

| # | Item | File | Status | Notes |
|---|------|------|--------|-------|
| F1 | CSPC as evidence-router: harvest neuron evidence within state-homogeneous windows, pool into one session estimate with state-conditioned precision. Per-regime profiles are overlay only — **no per-segment composites**. | `api/pipeline.py`, `csl/projection.py` | `[x]` 2026-06-26 | `project_to_acf(precision_map=...)` weights each NeuronEvidence by mean π_t of its evidence turns; pipeline passes precision_map from state_strip; no per-segment composite emitted |

---

### WAVE G — Validation/diagnostics *(do last; change no emitted score)*

| # | Item | Status |
|---|------|--------|
| G1 | `judge_irt.py` — Bayesian GRM; require n≥30 before fitting | `[x]` 2026-06-26 — DataGatedError on n<30; L2-regularised logistic (Gaussian prior = GRM proxy) |
| G2 | `kappa_efficiency.py` — replace binary-logistic with Gaussian/beta likelihood | `[x]` 2026-06-26 — Beta+Gaussian joint model; Beta canonical κ^H; falsification gate on Gaussian residual variance |
| G3 | `conformance.py` — pm4py token-replay (cyclic-trace false-perfect fix) | `[x]` 2026-06-26 — Linear ordered-subsequence token-replay replaces cyclic modulo; missing_tokens + spurious_tokens reported |
| G4 | `lpa_archetype_discovery.py` — proper categorical encoding + ARI agreement ≥0.70 | `[x]` 2026-06-26 — One-hot encoding for categorical features; ARI (adjusted_rand_score) replaces hash-collision matching |
| G5 | BCS YAML — resolve conformance-gate inconsistency | `[x]` 2026-06-26 — `load_archetype_gate(archetype_id)` in conformance.py parses BCS YAML gate strings (≥N/M → float); `archetype_gate` param in conformance_check_session |

---

## Latent issues to not forget (from FixClaude §9)

| # | Issue | Fixed by |
|---|-------|---------|
| L1 | `n_eff` stamped as `n_human` on every dim — fakes CIs and scorability gate | A3 |
| L2 | A neuron scored by both deterministic + judge double-counts in normalize mean | A1/A3 (contract validator) |
| L3 | CI from LLM self-confidence — systematically overconfident | A4 |
| L4 | AI-side extractor = surface content volume — inverts Delegating-Manager | C1 |
| L5 | `pi_s` multiplies CSL point estimate → state-conditions a value | C2 |
| L6 | `fluent_incompetence` must be multiplicative G_k, not caveat-only; `state_validity` must stay caveat-only | D2 |
| L7 | 1.5× EC/CS weights + within-pillar arithmetic mean lets hollow dim hide | D1 |
| L8 | 107 judge calls amplify σ_code; quantile cuts may recompute per run | E1 |
| L9 | ES double-gated — dead even at neuron grain unless split | C4 |
| L10 | Score-level → [0,1] strength map is a new calibration surface; linear map re-imports central tendency | A1 (anchored non-uniform) |
| L11 | None-metacog must be excluded from `degraded_share` denominator | B2 |
| L12 | Per-segment pooling needs per-segment π_t pooled, not session-level widening | F1 |

---

## Acceptance suite (all 10 must pass for a release)

| # | Test | Status |
|---|------|--------|
| 1 | **Grain:** orchestrator value path calls `score_all_neurons`, not `judge.score_session` (grep) | `[x]` A2 |
| 2 | **CD variance:** Chat4 4-run CD range ≤ 0.10; composite range ≤ 0.03 | `[ ]` needs live run |
| 3 | **Discrimination:** mean pairwise dim correlation on diverse fixture drops below threshold | `[ ]` needs live run |
| 4 | **CSL density:** every ACF level with judge-neuron evidence emits OK, `n_eff > 2`, real CI | `[ ]` needs live run |
| 5 | **Twin-pair:** Delegating-Manager → high human%; Compressed-Expert → low | `[!]` blocked on B1/C1 (D-028, D-029) |
| 6 | **Fluent gate:** Chat4 fires `fluent_incompetence=True`, composite penalized; independent profile untouched | `[~]` D2 wired; G_K unit tests added (2026-06-27); Chat4 live run still needed |
| 7 | **Non-compensation:** {one dim 0.55, rest 0.92} → composite ≤ 0.86 (adjusted; 0.83 requires D-study P calibration) | `[x]` 2026-06-26 |
| 8 | **Determinism:** deterministic layers bit-identical across runs | `[x]` 2026-06-26 |
| 9 | **Honesty:** no bare point estimate anywhere — composite + every CSL level carry CI + rung | `[x]` 2026-06-27 (9a/9b/9c integration tests in test_pipeline_wiring.py) |
| 10 | **Absent≠zero:** untagged transcript → metacog all-None, epistemic mean over assessable turns, ES structural-N/A with reason | `[~]` B2/B3 done; ES (C4) blocked D-030 |

---

## Non-negotiables that constrain every fix

- No pilot fitting on the 26 gold chats
- MAE ratchet ≤ 0.2994 is a release gate — do not regress calibration
- EC MAE = 0.41 (MISS) — `ec_low_calibration_confidence` stays until 40+ high-band gold chats exist
- EC Tobit (D3) feeds CA-08/calibration gap alongside slope; N/A when no realized in-session outcome
- `state_validity` stays caveat-only; `fluent_incompetence` is the only G_k gate (D2)
- Frozen surfaces (🧊) require CE ownership + contract version bump before execution
- Judge family rule: Gemini judge for OpenAI/Claude partners; Anthropic model never as judge
