"""
src/api/routers/ingest.py — POST /v1/ingest + GET /v1/users/{ref}/chats.
OWNER: Chief Engineer.

POST /v1/ingest
  Idempotent on (user_ref, conversation_id). Writes to raw_chats + telemetry.
  Returns immediately — the scoring worker handles scoring asynchronously.

GET /v1/users/{user_ref}/chats
  Returns all chats for the user with their status + a summary block.
"""

from __future__ import annotations

from typing import Any

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from contracts.schemas import PartnerModel
from src.api.middleware.auth import require_api_key
from src.db.queries import (
    capture_completeness_error,
    canonicalize_turn_indexes,
    get_chats_for_user,
    replace_capture_artifacts,
    reconcile_captured_count,
    requeue_failed_chat,
    upsert_chat,
    upsert_telemetry,
)

router = APIRouter(dependencies=[Depends(require_api_key)])


def _require_pool(request: Request):
    from src.db.connection import get_pool_optional
    pool = get_pool_optional()
    if pool is None:
        raise HTTPException(503, detail="Database unavailable — is Postgres running?")
    return pool


# ── request / response models ────────────────────────────────────────────────

class TurnPayload(BaseModel):
    role: str                           # 'user' | 'assistant'
    text: str
    timestamp_ms: int | None = None
    turn_index: int


class TelemetryPayload(BaseModel):
    dwell_ms: list[int] | None = None
    copy_events: list[int] | None = None
    edit_detected: list[bool] | None = None
    selector_health: str | None = None


class IngestRequest(BaseModel):
    user_ref: str
    conversation_id: str
    source: str = Field(pattern="^(chatgpt_history|chatgpt_live)$")
    partner_model: PartnerModel
    turns: list[TurnPayload]
    telemetry: TelemetryPayload | None = None
    metadata: dict[str, Any] | None = None   # title, url
    # Capture completeness (ADR-0007 / D-015). All optional + nullable: absent →
    # legacy DOM path, deferred to the role-balance gate. capture_complete is
    # tri-state — True (proven complete) / False (proven incomplete → quarantine) /
    # None (unknown: scroll-probe / dom-live fallback).
    capture_method: str | None = None
    expected_turn_count: int | None = None
    captured_turn_count: int | None = None
    capture_complete: bool | None = None
    raw_retention_flag: str = "retain"
    # D-022 (#15 minor protection): the extension sets this during onboarding. It
    # threads ingest → raw_chats → worker → enforce() so a minor-flagged chat never
    # receives a bare composite / peer rank / debt verdict. Absent → False (the
    # adult default), matching prior behaviour for every legacy/unflagged ingest.
    is_minor: bool = False


class IngestResponse(BaseModel):
    chat_id: str
    status: str
    message: str


# ── routes ───────────────────────────────────────────────────────────────────

