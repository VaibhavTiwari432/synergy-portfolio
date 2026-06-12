"""Unit tests for count normalization (leaf)."""

from __future__ import annotations

import pytest

from contracts.schemas import Dimension, ScoreStatus
from src.aggregate.normalize import normalize_counts


def test_all_eight_dimensions_always_present():
    result = normalize_counts({}, {})
    assert set(result.per_dimension.keys()) == set(Dimension)
    for dn in result.per_dimension.values():
        assert dn.status == ScoreStatus.NOT_APPLICABLE
        assert dn.normalized is None


def test_mean_over_neurons_with_opportunities():
    firings = {Dimension.EC: {"EC-06": 0.5, "EC-07": 1.0}}
    opportunities = {Dimension.EC: {"EC-06": 4, "EC-07": 2, "EC-09": 3}}
    result = normalize_counts(firings, opportunities)
    ec = result.per_dimension[Dimension.EC]
    assert ec.status == ScoreStatus.OK
    # EC-09 had opportunities, no firing → measured 0; mean over 3 neurons
    assert ec.normalized == pytest.approx((0.5 + 1.0 + 0.0) / 3)
    assert ec.fired_weight == pytest.approx(1.5)
    assert ec.applicable_opportunities == 9


def test_neuron_count_standardization_no_structural_edge():
    # 1 active neuron at 0.6 in one dim vs 4 active neurons at 0.6 in another:
    # identical normalized value — more neurons must not mean more score
    one = normalize_counts(
        {Dimension.AL: {"AL-08": 0.6}}, {Dimension.AL: {"AL-08": 5}}
    ).per_dimension[Dimension.AL]
    four = normalize_counts(
        {Dimension.PR: {f"PR-0{i}": 0.6 for i in range(1, 5)}},
        {Dimension.PR: {f"PR-0{i}": 5 for i in range(1, 5)}},
    ).per_dimension[Dimension.PR]
    assert one.normalized == pytest.approx(four.normalized)


def test_zero_opportunity_neurons_are_excluded_entirely():
    result = normalize_counts(
        {Dimension.ES: {}}, {Dimension.ES: {"ES-01": 0}}
    )
    es = result.per_dimension[Dimension.ES]
    assert es.status == ScoreStatus.NOT_APPLICABLE  # 0-opportunity ≠ measured zero
    assert es.normalized is None


def test_strengths_clamped_to_unit_interval():
    result = normalize_counts(
        {Dimension.AL: {"AL-08": 1.7}}, {Dimension.AL: {"AL-08": 2}}
    )
    assert result.per_dimension[Dimension.AL].normalized == 1.0


def test_pure_and_deterministic():
    firings = {Dimension.EC: {"EC-06": 0.25}}
    opps = {Dimension.EC: {"EC-06": 4}}
    assert normalize_counts(firings, opps) == normalize_counts(firings, opps)
