"""Phase 2.6 acceptance — three-panel CSL report.

Acceptance (v3.2 §2.6): never a bare percentage; ARI and contribution visibly
separate; four states render distinctly; emergence carries the indicator-not-proof
caveat. Plus the two hard requirements: Panel B caveat is the SPEC_emergence
string verbatim; Panel C ARI dots are NEVER averaged into the ownership bars.
"""

from __future__ import annotations

import pytest

from contracts.schemas import (
    Censored,
    ConfidenceInterval,
    Dimension,
    DimensionScore,
    Rung,
    ScoreStatus,
)
from csl.crosswalk import ACF_LEVELS, load_acf_crosswalk
from csl.emergence import EmergenceEvent
from csl.ownership import OwnershipResult
from csl.report import (
    EMERGENCE_CAVEAT_TEMPLATE,
    ari_capability_by_level,
    build_csl_report,
)

CROSSWALK = load_acf_crosswalk()


def _own(level, status=ScoreStatus.OK, human_pct=0.6):
    if status == ScoreStatus.OK:
        return OwnershipResult(
            level=level, label=f"{level}-l", status=status,
            human_pct=human_pct, ai_pct=round(1 - human_pct, 6),
            ci=ConfidenceInterval(low=max(0.0, human_pct - 0.1), high=min(1.0, human_pct + 0.1)),
            n_eff=3.0, pi_s=1.0, censored=None, rung=Rung.DESIGNED,
            method_version="t", flags=(),
        )
    return OwnershipResult(
        level=level, label=f"{level}-l", status=status,
        human_pct=None, ai_pct=None, ci=None, n_eff=0.0, pi_s=None,
        censored=None, rung=Rung.DESIGNED, method_version="t", flags=(),
    )


def _profile(value=0.5):
    return {
        dim: DimensionScore(dim=dim, status=ScoreStatus.OK, value=value,
                            ci=ConfidenceInterval(low=value - 0.05, high=value + 0.05),
                            n_eff=5.0, rung=Rung.MEASURABLE)
        for dim in Dimension
    }


def _event(level="C4", trigger="BI"):
    return EmergenceEvent(
        ev_id="e1", turn_range=(1, 2), acf_level=level, trigger_type=trigger,
        confirmation="explicit", direction_change=True, output_delta=True,
        judge_confirmed=True,
    )


def test_report_has_three_panels_covering_seven_levels():
    own = {lvl: _own(lvl) for lvl in ACF_LEVELS}
    report = build_csl_report(own, [], _profile())
    assert len(report.panel_a) == 7
    assert len(report.panel_c) == 7
    assert report.panel_b is not None


# ── HARD REQUIREMENT 1: Panel B caveat verbatim from SPEC_emergence ─────────────


def test_panel_b_caveat_is_spec_string_verbatim_with_count():
    own = {lvl: _own(lvl) for lvl in ACF_LEVELS}
    report = build_csl_report(own, [_event(), _event("C6", "BI")], _profile())

    expected = EMERGENCE_CAVEAT_TEMPLATE.replace("N emergence events", "2 emergence events", 1)
    assert report.panel_b.caveat == expected
    # the rest of the spec wording is untouched
    assert "genuine complementarity" in report.panel_b.caveat
    assert "not proof of performance gain above what you could achieve alone" in report.panel_b.caveat
    assert "requires the unaided follow-up task to establish." in report.panel_b.caveat


def test_emergence_caveat_template_matches_spec_text_exactly():
    # guards against drift from SPEC_emergence.md line 176 (sans the N->count swap).
    spec_line = (
        "This session contained N emergence events: moments where the exchange "
        "produced formulations neither party was approaching independently. These "
        "indicate genuine complementarity. They are not proof of performance gain "
        "above what you could achieve alone, which requires the unaided follow-up "
        "task to establish."
    )
    assert EMERGENCE_CAVEAT_TEMPLATE == spec_line


def test_panel_b_zero_events_still_carries_caveat():
    own = {lvl: _own(lvl) for lvl in ACF_LEVELS}
    report = build_csl_report(own, [], _profile())
    assert report.panel_b.count == 0
    assert report.panel_b.caveat.startswith("This session contained 0 emergence events")


# ── HARD REQUIREMENT 2: ARI dots never averaged into the ownership bars ──────────


