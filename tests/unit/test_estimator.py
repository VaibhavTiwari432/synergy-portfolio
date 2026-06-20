"""Unit tests for StateEstimator / ProxyEstimator. OWNER: Chief Engineer."""

from __future__ import annotations

from contracts.schemas import (
    CanonicalSession,
    LoadLabel,
    MetacogLabel,
    MetacogResult,
    PartnerModel,
    Turn,
    TurnTags,
)
from src.state.estimator import ProxyEstimator, StateEstimator


def _session(n_human: int = 4) -> CanonicalSession:
    turns: list[Turn] = []
    for i in range(n_human):
        turns.append(Turn(index=len(turns), role="human", text=f"q{i}"))
        turns.append(Turn(index=len(turns), role="ai", text=f"a{i}"))
    return CanonicalSession(
        session_id="st-1", source="plaintext",
        partner_model=PartnerModel(family="openai"), turns=turns,
    )


def _tags(session: CanonicalSession) -> list[TurnTags]:
    return [TurnTags(turn_index=t.index, tags=[]) for t in session.turns if t.role == "human"]


def test_proxy_estimator_is_a_state_estimator():
    assert issubclass(ProxyEstimator, StateEstimator)


def test_all_channels_wired():
    s = _session(4)
    est = ProxyEstimator(
        classify_load=lambda sess: [LoadLabel.LOW_LOAD] * 4,
        classify_epistemic=lambda sess, tags: [0.5, 0.5, -0.5, -0.5],
        classify_metacog=lambda sess, tags: MetacogResult(
            labels=[MetacogLabel.ACTIVE] * 4, surrender_detected=False
        ),
        tom_slope=lambda sess: ([0.1, 0.2, 0.3, 0.4], 0.1),
    )
    strip, validity = est.estimate(s, _tags(s))
    assert len(strip) == 4
    assert strip[0].turn_index == 0 and strip[1].turn_index == 2  # human turn indices
    assert all(v.confidence == 1.0 for v in strip)
    assert all(v.a_t is None for v in strip)  # Tier-2 stub stays None
    assert validity.state_compromised is False
    assert validity.epistemic_mean == 0.0
    assert validity.epistemic_slope == -1.0  # second half mean − first half mean
    assert validity.tom_slope == 0.1
    assert validity.caveats == []


def test_missing_channels_are_none_with_caveats_never_fabricated():
    s = _session(3)
    strip, validity = ProxyEstimator().estimate(s, _tags(s))
    assert len(strip) == 3
    for v in strip:
        assert v.load is None and v.epistemic is None
        assert v.metacog is None and v.tom_signal is None
        assert v.confidence == 0.0
    assert {"load_unavailable", "epistemic_unavailable",
            "metacog_unavailable", "tom_unavailable"} <= set(validity.caveats)
    assert validity.state_compromised is False  # no evidence ≠ collapse
    assert validity.epistemic_mean is None


def test_surrender_compromises_state_and_reports_caveat():
    s = _session(4)
    est = ProxyEstimator(
        classify_metacog=lambda sess, tags: MetacogResult(
            labels=[MetacogLabel.ACTIVE, MetacogLabel.SURRENDER,
                    MetacogLabel.SURRENDER, MetacogLabel.SURRENDER],
            surrender_detected=True,
            surrender_onset_turn=2,
        ),
    )
    strip, validity = est.estimate(s, _tags(s))
    assert validity.state_compromised is True
    assert validity.m_t_collapse is True
    assert validity.surrender_onset_turn == 2
    assert any("precision" in c for c in validity.caveats)  # caveat, not suppression
    assert strip[1].metacog == MetacogLabel.SURRENDER


def test_length_mismatch_is_rejected_not_truncated():
    s = _session(4)
    est = ProxyEstimator(classify_load=lambda sess: [LoadLabel.LOW_LOAD] * 2)  # wrong length
    strip, validity = est.estimate(s, _tags(s))
    assert all(v.load is None for v in strip)
    assert "load_length_mismatch" in validity.caveats


def test_epistemic_slope_needs_enough_turns():
    s = _session(3)
    est = ProxyEstimator(classify_epistemic=lambda sess, tags: [0.2, 0.4, 0.6])
    _, validity = est.estimate(s, _tags(s))
    assert validity.epistemic_mean is not None
    assert validity.epistemic_slope is None  # <4 values → no slope claim
