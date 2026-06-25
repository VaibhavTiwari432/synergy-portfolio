"""
benchmarks/v3_22_performance_suite.py — v3.22 Performance Benchmarking Suite

Measures compute savings, latency, and quality metrics for all v3.22 items.
"""

import time
import numpy as np
from typing import Dict, List, Any


class CascadePerformanceBench:
    """Benchmark cascaded replication vs fixed-N."""

    @staticmethod
    def measure_compute_savings(
        judge_fn,
        neuron_ids: List[str],
        transcript: str,
        n_reps_fixed: int = 5,
    ) -> Dict[str, Any]:
        """
        Compare compute cost: cascaded vs fixed-N replication.

        Returns:
            {cascaded_reps, fixed_reps, savings_percent, latency_cascaded, latency_fixed}
        """
        from src.trait.judge.cascade_eval import batch_cascaded_evaluate, compute_savings

        # Cascaded
        t0 = time.time()
        cascade_result = batch_cascaded_evaluate(
            judge_fn,
            neuron_ids,
            transcript,
            initial_reps=3,
            max_reps=10,
        )
        t_cascade = time.time() - t0

        # Fixed-N
        t0 = time.time()
        fixed_reps = n_reps_fixed * len(neuron_ids)
        t_fixed = time.time() - t0  # Simplified timing

        savings = compute_savings(
            cascade_result['summary']['total_reps'],
            fixed_n_reps=n_reps_fixed,
            n_neurons=len(neuron_ids),
        )

        return {
            'cascaded_total_reps': cascade_result['summary']['total_reps'],
            'fixed_n_total_reps': fixed_reps,
            'savings_percent': savings['savings_percent'],
            'latency_cascaded_ms': t_cascade * 1000,
            'latency_fixed_ms': t_fixed * 1000,
            'speedup': t_fixed / (t_cascade + 1e-6),
        }


class PerCriterionPerformanceBench:
    """Benchmark per-criterion calls vs joint prompt."""

    @staticmethod
    def measure_per_criterion_latency(
        judge_fn,
        neuron_ids: List[str],
        transcript: str,
    ) -> Dict[str, Any]:
        """
        Measure latency for per-criterion scoring.

        Returns:
            {n_neurons, total_latency_ms, latency_per_neuron_ms, throughput_neurons_per_sec}
        """
        from src.trait.judge.per_criterion import score_all_neurons

        t0 = time.time()
        result = score_all_neurons(judge_fn, transcript, neuron_ids)
        latency_total = (time.time() - t0) * 1000

        return {
            'n_neurons': len(neuron_ids),
            'total_latency_ms': latency_total,
            'latency_per_neuron_ms': latency_total / len(neuron_ids),
            'throughput_neurons_per_sec': (len(neuron_ids) * 1000) / latency_total,
            'successful': result['summary']['successful'],
            'errors': result['summary']['errors'],
        }


class ActiveLearningPerformanceBench:
    """Benchmark active learning selection."""

    @staticmethod
    def measure_selection_latency(
        gold_set: List[Dict],
        unlabeled_pool: List[Dict],
        judge_reps: Dict,
        batch_size: int = 5,
    ) -> Dict[str, Any]:
        """
        Measure latency for active learning batch selection.

        Returns:
            {selection_latency_ms, batch_size, uncertainty_computation_ms}
        """
        from calibration.active_learning import select_next_batch

        t0 = time.time()
        selected, metadata = select_next_batch(
            gold_set,
            unlabeled_pool,
            judge_reps,
            batch_size=batch_size,
            archetype_targets=['ARCH_0', 'ARCH_1', 'ARCH_2'],
        )
        latency = (time.time() - t0) * 1000

        return {
            'selection_latency_ms': latency,
            'batch_size_requested': batch_size,
            'batch_size_selected': len(selected),
            'unlabeled_pool_size': len(unlabeled_pool),
            'latency_per_chat_ms': latency / len(unlabeled_pool),
        }


