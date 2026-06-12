# ADR-0005 — Judge prompt v2.0 → v2.1: ES calibration anchors

- **Status:** Accepted
- **Date:** 2026-06-12
- **Decider:** Chief Engineer (Stage-2 calibration iteration)
- **Code:** `src/trait/judge/prompt.py` (JUDGE_PROMPT_VERSION v2.1)
- **Evidence:** `calibration/results/stage2_prompt_v2.0.json`

## Context — the failure mode

The Stage-2 initial calibration (prompt v2.0, Gemini 2.5 Flash, 26/26 chats,
coverage 100%) beat the overall ratchet — shadow MAE 0.2771, headline 0.2920,
both ≤ 0.2994 — but failed the per-dimension gate on **ES alone: MAE 0.460**
(target ≤ 0.375), over just five scored pairs:

| Chat | Gold ES | Judge ES | Error |
|---|---|---|---|
| gc-004 | low (0.25) | **1.0** | +0.75 |
| gc-010 | mid (0.55) | 0.9 | +0.35 |
| gc-023 | low (0.25) | **1.0** | +0.75 |
| gc-027 | high (0.80) | 1.0 | +0.20 |
| gc-028 | low (0.25) | 0.0 | −0.25 |

The pattern is **saturation, not noise**: the judge awarded 1.0 whenever a
session *contained* ethically relevant subject matter that was handled
without incident. **Ethics content present ≠ ethics behavior demonstrated.**
The human annotator scores the user's *demonstrated* ethical handling
(redaction, consent care, harm awareness); v2.0 gave the judge a definition
("recognizing and handling ethically charged content") but no graded anchors,
so it collapsed to topic salience with a binary scale.

## Decision — v2.1 ES anchors

Added an ES anchor block in exactly the style of the v1.3 EC anchors (the
proven mechanism for the same disease — EC in v1.2 also saturated until
anchors landed; preserved in `legacy/judge_prompt_v1.3.md`):

- **Example A ≈ 0.80** — strong demonstrated sensitivity: unprompted PII
  stripping; challenging the AI on consent grounds and reframing the task;
  raising who could be harmed and adjusting the request.
- **Example B ≈ 0.25** — ethics-relevant content, no demonstrated handling:
  the session processes privacy-sensitive or ethically loaded material and
  the user simply proceeds — no redaction, no flagging, no harm awareness.
- **> 0.9 reserved** for multiple distinct safeguarding behaviors across the
  session; fluent engagement WITH an ethical topic while demonstrating none
  is Example B territory.

The anchor values 0.80 / 0.25 deliberately sit on the gold band centers
(high = 0.80, low = 0.25, BAND_TO_FLOAT in `calibration/gold_loader.py`), so
the judge's scale and the gold scale share fixed points.

## Why this is the same pattern as the v1.3 EC anchors

Both are inferential dimensions where the naive reading rewards *presence*
(of interaction volume for EC, of ethical topic for ES) rather than *behavior*
(active scrutiny for EC, active safeguarding for ES). The remedy is identical:
two concrete behavioral anchors pinning the scale's interior + an explicit
"presence is not the behavior" rule. v1.3's EC anchors took EC from
saturation to its best-understood dimension; v2.1 applies the same treatment
to ES. **Anyone touching the ES prompt must read this ADR first** — removing
or "simplifying" the anchors will reintroduce saturation, and the per-dim
gate will catch it only at the next full calibration run.

## Consequences

- JUDGE_PROMPT_VERSION bumped to v2.1; pinned in tests
  (`test_prompt_is_dimension_grain_not_neuron_grain` asserts the anchor block
  and the "NOT ethical sensitivity" rule are present).
- The full 26-chat re-run under v2.1 replaces the v2.0 report; v2.0 results
  are preserved at `calibration/results/stage2_prompt_v2.0.json`.
- If ES still misses after v2.1, the next hypothesis is the APPLICABILITY
  side, not the anchors: verify ES event-triggering (judge nulls vs gold
  not_applicable alignment), per the Stage-2 instruction.
- Side observation recorded for the corpus plan: EC MAE fell 0.407 → 0.239
  with the dimension-grain rewrite — non-negotiable #19's "EC is a data
  problem" pressure has eased; the 40+ high-band gold-chat target remains but
  is no longer the gating concern.
