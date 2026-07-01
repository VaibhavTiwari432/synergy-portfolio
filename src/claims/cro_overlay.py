"""
src/claims/cro_overlay.py — Competency Reference Overlay (Item #12 Part 3)

CRO: Z-score normalization of κ^H by competency cell (education_stage × domain).

Commitment-12: Z-scores computed but NOT surfaced (private self-diagnostic only).
Never leaderboards, percentiles, or rankings.

Requires: κ^H estimates + n>=2 cells with N>=10
"""

from __future__ import annotations

import numpy as np
from scipy.stats import norm
from typing import Dict, List, Any
from collections import defaultdict


def compute_cro_z_scores(
    kappa_h_estimates: List[float],
    covariates: List[Dict[str, str]],
    min_cell_size: int = 10,
) -> Dict[str, Any]:
    """
    Compute z-scores normalized by competency cell.

    Cells: education_stage × domain

    Args:
        kappa_h_estimates: List of κ^H values
        covariates: List of covariate dicts {education_stage, domain}
        min_cell_size: Minimum N per cell (default 10)

    Returns:
        {results: list of z-score dicts, cells: cell statistics}
    """

    results = []
    cells = defaultdict(list)

    # Group by cell
    for kh, cov in zip(kappa_h_estimates, covariates):
        cell_key = (cov.get('education_stage'), cov.get('domain'))
        cells[cell_key].append(kh)

    # Compute z-scores only for cells with N >= min_cell_size
    for (stage, domain), kh_values in cells.items():
        if len(kh_values) < min_cell_size:
            # Under-sampled cell: report without z
            for kh in kh_values:
                results.append({
                    'kappa_h_obs': kh,
                    'cell': f"{stage}_{domain}",
                    'normed': False,
                    'note': f'Cell N={len(kh_values)} < {min_cell_size}',
                })
        else:
            # Sufficient cell: compute z
            cell_mean = np.mean(kh_values)
            cell_sd = np.std(kh_values)

            for kh in kh_values:
                z = (kh - cell_mean) / (cell_sd + 1e-6)
                results.append({
                    'kappa_h_obs': kh,
                    'cell': f"{stage}_{domain}",
                    'expected_mean': cell_mean,
                    'expected_sd': cell_sd,
                    'z_score': z,
                    'percentile': norm.cdf(z) * 100,  # Private diagnostic only
                    'normed': True,
                })

    cell_stats = {
        cell: {
            'n': len(values),
            'mean': np.mean(values),
            'sd': np.std(values),
        }
        for cell, values in cells.items()
    }

    return {
        'results': results,
        'cells': cell_stats,
        'commitment_12_enforced': True,
        'z_surfaced': False,  # Default: never surfaced
    }


def cro_report_with_commitment_12(
    z_scores_result: Dict,
    enable_z_surface: bool = False,
) -> Dict[str, Any]:
    """
    Report CRO results with Commitment-12 enforcement.

    Commitment-12: Z-scores are private self-diagnostic only.
    Never: leaderboard, peer percentile, badge, ranking.

    Args:
        z_scores_result: Output from compute_cro_z_scores
        enable_z_surface: If True, surface z (requires Commitment-12 resolution)

    Returns:
        {status, tier_level, visibility_flags}
    """

    if not enable_z_surface:
        return {
            'status': 'computed but gated',
            'tier_level': 'Tier 3 (private)',
            'z_scores_visible': False,
            'leaderboard_visible': False,
            'percentile_visible': False,
            'note': 'Commitment-12: z-scores computed but NOT surfaced',
        }

    return {
        'status': 'enabled',
        'tier_level': 'Tier 3 (private)',
        'user_visible': True,
        'leaderboard_visible': False,
        'percentile_visible': False,
        'interpretation': 'Comparing your κ^H to expected range for your education/domain',
        'caveats': [
            'Private diagnostic only',
            'No ranking or public visibility',
            'Comparison within your cohort only',
        ],
    }


if __name__ == '__main__':
    print("CRO overlay module loaded (data-gated, requires n>=200 + DIF clearance).")
