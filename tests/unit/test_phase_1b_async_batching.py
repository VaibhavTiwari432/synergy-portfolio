"""Phase 1b acceptance tests: Async dimension-batching."""

import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.trait.judge.per_criterion import (
    group_by_dimension,
    format_dimension_rubric,
    build_dimension_schema,
    score_dimension,
    score_all_neurons,
)
from contracts.schemas import Dimension
from src.trait.judge.rubric_bank import neurons_by_dimension


def test_group_by_dimension():
    """Neurons are correctly grouped by their dimension."""
    # Test with a small subset of known neurons
    result = group_by_dimension(["AL-01", "AL-02", "AUI-01", "AUI-02"])

    # Both AL neurons should group together
    assert "Actualization" in result or any("AL" in nid for nid in result.get("Actualization", []))
    # All neurons should be accounted for
    total_neurons = sum(len(nids) for nids in result.values())
    assert total_neurons == 4


def test_format_dimension_rubric():
    """Dimension rubric formatting is correct."""
    neuron_ids = ["AL-01", "AL-02"]
    rubric = format_dimension_rubric("Actualization", neuron_ids)

    # Should contain the dimension name
    assert "Actualization" in rubric
    # Should reference the neurons
    assert "AL-01" in rubric
    assert "AL-02" in rubric


def test_build_dimension_schema():
    """Dimension schema has correct structure (one property per neuron)."""
    neuron_ids = ["AL-01", "AL-02"]
    schema = build_dimension_schema(neuron_ids)

    # Should have object type with properties
    assert schema["type"] == "object"
    assert "properties" in schema
    assert "AL-01" in schema["properties"]
    assert "AL-02" in schema["properties"]
    # All neurons should be required
    assert set(schema["required"]) == set(neuron_ids)


@pytest.mark.asyncio
async def test_score_dimension_success():
    """score_dimension makes one API call and parses the response."""
    mock_client = MagicMock()

    # Mock response: JSON with one field per neuron
    response_json = {
        "AL-01": "met",
        "AL-02": "exceeded",
    }
    mock_client._generate = MagicMock(return_value=json.dumps(response_json))

    result = await score_dimension(
        transcript="test transcript",
        dimension_name="Actualization",
        neuron_ids=["AL-01", "AL-02"],
        judge_client=mock_client,
    )

    # Should have results for both neurons
    assert "AL-01" in result
    assert "AL-02" in result
    # Scores should be numeric (not None)
    assert result["AL-01"] is not None
    assert result["AL-02"] is not None
    # The mock should have been called exactly once (one call per dimension)
    assert mock_client._generate.call_count == 1


@pytest.mark.asyncio
async def test_score_dimension_error_handling():
    """score_dimension handles invalid JSON gracefully."""
    mock_client = MagicMock()
    mock_client._generate = MagicMock(return_value="invalid json")

    result = await score_dimension(
        transcript="test transcript",
        dimension_name="Actualization",
        neuron_ids=["AL-01"],
        judge_client=mock_client,
    )

    # Should have an error for the neuron
    assert result.get("AL-01") is None or result.get("AL-01", {}).get("error") is not None


@pytest.mark.asyncio
async def test_score_all_neurons_concurrent():
    """score_all_neurons issues concurrent calls (one per dimension)."""
    mock_client = MagicMock()

    # Mock responses for different dimensions
    call_count = 0

    def mock_generate(system_prompt, user_prompt):
        nonlocal call_count
        call_count += 1
        # Return different responses based on the prompt content
        if "Actualization" in user_prompt:
            return json.dumps({"AL-01": "met", "AL-02": "met"})
        elif "Cognitive" in user_prompt:
            return json.dumps({"CA-01": "met"})
        else:
            return json.dumps({})

    mock_client._generate = mock_generate

    # Use a representative subset of neurons (one per dimension)
    test_neurons = ["AL-01", "AL-02", "CA-01"]

    result = await score_all_neurons(
        transcript="test transcript",
        neuron_ids=test_neurons,
        judge_client=mock_client,
    )

    # Should have results for all neurons
    assert result["summary"]["n_neurons"] == 3
    # Call count should be ~2-3 (one per dimension, not one per neuron)
    assert call_count <= 3, f"Expected ≤3 calls, got {call_count}"


@pytest.mark.asyncio
async def test_call_count_reduction():
    """Phase 1b call-count reduction: 107 neurons → 8 dimension calls."""
    mock_client = MagicMock()
    call_count = 0

    def mock_generate(system_prompt, user_prompt):
        nonlocal call_count
        call_count += 1
        # Return a valid but minimal response
        return json.dumps({})  # Empty is OK for this test

    mock_client._generate = mock_generate

    # All 107 neurons (or a representative set for testing)
    from src.trait.judge.rubric_bank import list_all_neurons
    all_neurons = list_all_neurons()

    result = await score_all_neurons(
        transcript="test transcript",
        neuron_ids=all_neurons[:50],  # Use first 50 for test speed
        judge_client=mock_client,
    )

    # Should have used dimension-batching: ~4-5 calls for 50 neurons (vs. 50 sequential)
    n_dimensions = result["summary"]["n_dimensions"]
    assert call_count == n_dimensions, f"Expected {n_dimensions} calls, got {call_count}"
    assert call_count < 10, f"Expected <10 calls for dimension-batching, got {call_count}"


def test_backward_compat_sync_wrapper():
    """score_all_neurons_sync provides backward compatibility for sync callers."""
    from src.trait.judge.per_criterion import score_all_neurons_sync

    # Mock judge function
    def mock_judge(prompt):
        return json.dumps({"score": "met"})

    result = score_all_neurons_sync(
        judge_fn=mock_judge,
        transcript="test",
        neuron_ids=["AL-01"],
    )

    # Should have results structure
    assert "results" in result
    assert "summary" in result
