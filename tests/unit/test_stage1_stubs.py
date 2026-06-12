"""Failing-stub tests — one per Stage-1 module (brief §5 Stage 0).

Each is xfail until its owner lands the module. Owners: flip your stub to a
real import IN THE SAME COMMIT that delivers the module (INTERFACES.md §5).
CI stays green; the xfail report is the visible build board.
"""

from __future__ import annotations

import importlib

import pytest

STAGE1_MODULES: dict[str, list[str]] = {
    # owner: modules
    "CODEX": [
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
    ],
    "ANTIGRAVITY": [
        "src.state.load_classifier",
        "src.state.epistemic_classifier",
        "src.state.metacog_classifier",
        "src.state.tomer_slope",
        "src.dynamics.transitions",
        "src.dynamics.overlay",
    ],
    "CE": [
        # delivered: eventlog (schema/writer/queries), ingestion.canonical,
        # adapters (claude_export/chatgpt_export/plaintext/gold_json),
        # judge (client/prompt/parser)
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
        "src.claims.rungs",
        "src.claims.tier_engine",
        "src.claims.report",
        "src.api.main",
        "calibration.gold_loader",
        "calibration.runner",
    ],
}

_ALL = [(owner, mod) for owner, mods in STAGE1_MODULES.items() for mod in mods]


@pytest.mark.stage1_stub
@pytest.mark.parametrize("owner,module", _ALL, ids=[f"{o}:{m}" for o, m in _ALL])
@pytest.mark.xfail(reason="Stage-1 module not yet implemented", strict=False)
def test_stage1_module_exists(owner: str, module: str) -> None:
    importlib.import_module(module)
