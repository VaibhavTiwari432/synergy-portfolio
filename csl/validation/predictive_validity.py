"""CSL Phase 3.3 — predictive-validity registration (PROBE-GATED stub).

The §8.3 test: do CSL ownership + emergence rate add incremental predictive
validity over a quality-only baseline at predicting Layer-4 retention/transfer?
This is the only test that crosses from displayed to genuine ownership — and it
CANNOT run until the retention/transfer probe is deployed (Continuous C.2). It is
registered now, run later.

It is a STUB: it raises a structured `DataGatedError` echoing the FROZEN
registered design. No model is fit; CSL ownership/emergence remain leading
indicators only until the probe exists (claims charter / addendum #2).
"""

from __future__ import annotations

from typing import NoReturn

from csl.validation.errors import DataGatedError
from csl.validation.preregistration import load_preregistration

GATE_NAME = "csl_predictive_validity"
_UNBLOCK = (
    "deploy the Layer-4 retention/transfer probe (Continuous C.2) and collect the "
    "registered outcome data, then run the nested-model comparison as registered"
)


def run_predictive_validity(
    csl_features=None,
    quality_baseline=None,
    probe_outcomes=None,
) -> NoReturn:
    """Run the predictive-validity comparison. PROBE-GATED: always raises until the
    retention/transfer probe is deployed. Nothing is fit here."""
    reg = load_preregistration().test("predictive_validity")
    probe_present = probe_outcomes is not None
    raise DataGatedError(
        gate=GATE_NAME,
        have=f"probe_deployed={probe_present}",
        need="probe_deployed=True with registered Layer-4 outcomes",
        requires=_UNBLOCK,
        detail=(
            f"Registered metric: {reg.metric.strip()} "
            f"Outcome variable: {reg.outcome_variable}. Status: {reg.status}."
        ),
    )
