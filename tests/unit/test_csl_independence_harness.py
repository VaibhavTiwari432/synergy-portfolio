"""Phase 3.1 acceptance — independence harness over real score rows (data-gated).

The harness fails LOUD below the corpus gate (min_sessions=8) and, above it,
delegates to independence() over aligned ARI-dimension vs CSL-ownership rows,
flagging any near-1.0 pair (partition failure: CSL re-measuring ARI).
"""

from __future__ import annotations

import pytest

from contracts.schemas import (
    ConfidenceInterval,
    Dimension,
    DimensionScore,
    Rung,
    ScoreStatus,
)
from csl.ownership import OwnershipResult
from csl.validation import (
    CorpusInsufficientError,
    DataGatedError,
    ari_row,
    csl_row,
    run_independence_check,
)


def _profile(values: dict[Dimension, float | None]):
    out = {}
    for dim in Dimension:
        v = values.get(dim)
        if v is None:
            out[dim] = DimensionScore(dim=dim, status=ScoreStatus.NOT_APPLICABLE,
                                      rung=Rung.MEASURABLE)
        else:
            out[dim] = DimensionScore(
                dim=dim, status=ScoreStatus.OK, value=v,
                ci=ConfidenceInterval(low=max(0.0, v - 0.05), high=min(1.0, v + 0.05)),
                n_eff=5.0, rung=Rung.MEASURABLE)
    return out


def _ownership(shares: dict[str, float | None]):
    out = {}
    for level, pct in shares.items():
        if pct is None:
            out[level] = OwnershipResult(
                level=level, label=f"{level}-l", status=ScoreStatus.NOT_APPLICABLE,
                human_pct=None, ai_pct=None, ci=None, n_eff=0.0, pi_s=None,
                censored=None, rung=Rung.DESIGNED, method_version="t", flags=())
        else:
            out[level] = OwnershipResult(
                level=level, label=f"{level}-l", status=ScoreStatus.OK,
                human_pct=pct, ai_pct=round(1 - pct, 6),
                ci=ConfidenceInterval(low=max(0.0, pct - 0.1), high=min(1.0, pct + 0.1)),
                n_eff=3.0, pi_s=1.0, censored=None, rung=Rung.DESIGNED,
                method_version="t", flags=())
    return out


# ── data gate ───────────────────────────────────────────────────────────────────


def test_gate_fires_loud_below_min_sessions():
    sessions = [
        (_profile({Dimension.EC: 0.5}), _ownership({"C3": 0.5}))
        for _ in range(3)
    ]
    with pytest.raises(CorpusInsufficientError) as exc:
        run_independence_check(sessions)
    err = exc.value
    assert isinstance(err, DataGatedError)
    assert err.gate == "csl_independence_check"
    assert err.have == 3 and err.need == 8
    assert "corpus" in err.requires.lower()


def test_gate_message_is_structured_and_loud():
    with pytest.raises(CorpusInsufficientError, match="data-gated"):
        run_independence_check([])


def test_runs_at_exactly_min_sessions():
    sessions = [
        (_profile({Dimension.EC: 0.5 + i * 0.01}), _ownership({"C3": 0.4 + i * 0.02}))
        for i in range(8)
    ]
    result = run_independence_check(sessions)
    assert result.min_n == 8
    assert result.per_pair  # at least the EC x C3 pair was computed


# ── row extraction (OK only; absent != zero) ────────────────────────────────────


def test_ari_row_takes_ok_values_only():
    profile = _profile({Dimension.EC: 0.7, Dimension.CS: None, Dimension.AL: 0.3})
    row = ari_row(profile)
    assert row == {"EC": 0.7, "AL": 0.3}
    assert "CS" not in row  # NOT_APPLICABLE dim is absent, not zero


def test_csl_row_takes_ok_levels_only():
    ownership = _ownership({"C3": 0.6, "C4": None, "C5": 0.2})
    row = csl_row(ownership)
    assert row == {"C3": 0.6, "C5": 0.2}
    assert "C4" not in row


# ── partition-failure flagging ──────────────────────────────────────────────────


def test_perfectly_correlated_pair_is_flagged_as_partition_failure():
    # EC value and C3 share move together perfectly -> correlation ~1.0 -> flagged.
    sessions = []
    for i in range(10):
        v = 0.1 * i
        sessions.append((_profile({Dimension.EC: v}), _ownership({"C3": v})))
    result = run_independence_check(sessions)
    flagged_pairs = {(r.ari_key, r.csl_key) for r in result.flagged}
    assert ("EC", "C3") in flagged_pairs


def test_independent_pair_is_not_flagged():
    # EC constant-ish vs C3 varying -> no near-1.0 correlation.
    sessions = []
    for i in range(10):
        sessions.append((
            _profile({Dimension.EC: 0.5}),
            _ownership({"C3": 0.1 * i}),
        ))
    result = run_independence_check(sessions)
    # constant EC -> zero variance -> correlation None -> never flagged
    assert all(not r.flag_if_near_one for r in result.per_pair)
