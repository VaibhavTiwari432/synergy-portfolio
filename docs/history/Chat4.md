# Chat4 — Framework Metrical Breakdown (4 Scored Sessions)

**Generated:** 2026-06-26  
**Subject:** `testing_102` | **Model:** GPT-5-5 (openai, era 2026-06) | **Framework:** SAF/ARI v3.22  
**Tier:** 2 (Transcript-only — no in-session probes, no longitudinal history)  
**Rung authority:** MEASURABLE on all live dims; DESIGNED on CSL ownership (ICC pending)

---

## Session Overview

| | Chat-1 | Chat-2 | Chat-3 | Chat-4 |
|---|---|---|---|---|
| **Captured at** | 00:14 | 00:12 | 00:06 | 00:02 |
| **Turns** | 294 | 294 | 294 | 294 |
| **Status** | scored | scored | scored | scored |
| **Session intent** | explore (0.886) | explore (0.886) | explore (0.886) | explore (0.886) |
| **Composite** | **0.9325** | **0.8674** | **0.9301** | **0.9294** |
| **CI** | [0.882 – 0.975] | [0.777 – 0.953] | [0.882 – 0.966] | [0.889 – 0.968] |
| **Rung** | MEASURABLE | MEASURABLE | MEASURABLE | MEASURABLE |

> **Note on identical turn counts and QQ/regime:** All 4 sessions were scored from the same underlying 294-turn corpus (same capture, different scoring runs). Variability in composite and dim values reflects judge stochasticity across runs, not different transcripts. This is a calibration-mode observation, not a multi-session longitudinal signal.

---

## 1. Composite Score

```
Chat-1:  0.9325  ████████████████████░  CI [0.882 – 0.975]
Chat-2:  0.8674  ████████████████░░░░░  CI [0.777 – 0.953]
Chat-3:  0.9301  ████████████████████░  CI [0.882 – 0.966]
Chat-4:  0.9294  ████████████████████░  CI [0.889 – 0.968]
```

Chat-2 scores ~0.065 below the others — the driver is a depressed CD (Cognitive Depth) at 0.55 vs 0.85–0.94 across the other three. This is the primary source of cross-run variance.

---

## 2. Eight-Dimension Profile

**Dimension key:**
- **AL** — Active Learning
- **CA** — Cognitive Autonomy
- **CD** — Cognitive Depth
- **CS** — Cognitive Steering
- **EC** — Epistemic Calibration
- **ES** — Exploratory Safety *(structural N/A — no applicable events)*
- **PR** — Productive Reasoning
- **AUI** — AI Use Intelligence

### 2.1 Dimension values with CI and n_eff

| Dim | Chat-1 | CI | Chat-2 | CI | Chat-3 | CI | Chat-4 | CI | n_eff | Status notes |
|-----|--------|-----|--------|-----|--------|-----|--------|-----|-------|-------------|
| AL | 0.9200 | [0.855–0.985] | 0.8800 | [0.801–0.960] | 0.9200 | [0.841–1.000] | 0.9200 | [0.865–0.975] | 140 | OK |
| CA | — | — | 0.9300 | [0.865–0.995] | — | — | — | — | 140 | MEASUREMENT_SATURATED (1,3,4); OK (2) |
| CD | 0.9200 | [0.855–0.985] | 0.5500 | [0.397–0.704] | 0.8500 | [0.746–0.954] | 0.9400 | [0.885–0.995] | 140 | OK — high variance across runs |
| CS | 0.9000 | [0.835–0.965] | 0.9200 | [0.841–1.000] | — | — | — | — | 140 | SATURATED (3,4); OK (1,2) |
| EC | 0.9600 | [0.896–1.000] | 0.9500 | [0.886–1.000] | 0.9800 | [0.917–1.000] | 0.9500 | [0.895–1.000] | 140 | OK — ec_low_calibration_confidence flagged all |
| ES | — | — | — | — | — | — | — | — | 0 | N/A — no applicable events in session |
| PR | 0.9100 | [0.845–0.975] | 0.8500 | [0.746–0.954] | 0.8800 | [0.801–0.960] | 0.9000 | [0.845–0.955] | 140 | OK |
| AUI | — | — | 0.9000 | [0.821–0.980] | — | — | 0.9000 | [0.845–0.955] | 140 | SATURATED (1,3); OK (2,4) |

