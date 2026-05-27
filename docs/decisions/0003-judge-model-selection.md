# ADR 0003 — Judge Model Selection

**Status:** Accepted
**Date:** 2026-05-22
**Deciders:** Sangillence (owner)

---

## Context

The judge service (Phase 1) calls the Anthropic API to score TaskFrames across 8 dimensions. Two model candidates:

- `claude-sonnet-4-6` — ~5× cheaper per token, lower latency
- `claude-opus-4-7` — highest reasoning capability, best edge-case reliability

The scoring workload is not uniform: roughly 80% of student-AI chat turns are routine (unambiguous prompt quality, clear iterative refinement) and 20% are edge cases requiring genuine reasoning depth, particularly on EC (Error Correction / hallucination detection) and CS (Contextual Synthesis), which demand the judge to reason about what the AI said vs. what was correct.

## Decision

**Default judge:** `claude-sonnet-4-6`

**Calibration anchor:** `claude-opus-4-7` — used to score all 23 gold-standard chats during Phase 1 mini-calibration. Opus results define the ceiling for comparison.

**Shipping criterion:** Run mini-calibration with both models against the gold standard. If Sonnet's band-match accuracy (judge band vs. human consensus band) is within **0.3 MAE** of Opus's on the 0–10 normalized scale, ship Sonnet for all dimensions. If Sonnet's gap exceeds 0.3 MAE specifically on EC or CS, route those two dimensions to Opus and use Sonnet for the remaining six.

This hybrid routing is not in the original spec — it is an extension of the model-selection decision approved here.

## Consequences

- `calibration/run_calibration.ts` must run both models and produce a side-by-side comparison report before the shipping decision is finalized.
- The judge service must support a per-dimension model override config so the EC/CS hybrid can be enabled without code changes.
- If Sonnet's MAE gap on EC/CS is > 0.3 but routing to Opus is not cost-acceptable, the fallback is Sonnet for all dimensions with a noted calibration caveat.
- ADR must be revisited when Anthropic releases new model versions that change the cost/capability tradeoff.

## Alternatives considered

**Opus for everything.** Reliable but ~5× the inference cost at production scale. Not justified when most scoring is unambiguous. Rejected.

**Sonnet for everything regardless of calibration gap.** Faster to ship but risks systematic EC misclassification, which corrupts the Parasite/Orchestrator archetype. Rejected.

**Run calibration once on Sonnet only.** Cheaper Phase 1, but leaves no ceiling reference. Rejected — the point of mini-calibration is to know whether Sonnet is good enough, which requires Opus as a reference.
