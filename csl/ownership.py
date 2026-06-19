"""CSL Phase 2.3 — ownership normalization + CSPC precision weighting.

Combines the two orthogonal Track-1 reads into a per-level displayed-ownership
contrast (`SPEC_ownership.md`):

  - human side: `LevelEvidence` from `projection.project_to_acf` (a re-projection
    of the existing NeuronMatrix — no new extraction);
  - AI side:   the displayed-contribution 7-vector from
    `ai_side_extractor.extract_ai_contribution`.

Formula (§"Formula"):

    human_weighted(level) = pi_s(level) * control_human(level)
    human_ownership(level) = human_weighted / (human_weighted + AI_displayed)
    ai_ownership(level)    = AI_displayed  / (human_weighted + AI_displayed)

These are level-local contrasts. They are NEVER averaged into a session scalar
(Do-NOT #5), the AI side is never an ARI score, and no ARI score is touched (#2).

CSPC enters as PRECISION only (non-negotiable #2 / R2): it attenuates how much a
control signal moves the estimate (via `pi_s` in `human_weighted`) and widens the
credible interval — it never changes an ARI value. The precision definition is
IMPORTED from `src/merge/precision.py`, never re-implemented here:

  - per-turn precision π_t  → `turn_precision` (its output is `StateVector.precision`);
  - session/CI widening      → `widening_factor`;
  - the downstream flag       → `STATE_CONDITIONED_FLAG`.

Claim rung: ownership is DESIGNED until per-level ICC certification (Phase 3.2);
each result is flagged `uncertified_pending_icc` until then. Genuine (vs
displayed) ownership additionally needs the retention probe.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Mapping

from contracts.schemas import (
    Censored,
    ConfidenceInterval,
    Rung,
    ScoreStatus,
    StateValidity,
    StateVector,
)
from csl.crosswalk import ACF_LEVELS
from csl.projection import LevelEvidence, NeuronEvidence
from src.merge.precision import (  # imported precision definition — never reimplemented
    STATE_CONDITIONED_FLAG,
    turn_precision,
    widening_factor,
)

METHOD_VERSION = "csl-ownership-0.1"
#: ownership stays uncertified until per-level ICC (Phase 3.2) clears it.
UNCERTIFIED_FLAG = "uncertified_pending_icc"
DEFAULT_BOOTSTRAP_N = 1000
#: deterministic bootstrap seed (Phase 0 determinism requirement).
DEFAULT_SEED = 20260619


@dataclass(frozen=True)
class CSPCState:
    """Adapter over the implemented CSPC proxy outputs (the state channel).

    The spec names a `CSPCState`; the implemented surface is the per-turn
    `state_strip` (each `StateVector` carries `.precision`, the persisted output
    of `turn_precision`) plus the session `StateValidity`. `from_state` wraps them
    without recomputing any degradation.
    """

    state_strip: tuple[StateVector, ...] = ()
    state_validity: StateValidity = field(default_factory=StateValidity)

    @classmethod
    def from_state(
        cls,
        state_strip: list[StateVector] | tuple[StateVector, ...],
        state_validity: StateValidity,
    ) -> "CSPCState":
        return cls(state_strip=tuple(state_strip), state_validity=state_validity)

    def precision_by_turn(self) -> dict[int, float | None]:
        """turn_index → per-turn precision π_t (None = unassessable, absent ≠ full)."""
        out: dict[int, float | None] = {}
        for sv in self.state_strip:
            p = sv.precision
            if p is None and (sv.load is not None or sv.metacog is not None):
                # labels present but precision not persisted → derive from the
                # canonical definition rather than reinvent it.
                p, _ = turn_precision(
                    sv.load, sv.metacog,
                    compromised=self.state_validity.state_compromised,
                )
            out[sv.turn_index] = p
        return out

    def session_pi_s(self) -> float:
        """Session-level precision factor = 1 / canonical widening factor."""
        wf = widening_factor(self.state_validity, list(self.state_strip))
        return 1.0 / wf if wf > 0 else 1.0

    def widening(self) -> float:
        return widening_factor(self.state_validity, list(self.state_strip))


@dataclass(frozen=True)
class OwnershipResult:
    """One ACF level's displayed-ownership contrast (`SPEC_ownership.md` output).

    Never a bare percentage: a CI accompanies every OK value, and non-OK statuses
    explain why no percentage exists. There is no "what the human could do without
    AI" field — that is θ and needs the probe (Do-NOT #12).
    """

    level: str
    label: str
    status: ScoreStatus
    human_pct: float | None
    ai_pct: float | None
    ci: ConfidenceInterval | None
    n_eff: float
    pi_s: float | None
    censored: Censored | None
    rung: Rung
    method_version: str
    flags: tuple[str, ...] = ()


def compute_ownership(
    human: Mapping[str, LevelEvidence],
    ai: Mapping[str, float],
    cspc: CSPCState,
    *,
    min_n_eff: float = 1.0,
    bootstrap_n: int = DEFAULT_BOOTSTRAP_N,
    seed: int = DEFAULT_SEED,
) -> dict[str, OwnershipResult]:
    """Combine human + AI sides into a 7-vector of per-level ownership results.

    Returns exactly the seven ACF levels. Every OK result carries a CI; every
    non-OK result carries a status reason and no percentage. No session scalar is
    emitted (#5); no ARI score is modified (#2).
    """
    precision_map = cspc.precision_by_turn()
    session_widen = cspc.widening()
    results: dict[str, OwnershipResult] = {}

    for level in ACF_LEVELS:
        ev = human.get(level)
        ai_displayed = float(ai.get(level, 0.0))

        if ev is None or ev.status == ScoreStatus.NOT_APPLICABLE:
            results[level] = _non_ok(level, ev, ScoreStatus.NOT_APPLICABLE)
            continue
        if ev.status == ScoreStatus.INSUFFICIENT_SAMPLE or ev.n_eff < min_n_eff:
            results[level] = _non_ok(level, ev, ScoreStatus.INSUFFICIENT_SAMPLE)
            continue

        # human status is OK here: control_strength is a real number (#12 0-of-N
        # is a genuine 0.0, not absence).
        pi_s = _clamp_unit(_level_pi_s(ev, precision_map, cspc.session_pi_s()))
        control = ev.control_strength if ev.control_strength is not None else 0.0
        human_weighted = pi_s * control
        denom = human_weighted + ai_displayed

        if denom <= 0.0:
            # the level arose but neither side displayed a resolvable contribution:
            # no honest contrast, not a fabricated 50/50.
            results[level] = _non_ok(level, ev, ScoreStatus.INSUFFICIENT_SAMPLE, pi_s=pi_s)
            continue

        human_pct = human_weighted / denom
        ai_pct = ai_displayed / denom

        saturation = _saturation_for(ev, human_pct)
        if saturation is not None:
            results[level] = OwnershipResult(
                level=level, label=ev.label,
                status=ScoreStatus.MEASUREMENT_SATURATED,
                human_pct=None, ai_pct=None, ci=None,
                n_eff=ev.n_eff, pi_s=pi_s, censored=saturation,
                rung=Rung.DESIGNED, method_version=METHOD_VERSION,
                flags=_flags(session_widen),
            )
            continue

        ci = _bootstrap_ci(
            ev, ai_displayed, precision_map, cspc.session_pi_s(),
            session_widen, bootstrap_n, seed,
        )
        results[level] = OwnershipResult(
            level=level, label=ev.label,
            status=ScoreStatus.OK,
            human_pct=round(human_pct, 6),
            ai_pct=round(ai_pct, 6),
            ci=ci,
            n_eff=ev.n_eff, pi_s=round(pi_s, 6), censored=None,
            rung=Rung.DESIGNED, method_version=METHOD_VERSION,
            flags=_flags(session_widen),
        )

    return results


# ── helpers ───────────────────────────────────────────────────────────────────


def _flags(session_widen: float) -> tuple[str, ...]:
    flags = [UNCERTIFIED_FLAG]
    if session_widen > 1.0:
        flags.append(STATE_CONDITIONED_FLAG)
    return tuple(flags)


def _non_ok(
    level: str,
    ev: LevelEvidence | None,
    status: ScoreStatus,
    *,
    pi_s: float | None = None,
) -> OwnershipResult:
    return OwnershipResult(
        level=level,
        label=ev.label if ev is not None else level,
        status=status,
        human_pct=None, ai_pct=None, ci=None,
        n_eff=ev.n_eff if ev is not None else 0.0,
        pi_s=pi_s, censored=None,
        rung=Rung.DESIGNED, method_version=METHOD_VERSION,
        flags=(UNCERTIFIED_FLAG,),
    )


def _clamp_unit(x: float) -> float:
    return min(1.0, max(1e-9, x))


def _weighted_control(firings: tuple[NeuronEvidence, ...] | list[NeuronEvidence]) -> float:
    """Opportunity-weighted mean control strength (mirrors projection's reducer)."""
    wsum = 0.0
    wtot = 0.0
    psum = 0.0
    pcount = 0
    for fe in firings:
        if fe.control_value is None:
            continue
        psum += fe.control_value
        pcount += 1
        w = max(fe.n_eff, 0.0)
        wsum += fe.control_value * w
        wtot += w
    if wtot > 0:
        return wsum / wtot
    if pcount > 0:
        return psum / pcount
    return 0.0


def _level_pi_s(
    ev: LevelEvidence,
    precision_map: dict[int, float | None],
    session_pi_s: float,
) -> float:
    """pi_s(level): opportunity-weighted mean of per-turn precision over the turns
    that contributed to the level (§"CSPC Precision Hook"). Falls back to the
    session precision factor when no contributing turn has an assessable π_t."""
    wsum = 0.0
    wtot = 0.0
    for fe in ev.firings:
        turns = fe.evidence_turns
        if not turns:
            continue
        per_turn_weight = max(fe.n_eff, 0.0) / len(turns)
        for ti in turns:
            p = precision_map.get(ti)
            if p is None:
                continue
            wsum += p * per_turn_weight
            wtot += per_turn_weight
    if wtot > 0:
        return wsum / wtot
    return session_pi_s


def _saturation_for(ev: LevelEvidence, human_pct: float) -> Censored | None:
    """Censor when all applicable human evidence sits at an observable bound
    (§"Credible Intervals"): all controls at the ceiling → high; all at the floor
    → low. A saturated result reports a censored bound, not a point."""
    values = [fe.control_value for fe in ev.firings if fe.control_value is not None]
    if len(values) < 2:  # one record cannot establish a saturated bound
        return None
    if all(v >= 1.0 for v in values):
        return Censored(direction="high", bound=round(min(1.0, human_pct), 6))
    if all(v <= 0.0 for v in values):
        return Censored(direction="low", bound=round(max(0.0, human_pct), 6))
    return None


def _bootstrap_ci(
    ev: LevelEvidence,
    ai_displayed: float,
    precision_map: dict[int, float | None],
    session_pi_s: float,
    session_widen: float,
    bootstrap_n: int,
    seed: int,
) -> ConfidenceInterval:
    """95% bootstrap CI on human ownership (§"Credible Intervals").

    Resamples the contributing human firing records with replacement; AI side is
    fixed (deterministic extractor). Each replicate recomputes control_b, pi_s_b,
    and human_ownership_b. The percentile interval is then widened by the canonical
    `widening_factor` to realise CSPC's CI-widening effect (separate from the
    pi_s attenuation already in the point estimate).
    """
    firings = list(ev.firings)
    point = _human_ownership(firings, ai_displayed, precision_map, session_pi_s)

    if len(firings) >= 2 and bootstrap_n > 0:
        rng = random.Random(seed)
        n = len(firings)
        samples: list[float] = []
        for _ in range(bootstrap_n):
            resample = [firings[rng.randrange(n)] for _ in range(n)]
            val = _human_ownership(resample, ai_displayed, precision_map, session_pi_s)
            if val is not None:
                samples.append(val)
        if samples:
            lo = _percentile(samples, 2.5)
            hi = _percentile(samples, 97.5)
        else:
            lo = hi = point if point is not None else 0.0
    else:
        # a single firing has no resampling variance — an honest point interval,
        # still widened below by state precision.
        lo = hi = point if point is not None else 0.0

    return _widen_clamped(lo, hi, session_widen)


def _human_ownership(
    firings: list[NeuronEvidence],
    ai_displayed: float,
    precision_map: dict[int, float | None],
    session_pi_s: float,
) -> float | None:
    control_b = _weighted_control(firings)
    # rebuild a thin level view so _level_pi_s can reuse the same turn weighting
    pi_s_b = _clamp_unit(_level_pi_s_from_firings(firings, precision_map, session_pi_s))
    hw = pi_s_b * control_b
    denom = hw + ai_displayed
    if denom <= 0.0:
        return None
    return hw / denom


def _level_pi_s_from_firings(
    firings: list[NeuronEvidence],
    precision_map: dict[int, float | None],
    session_pi_s: float,
) -> float:
    wsum = 0.0
    wtot = 0.0
    for fe in firings:
        turns = fe.evidence_turns
        if not turns:
            continue
        per_turn_weight = max(fe.n_eff, 0.0) / len(turns)
        for ti in turns:
            p = precision_map.get(ti)
            if p is None:
                continue
            wsum += p * per_turn_weight
            wtot += per_turn_weight
    return wsum / wtot if wtot > 0 else session_pi_s


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (pct / 100.0) * (len(ordered) - 1)
    lo_idx = int(rank)
    hi_idx = min(lo_idx + 1, len(ordered) - 1)
    frac = rank - lo_idx
    return ordered[lo_idx] + (ordered[hi_idx] - ordered[lo_idx]) * frac


def _widen_clamped(lo: float, hi: float, factor: float) -> ConfidenceInterval:
    """Widen [lo, hi] symmetrically around its midpoint by `factor`, clamped to
    [0, 1]. `factor` is the canonical `widening_factor` output — the degradation
    rule is imported; only this clamp geometry is local."""
    mid = (lo + hi) / 2.0
    half = (hi - lo) / 2.0 * max(factor, 1.0)
    return ConfidenceInterval(low=max(0.0, mid - half), high=min(1.0, mid + half))
