"""
src/ingestion/adapters/chatgpt_export.py — ChatGPT data-export adapter.
OWNER: Chief Engineer.

Handles the conversations.json shape of a ChatGPT export: each conversation
carries a `mapping` of node_id → {message, parent, children}. The canonical
turn order is reconstructed by walking the `current_node` parent chain
backwards (the active branch), falling back to a root-down walk when
current_node is absent. system/tool messages and empty parts are skipped —
they are not collaboration turns.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from contracts.schemas import CanonicalSession, PartnerModel
from src.ingestion.canonical import IngestionError, RawTurn, build_session


def _node_text(message: dict[str, Any]) -> str | None:
    content = message.get("content") or {}
    if content.get("content_type") not in (None, "text", "multimodal_text"):
        return None
    parts = content.get("parts") or []
    texts = [p for p in parts if isinstance(p, str) and p.strip()]
    return "\n".join(texts) if texts else None


def _timestamp(message: dict[str, Any]) -> datetime | None:
    ct = message.get("create_time")
    if ct is None:
        return None
    try:
        return datetime.fromtimestamp(float(ct), tz=timezone.utc)
    except (ValueError, OSError, OverflowError):
        return None


def _active_branch(conversation: dict[str, Any]) -> list[dict[str, Any]]:
    mapping: dict[str, dict] = conversation.get("mapping") or {}
    if not mapping:
        raise IngestionError("chatgpt_export conversation has no mapping")

    node_id = conversation.get("current_node")
    if node_id in mapping:
        chain: list[dict] = []
        while node_id is not None:
            node = mapping.get(node_id)
            if node is None:
                break
            chain.append(node)
            node_id = node.get("parent")
        return list(reversed(chain))

    # fallback: walk down from the root, taking the first child at each fork
    roots = [n for n in mapping.values() if n.get("parent") is None]
    if not roots:
        raise IngestionError("chatgpt_export mapping has no root node")
    chain = []
    node = roots[0]
    while node is not None:
        chain.append(node)
        children = node.get("children") or []
        node = mapping.get(children[0]) if children else None
    return chain


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
            raise IngestionError("chatgpt_export payload is an empty list")
        conversation = data[0]
    elif isinstance(data, dict):
        conversation = data
    else:
        raise IngestionError("chatgpt_export payload must be a dict or list of dicts")

    raw_turns: list[RawTurn] = []
    for node in _active_branch(conversation):
        message = node.get("message")
        if not message:
            continue
        role = ((message.get("author") or {}).get("role") or "").lower()
        if role not in ("user", "assistant"):
            continue  # system / tool nodes are not collaboration turns
        text = _node_text(message)
        if text is None:
            continue
        raw_turns.append((role, text, _timestamp(message)))

    pm = partner_model or PartnerModel(family="openai")
    return build_session(
        session_id=session_id or conversation.get("conversation_id") or conversation.get("id"),
        source="chatgpt_export",
        raw_turns=raw_turns,
        partner_model=pm,
        user_ref=user_ref,
        is_minor=is_minor,
        metadata={"title": conversation.get("title")},
    )
