# SAF/ARI v3.2 — Claude Code Implementation Guide
## Building the Cognitive Work Layer (CSL) over the existing Chat Classifier v2

**Read first:** `SAF_ARI_v3.2_SpecDelta_over_v3.1.md` (the framework spec). This document is the *implementation* companion — what to change in the codebase, in what order, with interfaces, acceptance criteria, and stop points.

**Current build state (do not re-derive):**
- `contract_table.yaml` populated for all 107 neurons. Test suite green (108/108). Overall MAE 0.2994 (≤0.375 threshold met). `EqualWeightScorer` ships; `GRMScorer` is interface-only. Three NLP metrics implemented (Attribution Gap, Verification Ratio, Gen/Extractive — plus Actualization Depth, Semantic Distance Δ, Iteration Depth).
- EC dimension MAE ≈ 0.41 (weak spot; needs 40+ gold; out of scope for v3.2 code).
- CSPC ships two proxies in the report (`load_level`, `tom_slope`); full HGF not built.

**The governing implementation principle:**
> CSL's human side is a re-aggregation of the EXISTING `NeuronMatrix`. Do NOT write a second extraction over the transcript for the human side. The only new extraction is the AI-side extractor and the emergence scanner. Re-running extraction for the human side would re-introduce the double-measurement bug the feature partition exists to prevent.

**Working conventions (unchanged from v2):**
- Pydantic models for all contracts. Fixed field names. Structured ordinal judge output only (no free text), fixed temperature, versioned prompts.
- Every score ships with a credible interval. Never emit a precision you do not have.
- Never score a non-applicable neuron as 0. Never average separate constructs together.
- Read dimensions/levels from `config.py`; never hardcode.

---

## PHASE 0 — Infrastructure Fixes (DO THESE FIRST — they precede all CSL work)

CSL built on a non-deterministic, insecure base inherits both problems. None of Phase 0 is CSL; all of it is prerequisite.

### 0.1 — Security: OpenAI key in `telemetry.metadata` (P0, has an external-harm clock)
- **Goal:** remove the live secret and prevent recurrence.
- **Actions:**
  1. Rotate the exposed OpenAI key immediately (out-of-band).
  2. Scrub all historical rows: null any secret-shaped value in `telemetry.metadata` JSONB.
  3. Add a **write-time guard** in the telemetry writer that rejects any string matching secret patterns (`sk-`, `AKIA`, bearer-token shapes, high-entropy 32+ char tokens) before persisting metadata.
- **Files:** wherever telemetry is written (`telemetry/writer.py` or equivalent); a new `telemetry/secret_guard.py`.
- **Acceptance:** a unit test asserts that writing metadata containing `sk-...` raises/scrubs; a migration confirms zero secret-shaped values remain in existing rows.

### 0.2 — Determinism: same chat must produce same scores
- **Goal:** eliminate run-to-run score drift from the four stochastic layers.
- **Actions:**
  1. **Tier A:** set `PYTHONHASHSEED=0` (or explicit), and make any async/parallel extraction ordering deterministic (sort by `turn.index` before reduction; no dict-iteration-order dependence).
  2. **Quantile cuts:** load frozen quantile boundaries from a versioned artifact (`config/quantile_cuts.json`); FAIL LOUDLY if the code path recomputes them at runtime.
  3. **Tier B embeddings:** pin batch composition (deterministic batching by `turn.index`); do not let batch size change embeddings.
  4. **Tier C judge:** keep temperature fixed; add an **N-replication wrapper** that runs the judge K times and reports mean±SD, invoked ONLY for items whose score lands near a quadrant boundary (configurable band).
- **Files:** `extraction/tier_a_deterministic.py`, `extraction/tier_b_embedding.py`, `extraction/tier_c_judge.py`, new `config/quantile_cuts.json`, new `extraction/judge_replication.py`.
- **Acceptance:** running the full pipeline twice on a fixture chat yields byte-identical `NeuronMatrix` for Tier A/B; the quantile loader raises if the frozen file is missing; the replication wrapper fires only inside the boundary band.

