"""CSL Phase 2.1 — human-side re-projection (NO new extraction).

The CSL human side is a *re-aggregation of the already-computed `NeuronMatrix`*,
not a second pass over the transcript (v3.2 §2.1 / Do-NOT #1). Re-running
extraction for the human side would re-introduce the double-measurement bug the
Phase-1.2 prompt partition (ADR-0011) exists to prevent.

One human extraction, two aggregations:

1. the existing ARI dimension scores (owned by the trait channel); and
2. these CSL ACF-level foundation-evidence objects.

The `NeuronMatrix` consumed here is the per-neuron evidence the pipeline already
materialises — `pipeline._neuron_firing_rows(...)` / `ScoreRun.neuron_firings`.
Those are the deterministic per-neuron firings: the things that actually *fire*
in the transcript (verification, recency-flagging, constraint injection, ...).
The 98 llm_judge neurons are dimension-grain by construction (the judge is not a
per-neuron instrument) and so are not per-neuron firings — that is a known scope
boundary documented in the pipeline, not a drop. Judge-grain foundation evidence
is the job of the partitioned CSL foundation prompt (later in Phase 2), never of
this re-projection, which calls no judge and reads no transcript.

`project_to_acf` therefore gathers, per ACF level, the firings of exactly the
neurons the frozen crosswalk maps to that level, and folds them into a
`LevelEvidence`. The credible interval is intentionally left `None` here: the
ownership layer (Phase 2.3) derives it by bootstrap with CSPC precision
(`SPEC_ownership.md` §"Credible Intervals"). Phase 2.1 owns only the projection
mechanics, never the score value of any ARI dimension (Do-NOT #2).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any, Literal

from contracts.schemas import ScoreStatus

from csl.crosswalk import ACF_LEVELS, ACFCrosswalk

#: source of a neuron's evidence. "deterministic" = a per-neuron extractor firing
#: (the only per-neuron grain that exists today). "judge" is reserved for a future
#: per-level foundation read and is not produced by this re-projection.
EvidenceSource = Literal["deterministic", "judge"]


@dataclass(frozen=True)
class NeuronEvidence:
    """One neuron's already-computed human-side evidence.

    A faithful wrapper over a single `ScoreRun.neuron_firings` row. `applicable`
    is False only when the neuron's opportunity never arose — and per the
    absent-≠-zero rule (#12) such a neuron is simply absent from the matrix, so
    `applicable` is True for every row the pipeline emits. The field is kept
    explicit so a future judge-grain source can mark structural non-applicability
    without changing the projection contract.
    """

    neuron_id: str
    dimension: str
    #: foundation-backed control strength on [0, 1]; None only when not applicable.
    control_value: float | None
    applicable: bool
    #: applicable opportunities backing this neuron (0-of-N is still applicable).
    opportunities: int
    #: effective contributing opportunities for bootstrap weighting.
    n_eff: float
    evidence_turns: tuple[int, ...] = ()
    source: EvidenceSource = "deterministic"


@dataclass(frozen=True)
class NeuronMatrix:
    """The already-computed per-neuron human evidence, keyed by neuron id.

    Built from the pipeline's persisted firing rows — never by re-extraction.
    """

    evidence: dict[str, NeuronEvidence]

    def get(self, neuron_id: str) -> NeuronEvidence | None:
        return self.evidence.get(neuron_id)

    @classmethod
    def from_firing_rows(cls, rows: Iterable[Mapping[str, Any]]) -> "NeuronMatrix":
        """Wrap `ScoreRun.neuron_firings` rows into a matrix.

        Each row carries: neuron_code, dimension, value, applicable_opportunities,
        n_eff, evidence_turn_indices, extractor_version. A row exists only when an
        opportunity arose (absent ≠ zero), so every wrapped neuron is applicable.
        Later rows for the same neuron id replace earlier ones (last write wins),
        which never happens within a single ScoreRun.
        """
        evidence: dict[str, NeuronEvidence] = {}
        for row in rows:
            neuron_id = str(row["neuron_code"])
            value = row.get("value")
            evidence[neuron_id] = NeuronEvidence(
                neuron_id=neuron_id,
                dimension=str(row.get("dimension", neuron_id.split("-", 1)[0])),
                control_value=None if value is None else float(value),
                applicable=True,
                opportunities=int(row.get("applicable_opportunities", 0)),
                n_eff=float(row.get("n_eff", row.get("applicable_opportunities", 0))),
                evidence_turns=tuple(int(t) for t in row.get("evidence_turn_indices", [])),
                source="deterministic",
            )
        return cls(evidence=evidence)


@dataclass(frozen=True)
class LevelEvidence:
    """Foundation evidence re-projected onto one ACF level (`SPEC_ownership.md`).

    `ci` is deliberately None at projection time; ownership (Phase 2.3) derives it
    by bootstrap with CSPC precision. `control_strength` is the opportunity-weighted
    mean foundation strength of the level's applicable mapped neurons.
    """

    level: str
    label: str
    status: ScoreStatus
    #: weighted foundation-backed human evidence on [0, 1]; None unless status OK.
    control_strength: float | None
    #: effective contributing opportunities after non-applicable firings removed.
    n_eff: float
    #: number of mapped neurons that actually contributed (were applicable).
    applicable_count: int
    #: the contributing neuron/opportunity records, for the Phase-2.3 bootstrap.
    firings: tuple[NeuronEvidence, ...] = ()
    #: precomputed interval if any; ownership derives it by bootstrap otherwise.
    ci: Any | None = None
    #: ids the crosswalk maps to this level but for which no evidence exists yet
    #: (e.g. judge-grain neurons, or deterministic neurons whose opportunity never
    #: arose). Kept for transparency; never coerced to zero (#12).
    unobserved_ids: tuple[str, ...] = field(default_factory=tuple)


def project_to_acf(
    matrix: NeuronMatrix,
    crosswalk: ACFCrosswalk,
    *,
    min_n_eff: float = 1.0,
    precision_map: "dict[int, float | None] | None" = None,
) -> dict[str, LevelEvidence]:
    """Re-project an already-computed `NeuronMatrix` onto the seven ACF levels.

    For each level the crosswalk defines, gather the firings of exactly its mapped
    neurons (a firing contributes to precisely the levels the crosswalk assigns),
    drop non-applicable neurons, and fold the rest into a `LevelEvidence`.

    Status per level:
      - NOT_APPLICABLE  — no mapped neuron's opportunity arose (no denominator).
      - INSUFFICIENT_SAMPLE — opportunities arose but n_eff < `min_n_eff`.
      - OK — enough evidence; `control_strength` is populated.

    F1: when `precision_map` (turn_index → π_t) is provided, control_strength is
    weighted by mean per-turn precision of each neuron's evidence turns, realising
    state-conditioned pooling without emitting per-segment composites (L12).

    This calls no extractor, reads no transcript, and never touches an ARI score.
    """
    results: dict[str, LevelEvidence] = {}

    for level in ACF_LEVELS:
        entry = crosswalk.levels[level]
        label = str(entry["label"])
        mapped_ids: tuple[str, ...] = tuple(entry["neurons"])

        contributing: list[NeuronEvidence] = []
        unobserved: list[str] = []
        for neuron_id in mapped_ids:
            ev = matrix.get(neuron_id)
            if ev is None or not ev.applicable:
                unobserved.append(neuron_id)
                continue
            contributing.append(ev)

        n_eff = sum(ev.n_eff for ev in contributing)
        applicable_count = len(contributing)

        if applicable_count == 0:
            results[level] = LevelEvidence(
                level=level,
                label=label,
                status=ScoreStatus.NOT_APPLICABLE,
                control_strength=None,
                n_eff=0.0,
                applicable_count=0,
                firings=(),
                unobserved_ids=tuple(unobserved),
            )
            continue

        if n_eff < min_n_eff:
            results[level] = LevelEvidence(
                level=level,
                label=label,
                status=ScoreStatus.INSUFFICIENT_SAMPLE,
                control_strength=None,
                n_eff=n_eff,
                applicable_count=applicable_count,
                firings=tuple(contributing),
                unobserved_ids=tuple(unobserved),
            )
            continue

        control_strength = _weighted_control_strength(contributing, precision_map)
        results[level] = LevelEvidence(
            level=level,
            label=label,
            status=ScoreStatus.OK,
            control_strength=control_strength,
            n_eff=n_eff,
            applicable_count=applicable_count,
            firings=tuple(contributing),
            unobserved_ids=tuple(unobserved),
        )

    return results


def _weighted_control_strength(
    firings: Iterable[NeuronEvidence],
    precision_map: "dict[int, float | None] | None" = None,
) -> float:
    """Opportunity-weighted mean of applicable foundation values.

    F1: when precision_map is given, each neuron's base n_eff weight is further
    scaled by the mean precision of its evidence turns, so turns in degraded state
    contribute proportionally less to the projection (L12 — per-turn π pooling,
    not session-level widening). Missing precision entries don't suppress the
    neuron — they contribute at the neuron's plain n_eff weight (#12).
    """
    weighted_sum = 0.0
    weight_total = 0.0
    plain_sum = 0.0
    plain_count = 0
    for ev in firings:
        if ev.control_value is None:
            continue
        plain_sum += ev.control_value
        plain_count += 1
        base_weight = max(ev.n_eff, 0.0)
        if precision_map is not None and ev.evidence_turns:
            precisions = [precision_map.get(t) for t in ev.evidence_turns]
            valid = [p for p in precisions if p is not None]
            prec_scale = sum(valid) / len(valid) if valid else 1.0
            weight = base_weight * prec_scale
        else:
            weight = base_weight
        weighted_sum += ev.control_value * weight
        weight_total += weight
    if weight_total > 0:
        return round(weighted_sum / weight_total, 6)
    if plain_count > 0:
        return round(plain_sum / plain_count, 6)
    return 0.0