**Flags present on all dims:** `state_conditioned_precision` — CI widths are precision-adjusted for estimated CSPC state. Not a validity concern; expected at Tier 2.

**EC-specific:** `ec_low_calibration_confidence` on all four runs. EC MAE = 0.41 (MISS at v1.3 calibration). EC scores are reported but carry reduced inferential weight. Do not use EC as a standalone gate.

**MEASUREMENT_SATURATED dims:** CA, CS, AUI hit the saturation ceiling on some runs — the judge fired the maximum possible neurons for those dimensions; no value is emitted to avoid false-precision at the top. This is expected behaviour for a high-engagement exploration session, not a failure.

---

## 3. Regime Overlay (CSPC State Strip)

Identical across all 4 runs — the regime is computed from the transcript structure, not judge stochasticity.

| Regime | Occupancy | Run lengths |
|--------|-----------|-------------|
| **drift** | **87.1%** | max=31, mean≈6.9 turns |
| **extractive** | **6.4%** | 9 runs, all length 1 |
| **generative** | **6.4%** | 9 runs, all length 1 |

**Interpretation:**
- Drift-dominant at 87% is typical for long exploration sessions — the user is consuming and following AI output without frequent pivots or steering events.
- Extractive and generative runs occur at equal rates (~6.4% each), both as single-turn bursts. No sustained generative or extractive phase.
- No `surrender` states — CSPC overlay is rules-only as required.
- `r_steer = 0.1338` (13.4% of total time was steered-out). `t_steered_out = 41,584` turns of token context were spent in steered-out windows.

---

## 4. Cognitive Scaffolding Ladder (CSL)

### 4.1 Ownership breakdown (human vs AI contribution share)

CSL rung = DESIGNED (ICC uncertified, pending inter-rater reliability study). Values are transcript observations, not capability measures.

| Level | Label | Human % | AI % | n_eff | Borrowed Brilliance | Status |
|-------|-------|---------|------|-------|---------------------|--------|
| **C1** | Knowledge Sourcing | 0.0% | 100.0% | 16 | ⚠ Yes | OK |
| **C2** | Sense-Making | 42.0% | 58.0% | 35 | No | OK |
| **C3** | Direction & Checking | 14.6% | 85.4% | 330 | ⚠ Yes | OK |
| **C4** | Problem Framing | 18.5% | 81.5% | 140 | ⚠ Yes | OK |
| **C5** | Quality Judging | N/A | N/A | 0 | — | N/A — did not arise |
| **C6** | Original Making | 18.8% | 81.2% | 280 | ⚠ Yes | OK |
| **C7** | Partnership Steering | N/A | N/A | 0 | — | N/A — did not arise |

*Identical across all 4 runs (CSL is deterministic from the transcript.)*

**Borrowed Brilliance flags (C1, C3, C4, C6):** The user scores well at these levels but the AI visibly carried the majority of the work. A high score at a BB-flagged level reflects the AI's output quality, not demonstrated human capability at that level. Follow-up unaided tasks are the correct instrument to separate contribution from ability.

### 4.2 Emergence

| | Count |
|-|-------|
| Candidate emergence events | 4 |
| Reportable emergence events | 0 |

4 candidate events were detected but none crossed the reportable threshold. No bilateral formulations in this session that neither party was approaching independently.

---

## 5. Question Quality (QQ)

Identical across all 4 runs (deterministic from transcript). Based on 140 user turns.

