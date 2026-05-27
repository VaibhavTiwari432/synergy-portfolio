# Holistic Prompt Decisions — Judge Service

This document records how the judge's holistic scoring prompt evolved across four
versions and why each change was made. It is the audit trail for calibration
decisions on gc-001. Read this before modifying `buildHolisticPrompt()` or the
frame-level scoring prompt in `prompt.ts`.

---

## Background: the mid-bias problem

The judge scores conversations in chunks (frames) and then aggregates frame-level
deltas into a single per-dimension score. Early versions used arithmetic to
aggregate. Arithmetic cannot replicate human holistic judgment because it treats
all signals as additive: one strong low-band frame + one strong high-band frame
= mid, regardless of which pattern dominates the session.

Human annotators apply three rules that arithmetic cannot:

1. **Mixed signal** — dominant pattern wins. One good moment in an otherwise
   passive session is still low.
2. **Absence as signal** — consistent 0.0 scoring with no active high-band
   behavior is low, not mid.
3. **Genuine mid** — reserved for real ambiguity, not mathematical averaging of
   opposing signals.

The holistic pass (v3+) is a single additional LLM call per chat. It receives
structured frame summaries (not raw turns) and applies these three rules. Its
output replaces arithmetic aggregation as the final score. The weighted aggregate
is retained in the report as `aggregate_weighted` for comparison.

---

## v1 — Equal-weight frame aggregation

**Mechanism:** Frame deltas averaged with equal weight regardless of frame size.

**gc-001 result:** All 8 dimensions scored mid. Band accuracy: 29% (2/7).
Within-2-delta: 100%.

**Why it failed:** Two structural problems.

*Mid-bias from equal weighting:* Frame 2 (2 turns) received the same weight as
Frames 0 and 1 (8 turns each). A 2-turn tail with mixed or null signal pulled
every average toward 0.

*No absence-as-signal logic:* Dimensions with consistent 0.0 frame scores (PR,
EC) came out mid instead of low, even though the human annotation was low.

The 100% within-2-delta masked these failures — all errors were ≤1.33 delta
points, so the coarse threshold passed. Band accuracy exposed the real problem.

---

## v2 — Turn-weighted aggregation

**Mechanism:** Frame deltas weighted by turn count. A frame with 8 turns
contributes 8/18 of the total weight; a 2-turn tail contributes 2/18.

**gc-001 result:** AL correctly became not\_applicable (no signal across all
frames). Band accuracy: 29% (2/7). Within-2-delta: 100%.

**Why it still failed:** Turn-weighting fixed the null-handling problem for AL
(all three frames had no AL signal, so the aggregate correctly excluded it). But
it could not fix cross-frame synthesis problems.

*CA remained mid:* Frame 0 = −1.0 (passive, 8 turns), Frame 1 = +1.0 (genuine
pushback, 8 turns). Weighted average: 0.0/mid. Human annotation: low. The human
reads this as "one genuine moment in an otherwise passive session." Arithmetic
reads it as "balanced."

*PR and EC remained mid:* Consistent low-band or null behavior across all frames,
aggregated to mid because 0.0 frames diluted the signal. Human: both low.

Turn-weighting is the correct aggregation method and is still used to produce
`aggregate_weighted` for comparison. But it is not sufficient as the final score.

---

## v3 — Holistic pass added

**Mechanism:** After frame scoring, one additional LLM call receives structured
frame summaries (frame index, turn range, turn count, per-dimension delta/band/
rationale for each frame) and the turn-weighted aggregate. It applies the three
corrective cases and outputs final per-dimension scores with a `reasoning` field.
The holistic result becomes the final score; the weighted aggregate is stored
alongside for comparison.

**gc-001 result:** Band accuracy: 43% (3/7). Within-2-delta: 86%.

**What it got right:**
- CA: weighted=mid → holistic=low ✓ — correctly identified dominant passive
  pattern despite one high-band frame.
- CD: weighted=mid → holistic=low ✓ — same logic.
- ES: weighted=mid → holistic=not\_applicable ✓ — no genuine ethical signal
  across any frame; Frame 0's 0.0 was noise, not evidence.

**What it got wrong:**

*EC over-uplift (weighted=mid → holistic=high, human=low):*
Frame 1 contained the turn "That's correct, but too generic." The frame-level
scorer categorized this as error correction (EC=+1.0). The holistic pass saw one
strong EC signal with no counterevidence and uplifted from mid to high. The human
scored EC=low because "too generic" is editorial dissatisfaction, not detection
of a factual error or hallucination. EC and PR were being conflated.

