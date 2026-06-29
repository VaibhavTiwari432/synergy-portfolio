# ADR-0019 — Pre-filter eligibility gate

**Date:** 2026-06-30  
**Status:** ACCEPTED (wired live by default; permissive scaffold remains review-gated)  
**Context:** v3.23 §3 (was "ADR-0016"), corrected by Appendix R.2/R.3/R.4/R.5  
**Impact:** Live path now passes judge-typed neuron IDs through the gate when
known task intents are present. The scaffold remains permissive, so reviewed
cell tightening is still the step that changes eligibility behavior.

---

## Decision

Add a pre-filter that, given a task's intent tags, decides which **judge-typed**
neurons the task can structurally elicit. Neurons a task cannot elicit are
marked **N/A with a structural reason** instead of being judge-scored — saving
judge calls and distinguishing "the task never called for this" (`STRUCTURAL_NA`)
from "could fire, did not" (`BEHAVIORAL_NA`).

The gate is wired in `src/api/pipeline.py` behind `SAF_ADR0019_GATE_ENABLED`
(default enabled). The current scaffold is permissive for any known intent, so
enabling the gate bounds the judge-neuron list without excluding reviewed cells
yet. Empty/untagged sessions stay on the legacy all-neuron path to avoid turning
tagger uncertainty into structural N/A.

---

## What landed in this commit

| Artifact | Path | State |
|---|---|---|
| Gate logic | `src/aggregate/eligibility_gate.py` | live code, unit-tested |
| Matrix scaffold | `contracts/neuron_task_eligibility.yaml` | permissive no-op; every cell `needs_review` |
| Tests | `tests/unit/test_eligibility_gate.py` | 8 passing |
| Pipeline wiring | `src/api/pipeline.py` | enabled by default via `SAF_ADR0019_GATE_ENABLED` |

---

## Deviations from the v3.23 spec (per Appendix R)

The spec text (§3) was written against an assumed tree. Corrections applied:

1. **Path (R.2):** gate lives at `src/aggregate/eligibility_gate.py`, not the
   non-existent `src/classifier/eligibility_gate.py`. Matrix lives at
   `contracts/neuron_task_eligibility.yaml` (frozen-contract neighbour), not
   `neurons/`.
2. **ADR number (R.3):** filed as **0019**, not "0016" — 0015/0016 are already
   taken twice in `adr/`.
3. **Intent set (R.4):** the matrix uses the real frozen 10 `IntentTag` members
   — `VERIFY, EXTRACT, INJECT_CONTEXT, OVERRIDE, SELF_AUDIT, DELEGATE, SCAFFOLD,
   PIVOT, DECOMPOSE, ACCEPT_FLAT`. The spec's `CLARIFY` and `ABSTRACT` **do not
   exist** and were dropped; `DELEGATE` and `ACCEPT_FLAT` (omitted by the spec,
   and central to offloading) are **included** in every cell.
4. **Scope = 98, not 107:** the gate filters only **judge-typed** neurons (98).
   The 9 deterministic neurons (`AL-08, EC-06, EC-07, EC-09, ES-01, PR-02, PR-05,
   PR-07, PR-14`) fire from event evidence, not intent — they are listed in
   `event_gated_exempt` and never filtered. Filtering them would double-gate
   (L9-style) and drop real event-driven firings.
5. **No new enum / no schema bump:** the spec proposed a new
   `STRUCTURAL_NA | BEHAVIORAL_NA` `ScoreStatus`. `ScoreStatus.NOT_APPLICABLE`
   already documents itself as "spec STRUCTURAL_NA", so we reuse it and carry the
   structural-vs-behavioral distinction in a **reason string**. This avoids a
   frozen-surface contract change (non-negotiable #1). Migration 017 (new enum
   columns) is therefore **not needed** as specced; if NA-reason persistence is
   wanted later, it is a nullable TEXT column, not an enum migration.

---

## The matrix scaffold

`neuron_task_eligibility.yaml` is generated from the live `rubric_bank` contract,
so all 98 judge-typed neuron IDs (+ dimension + title) are present and correct.
Every cell defaults to `triggers_on: [all 10 intents]` with `needs_review: true`.

Consequence: **the gate excludes nothing until a cell is tightened** — a safe
no-op. This deliberately leaves the load-bearing domain judgement (which neuron
fires on which intent) to human review (v3.23 §7 Q1: "Vaibhav drafts"), while
giving that review a complete, structurally-valid artifact to tighten rather than
author from scratch. Tightening any cell's `triggers_on` immediately makes the
gate filter for that neuron (covered by `test_tightened_cell_excludes_*`).

---

## Acceptance gate (before this is wired live)

Per v3.23 §3.7 — all gold-corpus gated, hence the flag-off posture:

- 60%+ judge-call reduction on representative chats once cells are tightened.
- EC MAE improvement on VERIFY-dominant chats (current 0.41), no regression on
  the overall MAE ratchet ≤ 0.2994.
- Structural vs. behavioral NA distribution documented per task type.
- Gate A variance (CD range ≤ 0.10) reconfirmed post-FIX-1 **before** any
  score-changing gate joins the live path.

---

## Consequences

- Reversible through `SAF_ADR0019_GATE_ENABLED=0`.
- In `src/api/pipeline.py`, after intent tagging, known task intents call
  `determine_scorable_neurons(intents)` to bound the judge-typed set passed to
  per-neuron scoring. Deterministic neurons bypass untouched.
- Structural N/A stamping for tightened cells remains the follow-up persistence
  work; the current scaffold excludes no known-intent cells.

---

## Notes

- Companion ADRs: **0017** (reject external integrations, ACCEPTED), **0018**
  (task-oriented scoring — corpus-gated, stub-only per R.5).
- Self-check: `python -m src.aggregate.eligibility_gate`.
