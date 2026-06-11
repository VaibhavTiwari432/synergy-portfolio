"""
Stage 1 — Transcript Parser.

Converts raw chat input into a list[Turn].

Accepted formats:
  1. JSON array of objects:  [{"role": "user"|"assistant", "content": "..."}]
  2. Plain alternating text: "Human: ...\nAssistant: ..." (role-prefixed blocks)

The Turn dataclass is the canonical unit for all downstream stages.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any


@dataclass
class Turn:
    index: int
    role: str        # "human" | "ai"
    content: str
    word_count: int


# ── Role-prefix patterns for plaintext format ─────────────────────────────────

_ROLE_PATTERNS = [
    (re.compile(r"^(?:Human|User|You)\s*:\s*", re.IGNORECASE), "human"),
    (re.compile(r"^(?:Assistant|Claude|ChatGPT|AI|Bot|GPT)\s*:\s*", re.IGNORECASE), "ai"),
]


# ── Public API ────────────────────────────────────────────────────────────────

def parse_transcript(raw: str | list[dict] | Any) -> list[Turn]:
    """
    Parse a chat transcript into a list of Turn objects.

    Args:
        raw: JSON string, list of role/content dicts, or plaintext string.

    Returns:
        list[Turn] with sequential indices, starting from 0.

    Raises:
        ValueError on unrecognised format.
    """
    if isinstance(raw, str):
        stripped = raw.strip()
        if stripped.startswith("[") or stripped.startswith("{"):
            try:
                parsed = json.loads(stripped)
                return _parse_json(parsed)
            except json.JSONDecodeError:
                pass
        return _parse_plaintext(stripped)

    if isinstance(raw, list):
        return _parse_json(raw)

    raise ValueError(
        f"parse_transcript expects a str or list, got {type(raw).__name__}"
    )


# ── Internal parsers ──────────────────────────────────────────────────────────

def _parse_json(data: Any) -> list[Turn]:
    """
    Parse a list of {"role": ..., "content": ...} dicts.
    Accepted role values: "user"|"human" → human; "assistant"|"ai" → ai.
    """
    if not isinstance(data, list):
        raise ValueError(
            f"JSON transcript must be a list, got {type(data).__name__}"
        )

    turns: list[Turn] = []
    for msg in data:
        raw_role = (msg.get("role") or msg.get("sender") or "").lower()
        if raw_role in ("user", "human"):
            role = "human"
        elif raw_role in ("assistant", "ai"):
            role = "ai"
        else:
            continue
        content = (msg.get("content") or msg.get("text") or "").strip()
        if not content:
            continue
        turns.append(
            Turn(
                index=len(turns),
                role=role,
                content=content,
                word_count=len(content.split()),
            )
        )
    return turns


def _parse_plaintext(raw: str) -> list[Turn]:
    """
    Parse a role-prefixed plain-text transcript into Turn objects.

    Supports multi-line turns — a new turn starts on any line that matches
    a known role prefix. Human turn is assumed first if the transcript
    doesn't start with a role prefix.
    """
    lines = raw.splitlines()
    segments: list[tuple[str, str]] = []
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
            if current_role is None and line.strip():
                # No role prefix found yet — treat first block as human
                current_role = "human"
                current_lines = [line]
            elif current_role is not None:
                current_lines.append(line)

    if current_role is not None and current_lines:
        segments.append((current_role, "\n".join(current_lines).strip()))

    turns: list[Turn] = []
    for role, content in segments:
        if content:
            turns.append(
                Turn(
                    index=len(turns),
                    role=role,
                    content=content,
                    word_count=len(content.split()),
                )
            )
    return turns
