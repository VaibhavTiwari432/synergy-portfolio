"""
csl/validation/judge_irt.py — IRT Diagnostics on Judge Output (Item #3 Part 1)

Purpose: Decompose judge error into noise vs bias via Bayesian GRM proxy.
Outputs per-neuron discrimination (a) and difficulty (d) parameters to guide rubric iteration.

G1 requirement: n≥30 gold-labeled replications before fitting; raises DataGatedError otherwise.
The fit uses a Bayesian-flavoured regularised logistic model (L2 prior as Gaussian prior on a,d)
rather than the earlier unregularised proxy — matches GRM spirit without a full MCMC stack.
"""

from __future__ import annotations

import numpy as np
from typing import Dict, Any

#: G1: minimum number of (neuron_id, human_label) pairs required before fitting.
_MIN_FIT_N = 30


class DataGatedError(Exception):
    """Raised when corpus is too small to fit reliably (non-negotiable: no pilot fitting)."""


def fit_grm_to_judge_reps(
    judge_replications: Dict[str, np.ndarray],
    human_gold: Dict[str, int],
) -> Dict[str, Dict[str, Any]]:
    """Fit Bayesian-GRM proxy to judge replications.

    G1: requires n≥30 (neuron, human_gold) pairs; raises DataGatedError with n<30.
    Uses L2-regularised logistic regression as a Gaussian-prior GRM proxy —
    avoids the unregularised model's arbitrary coef scale on small samples.

    Args:
        judge_replications: dict[neuron_id] -> array of scores from K replications
        human_gold: dict[neuron_id] -> human consensus label (0-4)

    Returns:
        dict[neuron_id] -> {discrimination, difficulty, interpretation, n_reps, ...}
    """
    from sklearn.linear_model import LogisticRegression

    paired = {nid: human_gold[nid] for nid in judge_replications if nid in human_gold}
    n = len(paired)
    if n < _MIN_FIT_N:
        raise DataGatedError(
            f"fit_grm_to_judge_reps requires n≥{_MIN_FIT_N} gold-labeled neurons; "
            f"got {n}. Collect more gold annotations before running IRT diagnostics. "
            "(non-negotiable: no pilot fitting on <30 samples)"
        )

    results: Dict[str, Dict[str, Any]] = {}
    for neuron_id, rep_scores in judge_replications.items():
        human_label = human_gold.get(neuron_id)
        if human_label is None:
            continue

        reps = np.asarray(rep_scores, dtype=float)
        judge_consensus = float(np.median(reps))
        n_reps = len(reps)

        try:
            # G1: L2 (C=1.0) = Gaussian(0,1) prior on weights → GRM-spirit regularisation
            clf = LogisticRegression(C=1.0, random_state=42, max_iter=500)
            X = reps.reshape(-1, 1)
            y = np.full(n_reps, human_label)
            clf.fit(X, y)

            a_param = float(clf.coef_[0][0])
            d_param = float(clf.intercept_[0]) / (a_param + 1e-6)

            interpretation = ""
            if a_param < 0.8:
                interpretation += "LOW DISCRIMINATION: Rubric ambiguous. "
            if abs(d_param) > 2.0:
                interpretation += "EXTREME DIFFICULTY: Prompt needs adjustment. "
            if not interpretation:
                interpretation = "Acceptable"

            results[neuron_id] = {
                "discrimination": round(a_param, 4),
                "difficulty": round(d_param, 4),
                "judge_consensus": round(judge_consensus, 4),
                "human_gold": human_label,
                "n_reps": n_reps,
                "interpretation": interpretation,
            }
        except Exception as exc:
            results[neuron_id] = {"error": True, "neuron_id": neuron_id, "detail": str(exc)}

    return results


if __name__ == '__main__':
    print("Judge IRT diagnostics module loaded.")