### 0.3 — Reporting: enforce four distinct states (never-collapse)
- **Goal:** stop collapsing `STRUCTURAL_NA`, `INSUFFICIENT_SAMPLE`, and genuine low scores; add the third sibling.
- **Actions:** add `MEASUREMENT_SATURATED` to the reporting state enum; ensure the report renderer maps each of the four conditions to a distinct, never-merged label. This same enum is reused by CSL (Phase 2.6).
- **Files:** `output/report.py`, `schemas.py` (extend the status enum).
- **Acceptance:** a fixture exercising all four conditions renders four visually distinct labels; a test asserts no two states share a label string.

---

## PHASE 1 — CSL Specification Artifacts (writable now, zero new data, NO measurement yet)

These are configuration and prompt artifacts, frozen before any judge runs against them (Goodhart prevention).

### 1.1 — The neuron→ACF crosswalk (frozen DATA, not code)
- **Goal:** define the projection from existing neurons onto the 7 ACF levels.
- **Files:** new `csl/acf_crosswalk.yaml`.
- **Schema:**
  ```yaml
  acf_levels:
    C1: {label: "Knowledge Sourcing", neurons: [CS-..., AL-...]}
    C2: {label: "Sense-Making",       neurons: [EC-02, EC-03, AL-01, ...]}
    C3: {label: "Direction & Checking", neurons: [EC-01, EC-06, EC-09, PR-...]}
    C4: {label: "Problem Framing",    neurons: [CS-05, CS-06, CS-08, CD-02]}
    C5: {label: "Quality Judging",    neurons: [EC-..., CA-15, CA-16]}
    C6: {label: "Original Making",    neurons: [CD-06, CD-08, CD-09, CS-01]}
    C7: {label: "Partnership Steering", neurons: [CA-01, CA-06, CA-13, CA-14, CA-17, AUI-02, AUI-08, AUI-09]}
  ```
- **CRITICAL:** the full mapping is reviewed and **frozen** before Phase 2. A neuron may appear in at most the levels where its construct genuinely belongs. Cross-check against the existing AILit phase classifier (the coarse predecessor).
- **Acceptance:** every neuron in `contract_table.yaml` is either mapped to ≥1 ACF level or explicitly listed as `csl_excluded` with a reason; the loader validates the crosswalk against the neuron contract IDs.

### 1.2 — The two PARTITIONED judge-prompt families  ⟵ **STOP-FOR-HUMAN-REVIEW**
- **Goal:** prevent the judge from collapsing ARI scoring and CSL foundation-detection into one measurement.
- **Files:** `extraction/prompts/ari_competency_prompt.txt` (the existing scoring prompt, versioned), new `csl/prompts/csl_foundation_prompt.txt`.
- **Requirement:**
  - The **ARI** prompt asks the judge to score the human's behavior as trait evidence (it may use AI-turn context, because ARI is dyadic, but it does NOT ask "who originated this").
  - The **CSL** prompt asks the judge to assess foundation evidence *relative to* the AI's preceding output (selective rejection, exogenous injection, criterion substitution — the §2.4.4 control signals) — i.e. it explicitly attends to the seam between AI output and human response.
- **STOP HERE.** A human must confirm the two prompts attend to *genuinely different things* before either is wired to the judge. If the partition is not enforced at the prompt level, the judge collapses the two measurements and the double-counting risk returns regardless of architecture.
- **Acceptance (post-review):** a documented sign-off that the two prompt families are partitioned; a diff showing the CSL prompt references the AI-turn baseline and the ARI prompt does not reference origination.

### 1.3 — The ownership formula + CSPC precision hook (spec only)
- **Goal:** fix the math before building.
- **Files:** `csl/SPEC_ownership.md` (a spec doc, then implemented in Phase 2.3).
- **Formula:**
  ```
  Human_ownership(level) =
       π(S_t) · control_human(level)
     ─────────────────────────────────────────────────
     π(S_t) · control_human(level) + AI_displayed(level)
  ```
  where `π(S_t)` comes from the CSPC proxies now (`load_level`, `tom_slope`), the full HGF later.
- **Acceptance:** the spec defines per-level credible-interval derivation (bootstrap over the contributing neuron firings) and states explicitly that the output is a 7-vector, never a scalar.

