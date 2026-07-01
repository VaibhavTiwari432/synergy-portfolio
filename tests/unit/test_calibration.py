"""Unit tests for the gold loader + MAE ratchet runner. OWNER: Chief Engineer.
No judge calls — score functions are synthetic."""

from __future__ import annotations

import pytest

from contracts.schemas import CanonicalSession, Dimension, PartnerModel, Turn
from calibration.gold_loader import BAND_TO_FLOAT, GoldChat, load_gold_corpus
from calibration.runner import MAE_RATCHET, run_calibration


# ── gold loader on the real corpus ───────────────────────────────────────────


def test_band_mapping_is_the_v1_mapping():
    assert BAND_TO_FLOAT == {"low": 0.25, "mid": 0.55, "high": 0.80, "not_applicable": None}


def test_loads_26_chats_with_targets_and_flags():
    corpus = load_gold_corpus()
    assert len(corpus) == 26
    by_id = {g.session.session_id: g for g in corpus}

    # gc-001 hand bands: AL low, AUI mid, ES not_applicable (see gc-001.json)
    gc1 = by_id["gc-001"]
    assert gc1.targets[Dimension.AL] == 0.25
    assert gc1.targets[Dimension.AUI] == 0.55
    assert gc1.targets[Dimension.ES] is None

    # D-005 resolved 2026-06-12: gc-003/016/018 re-judged with an OpenAI-family
    # judge — the conflicts list is empty and the headline pool is the full corpus
    assert {g for g, c in by_id.items() if c.judge_family_conflict} == set()
    assert {g for g, c in by_id.items() if c.ocr_excluded} == {
        "gc-004", "gc-012", "gc-013"
    }


# ── runner on a synthetic corpus ─────────────────────────────────────────────


def _gold(chat_id: str, target: float = 0.5, conflict: bool = False) -> GoldChat:
    session = CanonicalSession(
        session_id=chat_id, source="gold_json",
        partner_model=PartnerModel(family="google" if conflict else "openai"),
        turns=[Turn(index=0, role="human", text="q"), Turn(index=1, role="ai", text="a")],
    )
    return GoldChat(
        session=session,
        targets={dim: target for dim in Dimension},
        judge_family_conflict=conflict,
        ocr_excluded=False,
    )


def test_perfect_predictor_passes_ratchet():
    corpus = [_gold(f"c{i}") for i in range(4)]
    result = run_calibration(lambda s: {d: 0.5 for d in Dimension}, corpus)
    assert result["shadow"]["overall_mae"] == 0.0
    assert result["ratchet_passed"] is True
    assert result["shadow"]["n_chats"] == 4


def test_conflicted_chats_excluded_from_headline_but_in_shadow():
    corpus = [_gold("clean1"), _gold("clean2"), _gold("gem1", conflict=True)]
    result = run_calibration(lambda s: {d: 0.5 for d in Dimension}, corpus)
    assert result["shadow"]["n_chats"] == 3
    assert result["headline"]["n_chats"] == 2
    assert result["headline"]["excluded_conflicts"] == ["gem1"]


def test_missing_predictions_reported_as_coverage_not_zero():
    corpus = [_gold("c1")]

    def patchy(_s) -> dict[Dimension, float | None]:
        return {d: (None if d == Dimension.ES else 0.5) for d in Dimension}

    result = run_calibration(patchy, corpus)
    assert result["coverage"]["c1"]["missing"] == ["ES"]
    assert result["shadow"]["overall_mae"] == 0.0  # ES did not enter as an error


def test_ec_error_reports_but_does_not_gate_per_dim():
    # EC off by 0.45 (over the 0.375 per-dim target); others perfect.
    corpus = [_gold(f"c{i}", target=0.5) for i in range(8)]

    def ec_weak(_s) -> dict[Dimension, float | None]:
        return {d: (0.05 if d == Dimension.EC else 0.5) for d in Dimension}

    result = run_calibration(ec_weak, corpus)
    assert result["ec_tracked_separately"]["shadow_mae"] == 0.45
    # overall = 0.45/8 ≈ 0.056 ≤ ratchet; EC alone must not fail the gate
    assert result["shadow"]["overall_mae"] <= MAE_RATCHET
    assert result["ratchet_passed"] is True


