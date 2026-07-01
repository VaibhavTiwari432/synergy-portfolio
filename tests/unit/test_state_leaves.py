"""Unit tests for the four state leaf classifiers."""

from __future__ import annotations

import pytest

from contracts.schemas import (
    CanonicalSession,
    LoadLabel,
    MetacogLabel,
    PartnerModel,
    Turn,
    TurnTags,
)
from src.state.epistemic_classifier import classify_epistemic
from src.state.load_classifier import Z_THRESHOLD, classify_load
from src.state.metacog_classifier import classify_metacog
from src.state.tomer_slope import tom_slope
from src.trait.tagger import tag_turns


def _session(human_texts: list[str]) -> CanonicalSession:
    turns: list[Turn] = []
    for text in human_texts:
        turns.append(Turn(index=len(turns), role="human", text=text))
        turns.append(Turn(index=len(turns), role="ai", text="a sufficiently long ai reply"))
    return CanonicalSession(
        session_id="sl-1", source="plaintext",
        partner_model=PartnerModel(family="openai"), turns=turns,
    )


# ── load classifier ──────────────────────────────────────────────────────────


def test_load_threshold_matches_relative_contract():
    assert Z_THRESHOLD == 1.5


def test_load_short_sessions_default_low_load():
    s = _session(["hi", "what is X?"])
    assert classify_load(s) == [LoadLabel.LOW_LOAD, LoadLabel.LOW_LOAD]


def test_load_one_label_per_human_turn():
    s = _session(["a normal length question here", "another normal question here",
                  "and one more normal question"])
    assert len(classify_load(s)) == 3


def test_load_confusion_is_high_ecl():
    s = _session([
        "explain the architecture of the system in detail please",
        "now explain the deployment pipeline in similar detail",
        "wait?? I don't understand. this isn't working. huh",
        "describe the monitoring setup we discussed before",
    ])
    labels = classify_load(s)
    assert labels[2] == LoadLabel.HIGH_ECL


def test_load_unusually_long_complex_prompt_is_high_icl():
    s = _session([
        "short ask",
        "short ask again",
        "short one more",
        ("considering the asymptotic complexity characteristics of hierarchical "
         "attention architectures alongside quantization-induced degradation, "
         "evaluate whether mixture-of-experts routing meaningfully amortizes "
         "inference costs for retrieval-augmented generation workloads under "
         "production latency constraints with heterogeneous accelerators and "
         "elaborate the architectural tradeoffs in considerable analytical depth"),
    ])
    labels = classify_load(s)
    assert labels[3] == LoadLabel.HIGH_ICL


def test_load_late_session_shrinkage_is_fatigue():
    s = _session([
        "please compare the two database architectures across consistency and partition behavior",
        "now evaluate the caching layer options with the same level of rigor and detail",
        "walk through the failure modes of the leading option in production environments",
        "ok. fine. whatever",
    ])
    labels = classify_load(s)
    assert labels[3] == LoadLabel.FATIGUE


# ── epistemic classifier ─────────────────────────────────────────────────────


def test_epistemic_generative_vs_extractive_poles():
    s = _session([
        "break this down into sub-tasks; here is my context: ```data``` ",  # generative tags
        "what is the capital of France?",                                    # extractive
        "ok",                                                                # accept flat
    ])
    series = classify_epistemic(s, tag_turns(s))
    assert len(series) == 3
    assert series[0] > 0.5
    assert series[1] < 0
    assert series[2] < 0
    # B3: None is valid for unassessable turns; tagged turns remain bounded
    assert all(v is None or -1.0 <= v <= 1.0 for v in series)


def test_epistemic_substantial_contribution_nudges_positive():
    long_contribution = "my analysis of the market segments suggests " * 20
    s = _session([long_contribution])
    series = classify_epistemic(s, tag_turns(s))
    assert series[0] > 0


# ── metacog classifier ───────────────────────────────────────────────────────


def test_metacog_active_passive_assignment():
    s = _session([
        "are you sure about that claim?",   # ACTIVE (verify)
        "write me the essay",               # PASSIVE (delegate)
        "tell me more about the topic",     # PASSIVE (extract)
    ])
    result = classify_metacog(s, tag_turns(s))
    assert result.labels == [MetacogLabel.ACTIVE, MetacogLabel.PASSIVE, MetacogLabel.PASSIVE]
    assert result.surrender_detected is False
    assert result.surrender_onset_turn is None


