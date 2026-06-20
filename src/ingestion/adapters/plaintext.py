"""
src/ingestion/adapters/plaintext.py — speaker-marked plaintext adapter.
OWNER: Chief Engineer.

Parses transcripts of the form:

    User: how do I ...
    Assistant: you can ...
    User: but what about ...

Recognized speaker markers (case-insensitive, at line start, ending with ':'):
human — user, human, you, me; ai — assistant, ai, chatgpt, claude, gemini,
model, bot. Lines before the first marker belong to the first human turn;
continuation lines attach to the current speaker. Without any markers the
whole payload is a single human turn (degenerate but ingestible — the n_eff
gates downstream will say INSUFFICIENT_SAMPLE, never fabricate).
"""

from __future__ import annotations

import re

from contracts.schemas import CanonicalSession, PartnerModel
from src.ingestion.canonical import IngestionError, RawTurn, build_session

_HUMAN_MARKERS = ("user", "human", "you", "me")
_AI_MARKERS = ("assistant", "ai", "chatgpt", "claude", "gemini", "model", "bot")

_MARKER_RE = re.compile(
    r"^\s*(?P<name>" + "|".join(_HUMAN_MARKERS + _AI_MARKERS) + r")\s*:\s?",
    re.IGNORECASE,
)

#: marker → inferred partner family (used only when no PartnerModel is supplied)
_MARKER_FAMILY = {"chatgpt": "openai", "claude": "anthropic", "gemini": "google"}


def parse(
    payload: str,
    *,
    partner_model: PartnerModel | None = None,
    session_id: str | None = None,
    user_ref: str | None = None,
    is_minor: bool = False,
) -> CanonicalSession:
    if not isinstance(payload, str) or not payload.strip():
        raise IngestionError("plaintext payload must be a non-empty string")

    raw_turns: list[RawTurn] = []
    current_role: str | None = None
    current_lines: list[str] = []
    inferred_family = "unknown"

    def flush() -> None:
        nonlocal current_lines
        if current_role is not None:
            raw_turns.append((current_role, "\n".join(current_lines).strip(), None))
        current_lines = []

    for line in payload.splitlines():
        m = _MARKER_RE.match(line)
        if m:
            flush()
            name = m.group("name").lower()
            current_role = "human" if name in _HUMAN_MARKERS else "ai"
            if name in _MARKER_FAMILY:
                inferred_family = _MARKER_FAMILY[name]
            current_lines.append(line[m.end():])
        else:
            if current_role is None:
                current_role = "human"  # preamble belongs to the first human turn
            current_lines.append(line)
    flush()

    pm = partner_model or PartnerModel(family=inferred_family)  # type: ignore[arg-type]
    return build_session(
        session_id=session_id,
        source="plaintext",
        raw_turns=raw_turns,
        partner_model=pm,
        user_ref=user_ref,
        is_minor=is_minor,
        metadata={},
    )
