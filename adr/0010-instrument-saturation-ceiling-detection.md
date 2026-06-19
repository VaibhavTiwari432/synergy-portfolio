# ADR-0010 — Instrument-saturation detection: tau as a score-ceiling, conjunctive guard

- **Status:** Accepted
- **Date:** 2026-06-19
- **Decider:** Chief Engineer; tau table, thresholds, and the §0 reframe approved by project lead (STEP 1 sign-off)
- **Implements:** SAF/ARI v3 P1 — instrument saturation as the third censored-reporting
  sibling (`MEASUREMENT_SATURATED`), the state added structurally in Phase 0.3 / ADR-0004
  lineage. Wires the dormant `Censored` schema (contracts/schemas.py §A3) into the live
  scoring pipeline behind a frozen, guarded detector.
- **Files:** new `src/aggregate/saturation.py` (constants + `saturation_for`); wired into
  `src/api/pipeline.py::_profile_from_judge`; soft-min integration in
  `src/aggregate/softmin.py`; pinned by `tests/unit/test_saturation.py`.

## §0 — The architectural reframe (the thing not to re-litigate)

`tau` is a **score threshold on [0,1]** — how high a dimension's judge score sits against
the instrument's usable ceiling — **NOT an item count**. An earlier framing treated
saturation as "enough items fired"; that conflates *sample sufficiency* (already owned by
the n_eff scorability gate, `gates.N_EFF_TAU`) with *resolution ceiling* (the judge can no
longer distinguish "very high" from "higher still"). These are different failures and get
different machinery. Saturation is the latter: the score topped out the instrument's
resolution, so we report a censored `≥ tau` bound instead of a fabricated `= max`.

This conditions **precision only**, never the score value (non-negotiable #2): a saturated
dimension carries `status=MEASUREMENT_SATURATED`, `value=None`, and
`Censored(direction="high", bound=tau)`.

## §1 — The frozen tau table (ceilings)

Frozen before go-live; pinned by `test_tau_ceiling_table_is_frozen_exactly`. Any change
moves with the pin test and an ADR amendment.

| dim | tau | rationale |
|-----|-----|-----------|
| AL  | 0.95 | default |
| PR  | 0.95 | default |
| EC  | 0.97 | conservative — EC carries the standing low-calibration flag (#19) |
| ES  | 0.97 | conservative — D-004 ethics guard |
| CS  | 0.93 | ceiling-prone and highest-weight dimension |
| CD  | 0.95 | default |
| AUI | 0.95 | default |
| CA  | 0.95 | default |

Thresholds (§6 Q2, accepted): `SATURATION_MIN_NEFF = 5`, `SATURATION_CONF_FLOOR = 0.85`.
`SATURATION_MIN_NEFF ≥ gates.N_EFF_TAU` is asserted at import (and pinned by test) so a
saturated dimension always clears the n_eff scorability gate by construction.

## §2 — The detection rule (conjunctive guard)

A dimension saturates **iff all** of: a usable (non-None) score; **no standing
quality/calibration flag**; `n_eff ≥ SATURATION_MIN_NEFF`; `confidence ≥
SATURATION_CONF_FLOOR`; and `score ≥ TAU_CEILING[dim]`. Any single clause failing blocks
saturation.

The conjunction is the point: it stops **hallucination-as-ceiling**. A confident-looking
maximum resting on thin evidence (low n_eff), low judge confidence, or a calibration caveat
is not a saturated instrument — it is an unreliable high score, and must not be laundered
into a censored bound that reads as "off the charts".

## §3 — Floor detection is present but off

Floor (`direction="low"`) detection is structurally present (`SATURATION_FLOOR_ENABLED`,
`TAU_FLOOR`) but operationally **off** — no reviewed use case yet. When one lands, register
`TAU_FLOOR` and flip the one flag. Pinned: with the flag off, a `0.0` score emits nothing.

## §4 — Constants home

The constants live in `src/aggregate/saturation.py` (the aggregation layer, where the
soft-min composite consumes the censored bound), **not** in `precision.py` (the
widening/degradation layer). `precision.py` imports from `saturation.py`, never the
reverse.

## §5 — Soft-min integration

`compute_composite` (softmin.py) feeds `TAU_CEILING[dim]` (the censored bound) as the
aggregation value for a saturated dimension, never `None`. A saturated dim therefore still
**participates** in the soft-min composite: its bound is high by construction so it can
never *bind* the soft-min (a censored ceiling is never below an actual low score), but it
is no longer silently dropped from the composite or its CI endpoints.

## EC integration note

EC always carries `ec_low_calibration_confidence` (a standing flag, True until the corpus
grows — #19). By the §2 flag clause, **EC will not saturate until #19 is resolved.** This
is correct behavior, not a bug: EC's calibration is too weak today to assert a ceiling is
real rather than a model artifact. When #19 lands and the flag is retired, EC becomes
eligible at its conservative tau=0.97.

## Consequences

- A topped-out, well-evidenced dimension now reports `≥ tau` rather than a point value that
  overstates the instrument's resolution.
- The four reporting states (`OK`, `INSUFFICIENT_SAMPLE`, `NOT_APPLICABLE`,
  `MEASUREMENT_SATURATED`) remain never-collapsed.
- Detector is frozen and guarded; with an empty `TAU_CEILING` it emits nothing
  (never-emit-before-frozen), so the table is the sole enabling switch.
