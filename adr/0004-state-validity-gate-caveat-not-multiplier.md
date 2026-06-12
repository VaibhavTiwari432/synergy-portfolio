# ADR-0004 — State validity gate is a caveat, never a composite multiplier

- **Status:** Accepted
- **Date:** 2026-06-12
- **Decider:** Chief Engineer (sole agent); ratified by human lead's Stage-2 instruction
- **Code:** `src/aggregate/gates.py`, `src/aggregate/softmin.py`

## Context

Spec §3.6/§7.6 phrases the composite as a "penalized power-mean across pillars
**× validity gates** (scorability: ≥4/8 dims valid; state validity)". Read
literally, a failed STATE validity gate would multiply (scale down or zero)
the composite value.

That reading collides with **non-negotiable #2**: *no score multipliers for
state — state conditions evidence precision (CI width) only* (R2). A composite
scaled by a state gate is a state multiplier with one level of indirection:
the same behavioral evidence would produce a lower **value** because of the
inferred state, which is precisely the failure mode R2 exists to prevent (and
what `legacy/adr_v1/` records as a rejected idea — multipliers stay rejected,
non-negotiable #17).

## Decision

The two gates have different kinds of teeth:

| Gate | Effect on composite |
|---|---|
| **Scorability** (≥4/8 dims OK) | Gates **existence**: fail → `value: null`, `status: INSUFFICIENT_SAMPLE`. A composite over too few dimensions is not a worse composite; it is not a composite. |
| **State validity** (CSPC M_t collapse) | Gates **confidence**: fail → `state_compromised_caveat: true`, and the CIs feeding the composite were already widened in `src/merge/precision.py`. The VALUE is untouched. |

Where the brief conflicts with the spec, the brief wins on scope; where this
spec phrasing conflicts with non-negotiable #2, **the non-negotiable wins on
principle** — the spec's own R2 correction is the authority for what "state
conditioning" may do.

## Consequences

- `tests/unit/test_aggregate.py::test_state_gate_failure_caveats_but_never_scales`
  pins the behavior: identical composite value under CLEAN and COMPROMISED
  state, with the caveat flag and `gates_passed.state_validity: false` visible.
- The composite's CI is already wider under a compromised state because the
  dimension CIs it propagates were widened at the merge — the uncertainty
  shows up exactly where it belongs.
- If a future spec revision genuinely intends value-scaling validity gates,
  that is a multiplier proposal: per non-negotiable #17 it requires reading
  `legacy/adr_v1/` + spec §14, a new ADR, and an explicit stop for approval.
