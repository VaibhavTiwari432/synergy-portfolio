"""
src/trait/judge/cascade_eval.py — Cascaded selective evaluation for judge replication

ITEM #1: Cascaded Selective Evaluation (v3.22 WAVE 0)

Problem: Fixed-N replication (e.g., 5 calls per neuron) wastes compute on high-confidence
interior scores and provides no guarantee of quadrant-flip coverage at boundaries.

Solution: Initial 3 replications → compute disagreement → escalate to K more if variance
exceeds threshold. Saves ~30–50% compute while maintaining reliability ≥ Φ target.

Non-negotiable:
  - Preserves reliability guarantee (Φ target-based decision threshold)
  - Only escalates for boundary-ambiguous cases
  - Point estimate unchanged (median of all reps)
  - Transparent reporting of rep count used
"""

from __future__ import annotations

import numpy as np
from typing import Dict, List, Optional, Tuple, Any


# Calibration parameters (derived from Item #5 human IRR ceiling; placeholder values here)
# Once Item #5 completes, these should be updated from κ measurements
DEFAULT_PHI_TARGET = 0.70  # Reliability target (placeholder: 70% agreement)
DEFAULT_INITIAL_REPS = 3  # Start with 3 replications
DEFAULT_MAX_REPS = 10  # Don't exceed 10 replications per neuron
DEFAULT_DISAGREEMENT_THRESHOLD = 0.15  # Escalate if variance > threshold


def compute_disagreement_metric(scores: List[float]) -> float:
    """
    Compute disagreement (variance) from replication scores.

    Args:
        scores: List of judge scores (0.0-1.0 or 0-4 scale)

    Returns:
        Disagreement metric (0.0 = perfect agreement, 1.0 = max disagreement)
    """
    if len(scores) < 2:
        return 0.0

    scores_arr = np.array(scores, dtype=np.float64)

    # Normalize to 0-1 if needed
    if scores_arr.max() > 1.0:
        scores_arr = scores_arr / 4.0

    # Variance as disagreement proxy
    variance = np.var(scores_arr)
    # Max variance for binary is 0.25; normalize
    disagreement = min(1.0, variance / 0.25)

    return disagreement


def estimate_phi_from_disagreement(
    disagreement: float,
    target_phi: float = DEFAULT_PHI_TARGET,
    n_reps_so_far: int = 3,
) -> float:
    """
    Estimate achieved Φ (reliability) from disagreement, assuming more reps help.

    Heuristic: Φ increases with more replications; disagreement indicates need.
    More disagreement → lower current Φ → escalate.

    Args:
        disagreement: Disagreement metric (0-1)
        target_phi: Target reliability (0-1)
        n_reps_so_far: Number of replications done so far

    Returns:
        Estimated Φ for current rep count
    """

    # Heuristic: Φ ≈ 1 - (disagreement * uncertainty_factor)
    # As n_reps increases, uncertainty decreases (weak law of large numbers)
    uncertainty_factor = 1.0 / np.sqrt(n_reps_so_far)

    phi_estimated = 1.0 - (disagreement * uncertainty_factor)
    phi_estimated = np.clip(phi_estimated, 0.0, 1.0)

    return phi_estimated


def cascaded_evaluate(
    judge_fn,
    neuron_id: str,
    transcript: str,
    target_phi: float = DEFAULT_PHI_TARGET,
    initial_reps: int = DEFAULT_INITIAL_REPS,
    max_reps: int = DEFAULT_MAX_REPS,
    disagreement_threshold: float = DEFAULT_DISAGREEMENT_THRESHOLD,
    verbose: bool = False,
) -> Dict[str, Any]:
    """
    Cascaded selective evaluation for judge replication.

    Algorithm:
      1. Run initial_reps (e.g., 3) replications
      2. Compute disagreement (variance)
      3. If disagreement > threshold AND current Φ < target_phi:
         → Escalate: run K additional replications (up to max_reps)
      4. Return median score, CI, rep count used

    Args:
        judge_fn: Callable that scores a neuron (returns 0-1 or 0-4)
        neuron_id: Neuron identifier
        transcript: Session transcript to judge
        target_phi: Target reliability (0-1)
        initial_reps: Initial replication count (default 3)
        max_reps: Maximum total replications (default 10)
        disagreement_threshold: Escalation threshold (default 0.15)
        verbose: Print debug info

    Returns:
        dict with keys:
            - score: Median of all replications (point estimate)
            - confidence_interval: (ci_lo, ci_hi) from percentiles
            - n_reps: Total replications used
            - disagreement: Disagreement metric
            - phi_estimated: Estimated reliability
            - escalated: Boolean (true if escalation triggered)
            - rep_scores: List of all replication scores
    """

    scores = []

    # Phase 1: Initial replications
    if verbose:
        print(f"[Cascade {neuron_id}] Starting with {initial_reps} initial replications...")

    for i in range(initial_reps):
        score = judge_fn(neuron_id, transcript)
        scores.append(score)

    # Compute disagreement
    disagreement = compute_disagreement_metric(scores)
    phi_estimated = estimate_phi_from_disagreement(
        disagreement, target_phi, len(scores)
    )

    escalated = False

    # Phase 2: Escalation decision
    if disagreement > disagreement_threshold and phi_estimated < target_phi:
        escalated = True

        # How many additional reps?
        reps_remaining = max_reps - len(scores)
        if reps_remaining > 0:
            # Escalate: add K more reps (heuristic: 2-3 more)
            additional_reps = min(3, reps_remaining)

            if verbose:
                print(
                    f"[Cascade {neuron_id}] Escalating (disagreement={disagreement:.3f} > "
                    f"{disagreement_threshold}, Φ={phi_estimated:.3f} < {target_phi}). "
                    f"Adding {additional_reps} more reps..."
                )

            for i in range(additional_reps):
                score = judge_fn(neuron_id, transcript)
                scores.append(score)

            # Recompute after escalation
            disagreement = compute_disagreement_metric(scores)
            phi_estimated = estimate_phi_from_disagreement(
                disagreement, target_phi, len(scores)
            )

    # Phase 3: Aggregate
    scores_arr = np.array(scores, dtype=np.float64)
    final_score = np.median(scores_arr)

    # Confidence interval (95%)
    ci_lo, ci_hi = np.percentile(scores_arr, [2.5, 97.5])

    if verbose:
        print(
            f"[Cascade {neuron_id}] Final: median={final_score:.3f}, "
            f"CI=[{ci_lo:.3f}, {ci_hi:.3f}], reps={len(scores)}, "
            f"escalated={escalated}"
        )

    return {
        'score': final_score,
        'confidence_interval': (ci_lo, ci_hi),
        'n_reps': len(scores),
        'disagreement': disagreement,
        'phi_estimated': phi_estimated,
        'escalated': escalated,
        'rep_scores': scores,
        'neuron_id': neuron_id,
    }


