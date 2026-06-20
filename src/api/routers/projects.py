"""
src/api/routers/projects.py — Scope-C projects + sessions. OWNER: Chief Engineer.

Implements contracts/scope_c_contract.md (FROZEN v1.0):
    POST   /v1/users/{ref}/projects                      create (Idempotency-Key)
    GET    /v1/users/{ref}/projects?limit=&cursor=       keyset page
    GET    /v1/users/{ref}/projects/{project_id}         detail + aggregated radar
    PATCH  /v1/users/{ref}/projects/{project_id}         rename/describe (If-Match)
    DELETE /v1/users/{ref}/projects/{project_id}         delete (If-Match)
    POST   /v1/users/{ref}/projects/{project_id}/sessions          assign chats
    DELETE /v1/users/{ref}/projects/{project_id}/sessions/{sid}    unassign

Non-negotiables enforced structurally:
  - project_id is server-minted (DB gen_random_uuid) — never client-supplied.
  - saf_session_id IS raw_chats.id — the body sends chat_ids == saf_session_ids.
  - No project-level composite/total (#6): radar is per-dimension only, each dim
    carrying state + (when scored) CI + the response rung (#14).
  - Four reporting states never collapsed (#12): scored / STRUCTURAL_NA /
    INSUFFICIENT_SAMPLE / MEASUREMENT_SATURATED, each distinct.
  - Keyset pagination, optimistic concurrency (If-Match → 409), Idempotency-Key.
"""

from __future__ import annotations

import base64
import statistics
from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field

from contracts.schemas import Dimension
from src.api.middleware.auth import require_api_key
from src.db.queries import (
    add_project_sessions,
    create_project,
    delete_project,
    get_project,
    get_project_score_rows,
    list_projects,
    remove_project_session,
    update_project,
)

router = APIRouter(dependencies=[Depends(require_api_key)])

_DIMS = [d.value for d in Dimension]
_CONTRACT_VERSION = "scope-c/v1.0"
_DEFAULT_LIMIT = 20
_MAX_LIMIT = 100
#: a dim is a strength/watch when it sits this far above/below the project's own
#: scored-dim average — formative framing only (DESIGNED rung), never a verdict.
_RELATIVE_THRESHOLD = 0.08

#: stored profile ScoreStatus → frozen radar state (#12 never-collapse)
_STATUS_TO_STATE = {
    "OK": "scored",
    "N/A": "STRUCTURAL_NA",
    "INSUFFICIENT_SAMPLE": "INSUFFICIENT_SAMPLE",
    "MEASUREMENT_SATURATED": "MEASUREMENT_SATURATED",
}


def _require_pool(request: Request):
    from src.db.connection import get_pool_optional
    pool = get_pool_optional()
    if pool is None:
        raise HTTPException(503, detail="Database unavailable — is Postgres running?")
    return pool


# ── cursor (keyset) ────────────────────────────────────────────────────────────

def _encode_cursor(created_at: datetime, project_id: UUID) -> str:
    raw = f"{created_at.isoformat()}|{project_id}"
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii")


def _decode_cursor(cursor: str) -> tuple[datetime, UUID]:
    try:
        raw = base64.urlsafe_b64decode(cursor.encode("ascii")).decode("utf-8")
        ts, pid = raw.split("|", 1)
        return datetime.fromisoformat(ts), UUID(pid)
    except Exception as exc:  # malformed cursor is a client error, not a 500
        raise HTTPException(422, detail="invalid cursor") from exc


# ── radar aggregation (per-dim; NEVER a composite) ─────────────────────────────

