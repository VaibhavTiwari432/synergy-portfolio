# ADR-0009 — Judge non-determinism protocol: stratified N-replication at the composite-binding boundary

- **Status:** Accepted
- **Date:** 2026-06-19
- **Decider:** Chief Engineer; boundary definition + N/band confirmed by project lead
- **Implements:** SAF/ARI v3 P2 (`SAF_ARI_v3_ClaudeCode_Upgrades.md` §P2 / spec V2,
  §A2). Also closes the only live determinism gap from the Phase-0.2 investigation
  ("0.2-TierC") — recorded in DISCREPANCY D-017/D-018 (the other Tier sub-items are
  N/A here).
- **Scope guard:** this lands the wrapper + boundary detector **dormant** (a
  self-contained module under `src/trait/judge/`, not wired into the live scoring
  pipeline). Batch enablement is a separate step gated on human review of N + band
  (the brief's mandatory STOP-for-human-review on those two knobs).

## Context — the judge is not deterministic, and pretending otherwise flips reports

The Gemini judge runs at `temperature=0.1` (not 0) with no seed parameter; the same
chat scored twice can return different per-dimension scores. Field-standard practice
(spec §A2 / V2) is not to fake determinism but to **bound and report the variance**,
and to spend replication budget only where that variance can actually change a
reported decision — "stratified re-judging", not blanket N-replication.

## The architectural problem this build poses

The spec frames the boundary as a **synergy–sustainability quadrant boundary** and
suggests "within ±X of a gate value". **Neither maps to this Scope-B build:**

1. There is **no quadrant** and no synergy-plane assignment materialized — by design
   ("synergy" never appears in Tier-1 output, #4; never claim true synergy from a
   transcript, #3; no leaderboard/bare composite, #6). The headline is a single
   **softmin composite** (`src/aggregate/softmin.py`) plus per-dimension values.
2. The decision **gates** that exist (`scorability`, `n_eff ≥ τ`) are **count-based**
   and unaffected by judge-score variance, so "±0.05 of a gate value" has no target.

So "boundary" had to be re-grounded in the real decision surface, not copied
literally. That re-grounding is the substance of this ADR.

## Decision

### 1. Boundary = the composite-binding, mid-range / low-confidence set

The softmin composite is dominated by its **weakest** dimension(s); only their
variance moves the headline. So a session is a **re-judge candidate** iff, on the
first pass, **any composite-binding dimension is genuinely ambiguous.** Concretely
(all over the judge's per-dimension output, which already carries `score` and
`confidence`):

- **Binding set** = applicable dimensions whose first-pass `score` is within
  `bind_margin` of the minimum applicable score (a judge-time proxy for the softmin
  argmin set — documented as a proxy, since softmin runs on post-merge values).
- **Ambiguous** = a binding dimension is mid-scale (`|score − 0.5| ≤ band`, where
  ordinal uncertainty is highest) **or** low-confidence (`confidence < conf_floor`).

If any binding dimension is ambiguous → re-judge the session `N` times total and
report **per-dimension mean ± SD**; otherwise score once. Interior (clear-cut)
sessions cost one judge call, exactly as today.

Rejected alternatives: **proximity-to-declared-band-edges** (introduces categorical
cuts this build deliberately avoids — a leaderboard-shaped artifact); **blanket
N-replication** (N× cost on clear-cut sessions — the waste stratification exists to
avoid; retained only as an explicit calibration-only mode).

### 2. Parameters (config-tunable; the human-review knobs)

- `N = 5` replications on boundary sessions.
- `band = 0.10` (mid-range half-width → ambiguous score ∈ [0.40, 0.60]).
- `bind_margin = 0.10` (within 0.10 of the min judge score counts as binding).
- `conf_floor = 0.50` (below this, the judge's own confidence triggers re-judge).

These are defaults, not constants frozen against change — but they are **not**
silently picked by the implementation: they live in one config block and any change
is a reviewable diff. Enabling re-judging in batch requires sign-off on N + band.

### 3. The decision-relevant reliability number

Alongside per-dimension mean ± SD, report the **binding-flip rate**: across the N
replications, how often the argmin (the dimension that binds the composite) changes.
This is the no-quadrant analogue of the spec's "quadrant flip rate" — the number that
says how stable the headline-determining decision is under judge stochasticity. It
later feeds the §A1 G-study (judge-replication facet) when that runs.

### 4. Provenance

Every replicated result carries the `judge_config` (model id, family, prompt version,
temperature) so a later drift analysis (v3 V10) can attribute a shift to a judge
version. `JudgeOutput` already pins model/family/prompt_version; the wrapper records
them plus the sampling params.

### 5. Dormant until wired

The wrapper does not change `ScoreResponse` and is not called by `src/api/pipeline.py`
yet. Wiring mean±SD into the live report (as widened CIs, per #2 — precision not
value) is a downstream change made only after the N/band review. Until then this is a
tested, callable module with zero effect on shipped scores.

## Consequences

- Trustworthy variance bounds become available where they matter, at ~1 extra judge
  call only on genuinely ambiguous sessions.
- The boundary is honest about the architecture: it resolves the variance that moves
  *this build's* headline (softmin), not a quadrant this build does not compute.
- The G-study (P3, data-gated) inherits a ready judge-replication facet and flip-rate.
