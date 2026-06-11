"""Tests for Stage 1 — transcript_parser."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))

import pytest
from saf_chat_analyser.src.parser.transcript_parser import Turn, parse_transcript


# ── Fixtures ──────────────────────────────────────────────────────────────────

SIMPLE_JSON = [
    {"role": "user",      "content": "Hello, can you help me?"},
    {"role": "assistant", "content": "Sure, what do you need?"},
    {"role": "user",      "content": "Write a poem."},
]

PLAINTEXT = (
    "Human: Hello there.\n"
    "Assistant: Hi! How can I help?\n"
    "Human: Explain recursion."
)

OLD_SCHEMA = [
    {"role": "user",      "text": "Old schema text field."},
    {"role": "assistant", "text": "AI response here."},
]


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_parse_json_list_returns_turns():
    turns = parse_transcript(SIMPLE_JSON)
    assert len(turns) == 3
    assert all(isinstance(t, Turn) for t in turns)


def test_parse_json_string():
    turns = parse_transcript(json.dumps(SIMPLE_JSON))
    assert len(turns) == 3


def test_roles_normalised():
    turns = parse_transcript(SIMPLE_JSON)
    assert turns[0].role == "human"
    assert turns[1].role == "ai"
    assert turns[2].role == "human"


def test_indices_sequential():
    turns = parse_transcript(SIMPLE_JSON)
    assert [t.index for t in turns] == [0, 1, 2]


def test_word_count_set():
    turns = parse_transcript(SIMPLE_JSON)
    assert turns[0].word_count == len("Hello, can you help me?".split())


def test_parse_plaintext():
    turns = parse_transcript(PLAINTEXT)
    assert len(turns) == 3
    assert turns[0].role == "human"
    assert turns[1].role == "ai"


def test_old_text_field_accepted():
    turns = parse_transcript(OLD_SCHEMA)
    assert len(turns) == 2
    assert turns[0].content == "Old schema text field."


def test_empty_content_skipped():
    data = [
        {"role": "user",      "content": ""},
        {"role": "assistant", "content": "Response."},
    ]
    turns = parse_transcript(data)
    assert len(turns) == 1
    assert turns[0].role == "ai"


def test_unknown_role_skipped():
    data = [
        {"role": "system", "content": "You are helpful."},
        {"role": "user",   "content": "Hello."},
    ]
    turns = parse_transcript(data)
    assert len(turns) == 1


def test_invalid_type_raises():
    with pytest.raises((ValueError, TypeError)):
        parse_transcript(42)  # type: ignore[arg-type]