def test_overall_failure_fails_ratchet():
    corpus = [_gold("c1", target=0.8)]
    result = run_calibration(lambda s: {d: 0.2 for d in Dimension}, corpus)
    assert result["shadow"]["overall_mae"] == pytest.approx(0.6)
    assert result["ratchet_passed"] is False


# ── D-002 coverage gate ──────────────────────────────────────────────────────


def test_judge_unavailable_chat_is_excluded_not_skipped():
    corpus = [_gold("ok1"), _gold("dead1")]

    def scorer(session) -> dict[Dimension, float | None]:
        if session.session_id == "dead1":
            return {d: None for d in Dimension}  # judge unavailable
        return {d: 0.5 for d in Dimension}

    result = run_calibration(scorer, corpus)
    assert result["shadow"]["n_scored"] == 1
    assert result["shadow"]["n_excluded"] == 1
    assert "dead1" in result["excluded_chats"]
    assert result["shadow"]["coverage_pct"] == 50.0


def test_under_four_valid_dims_counts_as_failed_observation():
    corpus = [_gold("patchy1")]

    def scorer(_s) -> dict[Dimension, float | None]:
        # only 3 of 8 dims valid → failed observation, not a partial one
        out: dict[Dimension, float | None] = {d: None for d in Dimension}
        for d in (Dimension.AL, Dimension.PR, Dimension.CA):
            out[d] = 0.5
        return out

    result = run_calibration(scorer, corpus)
    assert result["shadow"]["n_scored"] == 0
    assert "patchy1" in result["excluded_chats"]
    assert result["shadow"]["overall_mae"] is None


def test_low_coverage_cannot_pass_ratchet_regardless_of_mae():
    # the D-002 regression: one perfectly-scored chat, four dead ones —
    # MAE is 0.0 but coverage is 20%, so the gate must fail
    corpus = [_gold("ok1")] + [_gold(f"dead{i}") for i in range(4)]

    def scorer(session) -> dict[Dimension, float | None]:
        if session.session_id.startswith("dead"):
            return {d: None for d in Dimension}
        return {d: 0.5 for d in Dimension}

    result = run_calibration(scorer, corpus)
    assert result["shadow"]["overall_mae"] == 0.0
    assert result["headline"]["coverage_pct"] == 20.0
    assert result["ratchet_passed"] is False


def test_coverage_floor_boundary_passes_at_80_pct():
    corpus = [_gold(f"ok{i}") for i in range(4)] + [_gold("dead1")]

    def scorer(session) -> dict[Dimension, float | None]:
        if session.session_id == "dead1":
            return {d: None for d in Dimension}
        return {d: 0.5 for d in Dimension}

    result = run_calibration(scorer, corpus)
    assert result["headline"]["coverage_pct"] == 80.0
    assert result["ratchet_passed"] is True


def test_conflicted_dead_chat_does_not_hurt_headline_coverage():
    # a judge-unavailable chat that is ALSO a conflict sits outside the
    # headline pool — it cannot drag headline coverage down
    corpus = [_gold("ok1"), _gold("gemdead", conflict=True)]

    def scorer(session) -> dict[Dimension, float | None]:
        if session.session_id == "gemdead":
            return {d: None for d in Dimension}
        return {d: 0.5 for d in Dimension}

    result = run_calibration(scorer, corpus)
    assert result["headline"]["coverage_pct"] == 100.0
    assert result["shadow"]["coverage_pct"] == 50.0
    assert result["ratchet_passed"] is True


# ── Dawid–Skene judge de-biasing (Phase D — data-gated) ──────────────────────
# The estimator is load-bearing-gated: it raises until ≥2 annotators on ≥3 chats
# per dimension exist. Its output is a calibration bias number, NEVER a score (#10).


