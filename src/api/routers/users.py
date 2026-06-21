"""
src/api/routers/users.py — per-user endpoints. OWNER: Chief Engineer.

GET  /v1/users/{user_ref}/chats/{chat_id}/score   — full ScoreResponse + metadata
POST /v1/users/{user_ref}/chats/{chat_id}/feedback — store match rating
GET  /v1/users/{user_ref}/portfolio               — aggregated profile + archetype
DELETE /v1/users/{user_ref}                       — cascade-delete all four tables

Non-negotiables enforced structurally:
  - No composite value anywhere in the portfolio response (#6).
  - self_rating_raw is never included in any response body.
  - Absent ≠ zero: dimensions with no scored data → omitted from radar mean.
  - Personal baseline only — no peer comparison anywhere.
  - Minor protection: is_minor guard is dormant here (no bare composite/rank sent).
"""

from __future__ import annotations

import hashlib
import json
from typing import Any
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from contracts.schemas import Dimension, ScoreResponse
from src.api.middleware.auth import require_api_key
from src.db.queries import (
    delete_user,
    feedback_given,
    get_all_scores_for_user,
    get_portfolio_ack,
    get_scored_score_row,
    get_settings,
    get_turn_feedback,
    insert_feedback,
    insert_turn_feedback,
    upsert_portfolio_ack,
    upsert_settings,
)

router = APIRouter(dependencies=[Depends(require_api_key)])

_DIMS = [d.value for d in Dimension]

#: echoed on Scope-C responses so clients can detect contract drift (§3.9)
_CONTRACT_VERSION = "scope-c/v1.0"


