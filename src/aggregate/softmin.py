"""
src/aggregate/softmin.py — soft non-compensatory composite. OWNER: Chief Engineer.
(Brief §3.7; spec §3.6/§7.6.)

Structure: 8 dimensions → 4 pillars → composite.
- Within a pillar: weighted arithmetic mean over the pillar's VALID dimensions
  (EC and CS carry 1.5×, DIMENSION_WEIGHTS).
- Across pillars: power mean with p = SOFTMIN_P < 0 — the soft-min. A genuinely
  hollow pillar drags the composite down and cannot be averaged away; but one
  INSUFFICIENT_SAMPLE dimension does not erase the rest (its pillar simply
  rests on its remaining dimension, and a fully-absent pillar is excluded).
- Composite exists only if the scorability gate passes (≥4/8 dims OK).
- The composite CI is interval arithmetic over dimension CIs through the same
  (monotone) aggregation — never presented bare (non-negotiable #6).
- A failed state gate sets the caveat flag; it never scales the value (#2).
"""

from __future__ import annotations

from contracts.schemas import (
    Composite,
    ConfidenceInterval,
    DIMENSION_WEIGHTS,
    Dimension,
    DimensionScore,
    Rung,
    ScoreStatus,
    StateValidity,
)
from src.aggregate.gates import scorability_gate, state_validity_gate

#: the 4 pillars (brief §3.1 table)
PILLARS: dict[str, tuple[Dimension, Dimension]] = {
    "engage": (Dimension.AL, Dimension.PR),
    "manage": (Dimension.EC, Dimension.ES),
    "create": (Dimension.CS, Dimension.CD),
    "design": (Dimension.AUI, Dimension.CA),
}

#: power-mean exponent across pillars; p<0 = soft-min (penalized, non-compensatory)
SOFTMIN_P = -2.0

#: floor used inside the power mean so a 0.0 pillar doesn't blow up 1/x^|p|;
#: outputs below this floor are indistinguishable from it (documented behavior)
_EPS = 1e-3

#: D2: multiplicative G_k penalty when fluent_incompetence fires
#: (NOT a state gate — state stays caveat-only per rule #2; this is behavioral)
_G_K = 0.85


def _pillar_value(values: dict[Dimension, float], dims: tuple[Dimension, ...]) -> float | None:
    present = [(d, values[d]) for d in dims if d in values]
    if not present:
        return None
    ws = sum(DIMENSION_WEIGHTS[d] for d, _ in present)
    # ponytail: within-pillar weighted power mean (same p as across-pillar) so a
    # hollow dim cannot hide behind a strong pillar-mate (D1 fix; p calibrated post corpus)
    return (sum(DIMENSION_WEIGHTS[d] * max(v, _EPS) ** SOFTMIN_P for d, v in present) / ws) ** (1.0 / SOFTMIN_P)


def _power_mean(values: list[float], p: float = SOFTMIN_P) -> float:
    clamped = [max(v, _EPS) for v in values]
    return (sum(v**p for v in clamped) / len(clamped)) ** (1.0 / p)


def _aggregate(values: dict[Dimension, float]) -> float | None:
    pillar_values = [
        pv for dims in PILLARS.values() if (pv := _pillar_value(values, dims)) is not None
    ]
    if not pillar_values:
        return None
    return min(1.0, max(0.0, _power_mean(pillar_values)))


def compute_composite(
    profile: dict[Dimension, DimensionScore],
    state_validity: StateValidity,
    *,
    fluent_incompetence: bool = False,
) -> Composite:
    gates = {
        "scorability": scorability_gate(profile),
        "state_validity": state_validity_gate(state_validity),
        "fluent_incompetence": not fluent_incompetence,
    }
    caveat = not gates["state_validity"]

    if not gates["scorability"]:
        return Composite(
            value=None,
            ci=None,
            status=ScoreStatus.INSUFFICIENT_SAMPLE,
            gates_passed=gates,
            state_compromised_caveat=caveat,
            rung=Rung.MEASURABLE,
        )

    # OK dims contribute their value; a MEASUREMENT_SATURATED dim contributes its
    # censored bound (TAU_CEILING[dim]) so a topped-out dimension still PARTICIPATES
    # in the soft-min instead of being silently dropped (§5.1). The bound is high by
    # construction, so it can never BIND the soft-min (a censored ceiling is never
    # below an actual low score) — but it is no longer erased from the composite.
    agg_value: dict[Dimension, float] = {}
    ok: dict[Dimension, DimensionScore] = {}
    for d, s in profile.items():
        v = s.value if s.value is not None else (s.censored.bound if s.censored else None)
        if v is None:
            continue
        agg_value[d] = v
        ok[d] = s
    value = _aggregate(agg_value)

    ci: ConfidenceInterval | None = None
    with_ci = {d: s for d, s in ok.items() if s.ci is not None}
    if with_ci and value is not None:
        # monotone aggregation → endpoint propagation is exact; dims without a
        # CI (incl. saturated dims) contribute their aggregation value at both
        # ends (no invented width)
        lows = {d: (s.ci.low if s.ci else agg_value[d]) for d, s in ok.items()}
        highs = {d: (s.ci.high if s.ci else agg_value[d]) for d, s in ok.items()}
        low, high = _aggregate(lows), _aggregate(highs)
        if low is not None and high is not None:
            ci = ConfidenceInterval(low=min(low, value), high=max(high, value))

    # D2: apply multiplicative G_k penalty when fluent_incompetence fires.
    # This is a behavioral gate, NOT a state gate — state stays caveat-only (#2).
    if fluent_incompetence and value is not None:
        value = round(value * _G_K, 6)
        if ci is not None:
            ci = ConfidenceInterval(
                low=max(0.0, ci.low * _G_K),
                high=min(1.0, ci.high * _G_K),
            )

    return Composite(
        value=value,
        ci=ci,
        status=ScoreStatus.OK,
        gates_passed=gates,
        state_compromised_caveat=caveat,
        rung=Rung.MEASURABLE,
    )
