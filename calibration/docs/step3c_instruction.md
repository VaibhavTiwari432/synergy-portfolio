# Task 3c — Branch B: Structural Fix Instructions

**Trigger condition:** 23-chat calibration run (phase1_expanded_23chat.json) 
failed Decision Gates 1 and 2. CS at 68.2% (threshold: 70%). PR dropped to 
73.9% (was 77.8%). Branch B is now active.

**New finding from expansion:** AL has a systematic high-band failure on all 
three new high-synergy chats (gc-024, gc-026, gc-027). AL dropped from 86.7% 
to 76.2%. The rubric audit must cover AL, PR, and CS — not CS alone.

Execute sub-steps in order. Stop and re-run calibration after each sub-step. 
If all decision gates pass after a sub-step, do not proceed to the next one.

---

## Decision gates (must all pass before Phase 2 begins)

1. CS within-2-delta ≥ 70%
2. PR within-2-delta ≥ 77.8%
3. CA within-2-delta ≥ 77.8%
4. No previously-passing dimension drops below 70%
5. AUI within-2-delta stays above 70%

---

## B.1 — High-band rubric anchor audit for AL, PR, CS

Target dimensions: AL, PR, CS only. Do not touch other dimensions.
Do not touch mid-band or low-band anchors.

**Failing chats per dimension (use these to diagnose anchor mismatch):**
- AL failures: gc-024, gc-026, gc-027
- PR failures: gc-007, gc-017, gc-018, gc-027
- CS failures: gc-007, gc-017, gc-018, gc-024

**Anchor error types to diagnose before rewriting:**
- Over-specificity: anchor describes one narrow behavioral pattern as the 
  only path to high-band, excluding equally valid high-synergy behaviors
- Superiority conflation: anchor implicitly requires the candidate to 
  outperform or correct the AI, when high-band should require active 
  steering and integration regardless of whether the AI was wrong
- Abstraction mismatch: anchor is written in terminology the judge 
  interprets inconsistently across different chat types

**Rewrite constraints:**
- Each high-band anchor must describe 2-3 distinct behavioral patterns 
  that all qualify as high-band, not one single pattern
- Must include at least one behavioral marker visible in gc-026 or gc-027 
  — these two chats were scored correctly as high-synergy and are positive 
  ground truth
- Must not require AI correction or error detection as a prerequisite for 
  high-band scoring. Agency and integration quality are the criteria
- Save output as: rubric_v0.2_highband_fix.json

**Calibration run after B.1:**
- Run against full 23-chat corpus
- Write results to: calibration/reports/phase1_b1_rubric_fix.json
- Write comparison report to: calibration/reports/b1_rubric_comparison.md
- Check all five decision gates above

**If all gates pass:** Write docs/decisions/0007-highband-rubric-fix.md 
documenting the anchor error types found and how they were corrected. Stop.

**If any gate fails:** Document which gates failed. Proceed to B.2.

---

## B.2 — CS holistic-only scoring

**Precondition:** B.1 complete and CS still below 70%.

Move CS out of per-frame Pass 1 scorer entirely. CS will be scored once 
per conversation in the holistic Pass 2 using full conversation context.

**Implementation:**
- In apps/judge/src/scorer.ts: remove CS from the frame-level dimension 
  list. CS must be absent from frame-level JudgeOutput.
- In apps/judge/src/prompt.ts: add a dedicated CS scoring block to the 
  holistic pass with this instruction: "Score CS (Contextual Synthesis) 
  based on the arc of the entire conversation. Look for whether the 
  candidate's language, framing, and problem approach evolve away from the 
  AI's framing over time. A candidate who begins by asking broad questions 
  and progressively develops their own analytical framework independent of 
  the AI's output is high-band CS, regardless of whether they explicitly 
  corrected the AI. A candidate whose final framing mirrors the AI's 
  initial framing is low-band CS, regardless of prompting skill."
- Implement under feature flag CS_HOLISTIC_ONLY injectable via JudgeConfig
- Production v5 behavior must be unchanged when the flag is absent

**Calibration run after B.2:**
- Run against full 23-chat corpus with CS_HOLISTIC_ONLY=true
- Write results to: calibration/reports/phase1_b2_cs_holistic.json
- Check all decision gates

**If all gates pass:** Write docs/decisions/0008-cs-holistic-scoring.md. Stop.

**If any gate fails:** Document which gates failed. Proceed to B.3.

---

## B.3 — Per-dimension confidence gate

**Precondition:** Both B.1 and B.2 complete, at least one gate still failing.

Add a confidence gate to the holistic synthesizer. Rule: for any dimension 
where all frame-level scores fall in the high band (raw score ≥7 on 0-10 
scale) at ≥0.70 reported confidence, the holistic pass must not apply a 
downward adjustment. The frame mean is carried forward as the holistic score.

**Implementation:**
- Implement in apps/judge/src/prompt.ts under feature flag 
  CONFIDENCE_GATE_HOLISTIC injectable via JudgeConfig
- Gate must be evaluated per-dimension per-chat, not as a global switch
- Gate must log which dimensions it triggered to a confidence_gates_fired 
  field in JudgeOutput schema for audit purposes

**Calibration run after B.3:**
- Run against full 23-chat corpus with both CS_HOLISTIC_ONLY and 
  CONFIDENCE_GATE_HOLISTIC enabled
- Write results to: calibration/reports/phase1_b3_confidence_gate.json
- Check all decision gates
- Write docs/decisions/0009-confidence-gate.md regardless of outcome

---

## Final step — required after whichever sub-step resolves the gates

Write calibration/reports/PHASE1_FINAL_HANDOFF.md containing:
1. Active corpus: 23 chats (gc-001 to gc-028, 3 excluded for OCR quality)
2. Final within-2-delta per dimension and overall
3. Active feature flags in production judge
4. Active rubric version
5. One-line description of each change made in Phase 1 remediation
6. Three DB schema fields required before any Phase 2 extension data is 
   collected: problem_statement_id, candidate_submission, session_number

Write docs/decisions/0010-phase1-remediation-complete.md with a single 
sentence verdict: either "Phase 1 remediation complete — all decision gates 
passed, system ready for Phase 2 extension build" or "Phase 1 remediation 
reached B.3 — gates [list] remain open, recommend human review before Phase 2."

Overall acceptance target: ≥85% within-2-delta across all 8 dimensions 
with no individual dimension below 70%.
