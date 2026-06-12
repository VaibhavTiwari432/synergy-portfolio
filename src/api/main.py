"""
src/api/main.py — the FastAPI app (brief §4.2). OWNER: Chief Engineer.

    POST /v1/sessions                  ingest → {session_id, detected_tier, event_count}
    GET  /v1/sessions/{id}/score       full ScoreResponse (claims-gated)
    GET  /v1/users/{ref}/trajectory    multi-session; INSUFFICIENT_HISTORY on 1
    POST /v1/calibration/run           the MAE ratchet
    GET  /v1/health                    liveness (no auth)
    GET  /v1/contracts                 contract/prompt versions (no auth)

The API is the Scope-A deliverable; everything else hangs off it.
"""

from __future__ import annotations

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
from src.api.store import SessionStore
from src.claims.tier_engine import detect_tier
from src.ingestion.canonical import IngestionError, ingest
from src.sustainability.ewma import debt_ewma
from src.trait.judge.prompt import JUDGE_PROMPT_VERSION


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


def create_app(store: SessionStore | None = None) -> FastAPI:
    app = FastAPI(title="saf-brain", version=SCHEMA_VERSION)
    app.state.store = store or SessionStore("saf_brain.db")

    def _store() -> SessionStore:
        return app.state.store

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
                "note": "trajectory requires at least 2 scored sessions",
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
