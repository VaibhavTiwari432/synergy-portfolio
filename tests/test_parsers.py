"""
Tests for ingestion/parsers.py — Phase 1 acceptance criteria.
"""

from __future__ import annotations

import pytest

from chat_classifier.ingestion.parsers import parse
from chat_classifier.schemas import RawChat
from tests.fixtures.sample_chats import (
    CHATGPT_FLAT_6_TURNS,
    CHATGPT_MAPPING_4_TURNS,
    CLAUDE_FLAT_4_TURNS,
    PLAINTEXT_20_TURN,
    PLAINTEXT_EMPTY,
    PLAINTEXT_SINGLE_TURN,
)


# ── Plaintext ────────────────────────────────────────────────────────────────

class TestPlaintextParser:
    def test_20_turns_parsed(self):
        chat = parse("plaintext", PLAINTEXT_20_TURN)
        assert isinstance(chat, RawChat)
        assert len(chat.turns) == 20

    def test_turns_sequentially_indexed(self):
        chat = parse("plaintext", PLAINTEXT_20_TURN)
        for i, t in enumerate(chat.turns):
            assert t.index == i

    def test_alternating_roles(self):
        chat = parse("plaintext", PLAINTEXT_20_TURN)
        for i, t in enumerate(chat.turns):
            expected = "human" if i % 2 == 0 else "ai"
            assert t.role == expected, f"Turn {i}: expected {expected}, got {t.role}"

    def test_single_turn(self):
        chat = parse("plaintext", PLAINTEXT_SINGLE_TURN)
        assert len(chat.turns) == 1
        assert chat.turns[0].role == "human"

    def test_empty_transcript_produces_empty_turns(self):
        chat = parse("plaintext", PLAINTEXT_EMPTY)
        assert chat.turns == []

    def test_multiline_turn_joined(self):
        transcript = "Human: First line\nSecond line\nAssistant: Reply."
        chat = parse("plaintext", transcript)
        assert len(chat.turns) == 2
        assert "Second line" in chat.turns[0].text

    def test_no_timestamps_in_plaintext(self):
        chat = parse("plaintext", PLAINTEXT_20_TURN)
        for t in chat.turns:
            assert t.timestamp is None


# ── ChatGPT flat-list ─────────────────────────────────────────────────────────

class TestChatGPTFlatParser:
    def test_six_turns_parsed(self):
        chat = parse("chatgpt", CHATGPT_FLAT_6_TURNS)
        assert len(chat.turns) == 6

    def test_source_model_set(self):
        chat = parse("chatgpt", CHATGPT_FLAT_6_TURNS)
        assert chat.source_model == "chatgpt"

    def test_roles_normalised(self):
        chat = parse("chatgpt", CHATGPT_FLAT_6_TURNS)
        assert chat.turns[0].role == "human"
        assert chat.turns[1].role == "ai"

    def test_round_trip_text_preserved(self):
        chat = parse("chatgpt", CHATGPT_FLAT_6_TURNS)
        assert chat.turns[0].text == "Hello, explain neural networks."

    def test_sequential_indices(self):
        chat = parse("chatgpt", CHATGPT_FLAT_6_TURNS)
        for i, t in enumerate(chat.turns):
            assert t.index == i


# ── ChatGPT mapping format ───────────────────────────────────────────────────

class TestChatGPTMappingParser:
    def test_four_turns_parsed(self):
        chat = parse("chatgpt", CHATGPT_MAPPING_4_TURNS)
        assert len(chat.turns) == 4

    def test_timestamps_parsed(self):
        chat = parse("chatgpt", CHATGPT_MAPPING_4_TURNS)
        assert chat.turns[0].timestamp is not None

    def test_chat_id_from_mapping(self):
        chat = parse("chatgpt", CHATGPT_MAPPING_4_TURNS)
        assert chat.chat_id == "conv-abc"

    def test_first_turn_is_human(self):
        chat = parse("chatgpt", CHATGPT_MAPPING_4_TURNS)
        assert chat.turns[0].role == "human"
        assert chat.turns[1].role == "ai"


# ── Claude flat-list ──────────────────────────────────────────────────────────

class TestClaudeParser:
    def test_four_turns_parsed(self):
        chat = parse("claude", {"chat_messages": CLAUDE_FLAT_4_TURNS})
        assert len(chat.turns) == 4

    def test_source_model_set(self):
        chat = parse("claude", {"chat_messages": CLAUDE_FLAT_4_TURNS})
        assert chat.source_model == "claude"

    def test_roles_normalised(self):
        chat = parse("claude", {"chat_messages": CLAUDE_FLAT_4_TURNS})
        assert chat.turns[0].role == "human"
        assert chat.turns[1].role == "ai"


# ── Unknown source raises ────────────────────────────────────────────────────

def test_unknown_source_raises():
    with pytest.raises(ValueError, match="Unknown source"):
        parse("gemini", {})


# ── All outputs are valid RawChat ────────────────────────────────────────────

@pytest.mark.parametrize(
    "source,raw",
    [
        ("plaintext", PLAINTEXT_20_TURN),
        ("chatgpt", CHATGPT_FLAT_6_TURNS),
        ("chatgpt", CHATGPT_MAPPING_4_TURNS),
        ("claude", {"chat_messages": CLAUDE_FLAT_4_TURNS}),
    ],
)
def test_parse_always_returns_rawchat(source, raw):
    result = parse(source, raw)
    assert isinstance(result, RawChat)
    # Every turn must be properly indexed
    for i, t in enumerate(result.turns):
        assert t.index == i