### 1.4 — The emergence sequence-scanner (spec only)
- **Goal:** specify the three-condition detector before building.
- **Files:** `csl/SPEC_emergence.md`.
- **Three conditions (all required, jointly):**
  1. Bilateral novelty: `semantic_distance(human_new, human_prior_centroid)` HIGH **and** `semantic_distance(human_new, ai_prior_centroid)` HIGH.
  2. Fused dependency: human turn shows BOTH uptake (low attribution gap to the *immediately preceding* AI turn) AND injection (CD/CS exogenous-content signature) in the same window.
  3. Reframing trace: actualization loop closes on a reframing (not a refinement).
- **Then judge-confirm** the candidate window (the three signals can co-occur by chance).
- **Acceptance:** the spec defines the window size, the centroid computation, and the candidate→judge handoff.

### 1.5 — OSF pre-registration
- Pre-register: the crosswalk, the two prompt families, the ownership formula, the emergence conditions, and **the independence test** (ARI scores vs CSL shares must not be ~1.0). Null results publishable.

---

## PHASE 2 — CSL Build (over the frozen Phase 1 spec)

### 2.1 — Track 1 human side: re-projection (NO new extraction)
- **Goal:** project the existing `NeuronMatrix` onto ACF levels.
- **Files:** new `csl/projection.py`.
- **Interface:**
  ```python
  def project_to_acf(matrix: NeuronMatrix, crosswalk: ACFCrosswalk) -> dict[str, LevelEvidence]:
      # for each ACF level, gather the firings of its mapped neurons
      # aggregate into a level-evidence object (control-signal strength + n_eff + CI)
      # returns {C1: LevelEvidence, ..., C7: LevelEvidence}
  ```
- **CRITICAL:** this function takes the ALREADY-COMPUTED matrix. It does NOT call the extractor. One extraction, two aggregations.
- **Acceptance:** on a fixture matrix, projecting yields 7 level-evidence objects; a neuron firing contributes to exactly the levels the crosswalk assigns; non-applicable neurons never contribute.

### 2.2 — Track 1 AI side: displayed-contribution extractor (the orthogonal piece)
- **Goal:** measure what the AI contributed at each ACF level — the only new extraction in Track 1.
- **Files:** new `csl/ai_side_extractor.py`.
- **Interface:**
  ```python
  def extract_ai_contribution(chat: RawChat, crosswalk: ACFCrosswalk) -> dict[str, float]:
      # near-deterministic read of AI turns:
      # at each ACF level, how much did the AI retrieve/generate/structure?
      # returns {C1: float, ..., C7: float}  (C7 ~ 0 by construction: AI cannot orchestrate itself)
  ```
- **Note:** this is the easy extraction — the AI's output is fully displayed; no foundation inference. Keep it deterministic where possible; use the judge only if a level genuinely needs semantic judgment.
- **Acceptance:** C7 AI-contribution is ~0 on all fixtures; the extractor is deterministic on Tier-A-derivable levels; output is a 7-vector.

### 2.3 — Track 1: ownership normalization + CSPC weighting
- **Goal:** combine human and AI sides into per-level ownership percentages.
- **Files:** new `csl/ownership.py`.
- **Interface:**
  ```python
  def compute_ownership(human: dict[str, LevelEvidence],
                        ai: dict[str, float],
                        cspc: CSPCState) -> dict[str, OwnershipResult]:
      # applies the §1.3 formula with π(S_t) from cspc proxies
      # OwnershipResult = {human_pct, ai_pct, ci, n_eff, status}
      # status uses the SAME 4-state enum as the rest of reporting
  ```
- **Acceptance:** output is per-level (7 results), each with a CI; a level with low n_eff returns `INSUFFICIENT_SAMPLE`; a level whose applicability never arose returns `STRUCTURAL_NA`; no level is ever a bare percentage without a denominator and CI.

### 2.4 — Track 2: emergence scanner + judge confirmation
- **Goal:** detect emergence events.
- **Files:** new `csl/emergence.py`, `csl/prompts/emergence_confirm_prompt.txt`.
- **Interface:**
  ```python
  def scan_emergence(chat: RawChat, embeddings: EmbeddingCache) -> list[EmergenceEvent]:
      # sliding window over (AI turn, following human turn(s))
      # test the 3 conditions jointly -> candidates
      # judge-confirm each candidate -> confirmed events
  ```
