"""
csl/validation/judge_irt.py — IRT Diagnostics on Judge Output (Item #3 Part 1)

Purpose: Decompose judge error into noise vs bias via GRM (Graded Response Model).
Outputs per-neuron discrimination (a) and difficulty (d) parameters to guide rubric iteration.
"""

from __future__ import annotations

import numpy as np
from typing import Dict, Any
from sklearn.linear_model import LogisticRegression


def fit_grm_to_judge_reps(
    judge_replications: Dict[str, np.ndarray],
    human_gold: Dict[str, int],
) -> Dict[str, Dict[str, Any]]:
    """
    Fit Graded Response Model to judge replications via ordinal logistic regression.

    Args:
        judge_replications: dict[neuron_id] -> array of scores from K replications
        human_gold: dict[neuron_id] -> human consensus label (0-4)

    Returns:
        dict[neuron_id] -> {discrimination, difficulty, interpretation, ...}
    """

    results = {}

    for neuron_id, rep_scores in judge_replications.items():
        human_label = human_gold.get(neuron_id, None)
        if human_label is None:
            continue

        judge_consensus = np.median(np.array(rep_scores))

        # Ordinal logistic proxy: fit logistic model
        X = np.array([[judge_consensus]])
        y = np.array([human_label])

        try:
            clf = LogisticRegression(random_state=42, max_iter=200)
            clf.fit(X.reshape(-1, 1), y)

            a_param = clf.coef_[0][0]  # Discrimination
            d_param = clf.intercept_[0] / (a_param + 1e-6)  # Difficulty

            interpretation = ""
            if a_param < 0.8:
                interpretation += "LOW DISCRIMINATION: Rubric ambiguous. "
            if abs(d_param) > 2.0:
                interpretation += "EXTREME DIFFICULTY: Prompt needs adjustment. "
            if not interpretation:
                interpretation = "Acceptable"

            results[neuron_id] = {
                'discrimination': a_param,
                'difficulty': d_param,
                'judge_consensus': judge_consensus,
                'human_gold': human_label,
                'interpretation': interpretation,
            }
        except Exception:
            results[neuron_id] = {
                'error': True,
                'neuron_id': neuron_id,
            }

    return results


if __name__ == '__main__':
    print("Judge IRT diagnostics module loaded.")
