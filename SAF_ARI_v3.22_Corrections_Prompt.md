# SAF/ARI v3.22 — Corrections Implementation Prompt

**For:** Claude Code (Codex agent)  
**Authority:** Chief Engineer sign-off required before executing any frozen-surface item (🧊).  
**Source:** Deep code-logic audit of branch `feat/v3.22-twelve-upgrades @ ec95ecd`, June 29 2026.  
**Read first:** `CLAUDE.md`, `DISCREPANCY.md`, `STATUS.md`, `INTERFACES.md`, `FixClaude.md §8`.  
**Non-negotiables that constrain every change here:** #1 (ontology freeze), #2 (no score multipliers), #6 (no bare point estimate), #12 (absent ≠ zero), #15 (minor protection), #19 (calibration before claims), #21 (no silent cross-ownership edits).

---

## CONTEXT: What the Audit Found

A file-level audit followed by a full control-flow trace revealed five categories of problem. Items are sequenced by dependency; do not skip ahead.

**Gate A Status (from `gate_a_runs.json`, run Jun 28):**
- CD 4-run range: **0.263** — target ≤ 0.10 → **FAIL**
- Composite 4-run range: **0.272** — target ≤ 0.03 → **FAIL** (run 3 = 0.003, run 4 = 0.275)
- Dims spread: 0.00–0.64 → PASS
- CSL C1–C7 populate → PASS

Gate A fails criteria (i). STATUS.md rule: "If any fail: stop, diagnose, do not proceed." The downstream waves (D/C/B/F/G) were already built; this prompt corrects the cause and the false done-markers.

---

## CORRECTIONS IN EXECUTION ORDER

### FIX-1 ← THE ROOT CAUSE: Wire replication-median around neuron scoring
**Priority: MUST DO FIRST. Everything else rests on this.**

**File:** `src/api/pipeline.py`  
**File:** `src/trait/judge/per_criterion.py` (read, do not break)  
**File:** `src/trait/judge/cascade_eval.py` (already has the machinery — use it)

**What is wrong:**  
`score_all_neurons_sync` (called at `pipeline.py:633`) runs each neuron's judge call exactly once via `_score_all_neurons_async`. `cascade_eval.py` contains `compute_disagreement_metric()`, `estimate_phi_from_disagreement()`, and the constants `DEFAULT_INITIAL_REPS=3`, `DEFAULT_MAX_REPS=10`, `DEFAULT_DISAGREEMENT_THRESHOLD=0.15` — but the replication loop is never invoked. Each neuron is scored once, so Gemini's run-to-run non-determinism (documented in ADR-0009) propagates directly into the composite. The CI source at `pipeline.py:471–477` uses between-neuron spread within a dimension (`judge_strengths`), which reflects genuine facet heterogeneity, not measurement noise — so it is the wrong signal for uncertainty.

**What to build:**  
Add a per-dimension replication wrapper that:

1. Calls `score_dimension(transcript, dim, nids, judge_client)` `DEFAULT_INITIAL_REPS` (=3) times.
2. For each neuron, collects the `DEFAULT_INITIAL_REPS` level values and computes `compute_disagreement_metric(per_neuron_scores)`.
3. If `disagreement > DEFAULT_DISAGREEMENT_THRESHOLD` for any neuron in the dimension: run up to `DEFAULT_MAX_REPS - DEFAULT_INITIAL_REPS` more passes for **that dimension only**.
4. Final neuron score = `median` of all reps for that neuron (not mean — median is resistant to outlier runs like the run-3 CD=0.000 collapse).
5. The per-neuron replication scores also give you the **real** within-neuron variance — use `compute_disagreement_metric(per_neuron_scores_across_reps)` as the CI source for A4. Replace the current `judge_strengths` spread at `pipeline.py:471–477` with this per-neuron replication variance. The flag `ci_from_disagreement` should stay; the label is correct, only the input changes.

