"""D-019 — scrub_secrets() is name-AND-shape based: a credential under an
unexpected key name is still stripped, while hashes / UUIDs / ids survive.
Pure function, no DB. OWNER: Chief Engineer."""

from __future__ import annotations

import hashlib

import pytest

from src.db.queries import scrub_secrets


def test_known_key_names_still_stripped():
    out = scrub_secrets({"openai_api_key": "sk-abc", "api_key": "x", "dwell_ms": 12})
    assert out == {"dwell_ms": 12}


@pytest.mark.parametrize(
    "secret",
    [
        "sk-proj-AbCdEf0123456789ghijklmnop",   # OpenAI project key
        "sk-or-v1-0123456789abcdef0123456789",  # OpenRouter
        "AKIAIOSFODNN7EXAMPLE",                  # AWS access key id
        "AIzaSyD-ExampleExampleExampleExample0",  # Google API key
        "ghp_0123456789abcdefghijklmnopqrstuvwx",  # GitHub PAT
        "xoxb-" + "1234567890-" + "abcdefghijklmnop",      # Slack bot token
    ],
)
def test_secret_shaped_value_stripped_under_any_key_name(secret):
    # the exact failure mode the name-only guard missed: an unexpected key name
    out = scrub_secrets({"note": secret, "creds": secret, "dwell_ms": 1})
    assert out == {"dwell_ms": 1}


def test_legitimate_values_survive():
    convo_id = "c4f1e2a0-1b2c-4d3e-8f90-abcdef123456"   # UUID conversation id
    content_hash = hashlib.sha256(b"hello").hexdigest()  # 64 hex chars
    meta = {
        "conversation_id": convo_id,
        "content_hash": content_hash,
        "model_slug": "gpt-4o",
        "timestamp": "2026-06-19T12:00:00Z",
        "copy_events": 3,
    }
    assert scrub_secrets(meta) == meta


def test_non_dict_returns_empty():
    assert scrub_secrets(None) == {}
    assert scrub_secrets("sk-not-a-dict") == {}
