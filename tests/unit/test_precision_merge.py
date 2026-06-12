"""Synthetic-fixture tests for the precision merge (Stage-2 Gate C, run early):
precision moves CIs, NEVER scores. OWNER: Chief Engineer."""

from __future__ import annotations

from contracts.schemas import (
    ConfidenceInterval,
    Dimension,
    DimensionScore,
    LoadLabel,
    MetacogLabel,
    Rung,
    ScoreStatus,
    StateValidity,
    StateVector,
)
from src.merge.precision import (
    STATE_CONDITIONED_FLAG,
    degraded_share,
    merge,
    widening_factor,
)


def _scores() -> dict[Dimension, DimensionScore]:
    out: dict[Dimension, DimensionScore] = {}
    for i, dim in enumerate(Dimension):
        if dim == Dimension.ES:
            out[dim] = DimensionScore(
                dim=dim, status=ScoreStatus.NOT_APPLICABLE, rung=Rung.MEASURABLE,
                status_reason="no_ethics_events_detected",
            )
        else:
            v = 0.3 + i * 0.05
            out[dim] = DimensionScore(
                dim=dim, status=ScoreStatus.OK, value=v,
                ci=ConfidenceInterval(low=max(0.0, v - 0.1), high=min(1.0, v + 0.1)),
                n_eff=5.0, rung=Rung.MEASURABLE,
            )
    return out


def _strip(labels: list[tuple]) -> list[StateVector]:
    return [
        StateVector(turn_index=2 * i, load=load, metacog=meta)
        for i, (load, meta) in enumerate(labels)
    ]


CLEAN = StateValidity()
COMPROMISED = StateValidity(state_compromised=True, m_t_collapse=True, surrender_detected=True)


# ── the audit invariant: values never change ─────────────────────────────────


def test_values_identical_under_any_state():
    scores = _scores()
    for validity, strip in [
        (CLEAN, []),
        (COMPROMISED, []),
        (COMPROMISED, _strip([(LoadLabel.HIGH_ECL, MetacogLabel.SURRENDER)] * 6)),
        (CLEAN, _strip([(LoadLabel.FATIGUE, None)] * 3)),
    ]:
        merged = merge(scores, validity, strip)
        for dim in Dimension:
            assert merged[dim].value == scores[dim].value          # R2, structurally
            assert merged[dim].status == scores[dim].status
            assert merged[dim].n_eff == scores[dim].n_eff


def test_high_ecl_state_widens_ci_score_unchanged():
    """The named synthetic fixture: HIGH_ECL → wider CI, same value."""
    scores = _scores()
    strip = _strip([(LoadLabel.HIGH_ECL, None)] * 4)
    merged = merge(scores, CLEAN, strip)
    for dim in Dimension:
        if scores[dim].ci is None:
            continue
        assert merged[dim].value == scores[dim].value
        assert merged[dim].ci.width > scores[dim].ci.width
        assert STATE_CONDITIONED_FLAG in merged[dim].flags


def test_clean_state_is_a_no_op():
    scores = _scores()
    merged = merge(scores, CLEAN, _strip([(LoadLabel.LOW_LOAD, MetacogLabel.ACTIVE)] * 4))
    assert merged == scores


def test_compromised_state_widens_everything():
    scores = _scores()
    merged = merge(scores, COMPROMISED, [])
    for dim in Dimension:
        if scores[dim].ci is None:
            continue
        assert merged[dim].ci.width > scores[dim].ci.width
        # 1.5× exactly, when no strip degradation and no clamping
        if 0.0 < merged[dim].ci.low and merged[dim].ci.high < 1.0:
            assert abs(merged[dim].ci.width - scores[dim].ci.width * 1.5) < 1e-9


def test_widening_clamps_to_unit_interval():
    scores = {
        Dimension.AL: DimensionScore(
            dim=Dimension.AL, status=ScoreStatus.OK, value=0.95,
            ci=ConfidenceInterval(low=0.85, high=1.0), n_eff=3.0, rung=Rung.MEASURABLE,
        )
    }
    merged = merge(scores, COMPROMISED, _strip([(LoadLabel.FATIGUE, MetacogLabel.SURRENDER)] * 5))
    ci = merged[Dimension.AL].ci
    assert 0.0 <= ci.low <= ci.high <= 1.0
    assert merged[Dimension.AL].value == 0.95


def test_absent_scores_pass_through_untouched():
    scores = _scores()
    merged = merge(scores, COMPROMISED, [])
    es = merged[Dimension.ES]
    assert es.status == ScoreStatus.NOT_APPLICABLE
    assert es.value is None and es.ci is None
    assert STATE_CONDITIONED_FLAG not in es.flags


# ── graded widening mechanics ────────────────────────────────────────────────


def test_degraded_share_counts_only_degraded_labels():
    strip = _strip([
        (LoadLabel.LOW_LOAD, MetacogLabel.ACTIVE),
        (LoadLabel.HIGH_ICL, MetacogLabel.PASSIVE),   # ICL is productive load — not degraded
        (LoadLabel.HIGH_ECL, None),
        (None, MetacogLabel.SURRENDER),
        (None, None),                                  # absent ≠ degraded
    ])
    assert degraded_share(strip) == 2 / 5


def test_widening_factor_composition():
    assert widening_factor(CLEAN, []) == 1.0
    assert widening_factor(COMPROMISED, []) == 1.5
    half_degraded = _strip([(LoadLabel.HIGH_ECL, None), (LoadLabel.LOW_LOAD, None)])
    assert widening_factor(CLEAN, half_degraded) == 1.25
    assert widening_factor(COMPROMISED, half_degraded) == 1.875


def test_no_multiplier_on_values_even_via_flags():
    # the only mutation surface is ci + flags; everything else is identity
    scores = _scores()
    merged = merge(scores, COMPROMISED, _strip([(LoadLabel.HIGH_ECL, None)] * 2))
    for dim in Dimension:
        a, b = scores[dim], merged[dim]
        assert (a.value, a.status, a.n_eff, a.raw_counts, a.rung,
                a.evidence_turns, a.provenance_share_displayed, a.status_reason) == (
                b.value, b.status, b.n_eff, b.raw_counts, b.rung,
                b.evidence_turns, b.provenance_share_displayed, b.status_reason)
