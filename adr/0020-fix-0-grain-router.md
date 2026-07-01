# ADR-0020 - FIX-0 grain router

**Date:** 2026-06-30  
**Status:** ACCEPTED  
**Context:** SAF/ARI v3.23 FIX-0, after ADR-0019 scaffold landed.

## Decision

Add `src/classifier/grain_router.py` as a deterministic internal classifier that
routes judge-typed neurons by evidence grain:

- `SYNERGY`
- `HUMAN_CONTROL`
- `AI_OUTPUT_SHAPING`
- `TASK_MANAGEMENT`
- `OUTPUT_QUALITY`
- `UNKNOWN`

The router is wired into `src/api/pipeline.py` for CI source selection. It does
not add schema fields or public enums. Existing `raw_counts` and flags carry
audit metadata (`grain_synergy_ci_neurons`, `grain_total_judge_neurons`,
`ci_from_grain_router`).

## Consequences

- Dimension values still come from the unified neuron matrix; the router does
  not delete non-synergy evidence from the value path.
- CI width uses the synergy subset when available, with a 0.15 guardrail matching
  the FIX-0 acceptance target.
- Unit coverage pins 20 grain cases plus routing/CI acceptance behavior.

## Verification

- `python -m pytest tests/test_grain_router.py`
- Included in full unit pass: `589 passed`.

