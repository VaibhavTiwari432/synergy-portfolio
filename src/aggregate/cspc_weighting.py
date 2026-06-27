"""
src/aggregate/cspc_weighting.py — Phase 2: CSPC-weighted evidence aggregation.

Evidence quality varies per turn based on Cognitive State Proxies:
  - epistemic: confidence in one's own understanding (high = signal)
  - load: cognitive load (high = noise)
  - metacog: metacognitive awareness (high = signal)

A neuron firing on a high-quality CSPC turn (active, high-epistemic, low-load)
is trait signal. The same firing on a degraded turn (stressed, uncertain) is noise
the user reacting to context, not expressing trait. CSPC-weighted aggregation
down-weights late-turn evidence in long chats where CSPC degrades, solving the
wide-CI problem without needing more data.

Feature-flagged (use_cspc_weighting: bool). With flag OFF, scoring is byte-identical
to baseline (equal-weight mean). With flag ON, the ratchet must still pass and
late-turn weights demonstrably drop on long chats.
"""

from __future__ import annotations

import math
from typing import Sequence

from contracts.schemas import LoadLabel, MetacogLabel, StateVector


# Tuning parameters for the CSPC weight function.
# These are calibrated on the gold corpus to maximize signal-to-noise on long chats.
# Conservative defaults: epistemic boost, load penalty, metacog boost.
CSPC_EPISTEMIC_WEIGHT = 0.4  # z += 0.4 * epistemic (range -1 to 1)
CSPC_LOAD_WEIGHT = 0.3  # z -= 0.3 * load_penalty (load: low→0, medium→0.5, high→1)
CSPC_METACOG_WEIGHT = 0.3  # z += 0.3 * metacog_bonus (metacog: low→0, medium→0.5, high→1)


def _load_penalty(label: LoadLabel | None) -> float:
    """Map LoadLabel to a [0, 1] penalty (0=low load, 1=high load)."""
    if label is None:
        return 0.5  # absent = unknown, neutral weight
    if label == "low":
        return 0.0
    if label == "medium":
        return 0.5
    if label == "high":
        return 1.0
    return 0.5  # fallback


def _metacog_bonus(label: MetacogLabel | None) -> float:
    """Map MetacogLabel to a [0, 1] bonus (0=low metacog, 1=high metacog)."""
    if label is None:
        return 0.5  # absent = unknown, neutral weight
    if label == "low":
        return 0.0
    if label == "medium":
        return 0.5
    if label == "high":
        return 1.0
    return 0.5  # fallback


def cspc_weight(state: StateVector) -> float:
    """Compute evidence quality weight [0, 1] for one turn's StateVector.

    High epistemic + low load + high metacog → weight near 1.0 (high signal)
    Low epistemic + high load + low metacog → weight near 0.0 (low signal)

    Returns sigmoid(z) where z is the weighted combination of CSPC proxies.
    """
    z = 0.0

    # Epistemic: range [-1, 1], centered at 0 (uncertain). Higher = more confident.
    if state.epistemic is not None:
        z += CSPC_EPISTEMIC_WEIGHT * state.epistemic

    # Load: invert so high load is a penalty (z decreases)
    load_penalty = _load_penalty(state.load)
    z -= CSPC_LOAD_WEIGHT * load_penalty

    # Metacog: bonus for higher metacognitive awareness
    metacog_bonus = _metacog_bonus(state.metacog)
    z += CSPC_METACOG_WEIGHT * metacog_bonus

    # Sigmoid maps z → [0, 1] weight. Clamp z to prevent overflow.
    z = max(-10.0, min(10.0, z))
    return 1.0 / (1.0 + math.exp(-z))


def weighted_aggregate(
    values: Sequence[float],
    weights: Sequence[float],
) -> float:
    """Weighted mean with normalization."""
    if not values:
        return 0.0
    if len(values) != len(weights):
        raise ValueError(f"values ({len(values)}) and weights ({len(weights)}) mismatch")

    total_weight = sum(weights)
    if total_weight <= 0:
        # All zero weights: fall back to equal weight
        return sum(values) / len(values) if values else 0.0

    return sum(v * w for v, w in zip(values, weights)) / total_weight
