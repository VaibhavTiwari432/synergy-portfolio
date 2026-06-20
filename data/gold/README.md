# Gold Standard Chat Transcripts

This directory contains the hand-scored chat transcripts used to calibrate the Synergy judge.

## Format

Each `gc-*.json` file in `chats/` is a JSON object conforming to the `GoldChat` schema defined in `packages/schemas`. It contains:

- Chat metadata and transcript turns
- Human-assigned band labels for all 8 dimensions: AL, PR, AUI, EC, CS, CD, ES, CA
- Scorer notes explaining the rationale for each band

## Status

Target: 20 transcripts before Phase 1 begins. ✓

Total transcripts: 28 (`gc-001` through `gc-028`; note `gc-014` and `gc-015` exist as `.md` only — no `.json` yet).

**Phase 1 calibration set: 23 chats** (18 original + 5 new; see Exclusions below).

Note: several JSON files were produced via OCR of screen-captured chat exports. These are archived but excluded from calibration (see below). For Phase II production, only direct text exports are acceptable as input — OCR'd image PDFs introduce UUID/page-number fragments and session-header noise that corrupt turn content and confuse the judge.

Note: gc-024 through gc-028 were reconstructed from human annotation notes (no original export available). Turns are synthesized to represent the interaction described by the annotator, with all direct quotes from annotation notes preserved verbatim in turn content. These chats are valid for calibration but should be flagged if MAE on them significantly exceeds the OCR-quality chats.

## Calibration set (18 chats)

| Chat | Included | Notes |
|------|----------|-------|
| gc-001 | ✓ | |
| gc-002 | ✓ | |
| gc-003 | ✓ | |
| gc-004 | ✗ | OCR data quality — see Exclusions |
| gc-005 | ✓ | |
| gc-006 | ✓ | |
| gc-007 | ✓ | |
| gc-008 | ✓ | Long (241 turns); sampled to first3+mid3+last3 frames in calibration |
| gc-009 | ✓ | |
| gc-010 | ✓ | |
| gc-011 | ✓ | |
| gc-012 | ✗ | OCR data quality — see Exclusions |
| gc-013 | ✗ | OCR data quality — see Exclusions |
| gc-014 | — | No JSON yet (`.md` only) |
| gc-015 | — | No JSON yet (`.md` only) |
| gc-016 | ✓ | |
| gc-017 | ✓ | |
| gc-018 | ✓ | |
| gc-019 | ✓ | |
| gc-020 | ✓ | |
| gc-021 | ✓ | |
| gc-022 | ✓ | |
| gc-023 | ✓ | Long (337 turns); sampled to first3+mid3+last3 frames in calibration |
| gc-024 | ✓ | Reconstructed from annotation notes — Yash/ChatGPT ML exam prep |
| gc-025 | ✓ | Reconstructed from annotation notes — Aditya/ChatGPT labor law |
| gc-026 | ✓ | Reconstructed from annotation notes — CERN CV optimization; multi-model cross-verification |
| gc-027 | ✓ | Reconstructed from annotation notes — Vaibhav/ChatGPT AI ethics; only ES:high chat in corpus |
| gc-028 | ✓ | Reconstructed from annotation notes — Startup self-analysis; contains ES:low + privacy boundary tests |

## Exclusions

Chats with `"calibration_excluded": true` in their JSON are loaded and schema-validated normally but skipped by `calibration/run_calibration.ts`. The `calibration_excluded_reason` field records why.

| Chat | Reason | Detail |
|------|--------|--------|
| gc-004 | `ocr_data_quality` | 358 turns, 38% under 100 chars. UUID fragments (e.g. `3-b630-832c-a28e-95b2ff2573ed`) and page-number markers (`18/64`) embedded throughout turn content from PDF screen-cap OCR. Single-topic cybersecurity PPT session; data not salvageable without re-export. |
| gc-012 | `ocr_data_quality` | 140 turns, 51% under 100 chars. Session headers (`"5/20/26, 8:49 PM Model Environment Fix"`) embedded in turn content at regular intervals from chat-app UI OCR. Judge would misread embedded timestamps as topic/session boundaries. |
| gc-013 | `ocr_data_quality` | 248 turns, ~50% under 100 chars. Same UUID + page-marker contamination pattern as gc-004. Single-topic HCI exam prep session. |

## Scoring Instructions

See spec Section 4 for rubric anchors. For each dimension, pick the band (`low`, `mid`, `high`, or `not_applicable`) that best fits. Record reasoning in the annotation `notes`.

Do not score synthetically. Every transcript here must reflect a real human's judgment, not a model's.