def _aggregate_radar(score_rows) -> dict[str, dict[str, Any]]:
    """Per-dimension state across a project's scored chats. §3.7 rule:
    scored (≥3 OK contributions, mean + CI) / INSUFFICIENT_SAMPLE (1–2) /
    MEASUREMENT_SATURATED (no OK but every contribution saturated) / STRUCTURAL_NA.
    No cross-dimension total is ever produced (#6)."""
    ok_values: dict[str, list[float]] = {d: [] for d in _DIMS}
    saturated: dict[str, int] = {d: 0 for d in _DIMS}
    seen: dict[str, int] = {d: 0 for d in _DIMS}

    for row in score_rows:
        profile = row["profile"] or {}
        for dim, ds in profile.items():
            if dim not in ok_values or not isinstance(ds, dict):
                continue
            status = ds.get("status")
            seen[dim] += 1
            if status == "OK" and ds.get("value") is not None:
                ok_values[dim].append(float(ds["value"]))
            elif status == "MEASUREMENT_SATURATED":
                saturated[dim] += 1

    radar: dict[str, dict[str, Any]] = {}
    for dim in _DIMS:
        vals = ok_values[dim]
        n = len(vals)
        if n >= 3:
            mean = sum(vals) / n
            half = 1.96 * (statistics.stdev(vals) / (n ** 0.5)) if n > 1 else 0.0
            radar[dim] = {
                "state": "scored",
                "value": round(mean, 3),
                "ci": [round(max(0.0, mean - half), 3), round(min(1.0, mean + half), 3)],
                "n": n,
            }
        elif n >= 1:
            radar[dim] = {"state": "INSUFFICIENT_SAMPLE", "value": None, "ci": None, "n": n}
        elif saturated[dim] > 0:
            radar[dim] = {"state": "MEASUREMENT_SATURATED", "value": None, "ci": None, "n": 0}
        else:
            radar[dim] = {"state": "STRUCTURAL_NA", "value": None, "ci": None, "n": 0}
    return radar


def _strengths_and_watch(radar: dict[str, dict[str, Any]]) -> tuple[list[str], list[str]]:
    scored = {d: r["value"] for d, r in radar.items() if r["state"] == "scored"}
    if len(scored) < 2:
        return [], []
    avg = sum(scored.values()) / len(scored)
    strengths = [d for d, v in scored.items() if v - avg >= _RELATIVE_THRESHOLD]
    watch = [d for d, v in scored.items() if avg - v >= _RELATIVE_THRESHOLD]
    return strengths, watch


# ── serialisers ────────────────────────────────────────────────────────────────

def _project_full(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "project_id": str(row["id"]),
        "name": row["name"],
        "description": row.get("description"),
        "version": row["version"],
        "created_at": row["created_at"].isoformat(),
        "updated_at": row["updated_at"].isoformat(),
        "session_count": row.get("session_count", 0),
        "contract_version": _CONTRACT_VERSION,
    }


# ── request models ──────────────────────────────────────────────────────────────

class CreateProjectRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)


class UpdateProjectRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)


class AssignSessionsRequest(BaseModel):
    chat_ids: list[UUID] = Field(min_length=1, max_length=200)


# ── routes ───────────────────────────────────────────────────────────────────

