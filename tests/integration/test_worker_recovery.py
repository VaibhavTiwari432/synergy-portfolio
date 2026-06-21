"""Audit Track 2 — worker recovery + capture-completeness (requires Postgres).

  - A chat stuck in 'scoring' past LEASE_TIMEOUT is reclaimed to 'pending' by the
    watchdog (reset_expired_scoring_leases) — a crashed/hung worker never wedges
    a chat forever.
  - An incomplete capture (capture_complete=false) is REJECTED at ingest
    (ValueError → 422 at the router), never entering 'pending' to be scored.

Run:  PHASE1_GATE=1 pytest tests/integration/test_worker_recovery.py -v
"""

from __future__ import annotations

import json
import os
import asyncio
import uuid

import pytest
import pytest_asyncio

pytestmark = pytest.mark.skipif(
    os.environ.get("PHASE1_GATE") != "1",
    reason="Set PHASE1_GATE=1 to run worker-recovery tests (requires Postgres)",
)

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://saf:saf_local@localhost:5432/saf_brain"
)

_PARTNER = {"family": "openai", "model_id": "gpt-4o", "era_key": "2024-01"}


def _turns(n: int) -> list[dict]:
    out = []
    for i in range(n):
        out.append({"role": "user", "text": "walk me through it step by step", "turn_index": i * 2})
        out.append({"role": "assistant", "text": "a long enough ai reply here", "turn_index": i * 2 + 1})
    return out


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def pool():
    import asyncpg

    async def _init(conn):
        await conn.set_type_codec("jsonb", encoder=json.dumps, decoder=json.loads, schema="pg_catalog")
        await conn.set_type_codec("json", encoder=json.dumps, decoder=json.loads, schema="pg_catalog")

    p = await asyncpg.create_pool(DATABASE_URL, init=_init)
    yield p
    await p.close()


@pytest_asyncio.fixture(loop_scope="module")
async def clean_user(pool):
    from src.db.queries import delete_user
    ref = f"recov_{uuid.uuid4().hex[:8]}"
    yield ref
    await delete_user(pool, ref)


@pytest.mark.asyncio(loop_scope="module")
async def test_stuck_scoring_row_is_reclaimed_after_lease_timeout(pool, clean_user):
    from src.db.queries import reset_expired_scoring_leases, upsert_chat

    row = await upsert_chat(
        pool, user_ref=clean_user, conversation_id="conv_stuck", source="chatgpt_live",
        partner_model=_PARTNER, turns=_turns(3), turn_count=6,
    )
    chat_id = row["id"]
    lease = 300

    # simulate a worker that claimed the chat then crashed: 'scoring', stale lease
    await pool.execute(
        "UPDATE raw_chats SET status='scoring', scoring_started_at = NOW() - INTERVAL '1 second' * $2 "
        "WHERE id = $1",
        chat_id, lease + 60,
    )
    assert await pool.fetchval("SELECT status FROM raw_chats WHERE id=$1", chat_id) == "scoring"

    async with pool.acquire() as conn:
        reset = await reset_expired_scoring_leases(conn, lease_timeout_seconds=lease)

    reset_ids = {r["id"] for r in reset}
    assert chat_id in reset_ids, "expired lease must be reclaimed"
    healed = await pool.fetchrow(
        "SELECT status, scoring_started_at FROM raw_chats WHERE id=$1", chat_id
    )
    assert healed["status"] == "pending" and healed["scoring_started_at"] is None


@pytest.mark.asyncio(loop_scope="module")
async def test_fresh_scoring_lease_is_NOT_reclaimed(pool, clean_user):
    from src.db.queries import reset_expired_scoring_leases, upsert_chat

    row = await upsert_chat(
        pool, user_ref=clean_user, conversation_id="conv_fresh", source="chatgpt_live",
        partner_model=_PARTNER, turns=_turns(3), turn_count=6,
    )
    chat_id = row["id"]
    await pool.execute(
        "UPDATE raw_chats SET status='scoring', scoring_started_at = NOW() WHERE id=$1", chat_id
    )
    async with pool.acquire() as conn:
        reset = await reset_expired_scoring_leases(conn, lease_timeout_seconds=300)
    assert chat_id not in {r["id"] for r in reset}, "a fresh lease must not be reclaimed"
    assert await pool.fetchval("SELECT status FROM raw_chats WHERE id=$1", chat_id) == "scoring"


@pytest.mark.asyncio(loop_scope="module")
async def test_incomplete_capture_is_rejected_not_scored(pool, clean_user):
    from src.db.queries import upsert_chat

    # capture_complete=false with a captured<expected mismatch must be refused at
    # ingest (ValueError → 422 at the router), never queued as 'pending'.
    with pytest.raises(ValueError):
        await upsert_chat(
            pool, user_ref=clean_user, conversation_id="conv_incomplete", source="chatgpt_live",
            partner_model=_PARTNER, turns=_turns(3), turn_count=6,
            expected_turn_count=20, captured_turn_count=6, capture_complete=False,
        )
    # nothing landed for that conversation
    n = await pool.fetchval(
        "SELECT COUNT(*) FROM raw_chats WHERE user_ref=$1 AND conversation_id='conv_incomplete'",
        clean_user,
    )
    assert n == 0


@pytest.mark.asyncio(loop_scope="module")
async def test_concurrent_workers_claim_and_finalize_once(pool, clean_user):
    from src.db.queries import claim_pending_batch, mark_scored, upsert_chat, upsert_score

    row = await upsert_chat(
        pool, user_ref=clean_user, conversation_id="conv_concurrent", source="chatgpt_live",
        partner_model=_PARTNER, turns=_turns(3), turn_count=6,
    )
    chat_id = row["id"]
    content_hash = row["content_hash"]
    await pool.execute(
        "UPDATE raw_chats SET captured_at = NOW() - INTERVAL '1 day' WHERE id=$1",
        chat_id,
    )

    async with pool.acquire() as conn1, pool.acquire() as conn2:
        claimed1, claimed2 = await asyncio.gather(
            claim_pending_batch(conn1, batch_size=20),
            claim_pending_batch(conn2, batch_size=20),
        )

    claimed_ids = [r["id"] for r in claimed1 + claimed2]
    assert claimed_ids.count(chat_id) == 1

    async with pool.acquire() as conn:
        await upsert_score(
            conn, chat_id=chat_id, prompt_version="test", tier=1,
            profile={}, composite=None, state_strip=None, state_validity=None,
            flags=None, reaction_signatures=None, regime_overlay=None,
            sustainability=None, report=None, raw_profile=None,
            telemetry_metrics={}, event_log=[], provenance={},
        )
        first = await mark_scored(conn, chat_id, content_hash)
        second = await mark_scored(conn, chat_id, content_hash)

    assert first == 1
    assert second == 0
    assert await pool.fetchval("SELECT status FROM raw_chats WHERE id=$1", chat_id) == "scored"
    assert await pool.fetchval("SELECT COUNT(*) FROM scores WHERE chat_id=$1", chat_id) == 1
