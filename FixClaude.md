# FixClaude.md — SAF/ARI v3.22 Total Remediation (extreme depth)

**Basis:** direct read of branch `feat/v3.22-twelve-upgrades` @ `2a44045` — schemas, live pipeline, judge, CSL, aggregation, state.
**Audience:** CE / Codex / Antigravity. Each fix names the file, the contract surface, the rung, dependencies, and the acceptance test that proves it.
**Reading rule:** fix in the order of §8. Do **not** start mid-list — most faults share a root and a wrong order will paper over symptoms without fixing causes.

Rungs: **D** DESIGNED · **M** MEASURABLE · **V** VALIDATED. ⛔ = mandatory stop-gate (human review).
🧊 = touches a frozen/contract surface (CE-only, version bump).

---

## 0. The two meta-faults (everything else is a consequence)

**META-1 — The integration gap.** The twelve upgrades are authored as modules but the live orchestrator `src/api/pipeline.py::score_session_with_artifacts` calls **none** of them. Wiring audit (refs in `src/api`+`src/worker`): `per_criterion` 0, `cascade_eval` 0, `ec_tobit` 0, two-table `eventlog` 0, `judge_irt`/`conformance` 0, `vigilance` 0, `kappa_efficiency` 0. The live path is the v3.21 stack. **Executing the existing `AUDIT_FINDINGS_AND_REMEDIATION.md` plan changes no emitted score**, because it fixes module internals without wiring them. This document fixes the wiring first.

**META-2 — Grain mismatch.** The dimension *value* is produced by **one joint LLM call scoring 8 dimensions** (`judge/prompt.py:6` — "scores the 8 DIMENSIONS directly — not the 107 neurons"; `_profile_from_judge`: `value = js.score`, "the judge owns value"). But CSL ownership needs **neuron-grain** evidence (`csl/projection.project_to_acf`). So the same system simultaneously (a) over-compresses dims via halo, and (b) starves CSL of the neuron evidence it requires. The fix that resolves the *most* symptoms at once is to move the value to neuron grain. That single move fixes: uniform dims, CD variance, the starved who-drives-what table, and unblocks the fluent-incompetence gate.

Everything below is downstream of these two.

---

## 1. SUBSYSTEM A — Trait value path (the keystone)

### A1 🧊 [M] Complete the judge rubric coverage — `src/trait/judge/rubric_bank.py`
**Fault.** Only **15/107** neurons have rubrics (verified: 15 distinct ids). `score_all_neurons` falls back to `list_all_neurons()` → 15. Any neuron-grain value path can therefore only score 15 of 107.
**Fix.** Author the missing judge-typed rubrics. Note the contract assigns each neuron an extractor *type*: deterministic (e.g. ES-01 PII, the EC VERIFY-evidence neurons, AL-08, PR mechanical), embedding (CD semantic-distance), or judge. **Only judge-typed neurons need a rubric** — do not author rubrics for deterministic/embedding neurons or you create the double-counting hazard in L2. Each rubric: `{title, dimension, anchors{0..N}, negative_criteria[], scale_levels[], strength_map}` where `strength_map: list[float]` maps each scale level → a [0,1] strength (this is the value the aggregator consumes; A3 depends on it).
**Why this is the bottleneck.** A2–A5, C (CSL human side), D2 (fluent gate) all depend on neuron-grain scores existing.
**Latent it exposes → L10:** the score-level→strength map is a *new calibration surface*. A lazy linear map (`level/N`) re-imports central tendency. Anchor each level to a behavioral exemplar and set non-uniform strengths.
**Test.** `len(list_all_neurons()) == count(judge_typed in contract_table)`; every judge-typed neuron id round-trips through `get_rubric` with a non-None `strength_map`.