@router.post("/v1/users/{user_ref}/projects", status_code=201)
async def create_project_route(
    user_ref: str,
    body: CreateProjectRequest,
    pool=Depends(_require_pool),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    name = body.name.strip()
    if not name:
        raise HTTPException(422, detail="name must not be blank")
    row = await create_project(
        pool, user_ref=user_ref, name=name, description=body.description,
        idempotency_key=idempotency_key,
    )
    if not row:
        raise HTTPException(500, detail="project create failed")
    out = _project_full({**row, "session_count": 0})
    return out


@router.get("/v1/users/{user_ref}/projects")
async def list_projects_route(
    user_ref: str,
    limit: int = _DEFAULT_LIMIT,
    cursor: str | None = None,
    pool=Depends(_require_pool),
) -> dict[str, Any]:
    limit = max(1, min(limit, _MAX_LIMIT))
    before_created_at = before_id = None
    if cursor:
        before_created_at, before_id = _decode_cursor(cursor)

    rows = await list_projects(
        pool, user_ref=user_ref, limit=limit + 1,  # over-fetch one to detect more
        before_created_at=before_created_at, before_id=before_id,
    )
    has_more = len(rows) > limit
    page = rows[:limit]
    next_cursor = (
        _encode_cursor(page[-1]["created_at"], page[-1]["id"]) if has_more else None
    )
    items = [
        {
            "project_id": str(r["id"]),
            "name": r["name"],
            "session_count": r["session_count"],
            "updated_at": r["updated_at"].isoformat(),
        }
        for r in page
    ]
    return {
        "items": items,
        "next_cursor": next_cursor,
        "limit": limit,
        "contract_version": _CONTRACT_VERSION,
    }


@router.get("/v1/users/{user_ref}/projects/{project_id}")
async def get_project_route(
    user_ref: str,
    project_id: UUID,
    pool=Depends(_require_pool),
) -> dict[str, Any]:
    row = await get_project(pool, user_ref=user_ref, project_id=project_id)
    if row is None:
        raise HTTPException(404, detail="project not found")

    score_rows = await get_project_score_rows(pool, user_ref=user_ref, project_id=project_id)
    radar = _aggregate_radar(score_rows)
    strengths, watch = _strengths_and_watch(radar)
    return {
        "project_id": str(row["id"]),
        "name": row["name"],
        "version": row["version"],
        "session_count": row["session_count"],
        "profile_radar": radar,         # per-dim only — NO project composite (#6)
        "strengths": strengths,
        "watch": watch,
        "rung": "DESIGNED",
        "contract_version": _CONTRACT_VERSION,
    }


def _require_if_match(if_match: str | None) -> int:
    if if_match is None:
        raise HTTPException(428, detail="If-Match header required (optimistic concurrency)")
    try:
        return int(if_match)
    except ValueError as exc:
        raise HTTPException(422, detail="If-Match must be an integer version") from exc


@router.patch("/v1/users/{user_ref}/projects/{project_id}")
async def update_project_route(
    user_ref: str,
    project_id: UUID,
    body: UpdateProjectRequest,
    pool=Depends(_require_pool),
    if_match: str | None = Header(default=None, alias="If-Match"),
) -> dict[str, Any]:
    expected = _require_if_match(if_match)
    name = body.name.strip() if body.name is not None else None
    result = await update_project(
        pool, user_ref=user_ref, project_id=project_id,
        name=name, description=body.description, expected_version=expected,
    )
    if result is None:
        raise HTTPException(404, detail="project not found")
    if "_conflict" in result:
        raise HTTPException(
            409, detail={"error": "version_conflict", "current_version": result["_conflict"]}
        )
    return _project_full(result)


@router.delete("/v1/users/{user_ref}/projects/{project_id}")
async def delete_project_route(
    user_ref: str,
    project_id: UUID,
    pool=Depends(_require_pool),
    if_match: str | None = Header(default=None, alias="If-Match"),
) -> dict[str, Any]:
    expected = _require_if_match(if_match)
    result = await delete_project(
        pool, user_ref=user_ref, project_id=project_id, expected_version=expected,
    )
    if result is None:
        raise HTTPException(404, detail="project not found")
    if "_conflict" in result:
        raise HTTPException(
            409, detail={"error": "version_conflict", "current_version": result["_conflict"]}
        )
    return {"deleted": True, "sessions_unlinked": result["sessions_unlinked"]}


@router.post("/v1/users/{user_ref}/projects/{project_id}/sessions")
async def assign_sessions_route(
    user_ref: str,
    project_id: UUID,
    body: AssignSessionsRequest,
    pool=Depends(_require_pool),
) -> dict[str, Any]:
    result = await add_project_sessions(
        pool, user_ref=user_ref, project_id=project_id, chat_ids=body.chat_ids,
    )
    if result is None:
        raise HTTPException(404, detail="project not found")
    return result


@router.delete("/v1/users/{user_ref}/projects/{project_id}/sessions/{saf_session_id}")
async def unassign_session_route(
    user_ref: str,
    project_id: UUID,
    saf_session_id: UUID,
    pool=Depends(_require_pool),
) -> dict[str, Any]:
    removed = await remove_project_session(
        pool, user_ref=user_ref, project_id=project_id, chat_id=saf_session_id,
    )
    if not removed:
        raise HTTPException(404, detail="session not linked to this project")
    return {"removed": True}
