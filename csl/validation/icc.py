"""CSL Phase 3.2 — per-ACF-level ICC certification (DATA-GATED stub).

Per-level inter-rater reliability (ICC) over replicate judge ratings decides which
ACF levels may expose ownership as a CERTIFIED output; levels below the registered
ICC threshold stay flagged `uncertified_pending_icc` (the flag ownership already
ships). This requires the 60+ gold corpus with archetype spread (Continuous C.1).

It is a STUB: it computes nothing and fits nothing on the pilot (addendum #2/#3).
It raises a structured `DataGatedError` echoing the FROZEN registered design
(metric, gate, outcome variable). The body is filled in only when the corpus
exists — at which point the gate already encodes the registered icc_threshold.
"""

from __future__ import annotations

from typing import NoReturn

from csl.validation.errors import DataGatedError
from csl.validation.preregistration import load_preregistration

GATE_NAME = "csl_per_level_icc"
_UNBLOCK = (
    "deploy the 60+ gold corpus with archetype spread (Continuous C.1), then "
    "implement per-level ICC against the registered icc_threshold — no pilot fitting"
)


def certify_levels(replicate_ratings=None, *, corpus_size: int = 0) -> NoReturn:
    """Certify ACF levels by per-level ICC. DATA-GATED: always raises until the
    corpus exists.

    `replicate_ratings`/`corpus_size` shape the structured error (have vs the
    registered need) and keep the signature forward-compatible; nothing is
    computed or fitted here.
    """
    reg = load_preregistration().test("per_level_icc")
    need = reg.gate.get("min_corpus")
    raise DataGatedError(
        gate=GATE_NAME,
        have=f"corpus_size={corpus_size}",
        need=f"corpus_size>={need}, ICC>={reg.gate.get('icc_threshold')} per level",
        requires=_UNBLOCK,
        detail=(
            f"Registered metric: {reg.metric}. Outcome: {reg.outcome_variable}. "
            f"Status: {reg.status}."
        ),
    )
