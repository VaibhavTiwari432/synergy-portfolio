# Gold Standard Chat Transcripts

This directory contains the 20 hand-scored chat transcripts used to calibrate the Synergy judge.

## Format

Each file in `chats/` is a JSON object conforming to the `GoldChat` schema (defined in `packages/schemas`). It contains:

- The raw chat transcript (user + AI turns)
- Human-assigned scores for all 8 dimensions (AL, PR, AUI, EC, CS, CD, ES, CA), each 1–5
- Scorer notes explaining the rationale for each score

## Status

Target: 20 transcripts before Phase 1 begins.

Current count: 0 / 20

## Scoring instructions

See spec §4 for rubric anchors. For each dimension, pick the band (1–2 / 3 / 4–5) that best fits, then assign the specific integer. Record your reasoning in `scorer_notes`.

Do not score synthetically. Every transcript here must reflect a real human's judgment, not a model's.