### 5.1 Aggregate metrics

| Metric | Value |
|--------|-------|
| User turns scored | 140 |
| Average EIG proxy | 0.2979 |
| Average specificity | 0.1538 |

EIG proxy = estimated information gain; specificity = lexical precision of the question. Both sit in the low-moderate range, consistent with a concept-completion dominant explore session.

### 5.2 Bloom's Taxonomy distribution

| Bloom Tier | Label | Count | % |
|-----------|-------|-------|---|
| 1 | Remember | 18 | 12.9% |
| **2** | **Understand** | **99** | **70.7%** | ← dominant
| 3 | Apply | 4 | 2.9% |
| 4 | Analyze | 8 | 5.7% |
| 5 | Evaluate | 4 | 2.9% |
| 6 | Create | 7 | 5.0% |

Tier 2 (Understand) dominates at 71%. The session is comprehension-oriented — the user is primarily asking the AI to explain, clarify, and define. Higher-order tiers (4–6: Analyze, Evaluate, Create) account for 13.6% combined.

### 5.3 Graesser question-type distribution

| Type | Count | % |
|------|-------|---|
| **concept_completion** | 118 | 84.3% | ← dominant
| causal_antecedent | 8 | 5.7% |
| judgmental | 4 | 2.9% |
| instrumental_procedural | 3 | 2.1% |
| definition | 2 | 1.4% |
| verification | 2 | 1.4% |
| example | 1 | 0.7% |
| expectational | 1 | 0.7% |
| disjunctive | 1 | 0.7% |

Concept-completion questions ("what is X?", "how does X work?") at 84% confirm the exploration/comprehension profile. Causal antecedent ("why did X happen?") at 5.7% is the strongest higher-order signal present.

---

## 6. Reliance Metrics

Identical across all 4 runs (deterministic).

| Metric | Value | Note |
|--------|-------|------|
| Weight of Advice (WoA) | 0.0 | Proxy from adopt/override intent tags |
| Switch fraction | 0.0 | Fraction of episodes where user switched from own answer to AI |
| Episodes (hold) | 2 | User held their own position |
| Episodes (adopt) | 0 | No AI-answer adoptions detected |
| Episodes (verify) | 0 | No verification episodes |
| Appropriate reliance | N/A | Requires ground-truth correctness — not available from transcript alone |

**Interpretation:** WoA = 0 and switch fraction = 0 with 2 hold episodes means the user maintained independent positions on the 2 detected episodes. Low episode count (2 of 140 turns) means the reliance signal is structurally sparse for this session type — consistent with a consumption-mode explore chat where the user is not in an adopt/override decision loop.

---

## 7. Neuron Firings

8 neurons fired per run, across 3 dimensions. All 4 runs produced identical firing patterns.

| Dimension | Fired neurons | Count | Avg value |
|-----------|--------------|-------|-----------|
| AL | AL-08 | 1 | 0.0 |
| EC | EC-06, EC-07, EC-09 | 3 | 0.3454 |
| PR | PR-02, PR-05, PR-07, PR-14 | 4 | 0.1357 |

**AL-08** (value=0.0): Fired but at floor — indicates the applicable condition was detected but the evidence did not meet the threshold for positive contribution.  
**EC-06/07/09**: Three epistemic calibration neurons active; mid-range average (0.35). EC neurons directly feed the EC dim value but carry the `ec_low_calibration_confidence` caveat.  
**PR-02/05/07/14**: Four productive reasoning neurons, low average (0.14). PR = 0.88–0.91 across runs despite low per-neuron values — the aggregate is accumulated across many opportunities (n_eff=140).

---

## 8. Sustainability

Identical across all 4 runs — sustainability is a longitudinal signal, not per-judge-run.

