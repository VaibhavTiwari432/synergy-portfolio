"""
src/ingestion/canonical.py — canonical session builder + source dispatch.
OWNER: Chief Engineer.

All adapters funnel through build_session() so normalization happens in exactly
one place. ingest() is the single entry point the API uses: detect the source
format, dispatch to the adapter, return a CanonicalSession. Nothing downstream
ever reads a raw source format.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from contracts.schemas import CanonicalSession, PartnerModel, SourceFormat, Turn


class IngestionError(Exception):
    """Raised when a payload cannot be parsed into a CanonicalSession."""


#: (role, text, timestamp) triples — every adapter reduces its format to this.
RawTurn = tuple[str, str, "datetime | None"]

_ROLE_MAP = {
    "human": "human",
    "user": "human",
    "you": "human",
    "ai": "ai",
    "assistant": "ai",
    "model": "ai",
}


def normalize_role(role: str) -> str:
    """Map a source-format role onto the canonical human/ai pair."""
    try:
        return _ROLE_MAP[role.strip().lower()]
    except KeyError:
        raise IngestionError(f"unmappable turn role: {role!r}") from None


def build_session(
    *,
    session_id: str | None,
    source: SourceFormat,
    raw_turns: list[RawTurn],
    partner_model: PartnerModel,
    user_ref: str | None = None,
    is_minor: bool = False,
    metadata: dict[str, Any] | None = None,
) -> CanonicalSession:
    """Normalize raw turns into a CanonicalSession.

    Lossless by construction: every raw turn becomes exactly one Turn, in
    order, text byte-identical. Indices are re-issued densely — the source's
    own numbering (if any) is the adapter's concern, never canonical state.
    """
    if not raw_turns:
        raise IngestionError("session has no turns")
    turns = [
        Turn(index=i, role=normalize_role(role), text=text, timestamp=ts)
        for i, (role, text, ts) in enumerate(raw_turns)
    ]
    return CanonicalSession(
        session_id=session_id or f"sess-{uuid.uuid4().hex[:12]}",
        source=source,
        partner_model=partner_model,
        turns=turns,
        user_ref=user_ref,
        is_minor=is_minor,
        metadata=metadata or {},
    )


def detect_source(payload: str | dict | list) -> SourceFormat:
    """Sniff the source format. Strings that parse as JSON are re-dispatched
    on their parsed shape; everything else is plaintext."""
    if isinstance(payload, str):
        stripped = payload.lstrip()
        if stripped[:1] in ("{", "["):
            try:
                return detect_source(json.loads(payload))
            except (json.JSONDecodeError, IngestionError):
                return "plaintext"
        return "plaintext"

    probe: dict | None = None
    if isinstance(payload, dict):
        probe = payload
    elif isinstance(payload, list) and payload and isinstance(payload[0], dict):
        probe = payload[0]
    if probe is not None:
        if "mapping" in probe:
            return "chatgpt_export"
        if "chat_messages" in probe:
            return "claude_export"
        if "platform" in probe and "turns" in probe:
            return "gold_json"
    raise IngestionError("unrecognizable payload shape")


def ingest(
    payload: str | dict | list,
    *,
    partner_model: PartnerModel | None = None,
    session_id: str | None = None,
    user_ref: str | None = None,
    is_minor: bool = False,
    source: SourceFormat | None = None,
) -> CanonicalSession:
    """Single ingestion entry point: detect (or accept) the format, dispatch."""
    # local imports: adapters import build_session from this module
    from src.ingestion.adapters import chatgpt_export, claude_export, gold_json, plaintext

    fmt = source or detect_source(payload)
    adapters = {
        "claude_export": claude_export.parse,
        "chatgpt_export": chatgpt_export.parse,
        "plaintext": plaintext.parse,
        "gold_json": gold_json.parse,
    }
    return adapters[fmt](
        payload,
        partner_model=partner_model,
        session_id=session_id,
        user_ref=user_ref,
        is_minor=is_minor,
    )