### A2 [M] Wire per-criterion scoring into the trait channel — `src/api/pipeline.py`, `src/trait/judge/`
**Fault.** `score_session_with_artifacts` calls `judge.score_session` (joint). `per_criterion.score_all_neurons` exists but is dead.
**Fix.** Replace the joint call with the neuron-grain path. Concretely, in the trait channel:
```python
# was: judge_output = judge.score_session(session)  # joint 8-dim, halo-prone
neuron_out = score_all_neurons(judge_fn=judge.neuron_fn, transcript=render(session))
# neuron_out['results'][nid] -> {'final_score_after_leniency_penalty': int level, 'reasoning', 'evidence_turns'?}
```
Keep `judge.score_session` available behind a flag for A/B, but the **value** path becomes neuron-grain. Preserve judge-family separation and version pinning per call (ADR-0002): the family-conflict check and `provenance_stamp` must run per neuron batch, not once.
**Cost/determinism caveat → routes to A4 and E.** 107 calls/session × judge stochasticity. Do **not** ship flat 107-replication; use `cascade_eval.cascaded_evaluate` (A4) for selective re-judging, and verify infra determinism (E) first so σ_code does not multiply across 107 calls.
**Depends:** A1.
**Test.** Integration test: a fixture session yields per-neuron rows for all judge-typed neurons; `judge.score_session` is not on the value path (grep the orchestrator).

### A3 [M] Aggregate neuron → dimension through `normalize.py` (the real fix for uniform dims + CD variance) — `src/api/pipeline.py`, `src/aggregate/normalize.py`
**Fault.** Today `value = js.score` (one number); deterministic firings are discarded into `raw_counts` ("the judge owns value"). CD has *zero* deterministic neurons (`cd.py`) and a single joint score → pure single-call variance (the 0.39 swing).
**Fix.** The dimension value becomes the normalized mean over **all** of the dimension's neurons, each scored by its designated extractor (judge / deterministic / embedding), merged into ONE firing matrix:
```python
def profile_from_neurons(neuron_scores, session) -> dict[Dimension, DimensionScore]:
    firings, opps, evid, neff = ddict(dict), ddict(dict), ddict(list), ddict(list)
    for nid, ns in neuron_scores.items():            # ns.value already in [0,1] via strength_map
        d = DIM_OF[nid]                              # the 107->8 Q-matrix (contract_table)
        firings[d][nid] = ns.value
        opps[d][nid]    = ns.applicable_opportunities  # judge-typed: 1 when scored; det: real count
        evid[d]        += ns.evidence_turns
        neff[d].append(ns.n_eff)                      # <-- L1 fix: real per-neuron n_eff, NOT n_human
    norm = normalize_counts(firings, opps).per_dimension   # mean strength over neurons w/ opportunities
    out = {}
    for d, dn in norm.items():
        if dn.status != ScoreStatus.OK:
            out[d] = DimensionScore(dim=d, status=dn.status, rung=Rung.MEASURABLE,
                                    status_reason=_reason(d, dn)); continue
        out[d] = DimensionScore(
            dim=d, status=ScoreStatus.OK, value=dn.normalized,
            n_eff=sum(neff[d]),                        # honest evidence sample
            ci=ci_from_dispersion(firings[d], replication[d]),   # A4, not self-confidence
            evidence_turns=sorted(set(evid[d])), rung=Rung.MEASURABLE,
            raw_counts={"n_neurons_fired": len(firings[d])})
    return out
```
**Why it fixes both symptoms.** (i) CD now averages ~11 neuron scores → variance falls ≈ √11 and halo is broken (independent calls). (ii) Dimensions spread because per-neuron anchored scoring discriminates where the joint call central-tendencies. (iii) The deterministic signal stops being discarded — it co-aggregates.
**Latent → L1, L2.** `n_eff` must be each neuron's real evidence count (cited turns / applicable opportunities), never `n_human` — the old code stamped `n_eff = n_human` on every dim, which faked the CI and the gate. And each neuron must have **exactly one** extractor in `contract_table` (judge XOR deterministic XOR embedding); a neuron scored twice double-counts. Add a contract validator.
**Depends:** A1, A2.
**Test.** Re-score the Chat4 four-run set: CD cross-run range ≤ 0.10; pairwise dim correlation drops; `n_eff[CD]` reflects cited turns, not 140-by-fiat.

