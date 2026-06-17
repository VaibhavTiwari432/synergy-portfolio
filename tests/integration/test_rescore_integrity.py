"""
Re-score integrity gate — requires a live Postgres instance.

Proves the D-006 / stuck-scoring fixes (CE bug triage 2026-06-16):

  R1  Identical re-ingest does NOT reset status (no redundant judge call).
  R2  Changed re-ingest (appended pair) resets status → 'pending' exactly once.
  R3  mark_scored is optimistic: if content changed mid-scoring it finalizes 0
      rows and the chat stays pending → it re-scores against the newer turns.
  R4  claim_pending_batch reclaims a 'scoring' row whose lease has expired.
  R5  upsert_telemetry keeps exactly one current row per chat (latest wins).
  R6  Identical re-ingest of a failed chat re-queues it for retry.
  R7  Structurally imbalanced captures are rejected before raw_chats write.

Run:  PHASE1_GATE=1 pytest tests/integration/test_rescore_integrity.py -v
"""

from __future__ import annotations

import os
import uuid

import pytest
import pytest_asyncio

pytestmark = pytest.mark.skipif(
    os.environ.get("PHASE1_GATE") != "1",
    reason="Set PHASE1_GATE=1 to run re-score integrity tests (requires Postgres)",
)

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://saf:saf_local@localhost:5432/saf_brain",
)


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def pool():
    import asyncpg
    import json as _json

    async def _init(conn):
        await conn.set_type_codec("jsonb", encoder=_json.dumps, decoder=_json.loads, schema="pg_catalog")
        await conn.set_type_codec("json",  encoder=_json.dumps, decoder=_json.loads, schema="pg_catalog")

    p = await asyncpg.create_pool(DATABASE_URL, init=_init)
    yield p
    await p.close()


@pytest_asyncio.fixture(loop_scope="module")
async def clean_user(pool):
    ref = f"rescore_{uuid.uuid4().hex[:8]}"
    yield ref
    # delete chats AND the opaque subject row, so the run leaves no orphan
    # subject behind (the subject's only reason to exist was this user_ref)
    await pool.execute("DELETE FROM raw_chats WHERE user_ref = $1", ref)
    await pool.execute("DELETE FROM subjects WHERE user_ref = $1", ref)


# ── helpers ───────────────────────────────────────────────────────────────────

def _pairs(n: int) -> list[dict]:
    turns = []
    for i in range(n):
        turns.append({"role": "user",      "text": f"Human turn {i}", "turn_index": i * 2})
        turns.append({"role": "assistant", "text": f"AI turn {i}",    "turn_index": i * 2 + 1})
    return turns


def _partner() -> dict:
    return {"family": "openai", "model_id": "gpt-4o", "era_key": "2024-01"}


async def _ingest(pool, user_ref, conv_id, n_pairs):
    from src.db.queries import upsert_chat
    return await upsert_chat(
        pool,
        user_ref=user_ref,
        conversation_id=conv_id,
        source="chatgpt_live",
        partner_model=_partner(),
        turns=_pairs(n_pairs),
        turn_count=n_pairs * 2,
    )


async def _status(pool, chat_id):
    return await pool.fetchval("SELECT status FROM raw_chats WHERE id = $1", chat_id)


# ── R1: identical re-ingest is a no-op on status ──────────────────────────────

@pytest.mark.asyncio(loop_scope="module")
async def test_r1_identical_reingest_keeps_status(pool, clean_user):
    from src.db.queries import set_chat_status

    row = await _ingest(pool, clean_user, "conv_r1", 3)
    chat_id = row["id"]
    assert row["status"] == "pending"
    first_hash = row["content_hash"]

    # Simulate the worker finishing.
    async with pool.acquire() as conn:
        await set_chat_status(conn, chat_id, "scored")

    # Re-ingest the SAME transcript (panel reopen / telemetry-only snapshot).
    again = await _ingest(pool, clean_user, "conv_r1", 3)
    assert again["id"] == chat_id, "must be the same row (idempotent)"
    assert again["content_hash"] == first_hash, "hash unchanged for identical content"
    assert await _status(pool, chat_id) == "scored", "identical re-ingest must NOT re-queue"


# ── R2: changed re-ingest re-queues ───────────────────────────────────────────

@pytest.mark.asyncio(loop_scope="module")
async def test_r2_changed_reingest_requeues(pool, clean_user):
    from src.db.queries import set_chat_status

    row = await _ingest(pool, clean_user, "conv_r2", 3)
    chat_id = row["id"]
    async with pool.acquire() as conn:
        await set_chat_status(conn, chat_id, "scored")

    # Conversation grew by one pair.
    grown = await _ingest(pool, clean_user, "conv_r2", 4)
    assert grown["id"] == chat_id
    assert grown["content_hash"] != row["content_hash"], "hash must change with new turns"
    assert grown["status"] == "pending", "changed transcript must re-queue for scoring"


# ── R3: mark_scored optimistic concurrency ────────────────────────────────────

