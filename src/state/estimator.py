"""
src/state/estimator.py — StateEstimator interface + ProxyEstimator.
OWNER: Chief Engineer.

Full HGF is deferred (non-negotiable #9): ProxyEstimator is the Scope-A
implementation behind the StateEstimator interface; HGFEstimator arrives later
behind the SAME interface without touching callers.

The four proxy channels are Antigravity's leaf classifiers, INJECTED as
callables matching INTERFACES.md §2 signatures. A missing channel produces
None per turn and a named caveat — never a fabricated value (#12). CSPC is
the sole owner of latent state (#8): SURRENDER exists only in this module's
inputs/outputs, and the validity gate widens precision downstream, never
scores (#2).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Callable, Protocol, Sequence

from contracts.schemas import (
    CanonicalSession,
    LoadLabel,
    MetacogResult,
    StateValidity,
    StateVector,
    TurnTags,
)

# leaf signatures (INTERFACES.md §2) — Antigravity implements these
LoadClassifier = Callable[[CanonicalSession], "Sequence[LoadLabel]"]
EpistemicClassifier = Callable[[CanonicalSession, list[TurnTags]], "Sequence[float]"]
MetacogClassifier = Callable[[CanonicalSession, list[TurnTags]], MetacogResult]
TomSlope = Callable[[CanonicalSession], "tuple[Sequence[float], float | None]"]


class StateEstimator(ABC):
    """The stable interface. ProxyEstimator now; HGFEstimator later (D1)."""

    @abstractmethod
    def estimate(
        self, session: CanonicalSession, tags: list[TurnTags]
    ) -> tuple[list[StateVector], StateValidity]:
        """One StateVector per HUMAN turn (turn order) + the session validity gate."""


def _epistemic_summary(series: list[float | None]) -> tuple[float | None, float | None]:
    """(session mean, half-to-half slope) over available values (brief §3.5)."""
    values = [v for v in series if v is not None]
    if not values:
        return None, None
    mean = sum(values) / len(values)
    if len(values) < 4:
        return mean, None  # slope needs enough turns to mean anything
    half = len(values) // 2
    first, second = values[:half], values[half:]
    slope = (sum(second) / len(second)) - (sum(first) / len(first))
    return mean, slope


class ProxyEstimator(StateEstimator):
    def __init__(
        self,
        *,
        classify_load: LoadClassifier | None = None,
        classify_epistemic: EpistemicClassifier | None = None,
        classify_metacog: MetacogClassifier | None = None,
        tom_slope: TomSlope | None = None,
    ) -> None:
        self._classify_load = classify_load
        self._classify_epistemic = classify_epistemic
        self._classify_metacog = classify_metacog
        self._tom_slope = tom_slope

    def estimate(
        self, session: CanonicalSession, tags: list[TurnTags]
    ) -> tuple[list[StateVector], StateValidity]:
        human_indices = [t.index for t in session.turns if t.role == "human"]
        n = len(human_indices)
        caveats: list[str] = []

        def _channel(name: str, values: Sequence | None) -> list:
            if values is None:
                caveats.append(f"{name}_unavailable")
                return [None] * n
            if len(values) != n:
                caveats.append(f"{name}_length_mismatch")
                return [None] * n
            return list(values)

        loads = _channel(
            "load", self._classify_load(session) if self._classify_load else None
        )
        epistemic = _channel(
            "epistemic",
            self._classify_epistemic(session, tags) if self._classify_epistemic else None,
        )

        metacog_result: MetacogResult | None = (
            self._classify_metacog(session, tags) if self._classify_metacog else None
        )
        if metacog_result is not None and len(metacog_result.labels) != n:
            caveats.append("metacog_length_mismatch")
            metacog_result = None
        metacog_labels = (
            list(metacog_result.labels) if metacog_result is not None else [None] * n
        )
        if metacog_result is None:
            caveats.append("metacog_unavailable")

        tom_series: list[float | None]
        tom_slope_value: float | None
        if self._tom_slope is not None:
            series, tom_slope_value = self._tom_slope(session)
            tom_series = _channel("tom", series)
        else:
            caveats.append("tom_unavailable")
            tom_series, tom_slope_value = [None] * n, None

        available = 4 - sum(
            1 for c in ("load", "epistemic", "metacog", "tom")
            if any(cv.startswith(c) for cv in caveats)
        )
        confidence = available / 4

        strip = [
            StateVector(
                turn_index=turn_index,
                load=loads[i],
                epistemic=epistemic[i],
                metacog=metacog_labels[i],
                tom_signal=tom_series[i],
                a_t=None,  # Tier-2 only; schema present, needs telemetry
                confidence=confidence,
            )
            for i, turn_index in enumerate(human_indices)
        ]

        epistemic_mean, epistemic_slope = _epistemic_summary(epistemic)

        surrender = metacog_result.surrender_detected if metacog_result else False
        onset = metacog_result.surrender_onset_turn if metacog_result else None
        if surrender:
            caveats.append(
                "metacognitive collapse detected: trait evidence precision is "
                "reduced for this session (scores reported with wider CIs)"
            )

        validity = StateValidity(
            state_compromised=surrender,  # M_t collapse → widen all trait CIs (§3.5)
            m_t_collapse=surrender,
            surrender_detected=surrender,
            surrender_onset_turn=onset,
            epistemic_mean=epistemic_mean,
            epistemic_slope=epistemic_slope,
            tom_slope=tom_slope_value,
            caveats=caveats,
        )
        return strip, validity
