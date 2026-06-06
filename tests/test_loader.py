"""
Tests for neurons/loader.py — Phase 2 Contract Gate acceptance criteria.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
import yaml

from chat_classifier.neurons.loader import load_contracts
from chat_classifier.schemas import NeuronContract


# ── Helpers ───────────────────────────────────────────────────────────────────

def _write_yaml(tmp_path: Path, neurons: list[dict]) -> Path:
    p = tmp_path / "test_contracts.yaml"
    p.write_text(yaml.dump({"neurons": neurons}), encoding="utf-8")
    return p


MINIMAL_VALID_EC_ROW = {
    "id": "EC-01",
    "dimension": "EC",
    "type": "behavioral",
    "context_scope": "chunk",
    "extractor_type": "llm_judge",
    "micro_rubric": {"0": "No verification.", "4": "Full multi-step verification."},
    "detector": None,
    "valence": 1,
    "applicability_rule": "AI produced a checkable claim",
    "sector_universal": True,
}

MINIMAL_VALID_PR_ROW = {
    "id": "PR-01",
    "dimension": "PR",
    "type": "behavioral",
    "context_scope": "chunk",
    "extractor_type": "llm_judge",
    "micro_rubric": {"0": "Vague prompt.", "4": "Fully scaffolded prompt."},
    "detector": None,
    "valence": 1,
    "applicability_rule": "Chunk contains a human prompt",
    "sector_universal": True,
}


# ── Load from bundled table ───────────────────────────────────────────────────

class TestBundledTable:
    def test_loads_without_error(self):
        contracts = load_contracts()
        assert len(contracts) > 0

    def test_returns_list_of_neuron_contracts(self):
        contracts = load_contracts()
        assert all(isinstance(c, NeuronContract) for c in contracts)

    def test_ec_dimension_covered(self):
        contracts = load_contracts()
        ec_ids = [c.id for c in contracts if c.dimension == "EC"]
        assert len(ec_ids) >= 5, "EC should have at least 5 seeded rows"

    def test_pr_dimension_covered(self):
        contracts = load_contracts()
        pr_ids = [c.id for c in contracts if c.dimension == "PR"]
        assert len(pr_ids) >= 1

    def test_no_duplicate_ids(self):
        contracts = load_contracts()
        ids = [c.id for c in contracts]
        assert len(ids) == len(set(ids))

    def test_all_valences_are_1_or_minus1(self):
        contracts = load_contracts()
        assert all(c.valence in (1, -1) for c in contracts)

    def test_context_scope_valid(self):
        contracts = load_contracts()
        assert all(c.context_scope in ("chunk", "chat") for c in contracts)


# ── Schema validation enforcement ─────────────────────────────────────────────

class TestSchemaEnforcement:
    def test_valid_row_loads(self, tmp_path):
        p = _write_yaml(tmp_path, [MINIMAL_VALID_EC_ROW])
        contracts = load_contracts(p)
        assert len(contracts) == 1
        assert contracts[0].id == "EC-01"

    def test_missing_required_field_raises(self, tmp_path):
        bad = {k: v for k, v in MINIMAL_VALID_EC_ROW.items() if k != "valence"}
        p = _write_yaml(tmp_path, [bad])
        with pytest.raises(ValueError, match="schema validation"):
            load_contracts(p)

    def test_invalid_valence_raises(self, tmp_path):
        bad = {**MINIMAL_VALID_EC_ROW, "valence": 2}
        p = _write_yaml(tmp_path, [bad])
        with pytest.raises(ValueError):
            load_contracts(p)

    def test_invalid_type_field_raises(self, tmp_path):
        bad = {**MINIMAL_VALID_EC_ROW, "type": "unknown_type"}
        p = _write_yaml(tmp_path, [bad])
        with pytest.raises(ValueError):
            load_contracts(p)

    def test_invalid_extractor_type_raises(self, tmp_path):
        bad = {**MINIMAL_VALID_EC_ROW, "extractor_type": "magic"}
        p = _write_yaml(tmp_path, [bad])
        with pytest.raises(ValueError):
            load_contracts(p)

    def test_invalid_context_scope_raises(self, tmp_path):
        bad = {**MINIMAL_VALID_EC_ROW, "context_scope": "session"}
        p = _write_yaml(tmp_path, [bad])
        with pytest.raises(ValueError):
            load_contracts(p)


# ── Structural invariant enforcement ──────────────────────────────────────────

class TestStructuralInvariants:
    def test_duplicate_id_raises(self, tmp_path):
        p = _write_yaml(tmp_path, [MINIMAL_VALID_EC_ROW, MINIMAL_VALID_EC_ROW])
        with pytest.raises(ValueError, match="Duplicate neuron id"):
            load_contracts(p)

    def test_unknown_dimension_raises(self, tmp_path):
        bad = {**MINIMAL_VALID_EC_ROW, "id": "XX-01", "dimension": "XX"}
        p = _write_yaml(tmp_path, [bad])
        with pytest.raises(ValueError, match="not in the configured dimension set"):
            load_contracts(p)

    def test_missing_neurons_key_raises(self, tmp_path):
        p = tmp_path / "bad.yaml"
        p.write_text("some_key: []\n", encoding="utf-8")
        with pytest.raises(ValueError, match="'neurons' key"):
            load_contracts(p)

    def test_non_list_neurons_raises(self, tmp_path):
        p = tmp_path / "bad.yaml"
        p.write_text("neurons: not_a_list\n", encoding="utf-8")
        with pytest.raises(ValueError, match="must be a YAML list"):
            load_contracts(p)

    def test_file_not_found_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_contracts(tmp_path / "nonexistent.yaml")

    def test_multiple_valid_rows_load(self, tmp_path):
        p = _write_yaml(tmp_path, [MINIMAL_VALID_EC_ROW, MINIMAL_VALID_PR_ROW])
        contracts = load_contracts(p)
        assert len(contracts) == 2
        assert {c.id for c in contracts} == {"EC-01", "PR-01"}


# ── NeuronContract schema guardrails ─────────────────────────────────────────

class TestItemResponseGuardrails:
    """Verify the absent≠zero guardrail is enforced at the schema level."""

    def test_non_applicable_with_score_raises(self):
        from pydantic import ValidationError as PydanticValidationError
        from chat_classifier.schemas import ItemResponse

        with pytest.raises(PydanticValidationError, match="Absent"):
            ItemResponse(
                neuron_id="EC-01",
                dimension="EC",
                scope="chunk",
                chunk_index=0,
                applicable=False,
                ordinal_score=0,   # must NOT be set when not applicable
                extractor="test",
            )

    def test_applicable_with_none_score_is_valid(self):
        from chat_classifier.schemas import ItemResponse

        item = ItemResponse(
            neuron_id="EC-01",
            dimension="EC",
            scope="chunk",
            chunk_index=0,
            applicable=True,
            ordinal_score=None,   # score pending but applicable=True is ok
            extractor="test",
        )
        assert item.applicable is True
        assert item.ordinal_score is None

    def test_ordinal_score_out_of_range_raises(self):
        from pydantic import ValidationError as PydanticValidationError
        from chat_classifier.schemas import ItemResponse

        with pytest.raises(PydanticValidationError, match="0-4"):
            ItemResponse(
                neuron_id="EC-01",
                dimension="EC",
                scope="chunk",
                chunk_index=0,
                applicable=True,
                ordinal_score=5,
                extractor="test",
            )
