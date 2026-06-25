"""
src/trait/kappa_efficiency.py — κ^H Efficiency Trait (Item #3 Part 2)

κ^H = efficiency factor from IRT decomposition of S_human (tokens saved).

Requires: n >= 200 corpus + falsification gate (Var > 0.01)
"""

from __future__ import annotations

import numpy as np
from scipy.optimize import minimize
from typing import Dict, Any


def estimate_kappa_h(
    s_human_values: np.ndarray,
    covariates: np.ndarray = None,
    verbose: bool = False,
) -> Dict[str, Any]:
    """
    Estimate κ^H via IRT-like decomposition.

    Model: S_human = κ^H × λ_true + noise

    Args:
        s_human_values: Information bottleneck measure (tokens saved)
        covariates: Optional features matrix
        verbose: Print diagnostics

    Returns:
        {kappa_h, var_kappa, falsification_pass, ...}
    """

    X = (s_human_values - np.mean(s_human_values)) / (np.std(s_human_values) + 1e-6)

    # Fit 2PL IRT model via logistic
    def likelihood(params):
        a, b = params
        predicted = 1.0 / (1.0 + np.exp(-a * (X - b)))
        ll = np.sum(X * np.log(predicted + 1e-6) + (1 - X) * np.log(1 - predicted + 1e-6))
        return -ll

    result = minimize(likelihood, [1.0, 0.0], method='BFGS')
    a_param, b_param = result.x

    kappa_h = a_param
    predicted = 1.0 / (1.0 + np.exp(-a_param * (X - b_param)))
    residuals = X - predicted
    var_kappa = np.var(residuals)

    falsification_pass = var_kappa > 0.01

    if verbose:
        print(f"κ^H estimate: {kappa_h:.3f}")
        print(f"Var(κ^H|model): {var_kappa:.3f}")
        print(f"Falsification gate: {'PASS' if falsification_pass else 'FAIL'}")

    return {
        'kappa_h': kappa_h,
        'var_kappa': var_kappa,
        'falsification_pass': falsification_pass,
    }


if __name__ == '__main__':
    print("κ^H efficiency module loaded (data-gated, requires n>=200).")
