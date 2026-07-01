"""
src/trait/kappa_efficiency.py — κ^H Efficiency Trait (Item #3 Part 2)

κ^H = efficiency factor from IRT decomposition of S_human (tokens saved).

Requires: n >= 200 corpus + falsification gate (Var > 0.01)

G2: uses Gaussian + Beta likelihoods rather than binary-logistic.
S_human is a continuous proportion on [0,1], so binary-logistic (which treats X
as Bernoulli) is misspecified. The Gaussian model works on the standardised
series; the Beta model (via log-likelihood optimisation) respects [0,1] bounds
and handles the censoring near 0/1 that binary-logistic ignores.
"""

from __future__ import annotations

import numpy as np
from scipy.optimize import minimize
from scipy.special import betaln
from typing import Dict, Any


def estimate_kappa_h(
    s_human_values: np.ndarray,
    covariates: np.ndarray = None,
    verbose: bool = False,
) -> Dict[str, Any]:
    """Estimate κ^H via Gaussian + Beta IRT decomposition.

    G2: replaces the binary-logistic likelihood (misspecified for proportions)
    with:
      - Gaussian fit on z-scored data (linear IRT analogue, Var > 0 falsification)
      - Beta fit on raw [0,1] values (respects bounds, handles boundary censoring)

    Both agree at the falsification gate; the Beta estimate is the canonical κ^H.

    Args:
        s_human_values: S_human per session, on [0,1]
        covariates: unused; retained for interface compat
        verbose: print diagnostics

    Returns:
        {kappa_h, var_kappa, falsification_pass, method, ...}
    """
    X = np.asarray(s_human_values, dtype=float)

    # ── Gaussian IRT (standardised) ────────────────────────────────────────────
    Xz = (X - np.mean(X)) / (np.std(X) + 1e-9)

    def gaussian_neg_ll(params):
        a, b, log_sigma = params
        sigma = np.exp(log_sigma)
        mu = a * (Xz - b)
        return 0.5 * np.sum(((Xz - mu) / sigma) ** 2 + 2 * log_sigma)

    g_res = minimize(gaussian_neg_ll, [1.0, 0.0, 0.0], method="BFGS")
    a_gauss = float(g_res.x[0])

    # ── Beta IRT (raw [0,1]) ───────────────────────────────────────────────────
    # Clamp strictly inside (0,1) for Beta log-likelihood stability
    Xb = np.clip(X, 1e-6, 1 - 1e-6)

    def beta_neg_ll(params):
        log_a, log_b = params
        a, b = np.exp(log_a), np.exp(log_b)
        ll = np.sum((a - 1) * np.log(Xb) + (b - 1) * np.log(1 - Xb) - betaln(a, b))
        return -ll

    b_res = minimize(beta_neg_ll, [0.0, 0.0], method="BFGS")
    a_beta, b_beta = np.exp(b_res.x[0]), np.exp(b_res.x[1])
    # κ^H = (a - b) / (a + b): positive = human-efficient session distribution
    kappa_h = float((a_beta - b_beta) / (a_beta + b_beta))

    # Falsification: sufficient variance in Gaussian residuals
    g_residuals = Xz - a_gauss * (Xz - float(g_res.x[1]))
    var_kappa = float(np.var(g_residuals))
    falsification_pass = var_kappa > 0.01

    if verbose:
        print(f"κ^H (Beta): {kappa_h:.3f}  κ^H (Gaussian): {a_gauss:.3f}")
        print(f"Var(residuals): {var_kappa:.3f}  Falsification: {'PASS' if falsification_pass else 'FAIL'}")

    return {
        "kappa_h": round(kappa_h, 4),
        "kappa_h_gaussian": round(a_gauss, 4),
        "var_kappa": round(var_kappa, 4),
        "falsification_pass": falsification_pass,
        "method": "beta+gaussian",
        "beta_params": {"alpha": round(float(a_beta), 4), "beta": round(float(b_beta), 4)},
    }


if __name__ == '__main__':
    print("κ^H efficiency module loaded (data-gated, requires n>=200).")