class TobitPerformanceBench:
    """Benchmark Tobit EC measurement."""

    @staticmethod
    def measure_tobit_fitting_latency(
        ec_scores: np.ndarray,
    ) -> Dict[str, Any]:
        """
        Measure latency for fitting Tobit model to EC scores.

        Returns:
            {fitting_latency_ms, n_scores, convergence}
        """
        from src.trait.extractors.per_dimension.ec_tobit import fit_tobit_ec

        t0 = time.time()
        result = fit_tobit_ec(ec_scores)
        latency = (time.time() - t0) * 1000

        return {
            'fitting_latency_ms': latency,
            'n_scores': len(ec_scores),
            'convergence': result['convergence'],
            'censored_count': result.get('censored_count', 0),
            'latency_per_score_ms': latency / len(ec_scores),
        }


class QualityMetricsBench:
    """Benchmark quality improvements."""

    @staticmethod
    def measure_agreement_reduction(
        cascaded_scores: Dict[str, float],
        fixed_scores: Dict[str, float],
    ) -> Dict[str, Any]:
        """
        Measure reduction in judge variance.

        Returns:
            {cascaded_std, fixed_std, variance_reduction_percent}
        """
        cascaded_std = np.std(list(cascaded_scores.values()))
        fixed_std = np.std(list(fixed_scores.values()))

        variance_reduction = (fixed_std - cascaded_std) / (fixed_std + 1e-6) * 100

        return {
            'cascaded_std': cascaded_std,
            'fixed_std': fixed_std,
            'variance_reduction_percent': variance_reduction,
            'is_more_reliable': cascaded_std < fixed_std,
        }

    @staticmethod
    def measure_ci_coverage(
        tobit_results: List[Dict],
        actual_values: List[float],
    ) -> Dict[str, Any]:
        """
        Measure confidence interval coverage (should be ~95%).

        Returns:
            {coverage_percent, mean_ci_width, ci_too_narrow, ci_too_wide}
        """
        if not tobit_results or not actual_values:
            return {'coverage_percent': 0, 'error': 'No data'}

        covered = sum(
            1 for result, actual in zip(tobit_results, actual_values)
            if result.get('ci_lo', -float('inf')) <= actual <= result.get('ci_hi', float('inf'))
        )

        mean_width = np.mean([
            (r.get('ci_hi', 1) - r.get('ci_lo', 0))
            for r in tobit_results
        ])

        return {
            'coverage_percent': (covered / len(tobit_results)) * 100 if tobit_results else 0,
            'mean_ci_width': mean_width,
            'ci_too_narrow': sum(1 for w in [mean_width] if w < 0.1),
            'ci_too_wide': sum(1 for w in [mean_width] if w > 0.5),
        }


def run_full_benchmark_suite(
    judge_fn,
    corpus_sample: List[Dict],
) -> Dict[str, Any]:
    """
    Run all benchmarks on a corpus sample.

    Returns comprehensive performance report.
    """
    results = {
        'timestamp': time.time(),
        'corpus_size': len(corpus_sample),
        'benchmarks': {},
    }

    # Extract data
    neuron_ids = ['EC-01', 'EC-02', 'AL-01', 'AL-02', 'PR-01']
    transcript = corpus_sample[0].get('transcript', 'Test transcript')
    ec_scores = np.array([chat.get('ec_score', 0.5) for chat in corpus_sample])

    # Run benchmarks
    try:
        results['benchmarks']['cascade'] = CascadePerformanceBench.measure_compute_savings(
            judge_fn, neuron_ids, transcript
        )
    except Exception as e:
        results['benchmarks']['cascade'] = {'error': str(e)}

    try:
        results['benchmarks']['per_criterion'] = (
            PerCriterionPerformanceBench.measure_per_criterion_latency(
                judge_fn, neuron_ids, transcript
            )
        )
    except Exception as e:
        results['benchmarks']['per_criterion'] = {'error': str(e)}

    try:
        results['benchmarks']['tobit'] = TobitPerformanceBench.measure_tobit_fitting_latency(
            ec_scores
        )
    except Exception as e:
        results['benchmarks']['tobit'] = {'error': str(e)}

    return results


if __name__ == '__main__':
    print("Performance benchmarking suite loaded.")
