"""
src/ingestion/adapters/gold_json.py — INTERNAL adapter for the gold corpus
format (data/gold/chats/*.json). OWNER: Chief Engineer.

Not an API-exposed source. Gold annotations (the calibration targets) are
deliberately NOT copied into the session — the pipeline must never see its
own answer key; calibration/gold_loader.py reads them separately.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from contracts.schemas import CanonicalSession, PartnerModel
from src.ingestion.canonical import IngestionError, RawTurn, build_session

#: gold "platform" → PartnerModel.family
PLATFORM_FAMILY = {
    "chatgpt": "openai",
    "claude": "anthropic",
    "gemini": "google",
}


def parse(
    payload: str | dict,
    *,
    partner_model: PartnerModel | None = None,
    session_id: str | None = None,
    user_ref: str | None = None,
    is_minor: bool = False,
) -> CanonicalSession:
    data: dict[str, Any] = json.loads(payload) if isinstance(payload, str) else payload
    if not isinstance(data, dict) or "turns" not in data:
        raise IngestionError("gold_json payload must be a dict with a 'turns' list")

    platform = str(data.get("platform", "")).lower()
    family = PLATFORM_FAMILY.get(platform, "unknown")
    pm = partner_model or PartnerModel(family=family)

    raw_turns: list[RawTurn] = []
    for t in data["turns"]:
        ts = None
        if t.get("timestamp_ms") is not None:
            ts = datetime.fromtimestamp(t["timestamp_ms"] / 1000, tz=timezone.utc)
        raw_turns.append((t["role"], t["content"], ts))

    metadata: dict[str, Any] = {"gold_id": data.get("id")}
    if data.get("rubric_version") is not None:
        metadata["rubric_version"] = data["rubric_version"]
    if data.get("calibration_excluded"):
        metadata["calibration_excluded"] = True
        metadata["calibration_excluded_reason"] = data.get("calibration_excluded_reason")

    return build_session(
        session_id=session_id or data.get("id"),
        source="gold_json",
        raw_turns=raw_turns,
        partner_model=pm,
        user_ref=user_ref,
        is_minor=is_minor,
        metadata=metadata,
    )
