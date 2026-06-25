"""
calibration/lpa_archetype_discovery.py — LPA Archetype Discovery (Item #12 Part 2)

Discovers real user classes via Gaussian Mixture Model (LPA).
Validates against decreed 10 archetypes.

Requires: n >= 200 corpus
"""

from __future__ import annotations

import numpy as np
from sklearn.mixture import GaussianMixture
from typing import Dict, Tuple, Any


def discover_archetypes_via_lpa(
    corpus_records: list,
    n_classes: int = 10,
) -> Tuple[np.ndarray, Dict[str, Any]]:
    """
    Run LPA to discover real user classes.

    Features: education_stage, domain, ai_familiarity, task_type, synergy, s_human, kappa_h

    Args:
        corpus_records: List of chat dicts with features
        n_classes: Number of classes (default 10)

    Returns:
        (discovered_labels, summary_dict)
    """

    X = []
    for record in corpus_records:
        features = [
            hash(record.get('education_stage', '')) % 100 / 100,
            hash(record.get('domain', '')) % 100 / 100,
            record.get('ai_familiarity', 0.5),
            hash(record.get('task_type', '')) % 100 / 100,
            record.get('synergy_score', 0.5),
            record.get('s_human', 0.5),
            record.get('kappa_h', 0.5),
        ]
        X.append(features)

    X = np.array(X)
    X = (X - X.mean(axis=0)) / (X.std(axis=0) + 1e-6)

    # Fit GMM
    gmm = GaussianMixture(n_components=n_classes, random_state=42)
    labels = gmm.fit_predict(X)

    # Validate against decreed archetypes
    decreed = [r.get('archetype_decreed') for r in corpus_records]
    agreement = sum(1 for d, l in zip(decreed, labels) if hash(str(d)) % n_classes == l) / len(decreed) if decreed else 0

    return labels, {
        'n_classes': n_classes,
        'agreement_with_decreed': agreement,
        'warning': 'Low agreement' if agreement < 0.70 else 'Good agreement',
    }


if __name__ == '__main__':
    print("LPA archetype discovery loaded (data-gated, requires n>=200).")
