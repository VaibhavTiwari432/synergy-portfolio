# ADR 0004 — Two-Pass EC Scoring

**Status:** Accepted
**Date:** 2026-05-22
**Deciders:** Sangillence (owner)

---

## Context

EC (Error Correction) measures whether the user caught AI mistakes, hallucinations, or logical traps. The spec (§6) flagged this as a potential two-pass problem: a user catching an error in turn 3 can only be confirmed as correct if you know what the AI actually said — which may only be verifiable after reading the full conversation.

Single-pass scoring evaluates EC within the TaskFrame window like all other dimensions. The risk: the judge sees a student pushing back on an AI claim but cannot verify whether the AI claim was actually wrong, because verifying that would require broader conversation context.

## Decision

**Yes to two-pass EC scoring.** The implementation is:

1. **Pass 1** (per-frame): Score all 7 non-EC dimensions normally within the TaskFrame window.
2. **Pass 2** (per-chat): Send the full conversation turns plus the Pass 1 scores and re-score EC only. The Pass 2 prompt explicitly tells the judge: "You have the full conversation. Your only task is to score EC. All other scores are final."

The second pass is one additional API call per chat (not per turn), making the cost overhead bounded. At production scale this adds approximately 15–20% to total inference cost.

## Why EC is uniquely load-bearing

EC is the primary distinguishing signal between the Parasite archetype (accepts AI output uncritically) and the Orchestrator archetype (challenges, verifies, corrects). Getting EC wrong systematically means misclassifying the most important archetype boundary in the portfolio. The cost of a second pass is justified by EC's central role in classification correctness.

## Consequences

- The judge service must implement two sequential API calls per scoring job: frame-level Pass 1 then chat-level Pass 2 for EC.
- The `JudgeOutput` schema does not change — EC delta comes from Pass 2 and replaces the Pass 1 EC value before the output is written.
- The judge prompt template (§6) needs two separate prompt variants: one for Pass 1 (7 dimensions, no EC) and one for Pass 2 (EC only, full context).
- `calibration/run_calibration.ts` must run both passes and log Pass 1 EC vs. Pass 2 EC separately so we can quantify the improvement.
- If Pass 2 EC shows negligible improvement over Pass 1 EC on the gold standard, this decision should be revisited to cut cost.

## Alternatives considered

**Single-pass EC.** Simpler, but local context may miss verification signals. Rejected because EC is load-bearing for archetype classification.

**Two passes for all dimensions.** Correct in theory but multiplies cost by ~2×. Most dimensions (PR, CA, CD, AUI) are evaluable locally. Rejected.

**External fact-check call per AI claim.** Would involve grounding the AI's claims against web sources. Expensive, latency-heavy, and introduces a new failure mode. Not in scope for v0.1.