### A4 [M] CI from disagreement, not self-reported confidence — `src/trait/judge/cascade_eval.py`, `_profile_from_*`
**Fault.** CI half-width = `_CI_FLOOR + _CI_SPAN*(1 - js.confidence)` — the *judge's own confidence*, which LLMs systematically over-state. This is why last turn's CIs were narrower than the true between-run spread (Chat-3 CD CI excluded Chat-2's 0.55 on the same transcript).
**Fix.** Use `cascade_eval`: for boundary/high-leverage neurons, re-judge K times; the CI comes from `compute_disagreement_metric` → `estimate_phi_from_disagreement`. Interior neurons scored once. The dimension CI is the dispersion of its neuron strengths combined with the replication variance — an *empirical* interval. Self-reported confidence may stay as a secondary flag, never the CI source.
**Why correct.** Separates accuracy (anchored level) from precision (replication dispersion). Makes the CI honest about the dominant noise source (judge stochasticity), which the spec's G-study (§8.5) requires.
**Depends:** A2.
**Test.** Property test: CI width is monotone in measured neuron-score dispersion; a transcript scored K times has its point inside the reported CI ≥95% of runs.

### A5 [M] Feed the unified NeuronMatrix into CSL — `src/api/pipeline.py::_neuron_firing_rows`, `csl/projection.py`
**Fault.** `project_to_acf` consumes `neuron_firing_rows`, but those rows are built only from the **deterministic** extractor firings (`_neuron_firing_rows(firings, opportunities, log)`). Since the judge was dimension-grain, the human side of CSL had almost no neurons → C5/C7 N/A, levels resting on 0–2 firings.
**Fix.** Include the per-neuron judge scores (A2) in `_neuron_firing_rows` with `value`, `n_eff` (cited turns), `evidence_turn_indices`. `project_to_acf` then has dense, real evidence per ACF level.
**Why correct.** This is the direct repair of the "shallow / weak who-drives-what" complaint — the human side stops starving.
**Depends:** A2, A3. **Test.** On the Chat4 fixture, CSL emits OK (not N/A) for levels that have judge-neuron evidence; per-level `n_eff > 2` where applicable so `_bootstrap_ci` produces a real interval.

---

## 2. SUBSYSTEM B — State / evidence layer (CSPC passivity)

### B1 🧊 [D] Rebalance the tagger; move past surface-only — `src/trait/tagger.py`
**Fault.** `EXTRACT` patterns (line 46) match almost any question; generative/active patterns require rare phrasings. Result: most turns tag extractive, few generative → epistemic pushed negative, metacog defaulted passive. The state signal is surface regex only (your point #4).
**Fix.** (a) Narrow `EXTRACT` so a substantive, constraint-bearing prompt is not auto-extractive; (b) broaden `SCAFFOLD/SELF_AUDIT/DECOMPOSE/INJECT_CONTEXT` coverage; (c) for ambiguous turns, add a **judge-confirm** pass (small per-turn classification) so the tag is not purely lexical. Frozen tag-set is unchanged (still 10 tags) — only detection changes; still a contract version bump because behavior shifts.
**Why correct.** De-biases every downstream consumer of tags (epistemic, metacog, EC evidence, deterministic opportunities).
**Test.** On a hand-labeled tag gold set, generative-tag recall rises and the extractive:generative ratio matches human labels within tolerance; `theater_counter`/`accept_run` unaffected.

### B2 [M] Stop defaulting untagged → PASSIVE — `src/state/metacog_classifier.py`, `MetacogResult`
**Fault.** Line 46: `if flat or not (turn_tags & _ACTIVE_TAGS): PASSIVE`. An **untagged** turn becomes PASSIVE — absence recorded as passivity, violating absent≠zero (#12).
**Fix.** Distinguish *evidence of passivity* from *no evidence*:
```python
_PASSIVE_TAGS = frozenset({IntentTag.EXTRACT, IntentTag.DELEGATE})
...
if turn_tags & _ACTIVE_TAGS:           labels.append(MetacogLabel.ACTIVE)
elif flat or (turn_tags & _PASSIVE_TAGS): labels.append(MetacogLabel.PASSIVE)
else:                                  labels.append(None)   # unlabeled — no metacog evidence
```
Change `MetacogResult.labels: list[MetacogLabel | None]`; the estimator passes `None` → `StateVector.metacog = None`, which `turn_precision` already treats as "unassessable → precision None" (not degraded). **No new enum value** needed (avoids a frozen change); `MetacogLabel` stays ACTIVE/PASSIVE/SURRENDER.
**Why correct.** The "drift-dominant 87% passive" was largely a default, not a measurement. This also lifts the artificial `pi_s` suppression of CSL human% (see C2): unlabeled turns no longer drag precision.
**Latent → L5 interaction.** Verify `degraded_share` denominator: `None`-metacog turns must contribute neither to `degraded` nor inflate the denominator (current `degraded_share` already iterates labels; ensure `None` is skipped, not counted as undegraded).
**Test.** A transcript of purely untagged turns yields metacog all-`None`, `degraded_share == 0`, and precision `None` (not 1.0, not PASSIVE).

### B3 [D] Epistemic neutral-vs-unknown — `src/state/epistemic_classifier.py`
**Fault.** Untagged turn → `score = 0.0` (neutral), indistinguishable from a genuinely balanced turn. Combined with the extractive-heavy tagger, the session epistemic mean is artificially depressed.
**Fix.** Return `None` for turns with no generative/extractive tag *and* no substantial own-content, so the session mean/slope are computed over *assessable* turns only (mirror B2). `StateVector.epistemic` is already `float | None`.
**Test.** Session epistemic_mean excludes unassessable turns; a chat with rich generative bursts no longer reads net-extractive because of untagged filler.

---

## 3. SUBSYSTEM C — CSL ownership (who-drives-what)

### C1 [D] **AI side must measure control, not content volume** — `csl/ai_side_extractor.py` (the inversion fix)
**Fault — and it contradicts the framework's own principle.** `extract_ai_contribution` = share of AI turns whose text matches broad explanatory regex ("because", "however", "here's a", ` ``` `). That is **surface attribution by content volume** — exactly what the spec's rejection log forbids ("Surface-attribution as the ownership metric … *inverts* the truth at the Compressed-Expert / Delegating-Manager boundary"). A Delegating-Manager who critically directs a verbose AI gets *low* human ownership because the AI produced lots of matching text — the precise inversion CSL was built to prevent.
**Fix.** AI ownership at a level = AI provision **discounted by human control over that provision**:
```python
# human exercised control over level-content when, downstream of AI provision at that level,
# the human VERIFY/OVERRIDE/INJECT_CONTEXT/PIVOT-ed (the control tags, within REACTION_WINDOW_K).
ai_uncontrolled(level) = ai_displayed(level) * (1 - human_control_fraction(level, tags))
denom = human_weighted + ai_uncontrolled
human_pct = human_weighted / denom
```
So heavy AI content that the human steered/checked counts *toward* the human, not against. This restores the twin-pair discrimination the AI-side extractor currently breaks.
**Why correct.** Aligns the implementation with the load-bearing CSL design constraint (ownership = cognitive control). Stops verbose AIs from winning the denominator.
**Depends:** the tagger (B1) supplies the control tags reliably.
**Test.** Twin-pair fixture: Compressed-Expert (low control, AI carries) → low human%; Delegating-Manager (high control, AI carries) → **high** human%. Current code fails this; fixed code passes.

### C2 [M] Take `pi_s` out of the point estimate — `csl/ownership.py:166`
**Fault.** `human_weighted = pi_s * control`. `pi_s` is a *precision* quantity, yet it scales the *value* — conflating "human controlled less" with "we were less precise (the session looked passive)." Given the passivity itself is a tagger artifact (B2), this double-suppresses human%.
**Fix.** Point estimate uses `control` only; `pi_s` enters **only** the CI (it already does, via `_widen_clamped`). Keep the precision→interval path; remove precision→value.
**Why correct.** Clean separation of estimate vs confidence, consistent with #2's spirit even though ownership is not an ARI value.
**Test.** Two sessions with identical control evidence but different state precision yield the *same* `human_pct`, different CI widths.

### C3 [M] Per-level CI / n_eff honesty — `csl/ownership.py`
**Fault.** Levels with 1 firing get a degenerate point interval (`_bootstrap_ci` needs ≥2). After A5 most levels get ≥2, but enforce: never emit a bare `human_pct` without a CI, and surface `n_eff` per level (Chat4 reported "0.0%/100.0%" at n=16 with no interval — false precision).
**Fix.** Already structurally supported (`OwnershipResult.ci`, `.n_eff`); make the report layer *render* the CI and n_eff per level and forbid point-only display.
**Test.** Report golden: every OK level row carries `[lo, hi]` and `n_eff`.

### C4 🧊 [D] Split ES so it can fire on judgment, not only on hard events — `src/trait/extractors/per_dimension/es.py` + ES rubrics
**Fault.** ES is double-gated: the deterministic extractor requires an `E_OVERREACH/E_CORRECT/E_ERR` event *and* the joint judge returns ES=`no_ethics_events_detected`. With a single PII neuron, ES is N/A on virtually every chat.
**Fix.** Keep ES-01 (PII) deterministic and PII-gated (correct — absent PII is genuine structural N/A). Make the **other** ES neurons (ethical reasoning, governance awareness, boundary-setting) **judge-typed** with rubrics (A1) so they fire on ethics-*adjacent* reasoning without a hard overreach event. ES then reports OK when the user actually reasons about ethics, and structural-N/A only when no ethics-relevant content arises at all.
**Why correct.** Preserves absent≠zero (don't fabricate ES on neutral chats) while ending the dead-by-gating behavior.
**Test.** A chat with explicit ethical reasoning but no overreach event yields ES = OK; a purely technical chat yields ES = structural N/A with reason.

---

## 4. SUBSYSTEM D — Aggregation & gates

### D1 [M] Non-compensation **within** pillars + calibrated exponent — `src/aggregate/softmin.py`
**Fault (high-ARI bias).** `_pillar_value` is a weighted *arithmetic* mean; `_aggregate` applies the power mean only *across* pillars (`SOFTMIN_P=-2`). So a low dim is averaged away by its high pillar-mate **before** the soft-min ever sees it — and EC/CS carry 1.5×, so they dominate their pillars. Empirically this is why CD=0.55 only dropped the composite to 0.867: CD was diluted by CS(1.5×) within "create", then the mild p=-2 couldn't bind.
**Fix.** Apply the penalized power mean **within** pillars too, so a hollow dimension cannot hide behind a strong mate:
```python
def _pillar_value(values, dims, p=SOFTMIN_P):
    present = [(d, values[d]) for d in dims if d in values]
    if not present: return None
    ws = sum(DIMENSION_WEIGHTS[d] for d,_ in present)
    return (sum(DIMENSION_WEIGHTS[d]*(max(v,_EPS)**p) for d,v in present)/ws)**(1.0/p)
```
And **calibrate `SOFTMIN_P` via the D-study**, not the arbitrary -2. Safe to make it more negative now, because the noise-floor risk the soft-min originally guarded (EC=0.05 by chance) is already handled upstream: the `n_eff` gate (`gates.py`, `N_EFF_TAU`) excludes undersampled dims *before* aggregation. So genuine lows bind; sampling-noise lows are gated out, not averaged in.
**Why correct.** Separates the two jobs cleanly: gate removes noise; power-mean (within+across) enforces non-compensation on real signal.
**Latent → L7.** Re-examine the 1.5× EC/CS weights — under within-pillar non-compensation they no longer "rescue" a pillar, but they still tilt which dim binds. Justify or recalibrate.
**Test.** Synthetic profile {CD=0.55, others≈0.92}: composite drops materially (target ≈0.78–0.83, not 0.867); a profile hollow on one pillar cannot average to a high composite.

### D2 [M] Compute and gate on fluent-incompetence — `src/api/pipeline.py`, `src/aggregate/softmin.py`
**Fault.** `score_session_with_artifacts` hardcodes `fluent_incompetence=None` ("requires extractor evidence (Stage 2)"). It is **never computed** — the catching gate is off. (Correction to an earlier read: not mis-thresholded — absent.)
**Fix.** With neuron grain (A) + reliance + CSL available, compute it and apply it as a **multiplicative validity gate** G_k ∈ (0,1] per spec §3.7:
```python
fi = (pr_high and verification_ratio < TAU_V
      and attribution_gap > TAU_A and generative_ratio < 0.3)
G_fluent = FLUENT_PENALTY if fi else 1.0           # FLUENT_PENALTY ∈ (0,1], D-study-set
composite_value = _aggregate(agg_value) * G_fluent
```
Inputs are now real: `verification_ratio` from EC evidence/reliance, `attribution_gap` from the CSL Borrowed-Brilliance signal, `generative_ratio` from epistemic/regime, `pr_high` from the PR dimension.
**Critical distinction → L6.** This is a **trait-validity** gate and so it *may* scale the value (spec `× ∏ G_k`). It is **not** a state gate — `state_validity` must stay caveat-only (scaling it would violate #2; current code is correct on that). Keep the two gate classes separate in `gates.py`.
**Why correct.** A composite of 0.93 on a session where the AI carried 80–100% at every CSL level (4/5 BB flags, WoA=0, concept-completion 84%) should not be emitted at face value. This is the gate that makes ARI and CSL agree.
**Test.** The Chat4 profile (which meets all four conditions) now fires `fluent_incompetence=True` and the composite is penalized; a genuinely independent profile is untouched.

### D3 [M] Wire EC Tobit — `src/trait/extractors/per_dimension/ec_tobit.py`
**Fault.** Live uses `ec.py` point value; `ec_tobit` is dead. EC verification is off-screen-censored (most checking is invisible in the transcript) → EC is a censored lower bound, not a point. The existing audit also flags no convergence handling.
**Fix.** (a) Add convergence handling (existing audit Item #6); (b) wire Tobit so EC enters as a left-censored estimate, surfaced through the existing `Censored`/`MEASUREMENT_SATURATED` machinery in `softmin` (which already participates a censored bound). Keep the `ec_low_calibration_confidence` flag until the high-band gold set lands.
**Test.** EC on a transcript with implied-but-unshown verification reports a censored "≥ X" with appropriate width, not a deceptively precise point.

### D4 [D] Two-table event log on the live path — `src/eventlog/`
**Fault.** `compute_transitions/regime_overlay/reactions` consume a single `log.events`; the Human Control-Signal / AI Action split (`schema.py`) is unused.
**Fix.** Route dynamics through the two tables so human control signals and AI actions are queried separately (prerequisite for clean attribution and for C1's control fraction). Additive; failure-isolated like the CSL artifact.
**Test.** Dynamics output is identical-or-better on the regression set; the two tables reconcile to the single log’s event count.

---

## 5. SUBSYSTEM E — Determinism infrastructure (do before A2 scales to 107 calls)

### E1 [M] Verify and harden infra determinism — repo-wide
**Fault (assumed-fixed, unverified).** Spec names four stochastic layers; **Tier-A code nondeterminism** (`PYTHONHASHSEED`, async ordering) and **un-frozen quantile cuts** are *bugs*, not judge noise. If unfixed, going to 107 judge calls multiplies σ_code across every call.
**Fix.** Confirm `PYTHONHASHSEED` pinned, async/iteration order deterministic, embedding batch composition pinned, and **quantile boundaries frozen, never recomputed per run** (search for per-call quantile computation; freeze to a stored boundary set). These precede the G-study so σ_judge is not contaminated by σ_code.
**Test.** The same transcript through the deterministic layers (tags, phases, extractors, normalize with frozen cuts) is **bit-identical** across runs; only the judge layer varies.

### E2 [M] Replication protocol, not flat-K — `src/trait/judge/replication.py` + `cascade_eval`
**Fault.** Chat4 showed 4 raw single-run scores reported independently — the opposite of replication-with-aggregation.
**Fix.** Emit **one** median/posterior-mean estimate with a dispersion-derived CI (A4), using cascade selective re-judging (interior once, boundary K times). Never present N independent composites as if they were N measurements.
**Test.** The scorer emits a single estimate + CI; the cross-run variance is *inside* the CI by construction.

---

## 6. SUBSYSTEM F — Your segmentation idea, done correctly

### F1 [D] CSPC as evidence-router + precision (NOT a scoring partition)
**Your proposal #1** (segment chats, run every op per segment) — the instinct is right (whole-session joint scoring is lossy), the naive form is wrong.
**Why naive segment-then-score fails.** AL/EC/PR are stable only because of averaging over n_eff≈140. Split 294 turns into regime runs (drift mean ≈6.9; extractive/generative single-turn bursts) and most segments have n_eff 1–7 → per-segment scores swing like CD's 0.39 **everywhere**, and the scorability gate (≥4/8, `N_EFF_TAU=1`) fails on short segments → **more "pauses," not fewer**. And you'd segment on a state signal driven by the (pre-B1) weak tagger.
**Correct form.** Run neuron-grain extraction **within** each state-homogeneous window (so CD/CS evidence is harvested from generative bursts, EC from verification stretches), then **pool** per-segment firings into ONE session-level dimension estimate with state-conditioned precision (per-segment π_t pooled via the existing `_level_pi_s` weighting). Per-regime profiles are a **descriptive overlay only** — never independent composites.
**Depends:** A (neuron grain), B (clean state signal). **Gate:** only attempt after A4 passes.
**Test.** Pooled estimate ≈ session estimate within CI; per-regime overlay shows the generative-burst dims higher than the drift-stretch dims, with no per-segment composite emitted.

---

## 7. SUBSYSTEM G — Validation/diagnostic modules (corpus-gated; off the live score path)

These are correct to fix (per the existing audit) but **change no emitted score** — sequence them after A–D unless a release gate needs a diagnostic.

- **G1 [M→V] `csl/validation/judge_irt.py`** — Bayesian GRM; accumulate judge reps across corpus; require n≥30 before fitting. Currently fits on n=1 pairs (unstable).
- **G2 [M] `src/trait/kappa_efficiency.py`** — Ŝ_human is continuous; replace the binary-logistic likelihood with a Gaussian/beta likelihood; falsification `Var(κ^H|model)→0`.
- **G3 [D] `csl/analytics/conformance.py`** — replace naive subsequence matching with pm4py token-replay (the cyclic-trace false-perfect-fit bug).
- **G4 [D] `lpa_archetype_discovery.py`** — proper categorical encoding + ARI agreement (≥0.70), not hash-modulo.
- **G5 [D] BCS YAML** — resolve the conformance-gate inconsistency (one archetype affected).

---

## 8. Execution sequence, dependency DAG, and stop gates

```
E1 (infra determinism)  ─┐
A1 (rubric judge-typed) ─┴─▶ A2 (wire per-criterion) ─▶ A3 (neuron→dim aggregation, L1/L2)
                                                      ├─▶ A4 (CI from disagreement)
                                                      └─▶ A5 (feed CSL NeuronMatrix)
                                                                 │
                                              ⛔ GATE A: re-score Chat4 4-run set
                                              required: CD range ≤0.10 · dims spread · CSL levels populate
                                                                 │
        ┌──────────────────────────┬─────────────────────┬──────┴─────────┐
        ▼                          ▼                     ▼                ▼
  D2 fluent gate            C1 AI-control fix      B1/B2/B3 state    D1 within-pillar
  D3 EC Tobit               C2 pi_s out           (de-artifact)     non-compensation
  D4 two-table log          C3/C4 CSL honesty
        │
        └────────────────────────────────▶ ⛔ GATE B: ARI↔CSL agreement on twin-pair fixtures
                                                                 │
                                                          F1 segmentation (overlay only)
                                                                 │
                                                          G1–G5 validation modules
```
- **A1 + E1 are the bottleneck** for every score-moving fix. Do them first.
- **B-wave is parallelizable** with A but its payoff (de-artifacting CSL%) only manifests after A5.
- **Reorder vs the existing remediation plan:** that plan front-loads G (diagnostics that move no score) and never wires. Correct order: **E1+A1 → A2/A3/A4/A5 (+Gate A) → D2/D3 + C1/C2 + B → D1 (+Gate B) → F → G.**

---

## 9. Latent issues surfaced while fixing (the "anything still exists" you asked for)

| # | Latent issue | Where it bites | Handled in |
|---|--------------|----------------|-----------|
| L1 | Judge-neuron `n_eff` was stamped as `n_human`, faking CIs and the scorability gate | every dim CI; `_bootstrap_ci`; gate | A3 (real per-neuron n_eff) |
| L2 | A neuron scored by *both* a deterministic extractor and the judge double-counts | normalize mean | A1/A3 (one extractor per neuron + contract validator) |
| L3 | CI from the judge's self-reported confidence is unreliable (LLM overconfidence) | narrow, dishonest CIs | A4 (disagreement-based) |
| L4 | The AI-side extractor is surface-attribution by volume — it **re-introduces the Compressed-Expert/Delegating-Manager inversion the spec explicitly rejects** | CSL ownership truth | C1 (control-discounted AI) |
| L5 | `pi_s` multiplies the CSL point estimate → state-conditions a value | low human% (compounded by B2 artifact) | C2 |
| L6 | If `fluent_incompetence` were wired as caveat-only it would not bite; it must be a multiplicative G_k — but `state_validity` must stay caveat-only (#2) | composite value | D2 (gate-class separation) |
| L7 | Within-pillar arithmetic mean + EC/CS 1.5× lets a hollow dim hide behind its pillar-mate | high-ARI bias | D1 |
| L8 | 107 judge calls amplify any residual σ_code; quantile cuts may still be recomputed per run | determinism across the new path | E1 (verify first) |
| L9 | ES is double-gated (extractor event-gate **and** judge event-gate) → dead even at neuron grain unless split | ES always N/A | C4 |
| L10 | The judge score-level → [0,1] strength map is a new calibration surface; a linear map re-imports central tendency | dimension values | A1 (anchored non-uniform strengths) |
| L11 | Adding `None` metacog must be excluded from `degraded_share` denominator, or precision math shifts | precision merge | B2 (verify denominator) |
| L12 | Per-segment pooling needs per-segment π_t pooled, not session-level widening | segmentation correctness | F1 (reuse `_level_pi_s`) |

---

## 10. Acceptance suite (the proofs)

1. **Grain:** orchestrator value path calls `score_all_neurons`, not `judge.score_session`. (grep)
2. **CD variance:** Chat4 four-run CD range ≤ 0.10; composite range ≤ 0.03.
3. **Discrimination:** mean pairwise dim correlation on a diverse fixture set drops below a set threshold (no longer all-high-together).
4. **CSL density:** every ACF level with judge-neuron evidence emits OK with `n_eff>2` and a real CI; C5/C7 N/A only when truly absent.
5. **Twin-pair:** Delegating-Manager fixture → high human%; Compressed-Expert → low. (C1)
6. **Fluent gate:** Chat4 profile fires `fluent_incompetence=True` and penalizes the composite; independent profile untouched. (D2)
7. **Non-compensation:** {one dim 0.55, rest 0.92} composite ≤ 0.83. (D1)
8. **Determinism:** deterministic layers bit-identical across runs; only judge varies. (E1)
9. **Honesty:** no bare point estimate anywhere — composite and every CSL level carry CI + rung. (#6)
10. **Absent≠zero:** untagged-only transcript → metacog all-`None`, epistemic mean over assessable turns only, ES structural-N/A with reason. (B2/B3/C4)

---

*Nothing here is VALIDATED — validation is gated on a corpus that does not yet exist. Rungs describe each change's current maturity, not its target. Frozen surfaces (🧊) are CE-only with a version bump. Assign file-ownership (CE/Codex/Antigravity) per item before execution, respecting existing module boundaries.*
