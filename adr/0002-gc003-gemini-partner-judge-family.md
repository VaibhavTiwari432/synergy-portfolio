# ADR-0002 — gc-003 has a Gemini partner: judge-family exception, flagged

- **Status:** Accepted (standing caveat)
- **Date:** 2026-06-12
- **Decider:** Human lead via `AGENT_REBUILD_BRIEF_v3.md` §3.4; recorded by Chief Engineer

## Context

Non-negotiable #20: **the judge family must differ from the partner family** (a model
should not grade conversations held with its own family — shared blind spots and style
affinity bias the scores). The pipeline judge is **Gemini 2.5 Flash**; the gold corpus
partners are mostly ChatGPT and Claude, where the rule holds.

**gc-003 (Ritesh) has a Gemini partner.** The v1 build judged it with a Gemini judge —
a same-family judgment. Its human gold scores are unaffected (human-annotated), but any
*judge* score for gc-003 carries same-family risk. gc-016 (Puransh_Gemini) and
gc-0xx (Shreyas_Gemini) source PDFs suggest other Gemini-partner chats may exist in the
corpus — verify `partner_model.family` per chat when adapters land.

## Decision

1. `PartnerModel` (family, model_id, era_key) is a **required** schema field from
   Stage 0, so every session records its partner family at ingestion.
2. When `judge_family == partner_family` for a session, the pipeline sets a
   `judge_family_conflict: true` flag on the judge output — the score is still
   produced, never silently suppressed (absent ≠ zero, #12), but the flag propagates
   to the score response and calibration reports.
3. **Calibration:** gc-003 (and any other Gemini-partner gold chat) is **excluded or
   down-weighted in judge-family-sensitive analyses** — e.g. when comparing judge
   agreement across families or attributing MAE movement to prompt changes. It stays
   in the headline 26-chat MAE for ratchet continuity with v1.3 (which included it),
   with the conflict flag visible in the per-chat report rows.
4. Scoring a Gemini-partner chat in production follows the same rule: flag, never block.

## Consequences

- `calibration/runner.py` must surface `judge_family_conflict` per chat in its report.
- If the corpus gains enough Gemini-partner chats to matter, the durable fix is a
  second judge family (e.g. an OpenAI judge for Gemini-partner sessions) — that is a
  future ADR, not Scope A.