@pytest.mark.asyncio(loop_scope="module")
async def test_r3_mark_scored_is_optimistic(pool, clean_user):
    from src.db.queries import claim_pending_batch, mark_scored

    row = await _ingest(pool, clean_user, "conv_r3", 3)
    chat_id = row["id"]

    # Worker claims it; this is the hash it will score against.
    async with pool.acquire() as conn:
        batch = await claim_pending_batch(conn, batch_size=10)
    claimed = next(c for c in batch if c["id"] == chat_id)
    scored_hash = claimed["content_hash"]
    assert await _status(pool, chat_id) == "scoring"

    # While "scoring", a newer ingest lands with more turns → resets to pending.
    grown = await _ingest(pool, clean_user, "conv_r3", 5)
    assert grown["status"] == "pending"

    # The worker now tries to finalize the OLD transcript: must be a no-op.
    async with pool.acquire() as conn:
        n = await mark_scored(conn, chat_id, scored_hash)
    assert n == 0, "stale finalize must update 0 rows"
    assert await _status(pool, chat_id) == "pending", "row stays pending for re-score"

    # Re-claim and finalize with the CURRENT hash → succeeds exactly once.
    async with pool.acquire() as conn:
        batch2 = await claim_pending_batch(conn, batch_size=10)
    claimed2 = next(c for c in batch2 if c["id"] == chat_id)
    async with pool.acquire() as conn:
        n2 = await mark_scored(conn, chat_id, claimed2["content_hash"])
    assert n2 == 1, "current finalize must update exactly 1 row"
    assert await _status(pool, chat_id) == "scored"


# ── R4: expired lease is reclaimed ────────────────────────────────────────────

@pytest.mark.asyncio(loop_scope="module")
async def test_r4_expired_lease_reclaimed(pool, clean_user):
    from src.db.queries import claim_pending_batch

    row = await _ingest(pool, clean_user, "conv_r4", 2)
    chat_id = row["id"]

    # Simulate a worker that claimed it then died 10 minutes ago.
    await pool.execute(
        "UPDATE raw_chats SET status='scoring', scoring_started_at = NOW() - INTERVAL '10 minutes' WHERE id=$1",
        chat_id,
    )

    async with pool.acquire() as conn:
        batch = await claim_pending_batch(conn, batch_size=10)
    reclaimed_ids = {c["id"] for c in batch}
    assert chat_id in reclaimed_ids, "expired-lease 'scoring' row must be reclaimed"
    assert await _status(pool, chat_id) == "scoring", "reclaim re-leases it"


# ── R5: telemetry stays single-row ────────────────────────────────────────────

@pytest.mark.asyncio(loop_scope="module")
async def test_r5_telemetry_upsert_single_row(pool, clean_user):
    from src.db.queries import get_telemetry_for_chat, upsert_telemetry

    row = await _ingest(pool, clean_user, "conv_r5", 2)
    chat_id = row["id"]

    await upsert_telemetry(
        pool, chat_id=chat_id, dwell_ms=[100, 200, 300, 400],
        copy_events=[0, 0, 0, 0], edit_detected=[False] * 4,
        selector_health="ok", capture_mode="live_capture", metadata={"v": 1},
    )
    # Second snapshot of the same chat — must REPLACE, not append.
    await upsert_telemetry(
        pool, chat_id=chat_id, dwell_ms=[1, 2, 3, 4],
        copy_events=[1, 0, 0, 0], edit_detected=[True, False, False, False],
        selector_health="selector_miss", capture_mode="live_capture", metadata={"v": 2},
    )

    count = await pool.fetchval("SELECT COUNT(*) FROM telemetry WHERE chat_id = $1", chat_id)
    assert count == 1, f"expected exactly one telemetry row, got {count}"

    latest = await get_telemetry_for_chat(pool, chat_id)
    assert latest["selector_health"] == "selector_miss", "latest snapshot must win"
    assert latest["metadata"]["v"] == 2


# ── R6: failed identical re-ingest retries ───────────────────────────────────

@pytest.mark.asyncio(loop_scope="module")
async def test_r6_identical_failed_reingest_requeues(pool, clean_user):
    from src.db.queries import set_chat_status

    row = await _ingest(pool, clean_user, "conv_r6", 3)
    chat_id = row["id"]
    first_hash = row["content_hash"]

    async with pool.acquire() as conn:
        await set_chat_status(conn, chat_id, "failed")

    retry = await _ingest(pool, clean_user, "conv_r6", 3)
    assert retry["id"] == chat_id
    assert retry["content_hash"] == first_hash
    assert retry["status"] == "pending", "identical failed chat must re-queue for retry"
    assert await _status(pool, chat_id) == "pending"


# ── R7: invalid captures never enter the scoring queue ───────────────────────

@pytest.mark.asyncio(loop_scope="module")
async def test_r7_imbalanced_capture_rejected_before_write(pool, clean_user):
    from src.db.queries import upsert_chat

    turns = [
        {"role": "user", "text": f"Question {i}", "turn_index": i}
        for i in range(8)
    ] + [
        {"role": "assistant", "text": "Only one answer", "turn_index": 8}
    ]

    with pytest.raises(ValueError, match="imbalanced"):
        await upsert_chat(
            pool,
            user_ref=clean_user,
            conversation_id="conv_r7_bad",
            source="chatgpt_live",
            partner_model=_partner(),
            turns=turns,
            turn_count=len(turns),
        )

    count = await pool.fetchval(
        """
        SELECT COUNT(*)
        FROM raw_chats
        WHERE user_ref = $1 AND conversation_id = 'conv_r7_bad'
        """,
        clean_user,
    )
    assert count == 0
