"""
tests/unit/test_cascade_eval.py — Tests for cascaded selective evaluation

Tests:
  1. Disagreement computation: High variance → high disagreement
  2. Phi estimation: Disagreement + n_reps → Φ estimate
  3. Escalation logic: Escalates when needed, respects max_reps
  4. Batch processing: Processes all neurons, computes summary
  5. Savings computation: Fixed-N vs cascaded comparison
  6. Confidence intervals: CIs computed from percentiles
"""

import numpy as np
import pytest
from src.trait.judge.cascade_eval import (
    compute_disagreement_metric,
    estimate_phi_from_disagreement,
    cascaded_evaluate,
    batch_cascaded_evaluate,
    compute_savings,
)


class TestDisagreementMetric:
    """Test disagreement computation."""

    def test_perfect_agreement_zero_disagreement(self):
        """Identical scores should give zero disagreement."""
        scores = [0.5, 0.5, 0.5]
        disagreement = compute_disagreement_metric(scores)
        assert disagreement == 0.0

    def test_high_variance_high_disagreement(self):
        """Divergent scores should give high disagreement."""
        scores = [0.0, 0.5, 1.0]  # Max spread
        disagreement = compute_disagreement_metric(scores)
        assert disagreement > 0.5

    def test_single_score_zero_disagreement(self):
        """Single score can't compute disagreement."""
        scores = [0.7]
        disagreement = compute_disagreement_metric(scores)
        assert disagreement == 0.0

    def test_scale_invariance(self):
        """Should handle both 0-1 and 0-4 scales."""
        scores_01 = [0.0, 0.5, 1.0]
        scores_04 = [0.0, 2.0, 4.0]
        d01 = compute_disagreement_metric(scores_01)
        d04 = compute_disagreement_metric(scores_04)
        assert abs(d01 - d04) < 0.01


class TestPhiEstimation:
    """Test Phi (reliability) estimation."""

    def test_low_disagreement_high_phi(self):
        """Low disagreement should yield high Φ."""
        phi = estimate_phi_from_disagreement(disagreement=0.0, target_phi=0.70, n_reps_so_far=3)
        assert phi > 0.9

    def test_high_disagreement_low_phi(self):
        """High disagreement should yield low Φ."""
        phi = estimate_phi_from_disagreement(disagreement=0.8, target_phi=0.70, n_reps_so_far=3)
        assert phi < 0.65  # High disagreement yields lower Φ than low disagreement

    def test_phi_increases_with_reps(self):
        """More reps should increase estimated Φ."""
        d = 0.2  # Moderate disagreement
        phi_3reps = estimate_phi_from_disagreement(d, target_phi=0.70, n_reps_so_far=3)
        phi_10reps = estimate_phi_from_disagreement(d, target_phi=0.70, n_reps_so_far=10)
        assert phi_10reps > phi_3reps


