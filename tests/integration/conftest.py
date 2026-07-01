"""Shared fixtures for integration tests.

These tests build a real app via create_app(), which 503s when no SAF_API_KEY
is configured. Set the key the tests authenticate with (X-API-Key: test-key)
for the whole directory so each test doesn't repeat the monkeypatch.
"""

import pytest


@pytest.fixture(autouse=True)
def _saf_api_key(monkeypatch):
    monkeypatch.setenv("SAF_API_KEY", "test-key")
