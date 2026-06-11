# ADR 0001 — Delta-Band Encoding for DimensionScore

**Status:** Accepted
**Date:** 2026-05-20
**Deciders:** Sangillence (owner), Claude Code (implementation)

---

## Context

The judge must produce a per-dimension quality signal for each TaskFrame. The original schema used integer scores 1–5 with a flat `scores: Record<DimensionCode, number>` map. Three problems with that design:

1. **No within-band precision.** Scores 1 and 2 both map to "low" band, but an LLM judge can meaningfully distinguish a strong-low from a weak-low. Collapsing to integers loses that signal.
2. **Inconsistent (score, band) pairs.** If the judge outputs both a numeric score and a band label independently, they can disagree. That inconsistency is a silent bug with no natural validation point.
3. **No first-class not_applicable state.** ES (Ethics Sensitivity) cannot be scored when no ethical content is present. Using 0 as a sentinel is ambiguous; null-per-dimension required adding a separate flag array.

## Decision

Replace integer scores with a real-valued **delta** in [−2.0, +2.0] per dimension. Derive **band** server-side from delta using fixed thresholds. Use `null` to represent `not_applicable`.

**Thresholds (BAND_THRESHOLDS in §3):**
- `delta <= -0.67` → band `"low"`
- `-0.67 < delta < +0.67` → band `"mid"`
- `delta >= +0.67` → band `"high"`
- `delta = null` → band `"not_applicable"`

**Why ±0.67:** Divides the [-2, +2] range into three equal-width zones of ~1.33 each. Symmetric, no bias toward any band.

**Why server-derives band:** The judge outputs only `delta`. Band is computed at validation time and stored. This eliminates the class of bug where judge output contains inconsistent (delta, band) pairs. The judge has one continuous value to calibrate; the server handles categorical derivation.

**Why `null` not `0.0` for not_applicable:** A forced `0.0` for not_applicable is arithmetically ambiguous — it would be included in mean(delta) calculations and pull portfolio scores toward 0. `null` is explicitly excluded from aggregation. Every consumer of `DimensionScore.delta` that does arithmetic must handle null, which is a forcing function for correct implementation.

**Score normalization in Portfolio:** `mean(delta over applicable frames) → [-2, +2]`. Normalized to 0–10 via `(mean_delta + 2) × 2.5`.

## Consequences

- The judge prompt (§6) must instruct the judge to produce real-valued delta and explicitly not produce band.
- The server validation layer must derive and store band from delta immediately after receiving judge output.
- `GoldChat` annotations use band labels directly (not delta) since human scorers work at band granularity.
- Calibration compares judge band (derived from delta) against human consensus band — not numeric comparison.
- `MIN_FRAMES_FOR_ARCHETYPE` constant is affected: with continuous delta, fewer frames may be needed to get a stable mean. See §11, item 6 (OPEN).

## Alternatives considered

**Keep integer 1–5 scores.** Simpler but loses within-band precision and doesn't solve the inconsistent-pair problem.

**Let judge output both delta and band.** Adds validation complexity and creates the inconsistency-pair bug. Rejected.

**Use integer sentinel (0) for not_applicable.** Ambiguous in aggregation, fails silently. Rejected.