class TestCascadedEvaluation:
    """Test cascaded evaluation logic."""

    def test_returns_required_fields(self):
        """Should return all required fields."""
        def mock_judge(neuron_id, transcript):
            return 0.6

        result = cascaded_evaluate(mock_judge, 'EC-01', 'transcript')

        required_keys = [
            'score',
            'confidence_interval',
            'n_reps',
            'disagreement',
            'phi_estimated',
            'escalated',
            'rep_scores',
            'neuron_id',
        ]
        for key in required_keys:
            assert key in result, f"Missing key: {key}"

    def test_no_escalation_for_perfect_agreement(self):
        """Perfect agreement should not escalate."""
        def mock_judge(neuron_id, transcript):
            return 0.7  # Constant score

        result = cascaded_evaluate(
            mock_judge,
            'EC-01',
            'transcript',
            initial_reps=3,
            disagreement_threshold=0.15,
        )

        assert result['escalated'] is False
        assert result['n_reps'] == 3

    def test_escalation_on_high_disagreement(self):
        """High disagreement should trigger escalation."""
        scores = [0.2, 0.8, 0.3, 0.7, 0.4]  # High variance
        idx = [0]

        def mock_judge(neuron_id, transcript):
            result = scores[idx[0] % len(scores)]
            idx[0] += 1
            return result

        result = cascaded_evaluate(
            mock_judge,
            'EC-01',
            'transcript',
            initial_reps=2,
            max_reps=5,
            disagreement_threshold=0.15,
            target_phi=0.95,  # High target to trigger escalation
        )

        # With high variance and high Φ target, should escalate
        assert result['n_reps'] > 2

    def test_respects_max_reps(self):
        """Should not exceed max_reps."""
        def mock_judge(neuron_id, transcript):
            return np.random.uniform(0, 1)  # High variance

        result = cascaded_evaluate(
            mock_judge,
            'EC-01',
            'transcript',
            initial_reps=3,
            max_reps=7,
            disagreement_threshold=0.01,  # Low threshold → escalate
            target_phi=0.95,  # High target → escalate
        )

        assert result['n_reps'] <= 7

    def test_median_point_estimate(self):
        """Point estimate should be median of all reps."""
        scores = [0.2, 0.5, 0.8]
        idx = [0]

        def mock_judge(neuron_id, transcript):
            result = scores[idx[0]]
            idx[0] += 1
            return result

        result = cascaded_evaluate(
            mock_judge,
            'EC-01',
            'transcript',
            initial_reps=3,
            max_reps=3,
        )

        assert abs(result['score'] - 0.5) < 0.01  # Median of [0.2, 0.5, 0.8]

    def test_confidence_interval_bounds(self):
        """CI should contain all rep scores."""
        np.random.seed(42)

        def mock_judge(neuron_id, transcript):
            return np.random.uniform(0.3, 0.7)

        result = cascaded_evaluate(
            mock_judge,
            'EC-01',
            'transcript',
            initial_reps=5,
            max_reps=5,
        )

        ci_lo, ci_hi = result['confidence_interval']
        scores = result['rep_scores']

        # All scores should be within or very close to CI
        assert min(scores) >= ci_lo - 0.01
        assert max(scores) <= ci_hi + 0.01


class TestBatchEvaluation:
    """Test batch cascaded evaluation."""

    def test_batch_returns_all_neurons(self):
        """Should return results for all neurons."""
        def mock_judge(neuron_id, transcript):
            return 0.6

        neurons = ['EC-01', 'EC-02', 'PR-01']
        result = batch_cascaded_evaluate(mock_judge, neurons, 'transcript')

        for neuron_id in neurons:
            assert neuron_id in result['results']

    def test_batch_summary_statistics(self):
        """Batch summary should have correct statistics."""
        def mock_judge(neuron_id, transcript):
            return 0.6

        neurons = [f'EC-{i:02d}' for i in range(1, 11)]  # 10 neurons
        result = batch_cascaded_evaluate(mock_judge, neurons, 'transcript')

        summary = result['summary']
        assert summary['n_neurons'] == 10
        assert summary['total_reps'] >= summary['n_neurons'] * 3  # At least 3 per

    def test_escalation_rate_computed(self):
        """Should compute escalation rate."""
        def mock_judge(neuron_id, transcript):
            return 0.6

        neurons = [f'EC-{i:02d}' for i in range(1, 6)]
        result = batch_cascaded_evaluate(mock_judge, neurons, 'transcript')

        summary = result['summary']
        assert 'escalation_rate' in summary
        assert 0 <= summary['escalation_rate'] <= 1.0


class TestSavingsComputation:
    """Test savings computation."""

    def test_savings_calculation(self):
        """Should compute correct savings."""
        fixed_total = 107 * 5  # 535 calls
        cascaded_total = 107 * 3 + 50 * 3  # Initial 3 + 50 escalations @ 3 more = 471

        savings = compute_savings(cascaded_total, fixed_n_reps=5, n_neurons=107)

        assert savings['fixed_n_approach'] == fixed_total
        assert savings['cascaded_approach'] == cascaded_total
        assert savings['savings_absolute'] == fixed_total - cascaded_total
        assert savings['savings_percent'] > 0

    def test_no_savings_if_all_escalate(self):
        """If all escalate to max_reps, savings approaches zero."""
        fixed_total = 107 * 5  # 535
        cascaded_total = 107 * 10  # All maxed out

        savings = compute_savings(cascaded_total, fixed_n_reps=5, n_neurons=107)

        # Should be negative (more calls)
        assert savings['savings_absolute'] < 0

    def test_savings_percentage(self):
        """Savings percentage should be between -100% and 100%."""
        fixed_total = 100
        cascaded_total = 70

        savings = compute_savings(cascaded_total, fixed_n_reps=5, n_neurons=20)

        assert -100 <= savings['savings_percent'] <= 100


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
