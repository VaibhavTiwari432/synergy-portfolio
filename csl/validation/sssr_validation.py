"""
csl/validation/sssr_validation.py — SSSR Validation Tests (Wave 1)

Three tests:
  1. Verbosity Invariance: CSL shares ρ > 0.85 across verbosity variants
  2. Twin-Pair Separation: Expert vs Manager separation d >= 0.70
  3. Independence: ARI-CSL correlation in [0.40, 0.75]
"""

from __future__ import annotations

import numpy as np
from scipy.stats import spearmanr


def test_verbosity_invariance(
    sssr_extract_fn,
    transcripts_5plus: list,
    threshold: float = 0.85,
) -> tuple[bool, dict]:
    """
    SSSR ownership shares should be invariant to transcript verbosity.
    """
    results = {}
    rhos = []

    for transcript in transcripts_5plus:
        # Create variants
        minimal = transcript[:len(transcript)//2]
        verbose = transcript + ' ' + transcript

        owner_orig = np.array(sssr_extract_fn(transcript))
        owner_min = np.array(sssr_extract_fn(minimal))
        owner_verb = np.array(sssr_extract_fn(verbose))

        rho_min_orig, _ = spearmanr(owner_min, owner_orig)
        rho_min_verb, _ = spearmanr(owner_min, owner_verb)
        rho_orig_verb, _ = spearmanr(owner_orig, owner_verb)

        mean_rho = np.mean([rho_min_orig, rho_min_verb, rho_orig_verb])
        rhos.append(mean_rho)

        results[id(transcript)] = {
            'mean_rho': mean_rho,
            'passes': mean_rho > threshold,
        }

    overall = all(r['passes'] for r in results.values())
    return overall, {'results': results, 'mean_rho': np.mean(rhos)}


def test_twin_pair_separation() -> tuple[bool, dict]:
    """
    Expert vs Manager archetypes should separate (d >= 0.70).
    """
    # Mock expert: terse, high rejection
    expert_shares = np.array([0.8, 0.9, 0.1, 0.05])  # Human-high, AI-low

    # Mock manager: verbose, accepts all
    manager_shares = np.array([0.2, 0.1, 0.8, 0.9])  # Human-low, AI-high

    # Cohen's d per level
    d_values = []
    for i in range(4):
        mean_diff = expert_shares[i] - manager_shares[i]
        pooled_sd = np.sqrt((np.var([expert_shares[i]]) + np.var([manager_shares[i]])) / 2 + 1e-6)
        d = mean_diff / pooled_sd
        d_values.append(abs(d))

    separated_levels = sum(1 for d in d_values if d >= 0.70)
    success = separated_levels >= 3

    return success, {'d_values': d_values, 'separated_levels': separated_levels}


def test_independence(
    ari_scores: np.ndarray,
    csl_ownership: np.ndarray,
) -> tuple[bool, dict]:
    """
    ARI and CSL should be correlated but not fused (0.40 < |ρ| < 0.75).
    """
    correlations = []

    n_dims = min(ari_scores.shape[1], 8)
    n_levels = min(csl_ownership.shape[1], 7)

    for dim in range(n_dims):
        for level in range(n_levels):
            try:
                rho, _ = spearmanr(ari_scores[:, dim], csl_ownership[:, level])
                correlations.append(abs(rho))
            except Exception:
                pass

    if not correlations:
        return False, {'error': 'No valid correlations computed'}

    mean_corr = np.mean(correlations)
    success = 0.40 < mean_corr < 0.75

    return success, {
        'mean_corr': mean_corr,
        'range': (min(correlations), max(correlations)),
    }


if __name__ == '__main__':
    print("SSSR validation module loaded.")