**Contract invariants:**
- Do NOT add new neurons. Do NOT change the rubric bank.
- The `_add_judge_neuron_firings()` function at `pipeline.py:351` must continue to receive results in exactly the same format — `results: dict[str, dict]` where each entry has `final_score_after_leniency_penalty` or `score`. You are feeding it medians now instead of singles.
- The joint `judge.score_session()` call at `pipeline.py:637` must remain — it provides provenance metadata and family-conflict detection.
- `score_all_neurons_sync` is the public entrypoint. Either replace its internals or add a replicated variant and call it from `pipeline.py:633`. Do not break the sync shim — other callers may use the old path.

**Acceptance test (add to `tests/integration/test_v3_22_full.py`):**
```python
def test_gate_a_cd_variance():
    """Re-run Chat4 4 times. CD range must be ≤ 0.10, composite range ≤ 0.03."""
    # Use the Chat4 fixture from data/gold/chats/gc-004.json (or whichever chat
    # was the Gate-A stimulus — confirm from gate_a_runs.json context).
    # Four independent score calls. Compute per-dim ranges.
    ...
    assert cd_range <= 0.10, f"CD range {cd_range:.3f} exceeds Gate-A budget"
    assert composite_range <= 0.03, f"Composite range {composite_range:.3f} exceeds Gate-A budget"
```

**After the acceptance test passes: update STATUS.md:**
- Acceptance test #2: change `[ ] needs live run` → `[x] YYYY-MM-DD` with the actual ranges.
- Acceptance test #3: re-run discrimination check; update accordingly.
- Acceptance test #4: CSL density already passes — mark `[x]`.
- Acceptance test #6: re-run fluent gate; update accordingly.

---

### FIX-2: Wire ec_tobit onto the live EC value path (D3 — was marked done, is not wired)

**File:** `src/api/pipeline.py`  
**File:** `src/trait/extractors/per_dimension/ec_tobit.py` (read-only — do not change the module)  
**File:** `src/trait/extractors/per_dimension/ec.py` (read-only)

**What is wrong:**  
`apply_tobit_to_ec_scores()` exists and is unit-tested but is never called on the live path. The EC dimension score currently uses the deterministic `ec.py` neurons (EC-06/07/09) + the 11 judge rubrics. The Tobit CI enrichment never touches it.

**What to build:**  
After `_profile_from_judge()` returns the raw profile (at `pipeline.py:648`), for the `Dimension.EC` entry only:

1. Extract the current `ec_score = raw_profile[Dimension.EC].value` (skip if None or non-OK status).
2. Call:
   ```python
   from src.trait.extractors.per_dimension.ec_tobit import apply_tobit_to_ec_scores
   tobit_result = apply_tobit_to_ec_scores({'ec_score': ec_score})
   ```
3. `apply_tobit_to_ec_scores` returns `{'ec_score', 'ci_lo', 'ci_hi', 'censored', 'censored_bound_direction', 'sigma', 'chat_id'}`.
4. Replace the existing `DimensionScore.ci` for EC with `ConfidenceInterval(low=tobit_result['ci_lo'], high=tobit_result['ci_hi'])`.
5. If `tobit_result['censored']` is True: set `status=ScoreStatus.MEASUREMENT_SATURATED` and attach a `censored` bound (bound = 0.0, direction = 'low') — reuse the existing `CensoredBound` type that `saturation_for()` already returns.
6. Append `"ec_tobit_ci"` to the dimension's `flags` list.
7. Do NOT change `ec_score` (the value). Tobit conditions the CI only — non-negotiable #2.

**Acceptance test (add to `tests/unit/test_tobit_ec.py`):**
```python
def test_tobit_is_wired_to_ec_dimension():
    """score_session_with_artifacts produces an EC DimensionScore whose CI
    comes from Tobit (flagged 'ec_tobit_ci'), not raw judge self-confidence."""
    # Use a minimal CanonicalSession fixture with a few human turns.
    run = score_session_with_artifacts(fixture_session, judge=mock_judge)
    ec = run.profile[Dimension.EC]
    assert "ec_tobit_ci" in (ec.flags or []), "Tobit CI flag absent — not wired"
    if ec.ci:
        assert ec.ci.low >= 0.0 and ec.ci.high <= 1.0
```

