"""Loader for the frozen CSL validation pre-registration artifact (Phase 3).

Reads `PREREGISTRATION.yaml` fail-loud: the validation stubs echo the registered
design (metric / gate / outcome variable) in their data-gated errors so the gate
is anchored to a frozen artifact, never to ad-hoc code constants that could drift
after data arrives.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

DEFAULT_PREREG_PATH = Path(__file__).with_name("PREREGISTRATION.yaml")
_REQUIRED_TEST_KEYS = ("phase", "metric", "gate", "outcome_variable", "status")


@dataclass(frozen=True)
class RegisteredTest:
    name: str
    phase: str
    metric: str
    gate: dict[str, Any]
    outcome_variable: str
    status: str
    raw: dict[str, Any]


@dataclass(frozen=True)
class Preregistration:
    version: str
    status: str
    narrative_ref: str
    tests: dict[str, RegisteredTest]

    def test(self, name: str) -> RegisteredTest:
        if name not in self.tests:
            raise KeyError(f"no registered test '{name}' in pre-registration")
        return self.tests[name]


def load_preregistration(path: str | Path = DEFAULT_PREREG_PATH) -> Preregistration:
    """Load the frozen pre-registration. Fail loud if missing or malformed."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(
            f"pre-registration artifact missing: {p}. CSL validation tests refuse "
            "to run without their frozen registered design."
        )
    raw = yaml.safe_load(p.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("pre-registration must be a mapping")

    tests_raw = raw.get("tests")
    if not isinstance(tests_raw, dict) or not tests_raw:
        raise ValueError("pre-registration must define a non-empty tests mapping")

    tests: dict[str, RegisteredTest] = {}
    for name, entry in tests_raw.items():
        if not isinstance(entry, dict):
            raise ValueError(f"registered test '{name}' must be a mapping")
        missing = [k for k in _REQUIRED_TEST_KEYS if k not in entry]
        if missing:
            raise ValueError(f"registered test '{name}' missing keys: {missing}")
        gate = entry["gate"]
        if not isinstance(gate, dict):
            raise ValueError(f"registered test '{name}' gate must be a mapping")
        tests[name] = RegisteredTest(
            name=name,
            phase=str(entry["phase"]),
            metric=str(entry["metric"]),
            gate=dict(gate),
            outcome_variable=str(entry["outcome_variable"]),
            status=str(entry["status"]),
            raw=dict(entry),
        )

    return Preregistration(
        version=str(raw.get("version", "")),
        status=str(raw.get("status", "")),
        narrative_ref=str(raw.get("narrative_ref", "")),
        tests=tests,
    )
