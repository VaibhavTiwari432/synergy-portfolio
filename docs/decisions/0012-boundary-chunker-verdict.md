# ADR 0012 — Goal-Boundary Chunker Verdict: Not Beneficial

**Status:** Accepted  
**Date:** 2026-05-25  
**Deciders:** Sangillence (owner)  
**Report:** `calibration/reports/phase1_boundary_chunker.json`

---

## Summary

The goal-boundary chunker (ADR 0005) was implemented and tested against the 23-chat Phase 1 corpus using rubric v0.2_highband_fix and Gemini 2.5-flash as both the boundary classifier and the main judge. The result was a regression exceeding the 3 pp safety threshold. The boundary chunker is not deployed.

---

## Results

| Metric | Baseline (fixed 8-turn cap) | Boundary chunker | Delta |
|--------|:-----------:|:----------------:|:-----:|
| Overall within-2-delta | 89.4% | 84.9% | **−4.5 pp** |
| Overall MAE | 1.030 | 1.105 | +0.075 |
| EC within-2-delta | 89.5% | 70.0% | **−19.5 pp** |
| CS within-2-delta | 91.3% | 81.8% | **−9.5 pp** |
| CA within-2-delta | 87.0% | 78.3% | **−8.7 pp** |

The deployment safety gate was −3 pp overall. The actual change was −4.5 pp overall, with EC regressing −19.5 pp — far outside the allowed range.

### Full per-dimension comparison

| Dim | Baseline | Boundary chunker | Delta | n (chunker) |
|-----|:--------:|:----------------:|:-----:|:-----------:|
| AL  | 87.0%    | 91.3%            | +4.3 pp | 23 |
| PR  | 87.0%    | 87.0%            | 0 pp    | 23 |
| AUI | 95.7%    | 91.3%            | −4.4 pp | 23 |
| EC  | 89.5%    | 70.0%            | **−19.5 pp** | 20 |
| CS  | 91.3%    | 81.8%            | **−9.5 pp**  | 22 |
| CD  | 90.9%    | 90.5%            | −0.4 pp | 21 |
| ES  | 75.0%    | 100.0%           | +25.0 pp | 4 (unreliable, n<5) |
| CA  | 87.0%    | 78.3%            | **−8.7 pp**  | 23 |

AL, PR, and CD are unaffected or marginally positive. The regressions are concentrated in EC, CS, and CA — exactly the three dimensions that require cross-frame context.

---

## Why the boundary chunker regressed

The root cause is the same mechanism identified in ADR 0011 for EC two-pass: **reducing the holistic pass's full-conversation visibility degrades its ability to score dimensions that require inter-frame context.**

**1. EC requires full conversational scope to detect error-catching patterns.**

EC is scored on whether the user caught, called out, or corrected factual errors or hallucinations in the AI's outputs. These behaviors emerge across multiple turns and often across what natural-topic boundaries would classify as separate goals. When the boundary chunker splits on topic transitions, a user's error-catching turn in frame N+1 is scored independently from the AI error in frame N. The holistic pass cannot bridge the gap — it only sees frames within a single window.

**2. CS depends on synthesis that spans goal transitions.**

Conversation synthesis (CS) measures whether the user meaningfully integrated AI outputs, built on them, and directed the conversation toward a coherent outcome. Synthesis behaviors frequently span multiple topics — the user circles back, compares, or redirects. Boundary splits interrupt these arcs before the holistic pass can observe them.

**3. CA is longitudinal across the conversation.**

Cognitive agency (CA) measures sustained initiative-taking over the full conversation. Short frames created by natural-boundary splits fragment the longitudinal view the holistic judge relies on to distinguish a user who consistently drives the conversation from one who defers to the AI.

**4. The mechanism is identical to ADR 0011.**

EC two-pass replaced per-frame EC with a uniform chat-level score, degrading holistic input. The boundary chunker splits conversations into shorter windows, reducing the inter-frame diversity the holistic pass uses for Case 1/2/3 reasoning. Both changes attacked the same invariant: *the holistic pass requires full-conversation evidence to make cross-frame corrections.*

---

## Decision

The goal-boundary chunker is not deployed. `use_boundary_chunker` remains `false` (default) in production `JudgeConfig`.

The 8-turn hard-cap chunker remains the production chunking strategy. Hard-cap splits are handled by the holistic pass's aggregation logic, which was designed and calibrated for this window size.

---

## Alternatives not retried

**Boundary chunker with holistic pass spanning all frames (no window isolation):** The current architecture runs one holistic pass per chunk-window. A modified architecture could run a single global holistic pass regardless of how many boundary-split frames exist. This would preserve full-conversation visibility. Not tested — requires architectural changes to the holistic pass and re-calibration of the full corpus.

**Boundary chunker gated on conversation length:** Only apply boundary chunking to conversations with more than N turns (where a single 8-turn window is insufficient). For the Phase 1 corpus, most chats are ≤16 turns, making this moot. Revisit if Phase 2 corpus includes significantly longer conversations.
