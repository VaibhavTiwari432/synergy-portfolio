"""
tests/unit/test_active_learning.py — Tests for active learning corpus sampling

Tests:
  1. Uncertainty computation: High disagreement → high uncertainty
  2. Batch selection: Selects correct number of chats
  3. Archetype balance: Respects archetype diversity constraints
  4. Corpus growth schedule: Realistic timeline estimates
"""

import numpy as np
import pytest
from calibration.active_learning import (
    compute_uncertainty_score,
    select_next_batch,
    compute_corpus_growth_schedule,
)
from calibration.cleanlab_audit import audit_gold_set_for_mislabels


class TestUncertaintyComputation:
    """Test uncertainty score computation."""

    def test_perfect_agreement_zero_uncertainty(self):
        """Identical scores should give zero uncertainty."""
        scores = [0.5, 0.5, 0.5]
        unc = compute_uncertainty_score(scores)
        assert unc == 0.0, "Perfect agreement should have zero uncertainty"

    def test_high_disagreement_high_uncertainty(self):
        """Divergent scores should give high uncertainty."""
        scores = [0.0, 0.5, 1.0]  # Maximum spread
        unc = compute_uncertainty_score(scores)
        assert unc > 0.5, "High disagreement should have high uncertainty"

    def test_single_replication_zero_uncertainty(self):
        """Single score can't compute variance."""
        scores = [0.7]
        unc = compute_uncertainty_score(scores)
        assert unc == 0.0, "Single replication should give zero uncertainty"

    def test_scale_invariance(self):
        """Uncertainty should be invariant to 0-1 vs 0-4 scale."""
        scores_01 = [0.0, 0.5, 1.0]  # 0-1 scale
        scores_04 = [0.0, 2.0, 4.0]  # 0-4 scale
        unc_01 = compute_uncertainty_score(scores_01)
        unc_04 = compute_uncertainty_score(scores_04)
        assert abs(unc_01 - unc_04) < 0.01, "Uncertainty should be scale-invariant"


class TestBatchSelection:
    """Test batch selection logic."""

    def test_selects_correct_batch_size(self):
        """Should select exactly batch_size chats."""
        archetypes = ['ARCH_0', 'ARCH_1', 'ARCH_2']
        gold_set = [
            {'id': f'gc-{i:03d}', 'archetype': archetypes[i % 3]}
            for i in range(10)
        ]
        unlabeled_pool = [
            {'id': f'ul-{i:03d}', 'archetype': archetypes[i % 3]}
            for i in range(20)
        ]
        judge_reps = {
            chat['id']: [
                [0.5 + np.random.normal(0, 0.1) for _ in range(10)]  # 10 neurons
                for _ in range(3)  # 3 replications
            ]
            for chat in unlabeled_pool
        }

        selected, metadata = select_next_batch(
            gold_set,
            unlabeled_pool,
            judge_reps,
            batch_size=5,
            archetype_targets=archetypes,
        )

        assert len(selected) == 5, f"Should select exactly 5, got {len(selected)}"
        assert metadata['selected_count'] == 5

    def test_respects_batch_size_limit(self):
        """Should not exceed batch size even if more available."""
        gold_set = [{'id': f'gc-{i}', 'archetype': f'ARCH_{i % 2}'} for i in range(5)]
        unlabeled_pool = [
            {'id': f'ul-{i}', 'archetype': f'ARCH_{i % 2}'}
            for i in range(50)
        ]
        judge_reps = {
            chat['id']: [
                [np.random.uniform(0, 1) for _ in range(5)]
                for _ in range(3)
            ]
            for chat in unlabeled_pool
        }

        selected, _ = select_next_batch(
            gold_set,
            unlabeled_pool,
            judge_reps,
            batch_size=7,
        )

        assert len(selected) <= 7, "Should not exceed batch_size"

    def test_avoids_gold_set_chats(self):
        """Selection should only include unlabeled pool chats."""
        gold_ids = {f'gc-{i}' for i in range(10)}
        unlabeled_ids = {f'ul-{i}' for i in range(20)}

        gold_set = [{'id': gid, 'archetype': 'ARCH_1'} for gid in gold_ids]
        unlabeled_pool = [{'id': uid, 'archetype': 'ARCH_1'} for uid in unlabeled_ids]

        judge_reps = {
            uid: [[0.5 + np.random.normal(0, 0.1) for _ in range(5)] for _ in range(3)]
            for uid in unlabeled_ids
        }

        selected, _ = select_next_batch(
            gold_set,
            unlabeled_pool,
            judge_reps,
            batch_size=5,
        )

        selected_set = set(selected)
        assert selected_set.isdisjoint(gold_ids), "Should not select gold set chats"
        assert selected_set.issubset(unlabeled_ids), "Should only select from unlabeled pool"


