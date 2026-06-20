from __future__ import annotations

import pytest

from csl.validation.independence import independence


def test_independence_flags_near_perfect_correlation():
    ari = [{"EC": i / 10, "CS": (10 - i) / 10} for i in range(10)]
    csl = [{"C3": i / 10, "C4": 0.3} for i in range(10)]

    result = independence(ari, csl, min_n=8, near_one_threshold=0.95)

    flagged = {(row.ari_key, row.csl_key) for row in result.flagged}
    assert ("EC", "C3") in flagged
    assert ("CS", "C3") in flagged
    assert all(row.correlation is None for row in result.per_pair if row.csl_key == "C4")


def test_independence_drops_missing_pairwise_without_zero_fill():
    ari = [{"EC": 0.1}, {"EC": None}, {"EC": 0.3}, {"EC": "bad"}]
    csl = [{"C3": 0.2}, {"C3": 0.4}, {"C3": None}, {"C3": 0.8}]

    result = independence(ari, csl, min_n=2)

    row = result.per_pair[0]
    assert row.n == 1
    assert row.correlation is None
    assert row.flag_if_near_one is False


def test_independence_rejects_unaligned_inputs():
    with pytest.raises(ValueError, match="same session count"):
        independence([{"EC": 0.1}], [])


def test_independence_rejects_bad_thresholds():
    with pytest.raises(ValueError, match="near_one_threshold"):
        independence([], [], near_one_threshold=0)
    with pytest.raises(ValueError, match="min_n"):
        independence([], [], min_n=1)