def _multi_anns(chats: list[str], dim: str = "EC") -> list[dict]:
    out: list[dict] = []
    for chat in chats:
        out.append({"chat_id": chat, "dimension": dim, "annotator_id": "human_1", "score": 0.6})
        out.append({"chat_id": chat, "dimension": dim, "annotator_id": "human_2", "score": 0.4})
    return out


def test_dawid_skene_raises_when_data_gated():
    from calibration.dawid_skene import DataGatedError, run_dawid_skene

    # single annotator → the dual-annotation gate must fire, not a fabricated bias
    anns = [{"chat_id": "gc-001", "dimension": "EC", "annotator_id": "human_1", "score": 0.5}]
    with pytest.raises(DataGatedError):
        run_dawid_skene(anns)


def test_dawid_skene_empty_annotations_raise():
    from calibration.dawid_skene import DataGatedError, run_dawid_skene

    with pytest.raises(DataGatedError):
        run_dawid_skene([])


def test_dawid_skene_accepts_multi_annotated():
    from calibration.dawid_skene import run_dawid_skene

    result = run_dawid_skene(_multi_anns(["gc-001", "gc-002", "gc-003"]))
    assert result["EC"]["status"] == "OK"
    assert result["EC"]["bias"] is not None
    assert result["EC"]["n_multi_annotated"] == 3
    # output is a calibration number — a plain float, never a DimensionScore (#10)
    assert isinstance(result["EC"]["bias"], float)


def test_dawid_skene_under_threshold_dimension_is_data_gated_not_raised():
    from calibration.dawid_skene import run_dawid_skene

    # PR has only 2 multi-annotated chats (< 3) but EC has 3 → no raise; PR is
    # reported DATA_GATED with a None bias (absent ≠ a fabricated zero, #12)
    anns = _multi_anns(["gc-001", "gc-002", "gc-003"], dim="EC")
    anns += _multi_anns(["gc-001", "gc-002"], dim="PR")
    result = run_dawid_skene(anns)
    assert result["EC"]["status"] == "OK"
    assert result["PR"]["status"] == "DATA_GATED"
    assert result["PR"]["bias"] is None


# ── Phase F — frozen-anchor judge-drift detection ────────────────────────────


def _anchor_corpus(target: float = 0.5):
    from calibration.drift_check import ANCHOR_CHAT_IDS

    return [_gold(aid, target=target) for aid in ANCHOR_CHAT_IDS]


def test_compute_drift_stable_when_predictor_beats_baseline():
    from calibration.drift_check import compute_drift

    # perfect predictor (MAE 0.0) well under a 0.25 baseline → no drift
    out = compute_drift(
        lambda s: {d: 0.5 for d in Dimension},
        baseline_mae=0.25, judge_model_id="judge-x", prompt_version="v2.1",
        corpus=_anchor_corpus(0.5),
    )
    assert out["mae_overall"] == 0.0
    assert out["drift_detected"] is False
    assert out["anchor_set"] and out["mae_per_dimension"]


def test_compute_drift_flags_a_mae_rise_over_threshold():
    from calibration.drift_check import compute_drift

    # predictor off by 0.5 on every dim → MAE 0.5, baseline 0.25 → Δ=+0.25 > 0.05
    out = compute_drift(
        lambda s: {d: 0.0 for d in Dimension},
        baseline_mae=0.25, judge_model_id="judge-x", prompt_version="v2.1",
        corpus=_anchor_corpus(0.5),
    )
    assert out["mae_overall"] == pytest.approx(0.5)
    assert out["drift_detected"] is True
    assert "DRIFT" in out["drift_note"]


def test_compute_drift_is_indeterminate_without_a_baseline():
    from calibration.drift_check import compute_drift

    # no baseline → never a false 'stable'; drift_detected is None (unknown, #12)
    out = compute_drift(
        lambda s: {d: 0.5 for d in Dimension},
        baseline_mae=None, judge_model_id="judge-x", prompt_version="v2.1",
        corpus=_anchor_corpus(0.5),
    )
    assert out["drift_detected"] is None
    assert "indeterminate" in out["drift_note"]
