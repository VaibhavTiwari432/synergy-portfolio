# Phase 1 Calibration Handoff

**Status:** PASSED  
**Completed:** 2026-05-23  
**Report:** `calibration/reports/phase1_gemini_full.json`

---

## Exit criteria result

| Criterion | Result |
|-----------|--------|
| Structural validity | PASS — 18/18 chats scored, 0 failed |
| Within-2-delta | **81.0%** (threshold: 70%) |
| Overall | **PASSED** |

18 chats evaluated. 3 excluded from gold set (OCR quality — gc-004, gc-012, gc-013). 106 API calls consumed against a 150-call cap.

---

## Per-dimension MAE (18-chat aggregate)

| dim | MAE   | within_2_delta | n  | note |
|-----|-------|----------------|----|------|
| AL  | 1.300 | 86.7%          | 15 | |
| PR  | 1.298 | 77.8%          | 18 | |
| AUI | 1.185 | 94.4%          | 18 | |
| EC  | 1.011 | 80.0%          | 15 | |
| CS  | 1.713 | **61.1%**      | 18 | below 70% individual threshold |
| CD  | 0.904 | 88.2%          | 17 | |
| ES  | 1.667 | 100%           | 2  | n too small to interpret |
| CA  | 1.344 | 77.8%          | 18 | |

Overall MAE: **1.265**. CS is the only dimension below the 70% individual threshold; all others pass. ES has n=2 and is excluded from Phase 2 threshold tracking until more annotated examples exist.

---

## Known issue: "prefer Case 1" tie-break under-scores high chats

**What it is.** The holistic prompt contains the instruction: *"When in doubt between Case 1 and Case 3, prefer Case 1."* This was added to fix mid-bias (the judge defaulting to 0.0 on passive sessions). It works — mid-bias is resolved. But it produces a directional error on the other end: when a session has two or more high-scoring frames and one weak frame, the judge anchors on the weak frame, calls Case 1 (dominant low), and under-scores the session.

**Observed in three chats.**

| chat | dims failed (error > 2) | pattern |
|------|------------------------|---------|
| gc-007 | PR, CS, CA | judge found one weak frame in a 3-frame chat; called Case 1 across all three |
| gc-016 | PR, AUI, EC, CS, CD | judge anchored on Frame 1 (image-generation request AI couldn't fulfill); applied Case 1 session-wide |
| gc-017 | PR, CS, CA | identical pattern to gc-007 |

All three chats had human gold of mostly-high (5–7 high dimensions). The judge scored them mostly-low. The holistic reasoning in all three is substantive — the judge is making a defensible but wrong call, not producing empty text.

**CS most affected** because synthesis signals are often absent in individual frames and only visible at the session level; the tie-break pushes borderline cases toward low rather than inspecting the full arc.

---

## Open decision for Phase 2: tie-break direction

Two options. Neither has been tested. Decision deferred until Phase 2 pilot data shows which error direction causes more user-facing harm.

**Option A — Remove the tie-break.**  
Delete "when in doubt between Case 1 and Case 3, prefer Case 1" from the holistic prompt. Re-run gc-007, gc-016, gc-017 to verify the three flagged chats recover. Risk: mid-bias may partially return on genuinely passive sessions that were previously under-scored as mid.

**Option B — Add a counter-weight for 2+ high frames.**  
Insert an instruction: *"If two or more frames show genuine high-band signal for a dimension, do not call Case 1 unless the low-band frame accounts for more than 60% of scored turn weight."* This preserves the tie-break for sessions with a single ambiguous signal while blocking the anchor-on-one-weak-frame failure. More surgical than Option A but adds prompt complexity.

Neither option changes the Phase 1 result. The 81.0% within-2-delta passes with the current prompt. This is a Phase 2 prompt decision, not a Phase 1 blocker.

---

## Judge model

**Gemini 2.5 Flash** confirmed as production judge model for Phase 1 and Phase 2.

- Tier 1 (paid) key in use. Free-tier limit is 20 req/day — not sufficient for full calibration runs.
- `thinkingBudget: 0` required; thinking mode degrades output format reliability.
- Provider adapter pattern is in place in `apps/judge/src/scorer.ts`. Swapping to a different model requires only a new adapter implementation — no changes to the scoring loop, holistic pass, or report schema.

---

## Gold standard set

**Active: 18 chats**  
gc-001, gc-002, gc-003, gc-005, gc-006, gc-007, gc-008, gc-009, gc-010, gc-011, gc-016, gc-017, gc-018, gc-019, gc-020, gc-021, gc-022, gc-023

**Excluded: 3 chats**

| chat | reason |
|------|--------|
| gc-004 | OCR-sourced transcript — text quality too low for reliable scoring |
| gc-012 | OCR quality — same basis as gc-004 and gc-013 |
| gc-013 | OCR-sourced transcript — text quality too low for reliable scoring |

**Annotation correction during calibration.**  
gc-001 CA band: `low` → `mid`. Corrected after rubric review during prompt iteration. Turn 11 of gc-001 shows the user pushing back when the AI's advice was clearly wrong — this constitutes reactive agency (mid-band CA), not passive acceptance (low-band). The original annotation over-weighted session-level passivity without reading the specific turn. Both `gold_standard/chats/gc-001.json` and `gold_standard/chats_anonymized/gc-001.json` updated. Revision note in the annotation record.

---

## Artifacts

| file | description |
|------|-------------|
| `calibration/reports/phase1_gemini_full.json` | canonical 18-chat Phase 1 report |
| `calibration/reports/phase1_gemini_gc001_v5.json` | gc-001 v5 prompt run (merged into full report) |
| `calibration/reports/phase1_gemini_from_gc-002.json` | 17-chat run artifact (gc-002 through gc-023) |
| `apps/judge/src/prompt.ts` | holistic prompt v5 — in production for Phase 2 |
| `calibration/docs/step2_instruction.md` | Step 2 pre-flight checklist (updated with correct quota: 20 req/day free tier) |
| `packages/rubric/rubric_v0.1.json` | rubric used for Phase 1 scoring |