**STATUS.md:** D3 remains `[x]` — no checkbox change needed; the module was correct. Just wiring.

---

### FIX-3: Wire grounding/vigilance into merge-side precision (or formally defer)

**This is a CE decision gate.** Present both options to CE before building.

**File:** `src/trait/grounding.py` — exposes `classify_grounding(session, tags) -> list[GroundingFunction]`  
**File:** `src/trait/vigilance.py` — exposes `score_vigilance(session, tags) -> VigilanceResult`  
**File:** `src/merge/precision.py` — THE meeting point; `turn_precision()` and `widening_factor()` live here  
**File:** `contracts/schemas.py` — `GroundingFunction` and `VigilanceResult` already added (D-027)

**What is wrong:**  
D-027 was marked RESOLVED after adding the schema types, but the D-027 decision itself says "the types have no consumer yet." The modules are produced nowhere and consumed nowhere — dead weight that passes tests only by not being called.

**Option A — Wire (recommended):**  
In `pipeline.py`, after the state estimator call (`pipeline.py:657`) and before `merge()`:
1. `grounding_seq = classify_grounding(session, tags)` — produces `list[GroundingFunction]` (one per turn).
2. `vig_result = score_vigilance(session, tags)` — produces `VigilanceResult`.
3. Pass both into `merge()` (which passes them through to `precision.py`).
4. In `merge/precision.py`, inside `turn_precision()`: if a turn's grounding label is `GroundingFunction.REPAIR`, apply a CI-widening factor (a repair signal means the human needed to correct a misunderstanding — evidence precision is lower). If `vig_result.pattern_detected`, widen EC/CA CI by a small graded amount.
5. These are PRECISION conditioners only — they widen CI; they must never change `DimensionScore.value` (#2).
6. Append `"grounding_conditioned"` or `"vigilance_conditioned"` to the affected dimension's `flags`.

**Minimum implementation spec for CI widening (DESIGNED rung — calibrate post Gate A):**
- REPAIR fraction = (count of REPAIR-labelled turns) / (total assessed turns). If > 0.20: widen EC CI by `× (1 + 0.15 × repair_fraction)`.
- `vig_result.score` in [0, 1] where 1 = highest vigilance signal. If `vig_result.pattern_detected` is True: widen CA CI by `× (1 + 0.10 × vig_result.score)`.
- Clamp all CIs to [0, 1]. Never assert CI crosses The Wall.

**Option B — Formally defer:**  
If CE decides not to wire now: add a DISCREPANCY entry `D-033 [OPEN]` noting that D-027 shipped schema but zero wiring, add a deferral entry to `PROPOSALS.md` with rung=DESIGNED and reinstatement trigger = "Gate A passes + n≥50 corpus", and move D-027's status from RESOLVED to RESOLVED-SCHEMA-ONLY. Update `STATUS.md` to reflect that D-027 is schema-only, not behavior-complete.

**Either way: update D-027 in DISCREPANCY.md to reflect the true state.**

---

### FIX-4: Correct the D2 fluent_incompetence gate logic

**File:** `src/api/pipeline.py` (lines 588–606 — `_compute_fluent_incompetence`)  
**Owner:** Chief Engineer (CE-owned file)

**Two logic defects, both fixable without a contract change:**

**Defect A — Wrong construct: `theater_frac` ≠ `attribution_gap`**  
Current code:
```python
theater_frac = ec_evidence.theater_counter / n_verify if n_verify > 0 else 0.0
```
The spec (FixClaude.md D2) defines the gate as: `pr_high ∧ verification_ratio < TAU_V ∧ attribution_gap > TAU_A ∧ generative_ratio < 0.3`. Attribution gap is the fraction of sessions where the human accepts AI output without tracking which ideas were AI-generated vs. their own. Theater fraction (hollow verification acts) is a component of EC evidence, not the same construct. Replace `theater_frac > _TAU_A` with the correct `attribution_gap` signal — this is already partially available from the reliance metrics (`rel` at `pipeline.py:628`): `rel.weight_of_advice` is the closest proxy for attribution gap (high WoA = human gives high weight to AI suggestions = low independent attribution). Use:
```python
from src.trait.reliance_metrics import RelianceMetrics
# rel is already computed at line 628
attribution_gap = rel.weight_of_advice if rel.weight_of_advice is not None else 0.0
```
Then replace `theater_frac > _TAU_A` with `attribution_gap > _TAU_A`.

**Defect B — Self-limiting conjunction**  
The conjunction `verify_ratio < _TAU_V (0.10) AND theater_frac > _TAU_A (0.50)` is nearly impossible to satisfy simultaneously: when verification is near-zero (< 0.10 of turns), `n_verify` is tiny, making `theater_frac = theater_counter / n_verify` numerically unstable and often 0.0 (zero theater events in zero verify slots). The gate cannot fire in the regime it is designed to catch.

Fix: restructure the gate as three independent behavioral signals, where the gate fires if at least two of three signal conditions are true (majority-vote, not AND):
```python
signals = [
    pr.value > _TAU_PR_HIGH,                             # high PR facade
    verify_ratio < _TAU_V,                               # rarely verifies
    attribution_gap > _TAU_A,                            # high AI weight
]
# Gate fires when majority of behavioral signals are present
# (more robust than the triple-AND which the self-limiting issue breaks)
behavioral_score = sum(signals)
gate_fires = behavioral_score >= 2 and ep_mean < _TAU_GEN
return gate_fires
```

**Note on thresholds:** All four threshold constants (`_TAU_PR_HIGH`, `_TAU_V`, `_TAU_A`, `_TAU_GEN`) remain at their current placeholder values — D-031 governs their calibration and is blocked on n≥50 gold chats. Do not tighten them here. The logic fix is independent of calibration.

**Acceptance test:**
```python
def test_fluent_gate_fires_on_majority_behavioral_signals():
    """Gate must fire with PR=0.80, verify_ratio=0.05, attribution_gap=0.70, ep_mean=0.20."""
    ...
    assert result is True

def test_fluent_gate_does_not_fire_on_low_ep_mean_alone():
    """No behavioral signals present → gate does not fire despite low epistemic mean."""
    ...
    assert result is False
```

---

### FIX-5: Update STATUS.md — stale checkboxes misrepresent Gate A outcome

**File:** `STATUS.md`  
**Owner:** Chief Engineer

Gate A ran (gate_a_runs.json exists, dated Jun 28 2026) but the acceptance test checkboxes still say "needs live run." The live data shows criteria (i) FAILS. The stale checkboxes are how the failed gate stayed invisible. These are purely documentary — no code change.

**Update each row:**

| Row | Current text | Correct text |
|-----|-------------|-------------|
| Test #2 (CD variance) | `[ ] needs live run` | `[!] GATE A FAIL — CD range 0.263 (target ≤ 0.10); composite range 0.272 (target ≤ 0.03). See gate_a_runs.json. Blocked on FIX-1.` |
| Test #3 (discrimination) | `[ ] needs live run` | `[x] PASS — dims spread 0.00–0.64 (no longer clustering 0.85–0.98). From gate_a_runs.json.` |
| Test #4 (CSL density) | `[ ] needs live run` | `[x] PASS — C1–C7 all populate. From gate_a_runs.json and diag_csl.json.` |
| Test #6 (fluent gate) | `[~] D2 wired; Chat4 live run still needed` | `[~] D2 wired (FIX-4 pending logic correction). Re-run after FIX-1 and FIX-4 land.` |

Also update the WAVE A status for A1–A5 to note "Gate A (i) FAILS — FIX-1 required before downstream waves are validated."

Also add to `DISCREPANCY.md`:
```
## D-033  [OPEN]  — Gate A criteria (i) failed on live data; downstream waves built without passing the gate
- Raised by: Audit
- Date: 2026-06-29
- File(s): gate_a_runs.json, STATUS.md, src/api/pipeline.py
- Problem: CD 4-run range = 0.263 (target ≤ 0.10); composite range = 0.272 (target ≤ 0.03).
  Root cause: replication-median (cascade_eval) not wired to live path — each neuron scored once.
  STATUS.md checkboxes still said "needs live run" masking the failure.
- Proposed fix: FIX-1 in this prompt (wire K-rep median). Re-score Chat4 4× after fix lands.
- Decision: <CE ONLY>
- Status: OPEN
```

---

### FIX-6: Add the five absent governance/register entries (zero code, documentation only)

These were agreed to in design sessions and confirmed absent by grep. All are low-effort; none require code.

**6A — CH/COMP construct validity grounding**  
File: `contracts/contract_table.yaml`  
Find the `EC` dimension section and the `fluent_incompetence` note. Add under the relevant neuron group:
```yaml
construct_validity_grounding:
  - source: "Noorani et al. 2026 (multi-round Human-AI collaboration)"
    finding: "GT loss rate — humans who rely heavily on AI explanations show degraded independent performance on transfer tasks; effect size d≈0.68 in classroom contexts."
    relevance: "External construct validity for Explanation Trap (EC) and Fluent Incompetence gate (D2). GT loss rate is the behavioral signature this instrument's EC dimension is designed to measure. Rung: MEASURABLE (external replication)."
```

**6B — DIF governance rule**  
File: `contracts/contract_table.yaml`  
Add a top-level governance section (or extend existing governance block):
```yaml
dif_governance:
  prohibition: "Reference classes in DIF testing MUST be education_stage, domain, ai_familiarity, language, task_type only. Occupation labels are PROHIBITED as reference classes — they encode socioeconomic confounds and cannot be cleared by standard DIF procedures. Violation requires CE sign-off and a new ADR before any DIF analysis."
  permitted_covariates: [education_stage, domain, ai_familiarity, language, task_type]
  prohibited_covariates: [occupation, employer, industry, income, job_title]
  authority: "non-negotiable #14 (fairness-safe covariates); spec §8.7"
```

**6C — Noorani deferral register entry**  
File: `PROPOSALS.md`  
Add an entry for the Noorani Tier-3 framework:
```markdown
## P-003 — Noorani Multi-Round Collaboration Framework (Tier 3 Intervention Target)

**Source:** Noorani et al. (2026) — Multi-Round Human-AI Collaboration
**Status:** ASPIRATIONAL (register entry only; zero current implementation)
**Rung:** ASPIRATIONAL → DESIGNED (when Tier 3 platform build begins)

**What it is:** A structured multi-round collaboration protocol where the AI progressively
reduces scaffolding while the human takes on more cognitive ownership. Operationalised
via Conformal Prediction (Venn-Abers/RAPS) for dynamic uncertainty quantification and
a GT (Ground Truth) loss rate metric for sustainability detection.

**Why deferred:** This is an *intervention* arm — it conditions the user's experience
based on score outputs, which would contaminate IRT calibration if deployed concurrently
with the retention-probe validation phase. Non-negotiable: intervention strictly separated
from measurement.

**Replaces:** The vague "Adaptive Friction Layer" placeholder in §10.3.

**Reinstatement triggers:**
1. SAF/ARI instrument validated (retention probe data at n≥200, Layer 4 cleared)
2. Separate intervention arm deployed in a distinct study arm (not the calibration cohort)
3. Conformal Prediction model fitted on post-validation score distributions

**Does NOT cross The Wall:** Intervention uses score outputs, not transcript-derived
counterfactuals. Layer 4 outcome data is the prerequisite, not a bypass.
```

**6D — Human IRR runner module**  
File: `calibration/human_irr_runner.py` (new file)  
Create a minimal stub that defines the interface, annotated as "not yet runnable — requires second rater + 30+ annotated chats":
```python
"""
calibration/human_irr_runner.py — Human IRR ceiling measurement (v3.22 Item #5).
OWNER: Chief Engineer.

Purpose: Compute Cohen's κ per neuron across two human raters for ≥30 annotated
gold chats. The resulting κ_per_neuron values set the empirical Φ target for the
cascaded replication threshold in cascade_eval.py:DEFAULT_DISAGREEMENT_THRESHOLD.

STATUS: NOT RUNNABLE — requires:
  1. Second human rater with access to the gold chat set
  2. Rater-2 annotations for ≥30 chats in the same format as data/gold/rationales/
  3. CE co-ordination to resolve disagreements before computing κ

When runnable:
  python -m calibration.human_irr_runner \
      --rater1 data/gold/rationales/ \
      --rater2 <rater2_dir>/ \
      --output calibration/results/irr_kappa.json

Output format:
  {
    "per_neuron_kappa": {"EC-01": 0.72, "EC-02": 0.68, ...},  # Cohen's κ per neuron
    "mean_kappa": 0.71,
    "phi_target": 0.70,  # = mean_kappa (or CE-adjusted value)
    "n_chats": 30,
    "rater1_id": "...",
    "rater2_id": "...",
    "computed_at": "..."
  }

After running: update cascade_eval.py:DEFAULT_PHI_TARGET and
DEFAULT_DISAGREEMENT_THRESHOLD from the output. File a new ADR.
"""

from __future__ import annotations
# Implementation pending rater-2 annotation set.
# Stub present to define the interface and prevent ambiguity about ownership.
raise NotImplementedError(
    "human_irr_runner not yet runnable — see module docstring for prerequisites."
)
```

**6E — SSSR Phase-0 telemetry (migration 015 displacement)**  
File: `DISCREPANCY.md`  
Add:
```
## D-034  [OPEN]  — SSSR Phase-0 telemetry columns not added; migration 015 was repurposed
- Raised by: Audit
- Date: 2026-06-29
- File(s): alembic/versions/015_research_question_quality_view.py, specs/v3.22/v3.22_SpecDelta.md §SSSR
- Problem: v3.22 SpecDelta specified migration 015 to add s0_snapshot, external_uncertainty_flag,
  semantic_volume, and competency_covariates columns (SSSR Phase-0 + CRO covariate capture).
  The actual migration 015 was instead used for a question_quality research view. Neither
  SSSR Phase-0 telemetry nor CRO competency_covariates were added. CRO Phase-0 is now
  also blocked (its migration dependency was 015-SSSR). This was not noted in any discrepancy.
- Proposed fix: Add migration 019 with the SSSR + CRO covariate columns (renumbered from
  the displaced 015 plan). CE to assign a new number and approve schema additions.
- Decision: <CE ONLY>
- Status: OPEN
```

---

## WHAT NOT TO DO IN THIS SESSION

These are either correctly deferred or require CE approval that has not yet been given:

- **DO NOT** attempt B1 (tagger rebalance) — frozen surface, D-028 OPEN, CE sign-off required.
- **DO NOT** attempt C1 (AI ownership discount) — blocked on B1, D-029 OPEN.
- **DO NOT** attempt C4 (ES split) — requires CE contract bump, D-030 OPEN.
- **DO NOT** attempt SSSR semantic entropy implementation — no migration landed yet; D-034 must close first.
- **DO NOT** attempt CRO z-score computation — awaits SSSR Phase-0 + n≥200 corpus.
- **DO NOT** run IRT/GRM/EFA on the gold set — corpus gate n≥200; current n=26.
- **DO NOT** tighten D-031 fluent gate thresholds — calibration gated on n≥50 annotated gold chats.

---

## ACCEPTANCE CRITERIA SUMMARY

Before closing this session, the following must all be true:

| # | Test | How to verify |
|---|------|--------------|
| 1 | FIX-1 merged and replication runs | `grep -n "cascaded\|replicate\|median\|n_reps" src/api/pipeline.py` shows the loop |
| 2 | Gate A CD range ≤ 0.10 | Re-run `python -c "from scripts.discovery.determinism_probe import *; main()"` or the new integration test |
| 3 | Gate A composite range ≤ 0.03 | Same run |
| 4 | EC Tobit flag present on scored sessions | `"ec_tobit_ci"` in `run.profile[Dimension.EC].flags` |
| 5 | D2 conjunction uses `attribution_gap`, not `theater_frac` | `grep theater_frac src/api/pipeline.py` returns nothing |
| 6 | D2 majority-vote fires correctly | New unit tests pass |
| 7 | STATUS.md checkboxes updated | Tests #2/#3/#4/#6 no longer say "needs live run" |
| 8 | D-033 filed in DISCREPANCY.md | Entry present |
| 9 | PROPOSALS.md has Noorani P-003 | `grep -n "Noorani\|P-003" PROPOSALS.md` |
| 10 | `contracts/contract_table.yaml` has CH/COMP grounding and DIF rule | `grep -n "Noorani\|dif_governance" contracts/contract_table.yaml` |
| 11 | `calibration/human_irr_runner.py` stub exists | `ls calibration/human_irr_runner.py` |
| 12 | D-034 filed for SSSR/CRO migration displacement | Entry in DISCREPANCY.md |
| 13 | Grounding/vigilance either wired or D-033 deferred | CE decision recorded |
| 14 | Full test suite still at ≥609 passed / 0 failed | `pytest -q --tb=short` |

---

## TECHNICAL REFERENCE (exact signatures to use)

```python
# FIX-1: cascade machinery already available
from src.trait.judge.cascade_eval import (
    compute_disagreement_metric,      # (scores: list[float]) -> float
    estimate_phi_from_disagreement,   # (disagreement, target_phi, n_reps) -> float
    DEFAULT_INITIAL_REPS,             # = 3
    DEFAULT_MAX_REPS,                 # = 10
    DEFAULT_DISAGREEMENT_THRESHOLD,   # = 0.15
)
from src.trait.judge.per_criterion import score_dimension  # async; call via asyncio.run
# score_dimension(transcript, dim_name, neuron_ids, judge_client) -> dict[nid, score]

# FIX-2: Tobit API
from src.trait.extractors.per_dimension.ec_tobit import apply_tobit_to_ec_scores
# apply_tobit_to_ec_scores({'ec_score': float}) -> {'ec_score', 'ci_lo', 'ci_hi', 'censored',
#   'censored_bound_direction', 'sigma', 'chat_id'}

# FIX-3 (if Option A): grounding/vigilance API
from src.trait.grounding import classify_grounding
# classify_grounding(session, tags) -> list[GroundingFunction]
from src.trait.vigilance import score_vigilance
# score_vigilance(session, tags) -> VigilanceResult

# FIX-4: reliance already computed — re-use
# rel = reliance_metrics(session)   [already at pipeline.py:628]
# rel.weight_of_advice: float | None   <- attribution_gap proxy

# Data types already imported in pipeline.py
from contracts.schemas import (
    ConfidenceInterval, DimensionScore, ScoreStatus, CensoredBound, Rung
)
```

---

## COMMIT DISCIPLINE

Separate commit per fix. Suggested messages:
```
feat: [FIX-1] wire K-rep median into neuron scoring; Gate A passes
fix:  [FIX-2] wire ec_tobit onto live EC value path (D3)
fix:  [FIX-4] D2 gate — attribution_gap replaces theater_frac; majority-vote conjunction
docs: [FIX-5] update STATUS.md with Gate A live results; file D-033
docs: [FIX-6] add absent governance entries (CH/COMP, DIF, Noorani, IRR stub, D-034)
[FIX-3: separate commit after CE decision on grounding/vigilance option]
```

Push each commit before verification; do not verify against a local-only commit.

---

*Prompt prepared from: `SAF_ARI_v3.22_Proposal_Audit.docx` + `SAF_ARI_v3.22_Deep_Code_Audit.docx`, June 29 2026. All file paths, function signatures, and line numbers verified against live repo at ec95ecd.*
