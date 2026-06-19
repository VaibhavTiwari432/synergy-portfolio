"""Phase 3.2 / 3.3 acceptance — data-gated stubs + frozen pre-registration.

Per-level ICC (3.2) and predictive validity (3.3) raise the canonical
DataGatedError until corpus/probe exist; nothing is fit on the pilot. The frozen
pre-registration artifact records each test's metric / gate / outcome variable.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from csl.validation import (
    DataGatedError,
    certify_levels,
    load_preregistration,
    run_predictive_validity,
)
from csl.validation.icc import GATE_NAME as ICC_GATE
from csl.validation.predictive_validity import GATE_NAME as PV_GATE


# ── frozen pre-registration artifact ────────────────────────────────────────────


def test_prereg_loads_with_three_registered_tests():
    reg = load_preregistration()
    assert reg.status == "FROZEN_PREREGISTRATION"
    assert set(reg.tests) == {"independence", "per_level_icc", "predictive_validity"}


def test_each_registered_test_records_metric_gate_outcome():
    reg = load_preregistration()
    for name in ("independence", "per_level_icc", "predictive_validity"):
        t = reg.test(name)
        assert t.metric            # what metric
        assert t.gate              # what gate
        assert t.outcome_variable  # what outcome variable
        assert t.phase and t.status


def test_icc_threshold_is_registered_convention():
    reg = load_preregistration().test("per_level_icc")
    assert reg.gate["icc_threshold"] == 0.75
    assert reg.gate["min_corpus"] == 60


def test_predictive_validity_requires_probe():
    reg = load_preregistration().test("predictive_validity")
    assert reg.gate["requires_probe"] is True
    assert reg.status == "REGISTERED_NOT_RUNNABLE"


def test_prereg_missing_file_fails_loud():
    with pytest.raises(FileNotFoundError):
        load_preregistration(Path("no/such/PREREGISTRATION.yaml"))


def test_prereg_malformed_fails_loud(tmp_path):
    bad = tmp_path / "PREREGISTRATION.yaml"
    bad.write_text(yaml.safe_dump({"tests": {"x": {"phase": "1"}}}), encoding="utf-8")
    with pytest.raises(ValueError, match="missing keys"):
        load_preregistration(bad)


# ── 3.2 per-level ICC stub (corpus-gated) ───────────────────────────────────────


def test_certify_levels_is_data_gated():
    with pytest.raises(DataGatedError) as exc:
        certify_levels(corpus_size=26)
    err = exc.value
    assert err.gate == ICC_GATE
    assert "26" in str(err.have)
    assert "60" in str(err.need)            # echoes the registered min_corpus
    assert "0.75" in str(err.need)          # echoes the registered icc_threshold


def test_certify_levels_raises_even_with_no_args():
    with pytest.raises(DataGatedError):
        certify_levels()


# ── 3.3 predictive validity stub (probe-gated) ──────────────────────────────────


def test_predictive_validity_is_data_gated():
    with pytest.raises(DataGatedError) as exc:
        run_predictive_validity(csl_features={"C4": 0.5}, quality_baseline=0.7)
    err = exc.value
    assert err.gate == PV_GATE
    assert "probe_deployed=False" in str(err.have)


def test_predictive_validity_still_gated_even_with_probe_outcomes():
    # passing outcomes flips the 'have' field but the stub is unimplemented:
    # it must still refuse rather than fabricate a result.
    with pytest.raises(DataGatedError):
        run_predictive_validity(
            csl_features={"C4": 0.5}, quality_baseline=0.7, probe_outcomes={"s1": 0.4}
        )


def test_data_gated_error_is_structured():
    try:
        certify_levels(corpus_size=10)
    except DataGatedError as err:
        assert hasattr(err, "gate") and hasattr(err, "have")
        assert hasattr(err, "need") and hasattr(err, "requires")
        assert "data-gated" in str(err)