- **EmergenceEvent schema:** `{ev_id, turn_range, acf_level ∈ {C4,C6}, trigger_type ∈ {HI,AR,BI}, confirmation ∈ {explicit,behavioral,none}, direction_change: bool, output_delta: bool, judge_confirmed: bool}`.
- **Acceptance:** an adoption-only fixture (human just builds on AI) yields ZERO events; a persistence-only fixture (human restates own prior idea) yields ZERO events; a genuine bilateral-fusion fixture yields one BI event at C4 or C6; events never appear at C1/C2.

### 2.5 — Tier-1 derived analytics
- **Goal:** the three buildable-now analytics from §2.6 Tier 1.
- **Files:** new `csl/analytics/flow.py`, `csl/analytics/bottleneck.py`, `csl/analytics/orchestration.py`.
- **Interfaces:**
  ```python
  def cognitive_flow(chat: RawChat) -> FlowGraph:
      # sequence structure: ordered cognitive-move transitions over the event log
  def bottleneck(ownership_history: list[dict[str, OwnershipResult]]) -> BottleneckReport:
      # the consistently-weak ACF level across sessions; TASK-CONDITIONED
  def orchestration_efficiency(chat: RawChat, quality: float) -> OrchestrationResult:
      # prompt-economy vs output quality; MUST carry quality alongside (never standalone)
  ```
- **Do NOT build (Tier 4):** cognitive leverage as a standalone ratio, cognitive diversity as a standalone breadth score. If implemented at all, leverage is gated inside λ × quality and diversity is conditioned on branch-viability — neither is in v3.2 scope.
- **Acceptance:** flow returns a transition graph, not a score; bottleneck refuses to flag a level as a bottleneck when task-context marks the delegation appropriate; orchestration_efficiency raises/refuses if called without a quality argument.

### 2.6 — CSL reporting layer
- **Goal:** the three-panel report, user-friendly, four-state, never-collapse.
- **Files:** new `csl/report.py`, `output/translation.py` (extend).
- **Requirements:**
  - Panel A: per-level H%/AI% **independent** bars (not summing to 100), user-friendly labels only.
  - Panel B: emergence ribbon ABOVE the stack (count, levels, bilateral fraction), with the mandatory MEASURABLE-indicator caveat string.
  - Panel C: ARI capability dot per level, flagging high-ARI / low-H% as the Borrowed-Brilliance signal. **ARI dots NEVER averaged into the bars.**
  - Reuse the four-state enum from Phase 0.3.
- **Acceptance:** the report never shows a bare percentage; ARI and contribution are visibly separate; the four states render distinctly; emergence carries the indicator-not-proof caveat.

---

## PHASE 3 — Validation (gated on corpus / probe)

### 3.1 — Independence test (the partition check)
- **Files:** `csl/validation/independence.py`.
- **Interface:** `independence(ari_scores, csl_shares) -> {per_level_corr, flag_if_near_one}`.
- **Acceptance:** computes the correlation between ARI dimension scores and CSL ownership shares; flags any level whose correlation exceeds the pre-registered threshold (signalling the partition failed and CSL is re-measuring ARI).

### 3.2 — Per-ACF-level ICC certification
- **Files:** extend `calibration/icc.py`.
- **Acceptance:** emits a per-level ICC; only levels meeting the ICC threshold expose ownership as a certified output (others present but flagged `uncertified`). C4 expected clean; C2 expected weakest.

### 3.3 — Predictive-validity registration (when the probe exists)
- Register the §8.3 test: does CSL ownership + emergence rate beat quality-only at predicting Layer 4 retention/transfer? **Cannot run until the probe is deployed** — register now, run later.

---

## CONTINUOUS — The Binding Constraints (no code substitutes for these)

- **C.1 Gold corpus → 60+ with archetype spread (§7.2a quota).** Gates CSL per-level ICC, EC few-shot, EFA, GRM. The single most important non-code task.
- **C.2 Retention probe deployment.** The only wall-crossing instrument. Validates CSL ownership (displayed → genuine), λ, and true synergy. Until deployed, the whole stack is process-description.