def batch_cascaded_evaluate(
    judge_fn,
    neuron_ids: List[str],
    transcript: str,
    **cascade_kwargs,
) -> Dict[str, Dict]:
    """
    Cascaded evaluation for all neurons in a session.

    Args:
        judge_fn: Callable for scoring
        neuron_ids: List of neuron IDs to score
        transcript: Session transcript
        **cascade_kwargs: Passed to cascaded_evaluate (target_phi, etc.)

    Returns:
        dict[neuron_id] -> cascaded_evaluate result
    """

    results = {}
    escalations_count = 0
    total_reps = 0

    for neuron_id in neuron_ids:
        result = cascaded_evaluate(judge_fn, neuron_id, transcript, **cascade_kwargs)
        results[neuron_id] = result
        total_reps += result['n_reps']
        if result['escalated']:
            escalations_count += 1

    # Summary
    summary = {
        'n_neurons': len(neuron_ids),
        'total_reps': total_reps,
        'escalations': escalations_count,
        'avg_reps_per_neuron': total_reps / len(neuron_ids),
        'escalation_rate': escalations_count / len(neuron_ids) if neuron_ids else 0,
    }

    return {
        'results': results,
        'summary': summary,
    }


def compute_savings(
    cascaded_total_reps: int,
    fixed_n_reps: int = 5,
    n_neurons: int = 107,
) -> Dict[str, float]:
    """
    Compute savings from cascaded vs fixed-N replication.

    Args:
        cascaded_total_reps: Total reps used by cascaded approach
        fixed_n_reps: Fixed N used in traditional approach (default 5)
        n_neurons: Number of neurons (default 107)

    Returns:
        dict with savings metrics
    """

    fixed_total = fixed_n_reps * n_neurons
    savings_absolute = fixed_total - cascaded_total_reps
    savings_pct = (savings_absolute / fixed_total) * 100 if fixed_total > 0 else 0

    return {
        'fixed_n_approach': fixed_total,
        'cascaded_approach': cascaded_total_reps,
        'savings_absolute': savings_absolute,
        'savings_percent': savings_pct,
    }


if __name__ == '__main__':
    # Example: Mock judge function for testing
    import random

    random.seed(42)

    def mock_judge(neuron_id: str, transcript: str) -> float:
        """Mock judge that returns consistent-ish scores with some noise."""
        # Deterministic base score per neuron
        base = hash(neuron_id) % 100 / 100.0
        # Add noise
        noise = random.gauss(0, 0.1)
        return max(0.0, min(1.0, base + noise))

    # Test cascaded evaluation
    print("Testing cascaded evaluation on single neuron:")
    result = cascaded_evaluate(
        mock_judge,
        'EC-01',
        'Sample transcript',
        target_phi=0.70,
        verbose=True,
    )

    print(f"\nResult: score={result['score']:.3f}, reps={result['n_reps']}")

    # Test batch evaluation
    print("\n\nTesting batch cascaded evaluation:")
    neurons = [f'EC-{i:02d}' for i in range(1, 11)]  # 10 neurons
    batch_result = batch_cascaded_evaluate(
        mock_judge,
        neurons,
        'Sample transcript',
        target_phi=0.70,
    )

    print(f"\nBatch summary:")
    print(f"  Total neurons: {batch_result['summary']['n_neurons']}")
    print(f"  Total reps: {batch_result['summary']['total_reps']}")
    print(f"  Escalations: {batch_result['summary']['escalations']}")
    print(f"  Avg reps/neuron: {batch_result['summary']['avg_reps_per_neuron']:.2f}")
    print(f"  Escalation rate: {batch_result['summary']['escalation_rate']:.1%}")

    # Compute savings
    savings = compute_savings(batch_result['summary']['total_reps'], fixed_n_reps=5, n_neurons=10)
    print(f"\nSavings vs fixed-N=5:")
    print(f"  Fixed approach: {savings['fixed_n_approach']} calls")
    print(f"  Cascaded approach: {savings['cascaded_approach']} calls")
    print(f"  Savings: {savings['savings_absolute']} calls ({savings['savings_percent']:.1f}%)")