| Signal | Value | Rung |
|--------|-------|------|
| Cognitive Debt EWMA | N/A | MEASURABLE |
| Debt mode | INSUFFICIENT_HISTORY | — |
| Sessions in history | 1 | — |
| Lambda (long-run trend) | N/A | DESIGNED |
| r_steer | 0.1338 | — |
| t_steered_out | 41,584 tokens | — |

Single-session — all longitudinal sustainability signals require ≥2 sessions. Debt EWMA and lambda are structurally N/A until cross-session corpus exists.

---

## 9. Flags Summary

| Flag | Chat-1 | Chat-2 | Chat-3 | Chat-4 | Meaning |
|------|--------|--------|--------|--------|---------|
| `ec_low_calibration_confidence` | ✓ | ✓ | ✓ | ✓ | EC MAE=0.41 at v1.3 — reduce inferential weight on EC |
| `state_conditioned_precision` | ✓ | ✓ | ✓ | ✓ | CI widths precision-adjusted for CSPC state — expected at Tier 2 |
| `debt_flag` | — | — | — | — | No cognitive debt signal |
| `theater_counter` | 0 | 0 | 0 | 0 | No accept-without-challenge runs detected |
| `accept_run_max` | 0 | 0 | 0 | 0 | No consecutive accept runs |
| `fluent_incompetence` | — | — | — | — | Not triggered |
| `judge_family_conflict` | false | false | false | false | Gemini judge, OpenAI partner — correct family separation |

---

## 10. Cross-Run Variance Analysis

All 4 sessions are the same transcript scored independently. Variance reflects judge stochasticity, not behavioural change.

| Dim | Min | Max | Range | Stability |
|-----|-----|-----|-------|-----------|
| Composite | 0.8674 | 0.9325 | 0.065 | Moderate — CD drives this |
| AL | 0.88 | 0.92 | 0.04 | Stable |
| CD | 0.55 | 0.94 | **0.39** | High variance — most sensitive dim |
| EC | 0.95 | 0.98 | 0.03 | Very stable |
| PR | 0.85 | 0.91 | 0.06 | Stable |

**CD is the high-variance outlier** (range 0.39). This is consistent with EC's known low calibration confidence — CD is adjacent to EC in the scoring graph and shares some evidence turns. The CD result in Chat-2 (0.55) should be treated as an outlier run; the modal CD estimate across runs is 0.88–0.94.

---

## 11. Interpretation Summary

**What the data says (rung: MEASURABLE, Tier 2):**

1. **High composite, stable across 3 of 4 runs** — 0.929–0.933 is a consistent signal. Chat-2's lower composite (0.867) is attributable to a single high-variance CD run and does not change the overall picture.

2. **Exploration-mode session** — intent=explore at 0.886 confidence, Bloom tier 2 dominant (71%), concept-completion questions at 84%. The user is in a learning/comprehension posture, not a creation or problem-solving posture.

3. **High AI contribution share at C1, C3, C4, C6** — Borrowed Brilliance flags at 4 of 5 active CSL levels. The session produced good outcomes but AI carried the majority of the cognitive work at each level. Not a concern in isolation; becomes one if this is the consistent pattern across sessions.

4. **Drift-dominant regime (87%)** — consistent with the exploration posture. No sustained generative or extractive phases. The user is following the AI's output more than steering it.

5. **Reliance signal sparse** — 2 episodes detected, WoA=0. Too few episodes to characterise reliance pattern; this session type does not generate the adopt/override decisions the reliance metric requires.

6. **No sustainability signal yet** — single session; longitudinal gates require ≥2 sessions before any trend claims are valid.

7. **EC flagged but not invalid** — EC scores (0.95–0.98) are present and reported. Low calibration confidence means treat with caution, not discard. The fix path is 40+ high-band gold chats (spec §EC data-gate).

---

*All claims carry rung: MEASURABLE or DESIGNED as annotated. Nothing in this document is presented above its rung. CSL ownership values are transcript observations, not ability measures. Sustainability is N/A pending multi-session corpus.*
