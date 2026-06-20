"""Unit tests for the claims engine (rungs, report, tier gating, minor
protection). OWNER: Chief Engineer."""

from __future__ import annotations

import pytest

from contracts.schemas import (
    CanonicalSession,
    CellGatedProb,
    Composite,
    ConfidenceInterval,
    DebtEwma,
    DebtMode,
    Dimension,
    DimensionScore,
    FrictionTransitionMatrix,
    PartnerModel,
    ReactionSignatures,
    RegimeOverlay,
    Report,
    Rung,
    ScoreResponse,
    ScoreStatus,
    SessionFlags,
    SHumanHat,
    StateValidity,
    StateVector,
    Sustainability,
    TransitionMetrics,
    Turn,
)
from src.claims.report import ForbiddenWordViolation, forbidden_word_scan, generate_report
from src.claims.rungs import exceeds_tier_ceiling, forbidden_words_for_tier, max_rung_for_tier
from src.claims.tier_engine import ClaimsViolation, detect_tier, enforce


def _profile(rung: Rung = Rung.MEASURABLE) -> dict[Dimension, DimensionScore]:
    return {
        dim: DimensionScore(
            dim=dim, status=ScoreStatus.OK, value=0.5,
            ci=ConfidenceInterval(low=0.4, high=0.6), n_eff=4.0, rung=rung,
        )
        for dim in Dimension
    }


def _response(profile=None, composite=None) -> ScoreResponse:
    gated = CellGatedProb()
    return ScoreResponse(
        session_id="cl-1",
        tier=1,
        profile=profile or _profile(),
        composite=composite or Composite(
            value=0.5, ci=ConfidenceInterval(low=0.45, high=0.55),
            gates_passed={"scorability": True, "state_validity": True},
        ),
        state_strip=[StateVector(turn_index=0)],
        state_validity=StateValidity(),
        flags=SessionFlags(),
        reaction_signatures=ReactionSignatures(
            ftm=FrictionTransitionMatrix(p_verify=gated, p_accept_flat=gated, p_disengage=gated),
            transition_metrics=TransitionMetrics(
                verify_after_error_rate=gated, constraint_before_generation_rate=gated,
                prediction_before_answer_rate=gated, revision_after_output_rate=gated,
            ),
        ),
        regime_overlay=RegimeOverlay(),
        sustainability=Sustainability(
            s_human_hat=SHumanHat(),
            debt_ewma=DebtEwma(mode=DebtMode.NONE, value=0.4, n_sessions=3),
        ),
        report=Report(tier_caveat="Tier 1 caveat."),
    )


# ── rungs ────────────────────────────────────────────────────────────────────


def test_tier_ceilings():
    assert max_rung_for_tier(1) == Rung.MEASURABLE
    assert exceeds_tier_ceiling(Rung.VALIDATED, 1) is True
    assert exceeds_tier_ceiling(Rung.MEASURABLE, 1) is False
    assert exceeds_tier_ceiling(Rung.DESIGNED, 1) is False
    assert exceeds_tier_ceiling(Rung.VALIDATED, 3) is False
    assert exceeds_tier_ceiling(Rung.ASPIRATIONAL, 1) is False  # not an evidence rung


def test_forbidden_words_per_tier():
    assert "synergy" in forbidden_words_for_tier(1)
    assert "surrender" in forbidden_words_for_tier(1)
    assert "synergy" not in forbidden_words_for_tier(3)  # tier 3 may say it
    assert "surrender" in forbidden_words_for_tier(3)    # but never this


# ── forbidden-word scan ──────────────────────────────────────────────────────


def test_scan_catches_word_and_derivatives():
    texts = ["great synergistic collaboration", "all fine here"]
    violations = forbidden_word_scan(texts, tier=1)
    assert len(violations) == 1 and "synergy" in violations[0]
    assert forbidden_word_scan(["clean text"], tier=1) == []


def test_scan_is_case_insensitive():
    assert forbidden_word_scan(["The user SURRENDERED control"], tier=1)


@pytest.mark.parametrize("derivative", [
    "synergize", "synergies", "synergized", "synergistic", "synergy",
    "Synergizing", "SYNERGIES",
])
def test_scan_catches_all_synergy_derivatives(derivative: str):
    # Gate B requirement: the stem scan must cover every derivative form
    violations = forbidden_word_scan([f"a {derivative} outcome"], tier=1)
    assert violations, f"{derivative!r} escaped the stem scan"