def test_panel_c_ari_never_averaged_into_panel_a_bars():
    own = {lvl: _own(lvl, human_pct=0.6) for lvl in ACF_LEVELS}

    low_ari = build_csl_report(own, [], _profile(value=0.1))
    high_ari = build_csl_report(own, [], _profile(value=0.9))

    # Panel A bars are byte-identical regardless of ARI capability: the bars are
    # pure ownership; ARI never leaks in.
    assert low_ari.panel_a == high_ari.panel_a

    # Panel C dots DO move with ARI (proving the value actually changed) ...
    low_dots = {d.level: d.ari_capability for d in low_ari.panel_c}
    high_dots = {d.level: d.ari_capability for d in high_ari.panel_c}
    assert low_dots != high_dots

    # ... and a bar's share is never equal to a blend of share and ARI.
    for bar, dot in zip(high_ari.panel_a, high_ari.panel_c):
        assert bar.your_share == 0.6              # exactly the ownership value
        assert dot.ari_capability == 0.9          # exactly the ARI value
        assert bar.your_share != dot.ari_capability


def test_borrowed_brilliance_flags_high_ari_low_share():
    # high ARI capability + low your-share at the same level -> borrowed brilliance.
    own = {lvl: _own(lvl, human_pct=0.1) for lvl in ACF_LEVELS}
    report = build_csl_report(own, [], _profile(value=0.9))
    assert any(d.borrowed_brilliance for d in report.panel_c)
    flagged = next(d for d in report.panel_c if d.borrowed_brilliance)
    assert flagged.ari_capability == 0.9 and flagged.your_share == 0.1


def test_no_borrowed_brilliance_when_share_is_high():
    own = {lvl: _own(lvl, human_pct=0.8) for lvl in ACF_LEVELS}
    report = build_csl_report(own, [], _profile(value=0.9))
    assert not any(d.borrowed_brilliance for d in report.panel_c)


# ── four-state + never-bare-percentage ──────────────────────────────────────────


def test_four_states_render_as_distinct_labels():
    own = {
        "C1": _own("C1", ScoreStatus.OK, 0.6),
        "C2": _own("C2", ScoreStatus.NOT_APPLICABLE),
        "C3": _own("C3", ScoreStatus.INSUFFICIENT_SAMPLE),
        "C4": OwnershipResult(
            level="C4", label="C4-l", status=ScoreStatus.MEASUREMENT_SATURATED,
            human_pct=None, ai_pct=None, ci=None, n_eff=3.0, pi_s=1.0,
            censored=Censored(direction="high", bound=0.8), rung=Rung.DESIGNED,
            method_version="t", flags=()),
    }
    report = build_csl_report(own, [], _profile())
    labels = {b.level: b.status_label for b in report.panel_a}
    distinct = {labels["C1"], labels["C2"], labels["C3"], labels["C4"]}
    assert len(distinct) == 4  # never collapsed into one bucket


def test_ok_bar_never_bare_percentage():
    own = {lvl: _own(lvl) for lvl in ACF_LEVELS}
    report = build_csl_report(own, [], _profile())
    for bar in report.panel_a:
        if bar.status == ScoreStatus.OK:
            assert bar.your_share is not None
            assert bar.ci_low is not None and bar.ci_high is not None  # always a CI


def test_saturated_bar_shows_censored_bound_not_point():
    own = {"C4": OwnershipResult(
        level="C4", label="C4-l", status=ScoreStatus.MEASUREMENT_SATURATED,
        human_pct=None, ai_pct=None, ci=None, n_eff=3.0, pi_s=1.0,
        censored=Censored(direction="high", bound=0.8), rung=Rung.DESIGNED,
        method_version="t", flags=())}
    report = build_csl_report(own, [], _profile())
    bar = next(b for b in report.panel_a if b.level == "C4")
    assert bar.your_share is None
    assert bar.censored == "≥ 0.80"


def test_report_passes_forbidden_word_scan_tier1():
    # build_csl_report raises ForbiddenWordViolation internally if any string is
    # dirty; reaching here means Tier-1 output is clean (no synergy/surrender/etc).
    own = {lvl: _own(lvl, human_pct=0.1) for lvl in ACF_LEVELS}
    report = build_csl_report(own, [_event()], _profile(value=0.9), tier=1)
    assert report is not None


def test_ari_capability_by_level_is_per_level_mean():
    caps = ari_capability_by_level(_profile(value=0.5), CROSSWALK)
    assert set(caps) == set(ACF_LEVELS)
    for level in ACF_LEVELS:
        assert caps[level] == 0.5  # all dims 0.5 -> every level mean 0.5
