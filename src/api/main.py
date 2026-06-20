"""
src/api/main.py — the FastAPI app (brief §4.2). OWNER: Chief Engineer.

Scope A endpoints (SQLite-backed, unchanged):
    POST /v1/sessions                  ingest → {session_id, detected_tier, event_count}
    GET  /v1/sessions/{id}/score       full ScoreResponse (claims-gated)
    GET  /v1/users/{ref}/trajectory    multi-session; INSUFFICIENT_HISTORY on 1
    POST /v1/calibration/run           the MAE ratchet
    GET  /v1/health                    liveness (no auth)
    GET  /v1/contracts                 contract/prompt versions (no auth)

Scope B endpoints (Postgres-backed — routers/ingest.py + routers/users.py):
    POST /v1/ingest                               write chat + telemetry → pending
    GET  /v1/users/{ref}/chats                    list chats + summary
    GET  /v1/users/{ref}/chats/{id}/score         full ScoreResponse from scores table
    POST /v1/users/{ref}/chats/{id}/feedback      store match rating
    GET  /v1/users/{ref}/portfolio                aggregated profile + archetype
    DELETE /v1/users/{ref}                        cascade-delete all four tables

Postgres pool is initialised at startup. If Postgres is unavailable the Scope B
endpoints return 503 — Scope A is unaffected (it uses SQLite only).
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field

from contracts.schemas import (
    SCHEMA_VERSION,
    CanonicalSession,
    DebtMode,
    PartnerModel,
    ScoreResponse,
    SourceFormat,
)
from src.api.middleware.auth import require_api_key
from src.api.pipeline import score_session
from src.api.routers.ingest import router as ingest_router
from src.api.routers.projects import router as projects_router
from src.api.routers.users import router as users_router
from src.api.store import SessionStore
from src.claims.tier_engine import detect_tier
from src.ingestion.canonical import IngestionError, ingest
from src.sustainability.ewma import debt_ewma
from src.trait.judge.prompt import JUDGE_PROMPT_VERSION

log = logging.getLogger(__name__)


# ── lifespan (Postgres pool) ──────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    from src.db.connection import close_pool, init_pool
    try:
        await init_pool()
    except Exception as exc:
        log.warning(
            "Postgres unavailable — Scope B endpoints will return 503. (%s: %s)",
            type(exc).__name__, exc,
        )
    yield
    await close_pool()


# ── Scope A request/response models (unchanged) ───────────────────────────────

class CreateSessionRequest(BaseModel):
    payload: str | dict | list
    source: SourceFormat | None = None
    user_ref: str | None = None
    partner_model: PartnerModel | None = None
    is_minor: bool = False


class CreateSessionResponse(BaseModel):
    session_id: str
    detected_tier: int
    event_count: int = Field(description="events in the log at ingestion (detectors add more)")


# ── app factory ───────────────────────────────────────────────────────────────

def create_app(store: SessionStore | None = None) -> FastAPI:
    app = FastAPI(title="saf-brain", version=SCHEMA_VERSION, lifespan=lifespan)
    app.state.store = store or SessionStore("saf_brain.db")

    # Scope B routers (Postgres)
    app.include_router(ingest_router)
    app.include_router(users_router)
    # Scope C routers (Postgres) — projects / sessions (D-012, scope-c/v1.0)
    app.include_router(projects_router)

    def _store() -> SessionStore:
        return app.state.store

    # ── Scope A routes (SQLite) ──

    @app.get("/v1/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/v1/contracts")
    async def contracts() -> dict[str, str]:
        return {
            "schema_version": SCHEMA_VERSION,
            "judge_prompt_version": JUDGE_PROMPT_VERSION,
            "ontology": "107 neurons / 8 dims / 4 pillars (frozen)",
        }

    @app.post(
        "/v1/sessions",
        response_model=CreateSessionResponse,
        dependencies=[Depends(require_api_key)],
    )
    async def create_session(request: CreateSessionRequest) -> CreateSessionResponse:
        try:
            session: CanonicalSession = ingest(
                request.payload,
                partner_model=request.partner_model,
                user_ref=request.user_ref,
                is_minor=request.is_minor,
                source=request.source,
            )
        except IngestionError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        _store().put_session(session)
        return CreateSessionResponse(
            session_id=session.session_id,
            detected_tier=detect_tier(session),
            event_count=0,
        )

    @app.get(
        "/v1/sessions/{session_id}/score",
        response_model=ScoreResponse,
        response_model_by_alias=True,
        dependencies=[Depends(require_api_key)],
    )
    async def get_score(session_id: str) -> ScoreResponse:
        store = _store()
        cached = store.get_score(session_id)
        if cached is not None:
            return cached
        session = store.get_session(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="unknown session_id")
        response = score_session(session)
        store.put_score(response)
        return response

    @app.get(
        "/v1/users/{user_ref}/trajectory",
        dependencies=[Depends(require_api_key)],
    )
    async def trajectory(user_ref: str) -> dict[str, Any]:
        scores = _store().scores_for_user(user_ref)
        history = [
            s.composite.value for s in scores if s.composite.value is not None
        ]
        if len(history) < 2:
            return {
                "user_ref": user_ref,
                "n_sessions": len(scores),
                "status": DebtMode.INSUFFICIENT_HISTORY.value,
                "composite_history": history,
                "trend_direction": None,
                "note": "at least two scored sessions are needed for trajectory",
            }
        ewma = debt_ewma(history)
        return {
            "user_ref": user_ref,
            "n_sessions": len(scores),
            "status": "ok",
            "composite_history": history,  # personal baseline — never a ranking
            "debt_ewma": ewma.model_dump(),
        }

    @app.post("/v1/calibration/run", dependencies=[Depends(require_api_key)])
    async def calibration_run() -> dict[str, Any]:
        from calibration.runner import run_calibration
        from src.api.pipeline import judge_score_fn

        result = run_calibration(judge_score_fn())
        return {
            "overall_mae": result["shadow"]["overall_mae"],
            "per_dim_mae": result["shadow"]["per_dim_mae"],
            "ratchet_passed": result["ratchet_passed"],
            "headline": result["headline"],
        }

    return app


app = create_app()
