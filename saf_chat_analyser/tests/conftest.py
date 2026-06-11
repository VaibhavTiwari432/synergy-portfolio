"""
Pytest configuration for SAF test suite.

Patches out the sentence-transformers model load for all tests.
The model triggers a Windows access-violation in torch when loaded inside
the pytest process (Python 3.13 / torch compatibility issue).
semantic_distance_delta returns None in all unit tests — the field is
tested for structural presence only; numeric values are tested in calibration.
"""
from __future__ import annotations

import pytest
from unittest.mock import patch

_ST_PATCH = "saf_chat_analyser.src.metrics.composite_metrics._compute_semantic_distance"


@pytest.fixture(autouse=True)
def _no_sentence_transformer():
    with patch(_ST_PATCH, return_value=None):
        yield