def test_metacog_surrender_on_three_flat_accepts():
    s = _session(["explain the plan", "ok", "continue", "sounds good", "no, use plan B instead"])
    result = classify_metacog(s, tag_turns(s))
    assert result.surrender_detected is True
    assert result.surrender_onset_turn == 2  # first turn of the run (human turn #2 → index 2)
    assert result.labels[1:4] == [MetacogLabel.SURRENDER] * 3
    assert result.labels[4] == MetacogLabel.ACTIVE  # override breaks the run


def test_metacog_two_accepts_are_not_surrender():
    s = _session(["explain", "ok", "continue", "what about the risks?"])
    result = classify_metacog(s, tag_turns(s))
    assert result.surrender_detected is False
    assert MetacogLabel.SURRENDER not in result.labels


def test_metacog_run_at_session_end_is_detected():
    s = _session(["explain", "ok", "thanks", "continue"])
    result = classify_metacog(s, tag_turns(s))
    assert result.surrender_detected is True
    assert result.labels[1:] == [MetacogLabel.SURRENDER] * 3


# ── ToM slope ────────────────────────────────────────────────────────────────


def test_tom_signatures_detected_and_bounded():
    s = _session([
        "you might not know this since your training data has a cutoff",
        "what's the answer?",
        "if you're unsure, say so — don't hallucinate",
        "given your context window, summarize in parts",
    ])
    series, slope = tom_slope(s)
    assert len(series) == 4
    assert series[0] > 0 and series[2] > 0 and series[3] > 0
    assert series[1] == 0.0
    assert all(0.0 <= v <= 1.0 for v in series)
    assert slope is not None


def test_tom_slope_none_under_four_turns():
    s = _session(["as an AI you can't browse", "ok", "fine"])
    series, slope = tom_slope(s)
    assert len(series) == 3
    assert slope is None  # insufficient sample, never 0.0


def test_tom_slope_sign_tracks_trajectory():
    rising = _session(["plain ask", "plain ask", "you may not know recent data",
                       "don't make things up; given your training cutoff, hedge"])
    _, slope_up = tom_slope(rising)
    assert slope_up > 0


# ── B2 acceptance: untagged turns → None (absent ≠ PASSIVE) ─────────────────


def test_metacog_untagged_turn_is_none_not_passive():
    """B2: a turn with no recognised tags must yield None, not PASSIVE."""
    s = _session(["a neutral remark"])
    # inject empty tags to guarantee no pattern fires
    result = classify_metacog(s, [TurnTags(turn_index=0, tags=[])])
    assert result.labels == [None]
    assert result.surrender_detected is False


def test_metacog_untagged_only_session_zero_degraded_share():
    """B2/L11: a session of entirely untagged turns → metacog all-None;
    degraded_share must be 0.0, not 0/n (absent ≠ degraded denominator)."""
    from src.state.estimator import ProxyEstimator
    from src.merge.precision import degraded_share

    s = _session(["x", "y", "z"])
    empty_tags = [TurnTags(turn_index=t.index, tags=[]) for t in s.turns if t.role == "human"]
    result = classify_metacog(s, empty_tags)
    assert all(label is None for label in result.labels)

    est = ProxyEstimator(classify_metacog=lambda sess, tags: result)
    strip, _ = est.estimate(s, empty_tags)
    assert all(v.metacog is None for v in strip)
    assert degraded_share(strip) == 0.0


# ── B3 acceptance: epistemic unassessable → None ─────────────────────────────


def test_epistemic_untagged_no_content_is_none():
    """B3: a turn with no tags and no substantial content must return None."""
    s = _session(["a"])  # single word, no recognisable tag
    result = classify_epistemic(s, [TurnTags(turn_index=0, tags=[])])
    assert result == [None]


def test_epistemic_session_mean_excludes_none_turns():
    """B3: session mean computed only over assessable turns."""
    from src.state.estimator import _epistemic_summary
    series = [0.8, None, None, 0.4]  # two assessable, two not
    mean, _ = _epistemic_summary(series)
    assert mean == pytest.approx((0.8 + 0.4) / 2)
