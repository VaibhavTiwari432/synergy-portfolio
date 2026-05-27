# ADR 0007 — High-Band Rubric Anchor Fix (v0.2)

**Status:** Accepted  
**Date:** 2026-05-24  
**Deciders:** Sangillence (owner)  
**Trigger:** Phase 1 expansion to 23-chat corpus failed Decision Gates 1 (CS 68.2%, threshold 70%) and 2 (PR 73.9%, down from 77.8%). AL also showed a new systematic high-band failure pattern (86.7% → 76.2%) exposed by three new high-synergy chats (gc-024, gc-026, gc-027).

---

## Anchor errors diagnosed

Three error types were identified by reading the judge's holistic reasoning on the failing chats and comparing it to the anchor text the judge was applying.

### Error 1 — Over-specificity (AL, PR, CS)

Each anchor described a single behavioral pattern as the only path to high-band, excluding equally valid high-synergy behaviors that the judge then scored as mid or low.

**AL:** The v0.1 anchor focused exclusively on uncertainty elicitation ("mark anything you're less than confident about with [?]") and factual domain trust calibration. The frame scorer reported "no observable AL behavior" for gc-026 (which opens with a detailed expert role assignment) and "purely philosophical — no active demonstration of AI limitations" for gc-027 (which treats AI accurately as a dialectical reasoning partner). Both behaviors are unambiguously high-band AL but appear nowhere in the v0.1 positive signals.

**PR:** The v0.1 anchor described only formal upfront prompt construction (role + worked example + rejection criteria). gc-027's opening prompt ("Let's play a game: ask me 5 questions one by one and we will identify ethical ways of interacting with an AI") was scored as mid because it "lacks specific constraints" — the structural conversation design pattern was not in the anchor.

**CS:** The v0.1 anchor required explicit verbalization of synthesis ("names which parts are being kept, modified, or discarded and why"). The frame scorer said gc-024 "does not layer their own context in a high-band way" even though Yash caught a specific zero-probability error by processing AI output through his ML knowledge — synthesis visible in the specificity of his next question, not in narrated keep/discard language.

### Error 2 — Negative framing (AL)

The v0.1 AL description framed high-band AL as purely defensive: "works around AI limitations." This caused the judge to look only for limitation-awareness signals (uncertainty elicitation, error avoidance) while missing capability-positive deployment signals (accurate role scoping, deliberate leverage of what AI IS good for).

gc-026's role assignment demonstrates accurate positive calibration — the user knows AI can serve as a strategic consultant for CV framing and structures the interaction accordingly. The judge found "no observable AL behavior" because the anchor gave no positive signal for this pattern.

### Error 3 — Abstraction mismatch (AL)

The v0.1 AL anchor assumed a factual or research task context in every positive signal and example. All three signals mapped to uncertainty elicitation in contexts where AI might produce unreliable factual claims. This made the anchor unrecognizable to the judge in task contexts where the risk is not factual inaccuracy but scope, framing, or reasoning quality: strategic drafting tasks (gc-026), philosophical inquiry tasks (gc-027), domain exam prep (gc-024).

---

## Changes made (rubric v0.2_highband_fix.json)

Only the three high-band anchors were modified. 21 anchors unchanged.

### AL high-band

- **Label changed** from "Actively works around AI limitations in prompt design" to "Accurate, task-calibrated model of AI capability."
- **Description reframed** from defensive (limitation workarounds) to calibration-positive: "the user knows what this AI can usefully contribute in this context and structures their engagement accordingly."
- **Positive signals expanded** from 3 to 3 distinct patterns (replacing the 3 that all covered uncertainty elicitation):
  1. Uncertainty elicitation — retained and tightened
  2. Bounded role assignment — new; covers gc-026 pattern
  3. Accurate reasoning-partner calibration in open-ended tasks — new; covers gc-027 pattern

### PR high-band

- **Label changed** to "Systematically constructed or iteratively precise prompts."
- **Description rewritten** to name three distinct high-band patterns explicitly: upfront specification (A), iterative diagnostic precision (B), structural conversation design (C).
- **Removed** the implicit criterion "first responses are consistently on-target" from the description — this is an outcome metric, not a behavioral marker, and caused the judge to downgrade chats where iterative refinement was the dominant pattern.
- **Positive signals expanded** from 4 to 3 (cleaner):
  1. Upfront construction — retained
  2. Iterative diagnostic precision — new; covers gc-007/017/018 iterative patterns
  3. Structural conversation design — new; covers gc-027 game-framing pattern

### CS high-band

- **Description rewritten** to decouple synthesis from its verbalization: "High-band CS does not require explicit narration of the synthesis process."
- **Positive signals** from 3 to 3 (same count, one replaced):
  1. Explicit synthesis narration — retained
  2. Progressive framework development — new; arc-visible synthesis not requiring work-product modification
  3. Domain-knowledge engagement — new; synthesis detectable from specificity of follow-up, not from keep/discard narration; covers gc-024 zero-probability catch pattern

---

## Calibration result after fix

- Overall within-2-delta: 77.4% → **89.4%** (+12.0 pp)
- Overall MAE: 1.309 → **1.030** (−0.279)
- All 5 Phase 1 decision gates: PASS

| Dim | Pre-fix | Post-fix | Δ pp |
|-----|:-------:|:--------:|:----:|
| AL  | 76.2%   | 87.0%    | +10.8 |
| PR  | 73.9%   | 87.0%    | +13.1 |
| CS  | 68.2%   | 91.3%    | +23.1 |
| AUI | 78.3%   | 95.7%    | +17.4 |
| CA  | 78.3%   | 87.0%    | +8.7  |

---

## Residual risk: gc-016

gc-016 (all-high human annotation) remains resistant at 5 dimension failures in both runs. The judge consistently scores a highly capable chat as low-band. This is a known outlier — it was resistant in the original 18-chat run and remains so after the rubric fix. It is not actionable from rubric changes alone; the issue is that gc-016's first frame (an image-generation request the AI could not fulfill) sets a strong Case 1 anchor the holistic pass does not override. Flagged for Phase 2 review.

## Residual risk: PR in gc-007

PR in gc-007 failed in all three runs (baseline, expanded, B.1). The judge consistently scores early prompts as vague and applies Case 1. The PR high-band fix expanded iterative-precision as a pattern but gc-007's frame structure (one vague early frame, later refinement) still triggers Case 1 dominant-low logic. Flagged for Phase 2 review alongside gc-016.
