"""
Tests for ingestion/chunker.py — Phase 1 acceptance criteria.
"""

from __future__ import annotations

import pytest

from chat_classifier.ingestion.chunker import chunk
from chat_classifier.ingestion.parsers import parse
from tests.fixtures.sample_chats import PLAINTEXT_20_TURN


def _make_chat(n_turns: int):
    transcript = "\n".join(
        f"{'Human' if i % 2 == 0 else 'Assistant'}: Turn {i}."
        for i in range(n_turns)
    )
    return parse("plaintext", transcript)


# ── Core acceptance criterion: 20-turn chat → 18 chunks ──────────────────────

class TestBasicChunking:
    def test_20_turns_yields_18_chunks(self):
        chat = parse("plaintext", PLAINTEXT_20_TURN)
        chunks = chunk(chat)
        assert len(chunks) == 18

    def test_chunk_indices_sequential(self):
        chat = _make_chat(20)
        chunks = chunk(chat)
        for i, c in enumerate(chunks):
            assert c.chunk_index == i

    def test_window_size_3(self):
        chat = _make_chat(10)
        chunks = chunk(chat)
        for c in chunks:
            assert len(c.turns) == 3

    def test_turn_span_consistent_with_turns(self):
        chat = _make_chat(10)
        chunks = chunk(chat)
        for c in chunks:
            assert c.turn_end - c.turn_start + 1 == len(c.turns)
            for j, t in enumerate(c.turns):
                assert t.index == c.turn_start + j

    def test_stride_1_full_overlap(self):
        chat = _make_chat(10)
        chunks = chunk(chat, window=3, stride=1)
        # With 10 turns, window=3, stride=1: starts at 0,1,2,...,7 → 8 chunks
        assert len(chunks) == 8
        assert chunks[0].turn_start == 0
        assert chunks[1].turn_start == 1


# ── Edge cases ────────────────────────────────────────────────────────────────

class TestEdgeCases:
    def test_single_turn_yields_one_chunk(self):
        chat = _make_chat(1)
        chunks = chunk(chat)
        assert len(chunks) == 1
        assert len(chunks[0].turns) == 1

    def test_two_turns_yields_one_chunk_window3(self):
        chat = _make_chat(2)
        chunks = chunk(chat, window=3)
        assert len(chunks) == 1
        assert len(chunks[0].turns) == 2

    def test_exactly_window_size(self):
        chat = _make_chat(3)
        chunks = chunk(chat, window=3)
        assert len(chunks) == 1
        assert len(chunks[0].turns) == 3

    def test_empty_chat_yields_no_chunks(self):
        chat = _make_chat(0)
        chunks = chunk(chat)
        assert chunks == []

    def test_stride_larger_than_window(self):
        chat = _make_chat(10)
        chunks = chunk(chat, window=2, stride=3)
        # starts: 0, 3, 6, 9 → 4 chunks
        assert len(chunks) == 4

    def test_stride_equals_window_no_overlap(self):
        chat = _make_chat(9)
        chunks = chunk(chat, window=3, stride=3)
        # starts: 0, 3, 6 → 3 non-overlapping chunks
        assert len(chunks) == 3
        assert all(len(c.turns) == 3 for c in chunks)


# ── Invalid arguments ─────────────────────────────────────────────────────────

def test_zero_window_raises():
    chat = _make_chat(5)
    with pytest.raises(ValueError, match="window"):
        chunk(chat, window=0)


def test_zero_stride_raises():
    chat = _make_chat(5)
    with pytest.raises(ValueError, match="stride"):
        chunk(chat, window=3, stride=0)


# ── Turns inside chunks carry correct content ─────────────────────────────────

def test_chunk_turns_have_correct_text():
    chat = _make_chat(5)
    chunks = chunk(chat, window=3, stride=1)
    # First chunk contains turns 0, 1, 2
    first = chunks[0]
    assert first.turns[0].text == chat.turns[0].text
    assert first.turns[2].text == chat.turns[2].text
