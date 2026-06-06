"""
Phase 1 — platform export parsers.
Each adapter converts one raw export format into a normalized RawChat.

Supported sources:
  "chatgpt"   — ChatGPT JSON conversation export
  "claude"    — Claude.ai conversation JSON export
  "plaintext" — role-prefixed text transcript ("Human: ...\nAssistant: ...")

Usage:
    raw_chat = parse("chatgpt", json_data)
    raw_chat = parse("plaintext", transcript_string)
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any

from chat_classifier.schemas import RawChat, Turn


# ── Public entry point ───────────────────────────────────────────────────────

def parse(source: str, raw: Any) -> RawChat:
    """
    Normalize a chat export into a RawChat.

    Args:
        source: one of "chatgpt", "claude", "plaintext"
        raw:    the export payload — dict/list for JSON sources, str for plaintext
    Returns:
        RawChat with sequentially indexed turns
    Raises:
        ValueError on unrecognised source or malformed input
    """
    parsers = {
        "chatgpt": _parse_chatgpt,
        "claude": _parse_claude,
        "plaintext": _parse_plaintext,
    }
    if source not in parsers:
        raise ValueError(
            f"Unknown source {source!r}. Supported: {sorted(parsers.keys())}"
        )
    return parsers[source](raw)


# ── ChatGPT export adapter ───────────────────────────────────────────────────

def _parse_chatgpt(raw: Any) -> RawChat:
    """
    Parse a ChatGPT JSON conversation export.

    Expected shape (single conversation):
    {
      "id": "...",
      "title": "...",
      "mapping": {
        "<node_id>": {
          "message": {
            "id": "...",
            "author": {"role": "user"|"assistant"|"system"|"tool"},
            "content": {"content_type": "text", "parts": ["..."]},
            "create_time": <float|null>
          },
          "parent": "<node_id>|null",
          "children": ["<node_id>", ...]
        }
      }
    }

    Also accepts a list of conversations (takes the first one).
    Also accepts the simpler flat-list format used by some export tools:
    [{"role": "user"|"assistant", "content": "..."}]
    """
    if isinstance(raw, str):
        raw = json.loads(raw)

    # Flat-list format (simple)
    if isinstance(raw, list):
        return _parse_flat_list(raw, source_model="chatgpt")

    # Single conversation in mapping format
    if isinstance(raw, dict):
        if "mapping" in raw:
            return _parse_chatgpt_mapping(raw)
        # Maybe it's a list-format dict wrapped — try flat anyway
        raise ValueError(
            "ChatGPT JSON does not contain 'mapping'. "
            "Pass a flat list or a full conversation export."
        )

    raise ValueError(f"ChatGPT parser expected dict or list, got {type(raw).__name__}")


def _parse_chatgpt_mapping(data: dict) -> RawChat:
    """Walk the parent-pointer tree to reconstruct turn order."""
    mapping = data["mapping"]

    # Build child → list[child] adjacency already exists in data; we walk via
    # parent pointers to identify the linear chain from root to leaf.
    parent_of: dict[str, str | None] = {
        nid: node.get("parent") for nid, node in mapping.items()
    }

    # Topological order: find root (no parent or parent = None)
    roots = [nid for nid, p in parent_of.items() if not p]
    if not roots:
        raise ValueError("ChatGPT mapping has no root node.")

    # Follow the *first* child at each step (handles linear conversations)
    children_of: dict[str, list[str]] = {nid: [] for nid in mapping}
    for nid, p in parent_of.items():
        if p and p in children_of:
            children_of[p].append(nid)

    ordered_nodes: list[str] = []
    stack = [roots[0]]
    while stack:
        nid = stack.pop()
        ordered_nodes.append(nid)
        kids = children_of.get(nid, [])
        # Reverse so leftmost child is processed first
        stack.extend(reversed(kids))

    turns: list[Turn] = []
    for nid in ordered_nodes:
        node = mapping[nid]
        msg = node.get("message")
        if not msg:
            continue
        author_role = msg.get("author", {}).get("role", "")
        if author_role not in ("user", "assistant"):
            continue
        role: str = "human" if author_role == "user" else "ai"
        content = msg.get("content", {})
        parts = content.get("parts", [])
        text = " ".join(str(p) for p in parts if isinstance(p, str)).strip()
        if not text:
            continue
        create_time = msg.get("create_time")
        ts = datetime.fromtimestamp(create_time) if create_time else None
        turns.append(Turn(index=len(turns), role=role, text=text, timestamp=ts))

    chat_id = data.get("id") or data.get("title") or "unknown"
    return RawChat(chat_id=str(chat_id), source_model="chatgpt", turns=turns)


# ── Claude.ai export adapter ─────────────────────────────────────────────────

def _parse_claude(raw: Any) -> RawChat:
    """
    Parse a Claude.ai conversation JSON export.

    Accepted shapes:
    1. {"uuid": "...", "name": "...", "chat_messages": [{"sender": "human"|"assistant", "text": "..."}]}
    2. Flat list: [{"role": "human"|"assistant", "content": "..."}]
    """
    if isinstance(raw, str):
        raw = json.loads(raw)

    if isinstance(raw, list):
        return _parse_flat_list(raw, source_model="claude")

    if isinstance(raw, dict):
        messages = raw.get("chat_messages") or raw.get("messages") or []
        turns: list[Turn] = []
        for msg in messages:
            sender = msg.get("sender") or msg.get("role") or ""
            if sender in ("human", "user"):
                role = "human"
            elif sender in ("assistant", "ai"):
                role = "ai"
            else:
                continue
            text = (msg.get("text") or msg.get("content") or "").strip()
            if not text:
                continue
            ts_raw = msg.get("created_at") or msg.get("timestamp")
            ts: datetime | None = None
            if ts_raw:
                try:
                    ts = datetime.fromisoformat(str(ts_raw).replace("Z", "+00:00"))
                except ValueError:
                    pass
            turns.append(Turn(index=len(turns), role=role, text=text, timestamp=ts))

        chat_id = raw.get("uuid") or raw.get("id") or raw.get("name") or "unknown"
        return RawChat(chat_id=str(chat_id), source_model="claude", turns=turns)

    raise ValueError(f"Claude parser expected dict or list, got {type(raw).__name__}")


# ── Plain-text adapter ───────────────────────────────────────────────────────

_ROLE_PATTERNS = [
    # "Human:", "User:", "You:" → human
    (re.compile(r"^(?:Human|User|You)\s*:\s*", re.IGNORECASE), "human"),
    # "Assistant:", "Claude:", "ChatGPT:", "AI:", "Bot:" → ai
    (re.compile(r"^(?:Assistant|Claude|ChatGPT|AI|Bot|GPT)\s*:\s*", re.IGNORECASE), "ai"),
]


def _parse_plaintext(raw: Any) -> RawChat:
    """
    Parse a role-prefixed plain-text transcript.

    Expects alternating turns like:
        Human: I want to understand X.
        Assistant: Sure, X works like...
        Human: Can you give an example?
        ...

    Multi-line turns are supported — a new turn starts on a new line that
    matches a known role prefix.
    """
    if not isinstance(raw, str):
        raise ValueError(f"plaintext parser expects a str, got {type(raw).__name__}")

    lines = raw.splitlines()
    segments: list[tuple[str, str]] = []  # [(role, text)]
    current_role: str | None = None
    current_lines: list[str] = []

    for line in lines:
        matched_role: str | None = None
        rest = line
        for pattern, role in _ROLE_PATTERNS:
            m = pattern.match(line)
            if m:
                matched_role = role
                rest = line[m.end():]
                break

        if matched_role is not None:
            if current_role is not None and current_lines:
                segments.append((current_role, "\n".join(current_lines).strip()))
            current_role = matched_role
            current_lines = [rest] if rest.strip() else []
        else:
            if current_role is not None:
                current_lines.append(line)

    if current_role is not None and current_lines:
        segments.append((current_role, "\n".join(current_lines).strip()))

    turns: list[Turn] = []
    for role, text in segments:
        if text:
            turns.append(Turn(index=len(turns), role=role, text=text))

    return RawChat(chat_id="plaintext-import", source_model="plaintext", turns=turns)


# ── Shared helper: flat list format ─────────────────────────────────────────

def _parse_flat_list(messages: list[dict], source_model: str) -> RawChat:
    """
    Parse a flat list of {"role": ..., "content": ...} dicts.
    Accepted role values: "user"|"human" → human; "assistant"|"ai" → ai.
    """
    turns: list[Turn] = []
    for msg in messages:
        raw_role = (msg.get("role") or msg.get("sender") or "").lower()
        if raw_role in ("user", "human"):
            role = "human"
        elif raw_role in ("assistant", "ai"):
            role = "ai"
        else:
            continue
        text = (msg.get("content") or msg.get("text") or "").strip()
        if not text:
            continue
        turns.append(Turn(index=len(turns), role=role, text=text))
    return RawChat(chat_id="flat-list-import", source_model=source_model, turns=turns)
