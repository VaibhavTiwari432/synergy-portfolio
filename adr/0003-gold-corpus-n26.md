# ADR-0003 — Gold regression corpus is n=26, not n=28 (gc-014 / gc-015 rationale-only)

- **Status:** Accepted
- **Date:** 2026-06-12
- **Decider:** Human lead (instruction to Chief Engineer, pre-Phase-0 housekeeping)
- **Context files:** `gold_standard/chats/gc-014.md`, `gold_standard/chats/gc-015.md`, `gold_standard/metadata.json`

## Context

`AGENT_REBUILD_BRIEF_v3.md` describes the regression suite as "the 28 gold chats" and
sets the MAE ratchet (overall ≤ 0.2994) against it. At the `v1-final` tag, inspection
of the committed corpus shows that two of the 28 IDs have **hand-scored rationales but
no machine-readable transcripts**:

| ID | Chat | What exists | What is missing |
|---|---|---|---|
| gc-014 | Jay_ChatGPT1 (HCI exam prep) | `gc-014.md` rationale + `Jay_ChatGPT1.pdf` | `gc-014.json` transcript |
| gc-015 | Pratik_ChatGPT (radar project viva prep) | `gc-015.md` rationale + `Pratik_ChatGPT.pdf` | `gc-015.json` transcript |

`gold_standard/chats_anonymized/` likewise contains 26 JSON files (gc-014 and gc-015
absent). A chat without a JSON transcript cannot be ingested by any adapter, cannot be
materialized into the event log, and therefore cannot contribute to MAE — its human
scores are unusable by the calibration runner regardless of how good they are.

## Decision

1. gc-014 and gc-015 are marked **`rationale_only`** in `gold_standard/metadata.json`.
2. The regression suite — and every reference to "the 28 gold chats" in the brief,
   TEAM.md, and the ratchet gate — is to be read as **n=26** until the missing
   transcripts are recovered.
3. The MAE ratchet target (overall ≤ 0.2994, per-dim ≤ 0.375, EC tracked separately)
   is **unchanged**; it simply applies over 26 chats. The v1.3 baseline was computed
   on the chats that have transcripts, so the ratchet comparison remains like-for-like.
4. The human scores in `gc-014.md` / `gc-015.md` are **preserved, not discarded**. If
   the transcripts are later re-extracted from `Jay_ChatGPT1.pdf` / `Pratik_ChatGPT.pdf`
   (OCR or manual transcription) and pass human review, both chats re-enter the suite
   and this ADR is superseded with the count restored to 28.

## Consequences

- `calibration/gold_loader.py` (rebuild version) must treat `rationale_only` entries as
  excluded — never as zero-score chats (non-negotiable #12: absent ≠ zero).
- Both excluded chats are low-band sessions (per their rationales). Their absence
  slightly thins low-band coverage; note this when reading per-dimension MAE, and
  prioritize their recovery if low-band calibration drifts.
- Any future corpus growth (e.g. the 40+ high-band EC chats per non-negotiable #19)
  counts from 26, not 28.
