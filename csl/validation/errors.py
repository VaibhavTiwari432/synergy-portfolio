"""Canonical data-gated errors for CSL validation (v3.1 addendum #3).

"Data-gated means stubbed": CDM, G-DINA, causal estimation, KT sustainability,
disclosure-effects, drift/invariance, longitudinal stability — and the CSL
validation steps (independence at scale, per-level ICC, predictive validity) —
raise a CLEAR data-gated error until the required corpus/probe exists. They never
silently degrade, and they never fit on the n=26 pilot (#2).
"""

from __future__ import annotations


class DataGatedError(RuntimeError):
    """A computation that is blocked until the required data/instrument exists.

    Structured so callers and tests can assert the gate, the shortfall, and the
    unblock condition without string-matching prose.
    """

    def __init__(self, *, gate: str, have, need, requires: str, detail: str = ""):
        self.gate = gate
        self.have = have
        self.need = need
        self.requires = requires
        self.detail = detail
        message = (
            f"{gate} is data-gated: have {have}, need {need}. "
            f"Unblock requires: {requires}."
        )
        if detail:
            message += f" {detail}"
        super().__init__(message)


class CorpusInsufficientError(DataGatedError):
    """Not enough aligned sessions to run a corpus-level check."""

    def __init__(self, *, gate: str, have: int, need: int, requires: str, detail: str = ""):
        super().__init__(gate=gate, have=have, need=need, requires=requires, detail=detail)
