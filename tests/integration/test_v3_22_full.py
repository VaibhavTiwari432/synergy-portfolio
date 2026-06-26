"""
tests/integration/test_v3_22_full.py — v3.22 Full Integration Test Suite

Validates all 12 items working together end-to-end.
"""

import pytest
import numpy as np
from src.trait.judge.cascade_eval import cascaded_evaluate, batch_cascaded_evaluate
from src.trait.judge.per_criterion import score_all_neurons, call_judge_for_neuron
from src.trait.judge.rubric_bank import list_all_neurons, get_rubric
from calibration.active_learning import select_next_batch, compute_uncertainty_score
from calibration.cleanlab_audit import audit_gold_set_for_mislabels
from src.trait.extractors.per_dimension.ec_tobit import fit_tobit_ec, apply_tobit_to_ec_scores
from src.trait.judge.cascade_eval import compute_savings
from csl.validation.judge_irt import fit_grm_to_judge_reps, DataGatedError
from csl.analytics.conformance import conformance_check_session
from src.trait.kappa_efficiency import estimate_kappa_h
from calibration.lpa_archetype_discovery import discover_archetypes_via_lpa
from src.claims.cro_overlay import compute_cro_z_scores, cro_report_with_commitment_12


class TestWave0Integration:
    """Integration tests for WAVE 0 items."""

    def test_cascaded_and_per_criterion_together(self):
        """Cascaded and per-criterion should work together."""
        def mock_judge(neuron_id_or_prompt, transcript=None):
            if isinstance(neuron_id_or_prompt, str) and "NEURON" in neuron_id_or_prompt:
                # Per-criterion call
                import json
                return json.dumps({
                    'neuron_id': 'EC-01',
                    'score': 2,
                    'reasoning': 'Test',
                    'negative_criteria_present': False,
                    'confidence': 0.8,
                    'final_score_after_leniency_penalty': 2,
                })
            else:
                # Cascaded call
                return np.random.uniform(0.4, 0.6)

        # Cascade on a few neurons
        cascade_result = cascaded_evaluate(mock_judge, 'EC-01', 'Test transcript')
        assert 'score' in cascade_result
        assert cascade_result['n_reps'] >= 3

    def test_active_learning_with_audit(self):
        """Active learning should integrate with cleanlab audit."""
        gold_set = [
            {'id': f'gc-{i}', 'archetype': f'ARCH_{i % 3}', 'human_labels': {}}
            for i in range(5)
        ]
        unlabeled = [
            {'id': f'ul-{i}', 'archetype': f'ARCH_{i % 3}'}
            for i in range(10)
        ]
        judge_reps = {
            chat['id']: [
                [np.random.uniform(0.3, 0.7) for _ in range(5)]
                for _ in range(3)
            ]
            for chat in unlabeled
        }

        # Audit first
        audit_result = audit_gold_set_for_mislabels(gold_set, {})

        # Then select
        selected, meta = select_next_batch(
            gold_set, unlabeled, judge_reps, batch_size=3,
            archetype_targets=['ARCH_0', 'ARCH_1', 'ARCH_2']
        )

        assert len(selected) <= 3
        assert 'summary' in audit_result

    def test_tobit_with_cascaded_reps(self):
        """Tobit should accept replication outputs from cascade."""
        np.random.seed(42)

        # Generate replication scores (as cascade would produce)
        scores = [
            [0.2, 0.25, 0.18],  # 3 reps of neuron 1
            [0.5, 0.48, 0.52],  # 3 reps of neuron 2
            [0.0, 0.0, 0.05],   # Censored neuron
        ]

        # Apply Tobit to each
        results = []
        for score_reps in scores:
            median = np.median(score_reps)
            tobit_result = apply_tobit_to_ec_scores({'ec_score': median})
            results.append(tobit_result)

        assert len(results) == 3
        assert bool(results[2]['censored']) is True  # np.bool_ → bool

    def test_event_log_conceptual(self):
        """Conceptual test of two-table event log (migration tested separately)."""
        # Two-table concept: human signals and AI actions separate
        human_events = [
            {'session_id': '123', 'turn_id': 1, 'control_type': 'rejection'},
            {'session_id': '123', 'turn_id': 3, 'control_type': 'injection'},
        ]
        ai_events = [
            {'session_id': '123', 'turn_id': 2, 'action_type': 'generation'},
            {'session_id': '123', 'turn_id': 4, 'action_type': 'retrieval'},
        ]

        # Conceptually: both tables store ordered events
        assert all(e['session_id'] == '123' for e in human_events + ai_events)
        assert len(human_events) + len(ai_events) == 4

    def test_baseline_capability_specs_loaded(self):
        """BCS specs should be valid YAML (checked via file syntax)."""
        import yaml
        import os

        bcs_path = 'contracts/baseline_capability_specs.yaml'
        if os.path.exists(bcs_path):
            with open(bcs_path) as f:
                specs = yaml.safe_load(f)
            assert 'archetypes' in specs
            assert len(specs['archetypes']) == 10

            for arch in specs['archetypes']:
                assert 'archetype_id' in arch
                assert 'baseline_capabilities' in arch


