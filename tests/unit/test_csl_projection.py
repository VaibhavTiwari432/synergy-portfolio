"""Phase 2.1 acceptance — human-side re-projection (csl/projection.py).

Acceptance (v3.2 §2.1): on a fixture matrix, projecting yields 7 level-evidence
objects; a neuron firing contributes to exactly the levels the crosswalk assigns;
non-applicable neurons never contribute.
"""

from __future__ import annotations

from contracts.schemas import ScoreStatus
from csl.crosswalk import ACF_LEVELS, load_acf_crosswalk
from csl.projection import NeuronMatrix, project_to_acf


def _row(code: str, dimension: str, value: float, opps: int, turns=()):
    return {
        "neuron_code": code,
        "dimension": dimension,
        "value": value,
        "applicable_opportunities": opps,
        "n_eff": float(opps),
        "evidence_turn_indices": list(turns),
        "extractor_version": "test",
    }


def test_projection_yields_exactly_seven_levels():
    crosswalk = load_acf_crosswalk()
    matrix = NeuronMatrix.from_firing_rows([_row("AL-08", "AL", 0.5, 2)])

    result = project_to_acf(matrix, crosswalk)

    assert tuple(result) == ACF_LEVELS
    assert len(result) == 7


def test_firing_contributes_to_exactly_its_crosswalk_levels():
    crosswalk = load_acf_crosswalk()
    # AL-08 maps to C1 and C3 in the frozen crosswalk; nowhere else.
    expected_levels = set(crosswalk.levels_for("AL-08"))
    assert expected_levels  # guard: the sentinel mapping exists

    matrix = NeuronMatrix.from_firing_rows([_row("AL-08", "AL", 0.8, 3, turns=(4,))])
    result = project_to_acf(matrix, crosswalk)

    contributing_levels = {
        level
        for level, ev in result.items()
        if any(f.neuron_id == "AL-08" for f in ev.firings)
    }
    assert contributing_levels == expected_levels


def test_non_applicable_neurons_never_contribute():
    crosswalk = load_acf_crosswalk()
    # An empty matrix: every level is NOT_APPLICABLE, no firings, no fabricated 0.
    result = project_to_acf(NeuronMatrix.from_firing_rows([]), crosswalk)

    for level, ev in result.items():
        assert ev.status == ScoreStatus.NOT_APPLICABLE
        assert ev.control_strength is None
        assert ev.firings == ()
        assert ev.n_eff == 0.0
        assert ev.applicable_count == 0


def test_unmapped_level_stays_not_applicable_when_only_other_levels_fire():
    crosswalk = load_acf_crosswalk()
    matrix = NeuronMatrix.from_firing_rows([_row("AL-08", "AL", 0.5, 2)])
    result = project_to_acf(matrix, crosswalk)

    al08_levels = set(crosswalk.levels_for("AL-08"))
    for level in ACF_LEVELS:
        if level in al08_levels:
            assert result[level].status == ScoreStatus.OK
        else:
            assert result[level].status == ScoreStatus.NOT_APPLICABLE


def test_control_strength_is_opportunity_weighted_mean():
    crosswalk = load_acf_crosswalk()
    # Two neurons that both map to C3 (EC-01 checking, EC-06 both in C3).
    c3_neurons = list(crosswalk.levels["C3"]["neurons"])
    a, b = c3_neurons[0], c3_neurons[1]
    dim_a = a.split("-")[0]
    dim_b = b.split("-")[0]

    matrix = NeuronMatrix.from_firing_rows([
        _row(a, dim_a, 1.0, 3),   # value 1.0, weight 3
        _row(b, dim_b, 0.0, 1),   # value 0.0, weight 1
    ])
    result = project_to_acf(matrix, crosswalk)

    c3 = result["C3"]
    assert c3.status == ScoreStatus.OK
    # weighted mean = (1.0*3 + 0.0*1) / (3+1) = 0.75
    assert c3.control_strength == 0.75
    assert c3.n_eff == 4.0
    assert c3.applicable_count == 2


def test_insufficient_sample_when_n_eff_below_threshold():
    crosswalk = load_acf_crosswalk()
    matrix = NeuronMatrix.from_firing_rows([_row("AL-08", "AL", 0.5, 1)])

    result = project_to_acf(matrix, crosswalk, min_n_eff=2.0)
    for level in crosswalk.levels_for("AL-08"):
        ev = result[level]
        assert ev.status == ScoreStatus.INSUFFICIENT_SAMPLE
        assert ev.control_strength is None
        assert ev.firings  # the records are retained for audit, just not scored


def test_zero_of_n_firing_is_applicable_not_absent():
    crosswalk = load_acf_crosswalk()
    # opportunity arose, behaviour provably did not occur -> value 0.0, applicable.
    matrix = NeuronMatrix.from_firing_rows([_row("AL-08", "AL", 0.0, 2)])
    result = project_to_acf(matrix, crosswalk)

    for level in crosswalk.levels_for("AL-08"):
        ev = result[level]
        assert ev.status == ScoreStatus.OK
        assert ev.control_strength == 0.0
        assert ev.applicable_count == 1


def test_no_session_level_scalar_is_emitted():
    crosswalk = load_acf_crosswalk()
    matrix = NeuronMatrix.from_firing_rows([_row("AL-08", "AL", 0.7, 2)])
    result = project_to_acf(matrix, crosswalk)

    # The contract is a 7-vector; there is no aggregate key (Do-NOT #5).
    assert set(result) == set(ACF_LEVELS)
    assert "session" not in result and "overall" not in result


def test_unobserved_ids_list_mapped_but_unfired_neurons():
    crosswalk = load_acf_crosswalk()
    matrix = NeuronMatrix.from_firing_rows([_row("AL-08", "AL", 0.5, 2)])
    result = project_to_acf(matrix, crosswalk)

    # C1 maps many neurons; only AL-08 fired, the rest are unobserved (not zero).
    c1 = result["C1"]
    assert "AL-08" not in c1.unobserved_ids
    assert set(c1.unobserved_ids) == set(crosswalk.levels["C1"]["neurons"]) - {"AL-08"}
