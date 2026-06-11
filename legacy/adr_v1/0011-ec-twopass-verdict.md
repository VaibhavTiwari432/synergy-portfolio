# ADR 0011 — EC Two-Pass Verdict: Not Beneficial

**Status:** Accepted  
**Date:** 2026-05-24  
**Deciders:** Sangillence (owner)  
**Report:** `calibration/reports/phase1_ec_twopass.json`

---

## Summary

EC two-pass scoring (ADR 0004) was implemented and tested against the 23-chat Phase 1 corpus using rubric v0.2_highband_fix. The result was a significant regression. EC two-pass is not deployed.

---

## Results

| Metric | Single-pass (Phase 1 final) | EC two-pass | Delta |
|--------|:-----------:|:------------:|:-----:|
| EC within-2-delta | 89.5% | 73.7% | **−15.8 pp** |
| EC MAE | 0.930 | 1.158 | +0.228 |
| Overall within-2-delta | 89.4% | 86.8% | −2.6 pp |
| Overall MAE | 1.030 | 1.060 | +0.030 |

The EC improvement threshold per ADR 0004 was +3 pp. The actual change was −15.8 pp — a regression, not an improvement.

---

## Why EC two-pass regressed

Three factors explain the result:

**1. Holistic pass already provides full-context EC correction.**

The single-pass holistic prompt already sees all per-frame EC scores and applies explicit EC-specific guidance: "EC requires identifying factually incorrect, logically flawed, or hallucinated content — editorial dissatisfaction is NOT EC." The holistic pass operates on the full frame evidence set and can make corrective judgments (Case 1/2/3 logic). EC two-pass adds a separate call that pre-empts the holistic, but the holistic was already doing the full-context work.

**2. Replacing per-frame EC with a uniform chat-level score degrades the holistic input.**

When EC two-pass runs, its single EC score is replicated to every frame output. The holistic judge then sees identical EC values across all frames — a signal that normally indicates "zero variance / low confidence" rather than "chat-level judgment." This is structurally misleading: the holistic judge cannot apply its mixed-signal (Case 1/3) logic when all frame EC values are identical.

**3. The EC two-pass prompt lacks the holistic corrective cases.**

The EC two-pass prompt scores EC from the full conversation but without the three-case corrective framework from the holistic prompt. It asks for a direct EC judgment without guidance about when to commit to Case 1 vs. Case 3. The holistic prompt's constraint ("if your delta is −0.5 but your reasoning says low dominates, that is a contradiction — commit to Case 1") is absent, producing softer EC scores that regress toward mid-band.

---

## Decision

EC two-pass is not deployed. The `ec_two_pass` feature flag remains available in `JudgeConfig` for future experiments but is `false` (default) in production.

The single-pass + holistic architecture already handles EC with full conversational context via the holistic pass. No further EC-specific intervention is needed at Phase 1 corpus size.

---

## Alternatives not retried

**EC-only holistic correction (no frame replacement):** Instead of replacing EC in frame outputs, pass the EC two-pass score only to the holistic prompt as a supplemental input. This would preserve frame EC variance for Case 1/3 logic. Not tested — the regression was large enough to warrant reconsidering the premise rather than tuning the approach.

**EC-aware holistic constraint strengthening:** Strengthen the EC-specific constraint in the existing holistic prompt. Lower-cost than a second API call and consistent with how AL/PR/CS calibration improved in Phase 1 (rubric anchors, not additional passes). Recommended direction if EC calibration degrades in Phase 2.