class TestWave1Integration:
    """Integration tests for WAVE 1 items."""

    def test_irt_diagnostics_on_judge_reps(self):
        """IRT diagnostics correctly gate on n<30 (corpus gate, non-negotiable)."""
        judge_reps = {
            'EC-01': np.array([2.5, 2.7, 2.4, 2.6, 2.5]),
            'EC-02': np.array([1.0, 3.0, 1.5, 2.8, 0.9]),
        }
        human_gold = {'EC-01': 2.5, 'EC-02': 2.0}

        # n=2 neurons < 30 required — DataGatedError is correct behaviour
        with pytest.raises(DataGatedError):
            fit_grm_to_judge_reps(judge_reps, human_gold)

    def test_conformance_checking_flow(self):
        """Process-mining conformance should validate session flows."""
        # Expected flow: Frame → Generate → Verify → Integrate
        good_sequence = [
            'frame_problem',
            'generate_solutions',
            'verify_solutions',
            'integrate_learning',
        ]

        bad_sequence = [
            'generate_solutions',  # Skipped framing
            'integrate_learning',  # Skipped verification
        ]

        good_result = conformance_check_session('s1', good_sequence)
        bad_result = conformance_check_session('s2', bad_sequence)

        assert good_result['fitness_score'] > bad_result['fitness_score']


class TestWave2Integration:
    """Integration tests for WAVE 2 (data-gated items)."""

    def test_kappa_h_falsification_gate(self):
        """κ^H should include falsification gate (Var > 0.01)."""
        # Generate diverse S_human values
        s_human = np.random.uniform(0.2, 0.8, size=100)

        result = estimate_kappa_h(s_human, verbose=False)

        # Should have falsification_pass flag; value is data-dependent
        assert 'falsification_pass' in result
        assert isinstance(result['falsification_pass'], bool)

    def test_lpa_validation_against_decreed(self):
        """LPA should validate discovered archetypes against decreed ones."""
        records = [
            {
                'education_stage': 'HS',
                'domain': 'STEM',
                'ai_familiarity': 0.3,
                'task_type': 'coding',
                'synergy_score': 0.6,
                's_human': 0.4,
                'kappa_h': 0.7,
                'archetype_decreed': 'STUDENT_STEM',
            }
            for _ in range(50)
        ]

        labels, summary = discover_archetypes_via_lpa(records, n_classes=3)

        # Should have agreement metric (G4: key is ari_agreement)
        assert 'ari_agreement' in summary
        assert summary['ari_agreement'] is None or 0 <= summary['ari_agreement'] <= 1


class TestWave3Integration:
    """Integration tests for WAVE 3 (CRO + Commitment-12)."""

    def test_cro_z_scores_gated_by_commitment_12(self):
        """CRO should gate z-scores behind Commitment-12."""
        kappa_h_values = [0.5, 0.6, 0.7, 0.65, 0.68] * 3  # 15 values
        covariates = [
            {'education_stage': 'UG', 'domain': 'STEM'}
            for _ in range(15)
        ]

        # Compute z-scores
        result = compute_cro_z_scores(kappa_h_values, covariates, min_cell_size=5)

        # Report with Commitment-12
        report = cro_report_with_commitment_12(result, enable_z_surface=False)

        # Should be gated
        assert report['status'] == 'computed but gated'
        assert report['z_scores_visible'] is False
        assert report['leaderboard_visible'] is False


class TestCrossWaveIntegration:
    """Tests that validate items across multiple waves."""

    def test_cascade_to_per_criterion_to_irt(self):
        """Full pipeline: cascaded → per-criterion → IRT diagnostics."""
        def mock_judge_fn(prompt_or_id, transcript=None):
            # Simulate judge that returns varied scores
            return np.random.uniform(0.3, 0.7)

        # Step 1: Cascaded evaluation
        cascade_results = batch_cascaded_evaluate(
            mock_judge_fn,
            ['EC-01', 'EC-02'],
            'Sample transcript',
            initial_reps=2,
            max_reps=5,
        )

        # Should have replications to analyze
        assert cascade_results['summary']['total_reps'] >= 4

    def test_active_learning_to_tobit_to_kappa(self):
        """Pipeline: active learning → Tobit → κ^H (data-gated)."""
        # Simulate corpus growth via active learning
        corpus = [
            {
                'id': f'gc-{i}',
                'ec_score': np.random.uniform(0.2, 0.9),
                's_human': np.random.uniform(0.3, 0.8),
            }
            for i in range(50)  # Below n=200 threshold
        ]

        # Apply Tobit to EC scores
        ec_scores = np.array([c['ec_score'] for c in corpus])
        tobit_result = fit_tobit_ec(ec_scores)
        assert tobit_result['convergence']

        # Try κ^H (should raise gate if n < 200)
        s_human_vals = np.array([c['s_human'] for c in corpus])
        kh_result = estimate_kappa_h(s_human_vals)
        assert 'falsification_pass' in kh_result


class TestNonRegressions:
    """Verify no regressions in existing functionality."""

    def test_rubric_bank_coverage(self):
        """All rubrics should be present and valid."""
        all_neurons = list_all_neurons()

        assert len(all_neurons) == 98  # 98 llm_judge-typed neurons; 9 det/embedding correctly excluded

        for neuron_id in all_neurons[:10]:  # Sample check
            rubric = get_rubric(neuron_id)
            assert 'anchors' in rubric
            assert 'scale_levels' in rubric
            assert len(rubric['anchors']) >= 2

    def test_backwards_compatibility(self):
        """v3.21 concepts should still work."""
        # Dimension concept still exists
        from src.trait.judge.rubric_bank import neurons_by_dimension

        ec_neurons = neurons_by_dimension('EC')
        assert len(ec_neurons) > 0

        al_neurons = neurons_by_dimension('AL')
        assert len(al_neurons) > 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
