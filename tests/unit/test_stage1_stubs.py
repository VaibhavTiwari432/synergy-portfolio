"""Stage-1 board — final state: every Stage-1 module is delivered.

This file began as the xfail stub board (brief §5 Stage 0). All 17 leaf
modules plus the CE spine have landed, so it is now a HARD import gate:
a module that stops importing is a regression, not a pending stub.
"""

from __future__ import annotations

import importlib

import pytest

STAGE1_MODULES: list[str] = [
    # trait leaves
    "src.trait.tagger",
    "src.trait.phase_classifier",
    "src.trait.extractors.per_dimension.al",
    "src.trait.extractors.per_dimension.pr",
    "src.trait.extractors.per_dimension.ec",
    "src.trait.extractors.per_dimension.es",
    "src.trait.extractors.per_dimension.cs",
    "src.trait.extractors.per_dimension.cd",
    "src.trait.extractors.per_dimension.aui",
    "src.trait.extractors.per_dimension.ca",
    "src.aggregate.normalize",
    # state + dynamics leaves
    "src.state.load_classifier",
    "src.state.epistemic_classifier",
    "src.state.metacog_classifier",
    "src.state.tomer_slope",
    "src.dynamics.transitions",
    "src.dynamics.overlay",
    # spine
    "src.ingestion.canonical",
    "src.ingestion.adapters.claude_export",
    "src.ingestion.adapters.chatgpt_export",
    "src.ingestion.adapters.plaintext",
    "src.ingestion.adapters.gold_json",
    "src.eventlog.schema",
    "src.eventlog.writer",
    "src.eventlog.queries",
    "src.trait.judge.client",
    "src.trait.judge.prompt",
    "src.trait.judge.parser",
    "src.trait.evidence",
    "src.state.estimator",
    "src.merge.precision",
    "src.aggregate.softmin",
    "src.aggregate.gates",
    "src.dynamics.reactions",
    "src.dynamics.reliability_map",
    "src.sustainability.debt_tracker",
    "src.sustainability.ewma",
    "src.sustainability.lambda_proxy",
    "src.sustainability.probe_schema",
    "src.claims.rungs",
    "src.claims.tier_engine",
    "src.claims.report",
    "src.api.pipeline",
    "src.api.main",
    "calibration.gold_loader",
    "calibration.runner",
]


@pytest.mark.parametrize("module", STAGE1_MODULES)
def test_stage1_module_imports(module: str) -> None:
    importlib.import_module(module)
