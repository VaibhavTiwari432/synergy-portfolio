"""B (v3.23) regression+diagnostics harness — deterministic tests, no judge spend."""

from calibration.gold_loader import load_gold_corpus
from calibration.run_regression_with_diagnostics import (
    N_JUDGE_TYPED,
    collect_diagnostics,
    neuron_grain_split,
    run,
)
from contracts.schemas import Dimension


def _corpus():
    """3 smallest gold chats — keeps provenance (Levenshtein over transcripts)
    fast in unit tests; the full-corpus run is the CLI measurement, not a test."""
    full = load_gold_corpus()
    return sorted(full, key=lambda g: sum(len(t.text) for t in g.session.turns))[:3]


def test_neuron_grain_split_covers_all_98():
    split = neuron_grain_split()
    assert sum(split.values()) == N_JUDGE_TYPED == 98


def test_diagnostics_run_without_a_judge():
    d = collect_diagnostics(_corpus())
    assert d["n_chats"] > 0
    assert d["gate_effect"]["baseline_judge_calls"] == 98 * d["n_chats"]
    # provenance tally never exceeds total human turns; copy/verbatim is a subset
    assert d["copy_paste_detected"] <= sum(d["provenance_distribution"].values())


def test_gate_effect_is_zero_on_permissive_scaffold():
    """Scaffold matrix excludes nothing -> 0% reduction. Flips >0% once tightened."""
    d = collect_diagnostics(_corpus())
    assert d["gate_effect"]["cost_reduction_pct"] == 0.0
    assert d["gate_effect"]["actual_judge_calls"] == d["gate_effect"]["baseline_judge_calls"]


def test_mae_block_present_only_with_score_fn():
    corpus = _corpus()
    # no score_fn -> diagnostics only
    assert "mae_ratchet" not in run(corpus)
    # trivial deterministic score_fn (perfect predictions) -> ratchet runs & passes
    report = run(corpus, score_fn=lambda s: {d: _target(corpus, s, d) for d in Dimension})
    assert "mae_ratchet" in report
    assert report["mae_ratchet"]["ratchet_passed"] is True  # MAE 0 on perfect preds


def _target(corpus, session, dim):
    for g in corpus:
        if g.session.session_id == session.session_id:
            return g.targets[dim]
    return None
