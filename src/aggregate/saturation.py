"""
src/aggregate/saturation.py — instrument-saturation (ceiling/floor) detection.
OWNER: Chief Engineer. (v3 P1; ADR-0010.)

Architectural reframe (ADR-0010 §0): tau is a SCORE threshold on [0,1] — how
high a dimension score sits against the instrument's usable ceiling — NOT an
item count. A dimension saturates when its score tops out the judge's resolution
*while the supporting evidence is strong enough that the ceiling is real* rather
than a hallucinated maximum.

Detection is a CONJUNCTIVE guard (ADR-0010 §2): score ≥ tau AND n_eff strong AND
confidence high AND no standing quality flag. Any single clause failing blocks
saturation — this is what stops "hallucination-as-ceiling": a confident-looking
max resting on thin evidence, low confidence, or a calibration caveat is not a
saturated instrument, it is an unreliable high score.

Saturation conditions PRECISION only — a censored "≥ X" bound — never the score
VALUE (non-negotiable #2). A saturated dimension carries status
MEASUREMENT_SATURATED with value None and Censored(direction="high", bound=tau);
the bound speaks in place of a fabricated "= max".

Floor detection (direction="low") is structurally present but operationally OFF
(SATURATION_FLOOR_ENABLED=False) — no reviewed use case yet (ADR-0010 §3). When
one lands, register TAU_FLOOR and flip the one flag.

This module is the aggregation-layer owner of the saturation constants; the
soft-min composite consumes the censored bound and precision.py imports from
here, never the reverse (ADR-0010 §4).
"""

from __future__ import annotations

from contracts.schemas import Censored, Dimension
from src.aggregate.gates import N_EFF_TAU

# ── frozen constants (ADR-0010 §1; pinned by tests/unit/test_saturation.py) ──

#: per-dimension ceiling tau — a SCORE threshold on [0,1], frozen before go-live.
#: EC=0.97 (conservative for the low-calibration flag, #19); ES=0.97 (D-004
#: guard); CS=0.93 (ceiling-prone and highest-weight); all others at the 0.95
#: default. Changing any value here must move with the pin test and an ADR.
TAU_CEILING: dict[Dimension, float] = {
    Dimension.AL: 0.95,
    Dimension.PR: 0.95,
    Dimension.EC: 0.97,
    Dimension.ES: 0.97,
    Dimension.CS: 0.93,
    Dimension.CD: 0.95,
    Dimension.AUI: 0.95,
    Dimension.CA: 0.95,
}

#: minimum effective sample for a ceiling to count as real (not hallucinated).
SATURATION_MIN_NEFF: float = 5.0

#: minimum judge confidence for a ceiling to count as real.
SATURATION_CONF_FLOOR: float = 0.85

#: floor detection (direction="low") is off until a reviewed use case lands.
SATURATION_FLOOR_ENABLED: bool = False

#: per-dimension floor tau — unregistered until SATURATION_FLOOR_ENABLED flips.
TAU_FLOOR: dict[Dimension, float] = {}

# A saturated dimension must clear the n_eff scorability gate by construction:
# its sample floor can never sit below that gate's tau, or we would emit a
# ceiling for a dimension the gate would otherwise demote (ADR-0010 §2). Fail
# loudly at import if the two constants ever drift apart.
assert SATURATION_MIN_NEFF >= N_EFF_TAU, (
    f"SATURATION_MIN_NEFF {SATURATION_MIN_NEFF} must be >= gates.N_EFF_TAU {N_EFF_TAU}"
)


def saturation_for(
    dim: Dimension,
    score: float | None,
    n_eff: float,
    confidence: float,
    flags: list[str],
) -> Censored | None:
    """Return a Censored bound iff `dim` saturates the instrument, else None.

    Conjunctive guard, all required:
      * a usable (non-None) score,
      * no standing quality/calibration flag,
      * n_eff ≥ SATURATION_MIN_NEFF,
      * confidence ≥ SATURATION_CONF_FLOOR,
      * the score at/beyond the registered tau.

    A dimension with no registered tau never saturates — this is the
    never-emit-before-frozen property (empty TAU_CEILING ⇒ zero emissions).
    """
    if score is None:
        return None
    # A standing quality/calibration flag means a high score is not trustworthy
    # AS A CEILING — block. This is precisely why EC (which always carries
    # "ec_low_calibration_confidence") does not saturate until #19 is resolved.
    if flags:
        return None
    if n_eff < SATURATION_MIN_NEFF:
        return None
    if confidence < SATURATION_CONF_FLOOR:
        return None

    ceiling = TAU_CEILING.get(dim)
    if ceiling is not None and score >= ceiling:
        return Censored(direction="high", bound=ceiling)

    if SATURATION_FLOOR_ENABLED:
        floor = TAU_FLOOR.get(dim)
        if floor is not None and score <= floor:
            return Censored(direction="low", bound=floor)

    return None
