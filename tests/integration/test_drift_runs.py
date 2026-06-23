"""
Drift-run persistence gate — requires a live Postgres (migrations ≥ 017).

Phase F acceptance: the drift_runs table exists, and a frozen-anchor drift check
computed by calibration.drift_check.compute_drift can be written as a row via
insert_drift_run. drift_detected=True is a warning signal, persisted for history —
it never blocks anything here.

Run:  PHASE1_GATE=1 pytest tests/integration/test_drift_runs.py -v
"""

from __future__ import annotations

import json
import os

import pytest
import pytest_asyncio

from contracts.schemas import (
    CanonicalSession,
    Dimension,
    PartnerModel,
    Turn,
)
from calibration.drift_check import ANCHOR_CHAT_IDS, compute_drift
from calibration.gold_loader import GoldChat

pytestmark = pytest.mark.skipif(
    os.environ.get("PHASE1_GATE") != "1",
    reason="Set PHASE1_GATE=1 to run drift-run persistence tests (requires Postgres)",
)

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://saf:saf_local@localhost:5432/saf_brain"
)


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def pool():
    import asyncpg

    async def _init(conn):
        await conn.set_type_codec("jsonb", encoder=json.dumps, decoder=json.loads, schema="pg_catalog")
        await conn.set_type_codec("json",  encoder=json.dumps, decoder=json.loads, schema="pg_catalog")

    p = await asyncpg.create_pool(DATABASE_URL, init=_init)
    yield p
    await p.close()


def _anchor_corpus(target: float):
    out = []
    for aid in ANCHOR_CHAT_IDS:
        session = CanonicalSession(
            session_id=aid, source="gold_json", partner_model=PartnerModel(family="openai"),
            turns=[Turn(index=0, role="human", text="q"), Turn(index=1, role="ai", text="a")],
        )
        out.append(GoldChat(
            session=session, targets={d: target for d in Dimension},
            judge_family_conflict=False, ocr_excluded=False,
        ))
    return out


@pytest.mark.asyncio(loop_scope="module")
async def test_drift_run_persists_a_flagged_row(pool):
    from src.db.queries import insert_drift_run

    # a drifted judge: off by 0.5 vs a 0.25 baseline → drift_detected True
    result = compute_drift(
        lambda s: {d: 0.0 for d in Dimension},
        baseline_mae=0.25, judge_model_id="judge-test", prompt_version="v2.1",
        corpus=_anchor_corpus(0.5),
    )
    assert result["drift_detected"] is True

    async with pool.acquire() as conn:
        run_id = await insert_drift_run(conn, **result)

    try:
        row = await pool.fetchrow("SELECT * FROM drift_runs WHERE id = $1", run_id)
        assert row is not None
        assert row["drift_detected"] is True
        assert row["mae_overall"] == pytest.approx(0.5)
        assert set(row["anchor_set"]) == set(ANCHOR_CHAT_IDS)
        assert row["mae_per_dimension"] is not None
        assert row["baseline_mae"] == pytest.approx(0.25)
    finally:
        await pool.execute("DELETE FROM drift_runs WHERE id = $1", run_id)


@pytest.mark.asyncio(loop_scope="module")
async def test_indeterminate_drift_persists_null_flag(pool):
    from src.db.queries import insert_drift_run

    # no baseline → drift_detected None must persist as NULL, never a false False
    result = compute_drift(
        lambda s: {d: 0.5 for d in Dimension},
        baseline_mae=None, judge_model_id="judge-test", prompt_version="v2.1",
        corpus=_anchor_corpus(0.5),
    )
    assert result["drift_detected"] is None

    async with pool.acquire() as conn:
        run_id = await insert_drift_run(conn, **result)
    try:
        flag = await pool.fetchval("SELECT drift_detected FROM drift_runs WHERE id = $1", run_id)
        assert flag is None, "indeterminate drift persists as NULL (absent ≠ False)"
    finally:
        await pool.execute("DELETE FROM drift_runs WHERE id = $1", run_id)
