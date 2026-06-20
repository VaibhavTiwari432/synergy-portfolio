"""Unit tests for canonical.py + the four adapters. OWNER: Chief Engineer."""

from __future__ import annotations

import json

import pytest

from contracts.schemas import PartnerModel
from src.ingestion.canonical import IngestionError, detect_source, ingest, normalize_role


# ── role + source detection ──────────────────────────────────────────────────


def test_normalize_role_maps_known_aliases():
    assert normalize_role("User") == "human"
    assert normalize_role("HUMAN") == "human"
    assert normalize_role("assistant") == "ai"
    assert normalize_role("model") == "ai"
    with pytest.raises(IngestionError):
        normalize_role("narrator")


def test_detect_source_shapes():
    assert detect_source({"mapping": {}, "title": "x"}) == "chatgpt_export"
    assert detect_source([{"chat_messages": [], "uuid": "u"}]) == "claude_export"
    assert detect_source({"platform": "chatgpt", "turns": []}) == "gold_json"
    assert detect_source("User: hi\nAssistant: hello") == "plaintext"
    assert detect_source(json.dumps({"mapping": {}})) == "chatgpt_export"
    with pytest.raises(IngestionError):
        detect_source({"unrelated": True})


# ── plaintext adapter ────────────────────────────────────────────────────────


def test_plaintext_parses_markers_and_continuations():
    payload = "User: first question\nspanning two lines\nChatGPT: an answer\nUser: follow-up"
    s = ingest(payload)
    assert s.source == "plaintext"
    assert [t.role for t in s.turns] == ["human", "ai", "human"]
    assert s.turns[0].text == "first question\nspanning two lines"
    assert s.partner_model.family == "openai"  # inferred from the ChatGPT marker


def test_plaintext_without_markers_is_one_human_turn():
    s = ingest("just a blob of text with no speakers")
    assert len(s.turns) == 1
    assert s.turns[0].role == "human"
    assert s.partner_model.family == "unknown"


def test_plaintext_rejects_empty():
    with pytest.raises(IngestionError):
        ingest("   ", source="plaintext")


# ── claude_export adapter ────────────────────────────────────────────────────


def _claude_payload() -> dict:
    return {
        "uuid": "c-1",
        "name": "demo",
        "chat_messages": [
            {"sender": "human", "text": "hi", "created_at": "2026-01-02T03:04:05Z"},
            {"sender": "assistant", "content": [{"type": "text", "text": "hello"}]},
            {"sender": "human", "text": "thanks"},
        ],
    }


def test_claude_export_parses_messages_and_content_blocks():
    s = ingest(_claude_payload())
    assert s.source == "claude_export"
    assert s.session_id == "c-1"
    assert [t.role for t in s.turns] == ["human", "ai", "human"]
    assert s.turns[1].text == "hello"
    assert s.turns[0].timestamp is not None
    assert s.partner_model.family == "anthropic"


def test_claude_export_list_takes_first_conversation():
    s = ingest([_claude_payload(), {"chat_messages": [{"sender": "human", "text": "other"}]}])
    assert s.session_id == "c-1"


# ── chatgpt_export adapter ───────────────────────────────────────────────────


def _chatgpt_payload() -> dict:
    def node(nid, parent, children, role=None, parts=None, ct=None):
        message = None
        if role is not None:
            message = {
                "author": {"role": role},
                "content": {"content_type": "text", "parts": parts or []},
                "create_time": ct,
            }
        return {"id": nid, "message": message, "parent": parent, "children": children}

    return {
        "conversation_id": "g-1",
        "title": "demo",
        "current_node": "n3",
        "mapping": {
            "root": node("root", None, ["n0"]),
            "n0": node("n0", "root", ["n1"], role="system", parts=["sys"]),
            "n1": node("n1", "n0", ["n2"], role="user", parts=["question"], ct=1736000000),
            "n2": node("n2", "n1", ["n3"], role="assistant", parts=["answer"]),
            "n3": node("n3", "n2", [], role="user", parts=["follow-up"]),
        },
    }


def test_chatgpt_export_walks_current_node_chain_and_skips_system():
    s = ingest(_chatgpt_payload())
    assert s.source == "chatgpt_export"
    assert s.session_id == "g-1"
    assert [t.role for t in s.turns] == ["human", "ai", "human"]
    assert [t.text for t in s.turns] == ["question", "answer", "follow-up"]
    assert s.turns[0].timestamp is not None
    assert s.partner_model.family == "openai"


def test_chatgpt_export_fallback_root_walk():
    payload = _chatgpt_payload()
    del payload["current_node"]
    s = ingest(payload)
    assert [t.text for t in s.turns] == ["question", "answer", "follow-up"]


# ── gold_json adapter ────────────────────────────────────────────────────────


def test_gold_json_maps_platform_to_family_and_keeps_gold_id():
    payload = {
        "id": "gc-xxx",
        "platform": "gemini",
        "rubric_version": "0.1",
        "turns": [
            {"role": "user", "content": "q", "turn_index": 0, "timestamp_ms": None},
            {"role": "assistant", "content": "a", "turn_index": 1, "timestamp_ms": 1736000000000},
        ],
        "annotations": {"bands": {"AL": "low"}},
    }
    s = ingest(payload)
    assert s.source == "gold_json"
    assert s.session_id == "gc-xxx"
    assert s.partner_model.family == "google"
    assert s.metadata["gold_id"] == "gc-xxx"
    assert s.turns[1].timestamp is not None
    # the answer key never enters the session
    assert "annotations" not in s.metadata
    assert "bands" not in json.dumps(s.metadata)


def test_partner_model_override_wins():
    s = ingest(
        "User: hi\nAssistant: hello",
        partner_model=PartnerModel(family="google", model_id="gemini-2.0", era_key="2026-01"),
    )
    assert s.partner_model.family == "google"
    assert s.partner_model.era_key == "2026-01"
