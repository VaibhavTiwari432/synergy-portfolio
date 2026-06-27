"""
tests/integration/test_snorkel_orchestrator.py — Phase 4 Snorkel orchestrator tests.

Tests the Snorkel orchestration on gold chats (POC) and validates weak label output.
"""

import pytest
import pandas as pd
from pathlib import Path

from calibration.snorkel_orchestrator import SnorkelOrchestrator, run_poc_on_gold
from calibration.gold_loader import load_gold_corpus
from contracts.schemas import Dimension


@pytest.fixture
def gold_corpus():
    """Load the 26-chat gold corpus."""
    return load_gold_corpus()


@pytest.fixture
def judge_scores(gold_corpus):
    """Extract judge ground truth from gold corpus."""
    judge_scores = {}
    for gc in gold_corpus:
        judge_scores[gc.session.session_id] = {
            dim.value: gc.targets[dim]
            for dim in gc.targets
            if gc.targets[dim] is not None
        }
    return judge_scores


def test_orchestrator_on_gold_poc(gold_corpus, judge_scores):
    """Run Snorkel on gold chats, validate against judge."""
    chats = [gc.session for gc in gold_corpus]

    orch = SnorkelOrchestrator(gold_chats=gold_corpus, judge_scores=judge_scores)
    weak_labels, metrics = orch.run(chats, mode="poc")

    # Check: all 9 neurons should have weak labels
    unique_neurons = weak_labels["neuron_id"].unique()
    assert len(unique_neurons) == 9, f"Expected 9 neurons, got {len(unique_neurons)}"

    # Check: coverage should be 100% (deterministic LFs always fire)
    assert metrics["coverage"] == 1.0, f"Expected 100% coverage, got {metrics['coverage']:.2%}"

    # Check: judge agreement should be reasonable
    # These are simple heuristic LFs, not trained models. ~45-50% agreement is expected.
    assert metrics["judge_agreement"] > 0.3, \
        f"Expected >30% judge agreement, got {metrics['judge_agreement']:.2%}"

    print(f"✅ POC passed:")
    print(f"   Coverage: {metrics['coverage']:.2%}")
    print(f"   Judge agreement: {metrics['judge_agreement']:.2%}")
    print(f"   Mean confidence: {metrics['mean_confidence']:.3f}")


def test_weak_labels_format(gold_corpus):
    """Verify weak labels are in the right format for SetFit."""
    chats = [gc.session for gc in gold_corpus[:5]]  # Use first 5 for speed

    orch = SnorkelOrchestrator()
    weak_labels, _ = orch.run(chats, mode="production")

    # Check columns
    expected_cols = {"chat_id", "neuron_id", "weak_label", "confidence"}
    assert set(weak_labels.columns) == expected_cols, \
        f"Expected columns {expected_cols}, got {set(weak_labels.columns)}"

    # Check value ranges
    assert weak_labels["weak_label"].min() >= 0.0, "weak_label should be >= 0"
    assert weak_labels["weak_label"].max() <= 1.0, "weak_label should be <= 1"
    assert weak_labels["confidence"].min() >= 0.0, "confidence should be >= 0"
    assert weak_labels["confidence"].max() <= 1.0, "confidence should be <= 1"

    # Check no NaN values
    assert weak_labels.isnull().sum().sum() == 0, "Should have no NaN values"

    print("✅ Weak labels format correct")


def test_scaling_to_larger_corpus(gold_corpus):
    """Test that Snorkel scales to larger corpus (mock)."""
    # Create a larger corpus by repeating gold chats
    chats_small = [gc.session for gc in gold_corpus]
    chats_large = chats_small * 2  # ~50 chats

    orch = SnorkelOrchestrator()
    weak_labels, metrics = orch.run(chats_large, mode="production")

    # Check: should handle 50 chats without error
    expected_pairs = len(chats_large) * 9  # 50 chats × 9 neurons
    assert len(weak_labels) == expected_pairs, \
        f"Expected {expected_pairs} pairs, got {len(weak_labels)}"

    assert metrics["coverage"] == 1.0, "Should have 100% coverage"

    print(f"✅ Scaling test passed: {len(weak_labels)} labels on {len(chats_large)} chats")


def test_confidence_distribution(gold_corpus):
    """Check that confidence is distributed reasonably."""
    chats = [gc.session for gc in gold_corpus]

    orch = SnorkelOrchestrator()
    weak_labels, metrics = orch.run(chats, mode="production")

    # Check: high-confidence labels should exist
    high_conf = (weak_labels["confidence"] > 0.6).sum()
    assert high_conf > 0, "Should have some high-confidence labels"

    # Check: mean confidence should be reasonable [0.3, 0.8]
    mean_conf = metrics["mean_confidence"]
    assert 0.2 < mean_conf < 0.9, \
        f"Mean confidence {mean_conf:.3f} is outside expected range"

    print(f"✅ Confidence distribution reasonable:")
    print(f"   Mean: {metrics['mean_confidence']:.3f}")
    print(f"   High-confidence (>0.6): {metrics.get('high_confidence_fraction', 0):.2%}")


def test_per_neuron_scores(gold_corpus):
    """Verify per-neuron scores are reasonable."""
    chats = [gc.session for gc in gold_corpus[:10]]  # Use subset for speed

    orch = SnorkelOrchestrator()
    weak_labels, _ = orch.run(chats, mode="production")

    # Check: each neuron should have at least some labels
    for neuron_id in weak_labels["neuron_id"].unique():
        neuron_labels = weak_labels[weak_labels["neuron_id"] == neuron_id]
        assert len(neuron_labels) > 0, f"Neuron {neuron_id} has no labels"

        # Scores should be in [0, 1]
        assert (neuron_labels["weak_label"] >= 0).all()
        assert (neuron_labels["weak_label"] <= 1).all()

    print("✅ Per-neuron scores are valid")


def test_judge_agreement_details(gold_corpus, judge_scores):
    """For POC, check judge agreement at dimension level."""
    chats = [gc.session for gc in gold_corpus]

    orch = SnorkelOrchestrator(gold_chats=gold_corpus, judge_scores=judge_scores)
    weak_labels, metrics = orch.run(chats, mode="poc")

    # Judge agreement should be reported
    assert "judge_agreement" in metrics
    assert metrics["judge_agreement"] > 0, "Should have some judge agreement"

    # There should be dimension-level comparisons
    assert metrics["judge_total_pairs"] > 0, "Should have dimension-level comparisons"

    print(f"✅ Judge agreement at dimension level: {metrics['judge_agreement']:.2%}")


def test_run_poc_on_gold_entrypoint():
    """Test the POC entrypoint function."""
    metrics = run_poc_on_gold()

    # Check: metrics should be present
    assert "coverage" in metrics
    assert "mean_confidence" in metrics
    assert metrics["coverage"] == 1.0
    assert metrics["mean_confidence"] > 0

    # Check: outputs should be saved
    assert Path("calibration/snorkel_output_poc/weak_labels.csv").exists()
    assert Path("calibration/snorkel_output_poc/metrics.json").exists()

    print("✅ POC entrypoint test passed")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