@pytest.mark.parametrize("derivative", [
    "surrendered", "surrendering", "dependence", "dependency", "dependents",
])
def test_scan_catches_surrender_and_dependent_derivatives(derivative: str):
    assert forbidden_word_scan([f"signs of {derivative} behavior"], tier=1)


def test_scan_does_not_overmatch_unrelated_words():
    # near-miss words sharing a prefix-of-a-prefix must not trip the scan
    assert forbidden_word_scan(["depends on the input", "syntax errors"], tier=1) == []


# ── report generation ────────────────────────────────────────────────────────


def _report_inputs(**flag_overrides):
    gated = CellGatedProb()
    return dict(
        tier=1,
        profile=_profile(),
        composite=Composite(
            value=0.5, ci=ConfidenceInterval(low=0.45, high=0.55),
            gates_passed={"scorability": True, "state_validity": True},
        ),
        state_validity=StateValidity(state_compromised=True),
        flags=SessionFlags(
            fluent_incompetence=True, theater_counter=2, accept_run_max=4,
            **flag_overrides,
        ),
        reactions=ReactionSignatures(
            ftm=FrictionTransitionMatrix(p_verify=gated, p_accept_flat=gated, p_disengage=gated),
            transition_metrics=TransitionMetrics(
                verify_after_error_rate=CellGatedProb(value=0.6, n_events=5),
                constraint_before_generation_rate=gated,
                prediction_before_answer_rate=gated,
                revision_after_output_rate=gated,
            ),
        ),
        sustainability=Sustainability(
            s_human_hat=SHumanHat(value=42.0, r_auto=0.5, r_steer=0.2,
                                  t_steered_out=140.0, status=ScoreStatus.OK,
                                  rung=Rung.MEASURABLE),
            debt_ewma=DebtEwma(mode=DebtMode.INSUFFICIENT_HISTORY, n_sessions=1),
        ),
    )


def test_report_has_three_evidence_levels_and_caveat():
    report = generate_report(**_report_inputs())
    assert report.observed and report.inferred and report.hypothesized
    assert "Tier 1" in report.tier_caveat
    # the compromised state appears as a caveat about uncertainty, not adjustment
    assert any("uncertainty" in t for t in report.inferred)


def test_report_never_says_forbidden_words_even_with_surrender_state():
    report = generate_report(**_report_inputs())
    all_text = " ".join([*report.observed, *report.inferred, *report.hypothesized,
                         report.tier_caveat]).lower()
    for word in ("synergy", "surrender", "dependent"):
        assert word not in all_text


def test_minor_report_form():
    inputs = _report_inputs()
    report = generate_report(**inputs, is_minor=True)
    assert "minor-protective" in report.tier_caveat
    # no composite line for minors
    assert not any("composite" in t for t in report.inferred)


# ── tier engine ──────────────────────────────────────────────────────────────


def _session(metadata: dict | None = None) -> CanonicalSession:
    return CanonicalSession(
        session_id="t-1", source="plaintext",
        partner_model=PartnerModel(family="openai"),
        turns=[Turn(index=0, role="human", text="hi")],
        metadata=metadata or {},
    )


def test_detect_tier_transcript_is_tier_1():
    assert detect_tier(_session()) == 1
    assert detect_tier(_session({"telemetry": {"dwell": []}})) == 2


def test_enforce_passes_clean_tier1_response():
    assert enforce(_response()) == _response()


def test_enforce_raises_on_rung_overreach():
    over = _response(profile=_profile(rung=Rung.VALIDATED))
    with pytest.raises(ClaimsViolation):
        enforce(over)


def test_minor_protection_withholds_composite_and_debt_value():
    protected = enforce(_response(), is_minor=True)
    assert protected.composite.value is None
    assert protected.composite.status == ScoreStatus.NOT_APPLICABLE
    assert protected.sustainability.debt_ewma.value is None
    assert protected.sustainability.debt_ewma.mode == DebtMode.NONE  # mode kept
    # profile (band material) remains
    assert all(s.status == ScoreStatus.OK for s in protected.profile.values())
