# ADR 0005 — Chunking Strategy (TaskFrame Boundaries)

**Status:** Accepted
**Date:** 2026-05-22
**Deciders:** Sangillence (owner)

---

## Context

The judge scores TaskFrames, not raw turns. A chunking strategy determines how raw conversation turns are grouped into frames before being sent to the judge.

Two main options were considered:

1. **Fixed window** — every N turns becomes one frame (e.g. every 6 turns). Deterministic and simple.
2. **Goal-boundary detection** — a classifier detects when the user starts a new task/goal and uses that as the frame boundary. Preserves the natural unit of analysis (one reasoning thread = one frame).

## Decision

**Goal-boundary detection with a hard cap of 8 turns per TaskFrame.**

The boundary classifier is a separate lightweight call using `claude-haiku-4-5` to keep cost down. It receives the last 2 turns of the previous frame and the next 2 turns of the candidate new frame and returns a binary `new_goal: boolean` signal. This is not scored — it is purely a segmentation decision.

The 8-turn hard cap prevents pathological frames where a user explores one topic across 20+ turns and receives a diluted, ambiguous score.

**Reasoning against fixed windows:** Iterative Refinement (PR) and Collaborative Agency (CA) are explicitly turn-evolution signals — they require seeing how the user's behavior develops within a single goal context. A 6-turn fixed window will arbitrarily slice a 9-turn refinement sequence in half, making the user appear to abandon refinement when they were actually continuing it. This is a systematic scoring bias against users who engage deeply on single problems.

## Boundary logging requirement

During Phase 1 calibration, all boundary decisions must be logged to `calibration/reports/boundary_decisions_<date>.jsonl` with the format:
```json
{ "chat_id": "gc-001", "turn_index": 6, "new_goal": true, "model": "claude-haiku-4-5", "context_snippet": "..." }
```

This allows auditing whether the boundary detector is consistent across runs (reproducibility check) before trusting the calibration numbers.

## Consequences

- The judge service needs a `chunkTurns(turns: Turn[]) => TaskFrame[]` function that invokes the Haiku boundary classifier.
- The boundary classifier adds one Haiku call per turn pair at frame boundaries, which is cheap (~$0.0003 per call).
- If the boundary detector disagrees with itself across two identical runs on the same chat, the chunking has a reproducibility problem that must be resolved before Phase 1 calibration numbers are trusted.
- Fixed-window chunking should remain as a fallback option in config for debugging, so we can compare frame distributions.
- The 8-turn cap may need adjustment after Phase 1 calibration reveals typical frame lengths. If most naturally-detected frames are 3–4 turns, the cap is irrelevant; if boundary detection often produces 10–12 turn frames, the cap is doing real work and its threshold should be validated.

## Alternatives considered

**Fixed 6-turn window.** Simple and reproducible, but creates systematic bias against deep single-goal conversations. Rejected.

**No cap on goal-boundary frames.** A user who rambles on one topic for 30 turns would produce one huge frame with averaged scores, masking turn-level variation. Rejected.

**Use GPT-4o-mini as boundary classifier.** Would work but adds a cross-provider dependency in the judge service. Haiku is cheaper and keeps the stack single-provider. Rejected.