@router.post("/v1/ingest", response_model=IngestResponse)
async def ingest_chat(
    body: IngestRequest,
    pool: asyncpg.Pool = Depends(_require_pool),
) -> IngestResponse:
    turns_dicts = canonicalize_turn_indexes([t.model_dump() for t in body.turns])
    partner_dict = body.partner_model.model_dump()

    # Server-derive the captured count (ADR-0007 / D-015): never trust the client
    # scalar for the gate — it must equal the turns actually delivered, or a
    # truncated transcript could claim a complete count. A client value that
    # disagrees with len(turns) is a broken bridge → structured 422.
    turns_len = len(body.turns)
    try:
        captured = reconcile_captured_count(
            turns_len=turns_len, client_captured=body.captured_turn_count
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "reason": "captured_count_mismatch",
                "capture_complete": False,
                "expected_turn_count": body.expected_turn_count,
                "captured_turn_count": turns_len,
                "message": f"Capture count mismatch — {exc}.",
            },
        ) from exc

    # Completeness gate: a PROVEN-incomplete interception is quarantined here — it
    # never becomes pending work. The structured 422 body lets the extension say
    # "captured M of N", not "API unreachable" (cf. D-009).
    incomplete_reason = capture_completeness_error(
        expected_turn_count=body.expected_turn_count,
        captured_turn_count=captured,
        capture_complete=body.capture_complete,
    )
    if incomplete_reason is not None:
        raise HTTPException(
            status_code=422,
            detail={
                "reason": "capture_incomplete",
                "capture_complete": False,
                "expected_turn_count": body.expected_turn_count,
                "captured_turn_count": captured,
                "message": (
                    f"Capture incomplete — {incomplete_reason}. "
                    "Reload ChatGPT and try Analyse now again."
                ),
            },
        )

    try:
        row = await upsert_chat(
            pool,
            user_ref=body.user_ref,
            conversation_id=body.conversation_id,
            source=body.source,
            partner_model=partner_dict,
            turns=turns_dicts,
            turn_count=len(body.turns),
            expected_turn_count=body.expected_turn_count,
            captured_turn_count=captured,
            capture_complete=body.capture_complete,
            is_minor=body.is_minor,
        )
    except ValueError as exc:
        # Role-balance / defensive completeness failure → string detail (D-014 shape)
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if int(row.get("turn_count") or 0) > len(body.turns):
        return IngestResponse(
            chat_id=str(row["id"]),
            status=row["status"],
            message="ignored stale partial capture",
        )

    tel = body.telemetry or TelemetryPayload()
    meta = body.metadata or {}
    # capture_mode mirrors source field for storage
    capture_mode = "history_import" if body.source == "chatgpt_history" else "live_capture"

    await upsert_telemetry(
        pool,
        chat_id=row["id"],
        dwell_ms=tel.dwell_ms,
        copy_events=tel.copy_events,
        edit_detected=tel.edit_detected,
        selector_health=tel.selector_health,
        capture_mode=capture_mode,
        metadata=meta,
    )

    await replace_capture_artifacts(
        pool,
        chat_id=row["id"],
        conversation_id=body.conversation_id,
        turns=turns_dicts,
        raw_retention_flag=body.raw_retention_flag,
    )

    return IngestResponse(
        chat_id=str(row["id"]),
        status=row["status"],
        message="queued for scoring",
    )


@router.post("/v1/users/{user_ref}/chats/{chat_id}/requeue")
async def requeue_chat(
    user_ref: str,
    chat_id: str,
    pool: asyncpg.Pool = Depends(_require_pool),
) -> dict[str, Any]:
    """Re-queue a failed chat for scoring without re-ingesting its transcript.

    Returns {chat_id, status: 'pending'} on success.
    Returns 409 if the chat exists but is not in 'failed' state (already
    pending/scoring/scored — the caller should poll rather than re-queue).
    Returns 404 if the chat does not exist or is not owned by this user."""
    from uuid import UUID
    try:
        uid = UUID(chat_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="invalid chat_id")

    async with pool.acquire() as conn:
        result = await requeue_failed_chat(conn, chat_id=uid, user_ref=user_ref)

    if result is None:
        raise HTTPException(status_code=404, detail="chat not found")
    if result != "pending":
        raise HTTPException(
            status_code=409,
            detail={"status": result, "message": f"chat is '{result}', not 'failed'"},
        )
    return {"chat_id": chat_id, "status": "pending"}


@router.get("/v1/users/{user_ref}/chats")
async def list_user_chats(
    user_ref: str,
    pool: asyncpg.Pool = Depends(_require_pool),
) -> dict[str, Any]:
    rows = await get_chats_for_user(pool, user_ref)

    chats = [
        {
            "chat_id": str(r["id"]),
            "conversation_id": r["conversation_id"],
            "captured_at": r["captured_at"].isoformat(),
            "status": r["status"],
            "turn_count": r["turn_count"],
            "source": r["source"],
        }
        for r in rows
    ]

    total = len(chats)
    scored = sum(1 for c in chats if c["status"] == "scored")
    pending = sum(1 for c in chats if c["status"] in ("pending", "scoring"))
    failed = sum(1 for c in chats if c["status"] == "failed")

    return {
        "chats": chats,
        "summary": {
            "total": total,
            "scored": scored,
            "pending": pending,
            "failed": failed,
        },
    }
