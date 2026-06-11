"""
Integration tests — full round-trip through Stages 1-4 + 6-8 (no LLM).

Stage 5 (Gemini judge) is skipped here: we inject stub neuron scores
rather than calling the paid API.  Tests cover the deterministic stages
that can run offline and the output contract assertions from the brief.

Note: sentence-transformers (semantic_distance_delta) is mocked out in all
tests here to avoid a Windows access-violation crash in torch when loading
the model inside the pytest process.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[3]))

from saf_chat_analyser.src.parser.transcript_parser import parse_transcript
from saf_chat_analyser.src.tagger.intent_tagger import tag_turns, intent_counts
from saf_chat_analyser.src.tagger.turn_classifier import compute_as_ratios
from saf_chat_analyser.src.tagger.phase_classifier import classify_phases
from saf_chat_analyser.src.metrics.composite_metrics import compute_metrics
from saf_chat_analyser.src.aggregator.dimension_aggregator import aggregate
from saf_chat_analyser.src.flags.risk_evaluator import evaluate_flags
from saf_chat_analyser.src.output.formatter import format_output

_GOLD_PATH = Path(__file__).parents[2] / "gold_standard" / "chats" / "gc-001.json"
_NEURONS_PATH = Path(__file__).parents[1] / "data" / "neurons_v6.json"

def _stub_neuron_scores(value: float = 0.55) -> dict[str, float]:
    neurons = json.load(open(_NEURONS_PATH, encoding="utf-8"))
    return {nid: value for nid in neurons}


def _load_gc001_turns():
    raw = json.loads(_GOLD_PATH.read_text(encoding="utf-8"))
    turn_list = [
        {"role": t["role"], "content": t.get("content") or t.get("text", "")}
        for t in raw["turns"]
    ]
    return parse_transcript(turn_list)


# ── Stage 1-4 offline pipeline ────────────────────────────────────────────────

def test_gc001_parses_nonzero_turns():
    turns = _load_gc001_turns()
    assert len(turns) > 0


def test_gc001_has_both_roles():
    turns = _load_gc001_turns()
    roles = {t.role for t in turns}
    assert "human" in roles
    assert "ai" in roles


def test_gc001_as_ratio_sums_to_one():
    turns = _load_gc001_turns()
    tagged = tag_turns(turns)
    ratios = compute_as_ratios(tagged)
    assert abs(ratios["a_turn_ratio"] + ratios["s_turn_ratio"] - 1.0) < 1e-9


def test_gc001_phase_sums_to_one():
    turns = _load_gc001_turns()
    tagged = tag_turns(turns)
    phases = classify_phases(tagged)
    assert abs(sum(phases.values()) - 1.0) < 1e-6


# ── Aggregation round-trip ────────────────────────────────────────────────────

def test_composite_equals_min_times_gates():
    turns = _load_gc001_turns()
    tagged = tag_turns(turns)
    metrics = compute_metrics(turns, tagged)
    scores = _stub_neuron_scores(0.6)
    agg = aggregate(scores, verification_ratio=metrics.verification_ratio)
    pillar_min = min(agg["pillar_scores"].values())
    gate_prod = math.prod(agg["gates"].values())
    expected = round(pillar_min * gate_prod, 4)
    assert agg["collaboration_quality_kappa"] == expected


# ── Full output contract ──────────────────────────────────────────────────────

def _full_output() -> dict:
    turns = _load_gc001_turns()
    tagged = tag_turns(turns)
    counts = intent_counts(tagged)
    metrics = compute_metrics(turns, tagged)
    scores = _stub_neuron_scores(0.55)
    agg = aggregate(scores, verification_ratio=metrics.verification_ratio)
    flags = evaluate_flags(scores, metrics)
    return format_output(
        session_id="gc-001-test",
        neuron_scores=scores,
        aggregation=agg,
        metrics=metrics,
        risk_flags=flags,
    )


def test_full_output_is_valid_json():
    out = _full_output()
    serialised = json.dumps(out)
    parsed = json.loads(serialised)
    assert isinstance(parsed, dict)


def test_claims_boundary_tier_1():
    out = _full_output()
    assert out["claims_boundary"]["tier"] == 1


def test_collaboration_quality_kappa_present():
    out = _full_output()
    assert "collaboration_quality_kappa" in out
    assert out["collaboration_quality_kappa"] is not None


def test_g_synergy_absent():
    out = _full_output()
    assert "g_synergy" not in out


def test_no_synergy_in_any_key():
    out = _full_output()

    def _walk(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                assert "synergy" not in k.lower(), f"Forbidden key: {k}"
                _walk(v)

    _walk(out)


def test_dependency_debt_ewma_is_none():
    out = _full_output()
    assert out["dependency_debt_ewma"] is None


def test_risk_flags_present_with_correct_keys():
    out = _full_output()
    rf = out["risk_flags"]
    assert "fluent_incompetence" in rf
    assert "cognitive_debt_flag" in rf
    assert "explanation_trap" in rf
    assert "genuine_collab_quality" in rf


def test_output_schema_tier_field():
    out = _full_output()
    assert out["tier"] == 1