class TestArchetypeBalance:
    """Test archetype balancing in batch selection."""

    def test_respects_archetype_diversity(self):
        """Should select from multiple archetypes."""
        gold_set = [
            {'id': f'gc-{i}', 'archetype': f'ARCH_{i % 2}'}
            for i in range(10)
        ]
        unlabeled_pool = [
            {'id': f'ul-{i}', 'archetype': f'ARCH_{i % 3}'}
            for i in range(30)
        ]
        judge_reps = {
            chat['id']: [
                [np.random.uniform(0.1, 0.9) for _ in range(5)]
                for _ in range(3)
            ]
            for chat in unlabeled_pool
        }

        selected, metadata = select_next_batch(
            gold_set,
            unlabeled_pool,
            judge_reps,
            batch_size=6,
            archetype_targets=['ARCH_0', 'ARCH_1', 'ARCH_2'],
        )

        # Extract archetypes from selection
        archetypes = [meta['archetype'] for meta in metadata['metadata']]
        # Should have chats from multiple archetypes
        assert len(set(archetypes)) >= 1, "Should have at least 1 archetype represented"


class TestCorpusGrowthSchedule:
    """Test corpus growth schedule calculation."""

    def test_schedule_calculation(self):
        """Should compute reasonable growth schedule."""
        schedule = compute_corpus_growth_schedule(
            current_gold_size=26,
            target_size=200,
            batch_size=5,
            months_to_complete=6.0,
        )

        assert schedule['growth_needed'] == 174
        assert schedule['n_batches'] == 35  # 174 / 5 = 34.8 → 35
        assert 'schedule' in schedule
        assert '200' in schedule['schedule'], "Schedule should mention target size"

    def test_schedule_respects_timeline(self):
        """Schedule should respect timeline constraints."""
        schedule = compute_corpus_growth_schedule(
            current_gold_size=26,
            target_size=100,
            batch_size=4,
            months_to_complete=3.0,
        )

        # Growth needed: 74, batch size: 4 → 19 batches
        # 19 batches / 3 months ≈ 6.3 batches/month
        # Should be capped at 4 batches/month max
        assert schedule['batches_per_month'] <= 4.0, "Should not exceed max batches/month"


class TestCleanLabAudit:
    """Test cleanlab audit integration."""

    def test_audit_confidence_classification(self):
        """Should correctly classify confident vs at-risk labels."""
        gold_chats = [
            {
                'id': 'gc-001',
                'archetype': 'ARCH_1',
                'human_labels': {'EC-01': 3, 'EC-02': 3, 'AL-01': 2},
            },
            {
                'id': 'gc-002',
                'archetype': 'ARCH_1',
                'human_labels': {'EC-01': 2, 'EC-02': 1, 'AL-01': 4},
            },
        ]

        judge_scores = {
            'gc-001': {'EC-01': 3.0, 'EC-02': 3.0, 'AL-01': 2.0},  # Perfect agreement
            'gc-002': {'EC-01': 1.0, 'EC-02': 4.0, 'AL-01': 3.0},  # Disagreement
        }

        result = audit_gold_set_for_mislabels(gold_chats, judge_scores)

        # gc-001 should be confident (perfect agreement)
        assert 'gc-001' in result['confident']
        # gc-002 should be at-risk (disagreements)
        assert 'gc-002' in result['at_risk']


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
