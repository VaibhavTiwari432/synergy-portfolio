"""
src/ingestion/adapters/claude_export.py — claude.ai data-export adapter.
OWNER: Chief Engineer.

Handles the conversations.json shape of a claude.ai export: a list of
conversations (or a single one), each with `chat_messages` carrying
`sender: "human" | "assistant"`, `text` (and/or a `content` block list),
and ISO `created_at`. A multi-conversation export parses the FIRST
conversation unless `conversation_index` is provided in the payload dict
under "_select" (API callers submit one conversation at a time).
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from contracts.schemas import CanonicalSession, PartnerModel
from src.ingestion.canonical import IngestionError, RawTurn, build_session


def _message_text(msg: dict[str, Any]) -> str:
    # Prefer the flat `text`; fall back to concatenating text-type content blocks.
    if msg.get("text"):
        return msg["text"]
    blocks = msg.get("content") or []
    parts = [b.get("text", "") for b in blocks if b.get("type") == "text"]
    return "\n".join(p for p in parts if p)


def _timestamp(msg: dict[str, Any]) -> datetime | None:
    raw = msg.get("created_at")
    if not raw:
        return None
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None


def parse(
    payload: str | dict | list,
    *,
    partner_model: PartnerModel | None = None,
    session_id: str | None = None,
    user_ref: str | None = None,
    is_minor: bool = False,
) -> CanonicalSession:
    data = json.loads(payload) if isinstance(payload, str) else payload
    if isinstance(data, list):
        if not data:
            raise IngestionError("claude_export payload is an empty list")
        conversation = data[0]
    elif isinstance(data, dict):
        conversation = data
    else:
        raise IngestionError("claude_export payload must be a dict or list of dicts")

    messages = conversation.get("chat_messages")
    if not isinstance(messages, list) or not messages:
        raise IngestionError("claude_export conversation has no chat_messages")

    raw_turns: list[RawTurn] = []
    for msg in messages:
        sender = msg.get("sender")
        if sender not in ("human", "assistant"):
            continue  # attachments/system artifacts
        text = _message_text(msg)
        raw_turns.append((sender, text, _timestamp(msg)))

    pm = partner_model or PartnerModel(family="anthropic")
    return build_session(
        session_id=session_id or conversation.get("uuid"),
        source="claude_export",
        raw_turns=raw_turns,
        partner_model=pm,
        user_ref=user_ref,
        is_minor=is_minor,
        metadata={"title": conversation.get("name")},
    )