---

## The v3.2 "Do NOT" List (cross-cutting guardrails)

1. **Do NOT re-extract the human side of CSL.** Re-project the existing `NeuronMatrix`. Re-extraction re-introduces double-measurement.
2. **Do NOT let CSL modify any ARI score.** CSL is parallel and descriptive. ARI scores are untouched.
3. **Do NOT average ARI capability into CSL contribution bars.** Separate layers, separate panels.
4. **Do NOT use surface attribution (token/word/lexical overlap) as the ownership signal.** Use the §2.4.4 control signals. Surface attribution inverts the twin pair.
5. **Do NOT report a session-level single ownership percentage.** Per-level 7-vector only, with CIs.
6. **Do NOT report emergence as proven synergy.** MEASURABLE indicator only; the caveat string is mandatory.
7. **Do NOT build cognitive leverage or diversity as standalone metrics.** Tier 4 — gated or out of scope.
8. **Do NOT wire either judge-prompt family before the Phase 1.2 human review.** The partition must be confirmed at the prompt level.
9. **Do NOT skip Phase 0.** CSL on a non-deterministic, insecure base inherits both problems.
10. **Do NOT score emergence at C1/C2.** Emergence is structurally impossible below C4 (those are human-checks-AI acts with no fusion).
11. **Do NOT claim CSL cross-validates ARI.** It shares ARI's evidence by construction.
12. **Do NOT populate a "what the human can do without AI" column from chat data.** That is θ; it requires the probe. Ship the H-share trend as a leading indicator only.

---

## Build Order (one line)

```
Phase 0 (fixes: security → determinism → 4-state reporting)
  → Phase 1 (frozen crosswalk → PARTITIONED prompts [STOP-REVIEW] → ownership spec → emergence spec → OSF prereg)
    → Phase 2 (re-projection → AI-side extractor → ownership+CSPC → emergence scanner → Tier-1 analytics → reporting)
      → Phase 3 (independence test → per-level ICC → predictive-validity registration)
        → CONTINUOUS (corpus growth, probe deployment)
```

---

## Repository additions summary

```
chat_classifier/
  config/
    quantile_cuts.json            # NEW (Phase 0.2) — frozen cuts
  telemetry/
    secret_guard.py               # NEW (Phase 0.1)
  extraction/
    judge_replication.py          # NEW (Phase 0.2) — N-replication at boundaries
    prompts/
      ari_competency_prompt.txt    # versioned (Phase 1.2)
  csl/                             # NEW PACKAGE (Phase 1-2)
    acf_crosswalk.yaml             # frozen crosswalk (Phase 1.1)
    SPEC_ownership.md              # (Phase 1.3)
    SPEC_emergence.md              # (Phase 1.4)
    projection.py                  # human side re-projection (Phase 2.1)
    ai_side_extractor.py           # orthogonal AI side (Phase 2.2)
    ownership.py                   # normalization + CSPC (Phase 2.3)
    emergence.py                   # sequence scanner (Phase 2.4)
    report.py                      # 3-panel CSL report (Phase 2.6)
    prompts/
      csl_foundation_prompt.txt    # partitioned CSL prompt (Phase 1.2)
      emergence_confirm_prompt.txt # (Phase 2.4)
    analytics/
      flow.py                      # (Phase 2.5)
      bottleneck.py                # (Phase 2.5)
      orchestration.py             # (Phase 2.5)
    validation/
      independence.py              # partition check (Phase 3.1)
  output/
    report.py                      # extend: 4-state enum (Phase 0.3)
    translation.py                 # extend: CSL user-friendly labels (Phase 2.6)
  calibration/
    icc.py                         # extend: per-ACF-level ICC (Phase 3.2)
  schemas.py                       # extend: MEASUREMENT_SATURATED, CSL schemas
```

---

*End of v3.2 Claude Code Implementation Guide. Phase 0 precedes everything. Phase 1.2 has a mandatory human-review stop. The human side of CSL re-projects existing evidence (no new extraction); only the AI-side extractor and emergence scanner are new measurement. Nothing built here crosses the wall — the retention probe (continuous track) remains the sole validator of synergy and sustainability claims.*