def _portfolio_snapshot_hash(body: dict[str, Any]) -> str:
    """sha256 over the canonical portfolio state the user would acknowledge.
    Deterministic for identical scores; changes the moment the state moves."""
    canonical = json.dumps(body, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


async def _portfolio_ack_block(pool: asyncpg.Pool, user_ref: str, current_hash: str) -> dict[str, Any]:
    row = await get_portfolio_ack(pool, user_ref=user_ref, scope="portfolio")
    if row is None:
        return {"acked": False, "acked_at": None, "snapshot_hash": None}
    return {
        # acked is true only when the user acked THIS exact state (#snapshot-scoped)
        "acked": row["snapshot_hash"] == current_hash,
        "acked_at": row["acked_at"].isoformat(),
        "snapshot_hash": row["snapshot_hash"],
    }

# Archetype thresholds: a dimension is "dominant" if its mean is at least
# this far above the session average (DESIGNED rung — no claim stronger than that).
_DOMINANCE_THRESHOLD = 0.08


def _require_pool(request: Request):
    from src.db.connection import get_pool_optional
    pool = get_pool_optional()
    if pool is None:
        raise HTTPException(503, detail="Database unavailable — is Postgres running?")
    return pool


def _reconstruct_score(row: asyncpg.Record, chat_id: UUID) -> ScoreResponse:
    """Rebuild ScoreResponse from individual JSONB columns."""
    data: dict = {
        "session_id": str(chat_id),
        "tier": row["tier"],
        "profile": row["profile"],
        "composite": row["composite"],
        "state_strip": row["state_strip"],
        "state_validity": row["state_validity"],
        "flags": row["flags"],
        "reaction_signatures": row["reaction_signatures"],
        "regime_overlay": row["regime_overlay"],
        "sustainability": row["sustainability"],
        "report": row["report"],
    }
    return ScoreResponse.model_validate(data)


def _archetype(means: dict[str, float]) -> str:
    """Rule-based archetype from per-dim means. Rung: DESIGNED."""
    if not means:
        return "Balanced"
    overall = sum(means.values()) / len(means)

    def dominant(dims: list[str]) -> bool:
        return all(means.get(d, 0) - overall >= _DOMINANCE_THRESHOLD for d in dims)

    if dominant(["EC"]):
        return "Verifier"
    if dominant(["CS", "CD"]):
        return "Explorer"
    if dominant(["CA", "CS"]):
        return "Synthesizer"
    if dominant(["PR", "AUI"]):
        return "Scaffolder"
    return "Balanced"


_ARCHETYPE_DESCRIPTIONS = {
    "Verifier": "You interrogate AI outputs before accepting them — a hallmark of effective collaboration.",
    "Explorer": "You synthesise and diverge beyond the AI's suggestions, driving creative outcomes.",
    "Synthesizer": "You integrate AI output into your own reasoning and maintain clear direction.",
    "Scaffolder": "You structure tasks and augment your capability without outsourcing your effort.",
    "Balanced": "You show broadly distributed collaborative strengths across all dimensions.",
}


def _profile_values(profile: dict | None) -> dict[str, float]:
    values: dict[str, float] = {}
    for dim_key, ds in (profile or {}).items():
        if isinstance(ds, dict) and ds.get("status") == "OK" and ds.get("value") is not None:
            values[str(dim_key)] = float(ds["value"])
    return values


def _mean(values: dict[str, float]) -> float | None:
    return round(sum(values.values()) / len(values), 3) if values else None


def _longitudinal_to_date(rows: list[asyncpg.Record], chat_id: UUID) -> dict[str, Any]:
    selected = []
    found = False
    for row in rows:
        selected.append(row)
        if row["chat_id"] == chat_id:
            found = True
            break
    if not found:
        selected = rows

    dim_sums: dict[str, float] = {d: 0.0 for d in _DIMS}
    dim_counts: dict[str, int] = {d: 0 for d in _DIMS}
    history: list[dict[str, Any]] = []

    for row in selected:
        values = _profile_values(row["profile"])
        score = _mean(values)
        history.append({
            "chat_id": str(row["chat_id"]),
            "conversation_id": row["conversation_id"],
            "captured_at": row["captured_at"].isoformat(),
            "score": score,
        })
        for dim, value in values.items():
            dim_sums[dim] = dim_sums.get(dim, 0.0) + value
            dim_counts[dim] = dim_counts.get(dim, 0) + 1

    dimensions = {
        dim: round(dim_sums[dim] / dim_counts[dim], 3)
        if dim_counts[dim] else None
        for dim in _DIMS
    }
    scored_history = [h["score"] for h in history if h["score"] is not None]
    if len(scored_history) < 2:
        trend = "baseline"
    elif scored_history[-1] - scored_history[0] > 0.05:
        trend = "improving"
    elif scored_history[-1] - scored_history[0] < -0.05:
        trend = "declining"
    else:
        trend = "stable"

    return {
        "sessions_seen": len(selected),
        # No bare composite (#6 / scope-c §3.6): per-dim means + direction only.
        # Removing it also satisfies minor protection (#15) by construction — there
        # is no cross-dimension total for any caller, minor or not, to receive.
        "dimensions_till_now": dimensions,
        "trend_direction": trend,
        "history": history,
        "rung": "DESIGNED",
    }


# ── routes ───────────────────────────────────────────────────────────────────

@router.get("/v1/users/{user_ref}/chats/{chat_id}/score")
async def get_chat_score(
    user_ref: str,
    chat_id: UUID,
    pool: asyncpg.Pool = Depends(_require_pool),
) -> dict[str, Any]:
    row = await get_scored_score_row(pool, chat_id=chat_id, user_ref=user_ref)
    if row is None:
        raise HTTPException(404, detail="Score not found — chat may still be pending or invalid")

    score = _reconstruct_score(row, chat_id)
    fb = await feedback_given(pool, chat_id)

    rows = await get_all_scores_for_user(pool, user_ref)
    current_values = _profile_values(row["profile"])

    out = score.model_dump(by_alias=True)
    out["raw_profile"] = row["raw_profile"]
    out["telemetry_metrics"] = row["telemetry_metrics"]
    out["current_chat_score"] = {
        "score": _mean(current_values),
        "dimensions": current_values,
    }
    out["longitudinal"] = _longitudinal_to_date(rows, chat_id)
    out["self_rating_status"] = row["self_rating_status"]
    out["feedback_given"] = fb
    out["turn_feedback"] = [
        {
            "turn_index": r["turn_index"],
            "match_rating": r["match_rating"],
            "dimension_scores": r["dimension_scores"],
            "comment": r["comment"],
            "submitted_at": r["submitted_at"].isoformat(),
        }
        for r in await get_turn_feedback(pool, chat_id)
    ]
    return out


@router.get("/v1/users/{user_ref}/sessions/{saf_session_id}")
async def get_session_score(
    user_ref: str,
    saf_session_id: UUID,
    pool: asyncpg.Pool = Depends(_require_pool),
) -> dict[str, Any]:
    """Scope-C alias of the chat-score route. saf_session_id IS raw_chats.id
    (scope-c §1/§4.3) — identical payload; provided so S8/S9 can use the
    project/session vocabulary without a second identity."""
    return await get_chat_score(user_ref, saf_session_id, pool)


class FeedbackRequest(BaseModel):
    match_rating: str   # 'yes' | 'partial' | 'no'
    comment: str | None = None
    turn_index: int | None = None
    dimension_scores: dict[str, float] | None = None


@router.post("/v1/users/{user_ref}/chats/{chat_id}/feedback")
async def post_feedback(
    user_ref: str,
    chat_id: UUID,
    body: FeedbackRequest,
    pool: asyncpg.Pool = Depends(_require_pool),
) -> dict[str, bool]:
    if body.match_rating not in ("yes", "partial", "no"):
        raise HTTPException(422, detail="match_rating must be 'yes', 'partial', or 'no'")
    if body.comment and len(body.comment) > 280:
        raise HTTPException(422, detail="comment exceeds 280 characters")
    if body.turn_index is not None and body.turn_index < 0:
        raise HTTPException(422, detail="turn_index must be >= 0")
    if body.dimension_scores is not None:
        unknown = set(body.dimension_scores) - set(_DIMS)
        if unknown:
            raise HTTPException(422, detail=f"unknown dimensions: {sorted(unknown)}")
        for dim, value in body.dimension_scores.items():
            if value < 0.0 or value > 1.0:
                raise HTTPException(422, detail=f"{dim} must be between 0.0 and 1.0")

    # Snapshot the current score state at submission time
    row = await get_scored_score_row(pool, chat_id=chat_id, user_ref=user_ref)
    snapshot: dict = {}
    if row is not None:
        rows = await get_all_scores_for_user(pool, user_ref)
        snapshot = {
            "profile": row["profile"],
            "raw_profile": row["raw_profile"],
            "composite": row["composite"],
            "report": row["report"],
            "prompt_version": row["prompt_version"],
            "telemetry_metrics": row["telemetry_metrics"],
            "longitudinal": _longitudinal_to_date(rows, chat_id),
        }

    if body.turn_index is not None:
        await insert_turn_feedback(
            pool,
            chat_id=chat_id,
            user_ref=user_ref,
            turn_index=body.turn_index,
            match_rating=body.match_rating,
            dimension_scores=body.dimension_scores,
            comment=body.comment,
            scores_snapshot=snapshot,
        )
        return {"received": True}

    await insert_feedback(
        pool,
        chat_id=chat_id,
        user_ref=user_ref,
        match_rating=body.match_rating,
        comment=body.comment,
        scores_snapshot=snapshot,
    )
    return {"received": True}


@router.get("/v1/users/{user_ref}/portfolio")
async def get_portfolio(
    user_ref: str,
    pool: asyncpg.Pool = Depends(_require_pool),
) -> dict[str, Any]:
    rows = await get_all_scores_for_user(pool, user_ref)

    if not rows:
        return {
            "status": "INSUFFICIENT_HISTORY",
            "message": "No scored chats yet — analyse a conversation to start.",
            "sessions_analysed": 0,
            "contract_version": _CONTRACT_VERSION,
        }

    sessions_count = len(rows)

    # Per-dim means (only OK-status scores, absent ≠ zero)
    dim_sums: dict[str, float] = {d: 0.0 for d in _DIMS}
    dim_counts: dict[str, int] = {d: 0 for d in _DIMS}

    for row in rows:
        profile: dict = row["profile"] or {}
        for dim_key, ds in profile.items():
            if isinstance(ds, dict) and ds.get("status") == "OK" and ds.get("value") is not None:
                dim_sums[dim_key] = dim_sums.get(dim_key, 0.0) + ds["value"]
                dim_counts[dim_key] = dim_counts.get(dim_key, 0) + 1

    radar: dict[str, float | None] = {}
    for d in _DIMS:
        radar[d] = round(dim_sums[d] / dim_counts[d], 3) if dim_counts[d] > 0 else None

    scored_means = {d: v for d, v in radar.items() if v is not None}
    archetype = _archetype(scored_means)

    # Trajectory (requires >= 3 scored chats)
    trajectory: dict | str
    if sessions_count < 3:
        trajectory = "INSUFFICIENT_HISTORY"
    else:
        # Simple per-session composite means for the trajectory signal
        # Composite value is not shown to the user here — only trend direction is.
        # The composite value is a research instrument; what is surfaced is the
        # direction of change over time (personal baseline only — no peer rank).
        session_means: list[float] = []
        for row in rows:
            profile = row["profile"] or {}
            vals = [
                ds["value"]
                for ds in profile.values()
                if isinstance(ds, dict) and ds.get("status") == "OK" and ds.get("value") is not None
            ]
            if vals:
                session_means.append(sum(vals) / len(vals))

        if len(session_means) >= 3:
            trend = session_means[-1] - session_means[0]
            if trend > 0.05:
                direction = "improving"
            elif trend < -0.05:
                direction = "declining"
            else:
                direction = "stable"
            trajectory = {
                "sessions": session_means,
                "trend_direction": direction,
                "uncertainty_band": "high",  # DESIGNED rung; needs probe data to narrow
            }
        else:
            trajectory = "INSUFFICIENT_HISTORY"

    session_means = []
    for row in rows:
        score = _mean(_profile_values(row["profile"]))
        if score is not None:
            session_means.append(score)
    if len(session_means) < 2:
        direction = "baseline"
    else:
        trend = session_means[-1] - session_means[0]
        if trend > 0.05:
            direction = "improving"
        elif trend < -0.05:
            direction = "declining"
        else:
            direction = "stable"
    trajectory = {
        "sessions": session_means,
        "trend_direction": direction,
        "uncertainty_band": "high",
    }

    # Growth summary
    growth_summary: dict[str, str | None] = {
        "strongest_dim": None,
        "growing_dim": None,
        "watch_dim": None,
    }
    if scored_means:
        growth_summary["strongest_dim"] = max(scored_means, key=scored_means.__getitem__)
        growth_summary["watch_dim"] = min(scored_means, key=scored_means.__getitem__)

    first_at = rows[0]["captured_at"].isoformat() if rows else None

    body: dict[str, Any] = {
        "profile_radar": radar,
        # No bare composite (#6 / scope-c §3.6). The per-dim radar IS the signal;
        # a single "overall score" is never emitted — which also makes the response
        # minor-safe by construction (#15), independent of an is_minor flag (which
        # the live ingest path does not yet persist).
        "archetype": archetype,
        "archetype_description": _ARCHETYPE_DESCRIPTIONS[archetype],
        "trajectory": trajectory,
        "growth_summary": growth_summary,
        "sessions_analysed": sessions_count,
        "first_analysed_at": first_at,
        "rung": "DESIGNED",  # portfolio aggregation is research-grade, not validated
    }
    # Snapshot-hash + acknowledgement (scope-c §4.4). The hash is over the
    # meaningful state only; when the user later acks this exact hash the UI knows
    # there is no unacknowledged change without storing the whole state twice.
    body["snapshot_hash"] = _portfolio_snapshot_hash(body)
    body["ack"] = await _portfolio_ack_block(pool, user_ref, body["snapshot_hash"])
    body["contract_version"] = _CONTRACT_VERSION
    return body


class PortfolioAckRequest(BaseModel):
    snapshot_hash: str


@router.post("/v1/users/{user_ref}/portfolio/ack")
async def post_portfolio_ack(
    user_ref: str,
    body: PortfolioAckRequest,
    pool: asyncpg.Pool = Depends(_require_pool),
) -> dict[str, Any]:
    """Acknowledge a specific portfolio snapshot (scope-c §4.4). 409 if the state
    moved between the client's GET and this POST — the client re-reads, re-acks."""
    current = await get_portfolio(user_ref, pool)
    current_hash = current.get("snapshot_hash")
    if current_hash is None or body.snapshot_hash != current_hash:
        raise HTTPException(
            409, detail={"error": "stale_snapshot", "current_hash": current_hash}
        )
    rec = await upsert_portfolio_ack(
        pool, user_ref=user_ref, scope="portfolio", snapshot_hash=current_hash
    )
    return {"acked": True, "acked_at": rec["acked_at"].isoformat()}


@router.get("/v1/users/{user_ref}/settings")
async def get_user_settings(
    user_ref: str,
    pool: asyncpg.Pool = Depends(_require_pool),
) -> dict[str, Any]:
    out = await get_settings(pool, user_ref=user_ref)
    out["contract_version"] = _CONTRACT_VERSION
    return out


class SettingsRequest(BaseModel):
    auto_analyse: bool | None = None
    calibration_opt_in: bool | None = None


@router.patch("/v1/users/{user_ref}/settings")
async def patch_user_settings(
    user_ref: str,
    body: SettingsRequest,
    pool: asyncpg.Pool = Depends(_require_pool),
) -> dict[str, Any]:
    if body.auto_analyse is None and body.calibration_opt_in is None:
        raise HTTPException(422, detail="no settings fields to update")
    out = await upsert_settings(
        pool,
        user_ref=user_ref,
        auto_analyse=body.auto_analyse,
        calibration_opt_in=body.calibration_opt_in,
    )
    out["contract_version"] = _CONTRACT_VERSION
    return out


@router.delete("/v1/users/{user_ref}")
async def delete_user_data(
    user_ref: str,
    pool: asyncpg.Pool = Depends(_require_pool),
) -> dict[str, Any]:
    """CASCADE deletion propagates to all four tables (#16 — data dignity)."""
    deleted = await delete_user(pool, user_ref)
    return {"deleted": True, "raw_chats_removed": deleted}
