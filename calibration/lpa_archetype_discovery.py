"""
calibration/lpa_archetype_discovery.py — LPA Archetype Discovery (Item #12 Part 2)

Discovers real user classes via Gaussian Mixture Model (LPA).
Validates against decreed 10 archetypes.

Requires: n >= 200 corpus

G4: replaces hash-based categorical encoding (which maps arbitrary strings to
pseudo-random floats and destroys semantic distance) with proper one-hot encoding
for categorical features, keeping continuous features on their natural scale.
ARI (Adjusted Rand Index) is used for agreement instead of hash-collision matching.
"""

from __future__ import annotations

import numpy as np
from sklearn.mixture import GaussianMixture
from sklearn.metrics import adjusted_rand_score
from sklearn.preprocessing import LabelEncoder
from typing import Dict, Tuple, Any, List

#: G4: categorical features must be one-hot encoded; continuous stay as-is
_CATEGORICAL_KEYS = ("education_stage", "domain", "task_type")
_CONTINUOUS_KEYS = ("ai_familiarity", "synergy_score", "s_human", "kappa_h")
_CONTINUOUS_DEFAULTS = {"ai_familiarity": 0.5, "synergy_score": 0.5, "s_human": 0.5, "kappa_h": 0.5}


def _one_hot(values: List[str]) -> np.ndarray:
    """One-hot encode a list of string labels. Unknown at inference time maps to zeros."""
    enc = LabelEncoder()
    int_labels = enc.fit_transform(values)
    n_classes = len(enc.classes_)
    oh = np.zeros((len(values), n_classes), dtype=float)
    oh[np.arange(len(values)), int_labels] = 1.0
    return oh


def discover_archetypes_via_lpa(
    corpus_records: list,
    n_classes: int = 10,
) -> Tuple[np.ndarray, Dict[str, Any]]:
    """Run LPA (GMM) to discover real user classes.

    G4: proper one-hot encoding for categorical features + ARI agreement metric.

    Features: education_stage (OHE), domain (OHE), task_type (OHE),
              ai_familiarity, synergy_score, s_human, kappa_h (all continuous)

    Args:
        corpus_records: List of chat dicts with features
        n_classes: Number of latent classes (default 10)

    Returns:
        (discovered_labels, summary_dict)
    """
    # ── feature matrix ─────────────────────────────────────────────────────────
    parts: list[np.ndarray] = []

    for key in _CATEGORICAL_KEYS:
        values = [str(r.get(key, "")) for r in corpus_records]
        parts.append(_one_hot(values))

    cont = np.array([
        [float(r.get(k, _CONTINUOUS_DEFAULTS[k])) for k in _CONTINUOUS_KEYS]
        for r in corpus_records
    ], dtype=float)
    parts.append(cont)

    X = np.hstack(parts)
    # Standardise only the continuous block; one-hot columns stay binary
    n_ohe = sum(len(set(str(r.get(k, "")) for r in corpus_records)) for k in _CATEGORICAL_KEYS)
    if X.shape[0] > 0:
        X[:, n_ohe:] = (
            (X[:, n_ohe:] - X[:, n_ohe:].mean(axis=0))
            / (X[:, n_ohe:].std(axis=0) + 1e-9)
        )

    # ── GMM fit ────────────────────────────────────────────────────────────────
    gmm = GaussianMixture(n_components=n_classes, random_state=42, n_init=3)
    labels = gmm.fit_predict(X)

    # ── G4: ARI agreement (not hash-collision matching) ────────────────────────
    decreed_raw = [r.get("archetype_decreed") for r in corpus_records]
    decreed_valid = [d for d in decreed_raw if d is not None]
    if len(decreed_valid) == len(corpus_records) and len(corpus_records) > 0:
        decreed_enc = LabelEncoder().fit_transform([str(d) for d in decreed_valid])
        ari = float(adjusted_rand_score(decreed_enc, labels))
    else:
        ari = float("nan")  # insufficient gold labels

    return labels, {
        "n_classes": n_classes,
        "ari_agreement": round(ari, 4) if not np.isnan(ari) else None,
        "warning": (
            "Low agreement (ARI < 0.70)" if (not np.isnan(ari) and ari < 0.70)
            else ("Good agreement" if not np.isnan(ari) else "No decreed labels to validate against")
        ),
        "n_records": len(corpus_records),
        "feature_dim": X.shape[1] if X.ndim == 2 else 0,
        "method": "GMM-LPA with OHE categorical features (G4)",
    }


if __name__ == '__main__':
    print("LPA archetype discovery loaded (data-gated, requires n>=200).")