*CS over-correction (weighted=mid → holistic=low, human=mid):*
Frame 0 = −2.0 (copy-pasting AI output, CS low), Frame 1 = +1.0 (synthesis
pushback, CS high). Same 44%/44% frame structure as CA and CD. The holistic pass
applied Case 1 (dominant pattern = low) to CS the same way it correctly applied
it to CA. But the human calls CS mid because the Frame 1 synthesis turn is
substantive enough to constitute genuine mixed behavior. The v3 prompt gave the
judge no way to distinguish these two cases.

*AL and PR stayed mid despite both being low:*
PR: Frame 0 = −2.0 (very vague prompt), Frame 1 = +1.0 (push for specificity),
Frame 2 = 0.0. The 44%/44% split was treated as Case 3 (genuine mixed). Human:
low — the single refinement turn does not constitute a pattern of strong prompting.

Within-2-delta dropped from 100% (v2) to 86% because EC's error grew to 2.33,
exceeding the 2.0 threshold.

---

## v4 — Three targeted prompt fixes

No architectural changes. Three additions to the holistic prompt text only.

### Fix 1 — EC constraint

Added under "Dimension-specific constraint":

> EC (Error Catching) requires the student to identify factually incorrect,
> logically flawed, or hallucinated content from the AI. Editorial dissatisfaction
> ("too generic", "not specific enough", "I don't like this") is NOT error catching
> — it is prompt refinement (PR). Do not uplift EC for editorial pushback turns.

**Rationale:** The frame-level scorer misclassified "That's correct, but too
generic" as EC=+1.0. The holistic prompt cannot fix that misclassification in the
frame data it receives, but it can prevent the holistic pass from compounding it
into a high-band final score. This constraint fires only on EC and is isolated
from the case logic.

### Fix 2 — Case 1 quantitative threshold

Replaced vague "dominant pattern wins" language with an explicit decision rule:

> Case 1 applies when low-band frames account for ≥60% of scored turn weight AND
> no more than one frame shows genuine high-band signal. When the split is
> ambiguous, examine the frame delta magnitude: a frame scored below −1.5
> represents deeply low behavior that a single +1.0 frame does not neutralize.
> When in doubt between Case 1 and Case 3, prefer Case 1.

**Rationale:** In v3, the judge correctly applied Case 1 to CA and CD but
incorrectly applied Case 3 to AL and PR — even though all four have the same
frame structure (F0=−2.0, F1=+1.0). The ≥60% clause gives a hard trigger for
unambiguous cases. The magnitude fallback handles the ambiguous 44%/44% splits
where frame delta depth matters: a F0=−2.0 is not neutralized by a single +1.0.

### Why the ≥30% Case 3 clause was removed

A first draft of Fix 2 also included: "Case 3 applies only when high-band and
low-band frames each account for ≥30% of scored turn weight."

This was removed before the v4 run because it would have re-broken CA and CD.
For gc-001, CA, CD, and CS all have the same 44%/44% turn-weight split between
their low-band and high-band frames. The ≥30% clause would have forced all three
into Case 3 (genuine mixed → mid), undoing the CA and CD fixes from v3.

The distinction the human is making between CA=low and CS=mid cannot be resolved
by turn-weight thresholds alone — it requires reading the content of the frames.
The magnitude fallback ("a frame scored below −1.5 does not get neutralized by a
single +1.0") guides the judge toward low for deeply negative frames without
mechanically overriding judgment for every 44%/44% split.

---

## Open risk going into the v4 run

**CS may still be pushed to low.**

CS, CA, and CD have structurally similar frame data in gc-001:

| Dim | Frame 0        | Frame 1       | Frame 2       | Human |
|-----|----------------|---------------|---------------|-------|
| CA  | −2.0 (8 turns) | +1.0 (8 turns)| 0.0 (2 turns) | low   |
| CD  | −2.0 (8 turns) | +1.0 (8 turns)| null          | low   |
| CS  | −2.0 (8 turns) | +1.0 (8 turns)| null          | mid   |

The magnitude guidance ("below −1.5 does not get neutralized by +1.0") applies
equally to all three. If the judge reads it mechanically, CS will go low — which
was the v3 regression. If the judge reads the frame rationales and recognizes that
Frame 1's synthesis turn for CS is substantive evidence of genuine mixed behavior,
CS will stay mid.

The `reasoning` field in the v4 output is the diagnostic. It will tell us whether
the judge cited the magnitude rule for CS (mechanically applying it → wrong) or
cited the content of Frame 1 as evidence of genuine mixed behavior (correctly
exercising Case 3 judgment). Read the CS reasoning before drawing conclusions
about the magnitude guidance.

**Secondary risk — AL and PR may still be mid.**

Both have the same 44%/44% split as CA/CD/CS. The magnitude guidance should push
them toward low, but if the judge interprets Frame 1's +1.0 signal as sufficient
to constitute genuine ambiguity, they will remain mid. Human: both low.

The v4 run is the test. No further prompt changes until reasoning text is reviewed.
