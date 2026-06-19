"""
Evidence-persistence gate — requires a live Postgres instance (migrations ≥ 006).

Proves the Track 1 + Track 2 recoverability fixes: the score is no longer kept
while its evidence, provenance and audit trail are discarded.

  P1  An ingested chat is keyed to an OPAQUE, random subject_id; the same
      user_ref always maps to the same subject; different user_refs differ.
  P2  subject_id is NOT derived from user_ref (not a hash/HMAC of it).
  P3  The worker's persistence calls land Track-1 evidence (neuron_firings,
      judge_runs) and Track-2 per-turn state (turn_state with pi_t) for a chat.
  P4  Deleting the user purges the subject mapping AND cascades to turn_state /
      neuron_firings / judge_runs — no orphan link or evidence survives (#16).

Run:  PHASE1_GATE=1 pytest tests/integration/test_evidence_persistence.py -v
"""

from __future__ import annotations

import hashlib
import json
import os
import uuid

import pytest
import pytest_asyncio

from contracts.schemas import CanonicalSession, Dimension, PartnerModel, Turn
from src.api.pipeline import score_session_with_artifacts
from src.trait.judge.client import JudgeClient

pytestmark = pytest.mark.skipif(
    os.environ.get("PHASE1_GATE") != "1",
    reason="Set PHASE1_GATE=1 to run evidence-persistence tests (requires Postgres)",
)

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://saf:saf_local@localhost:5432/saf_brain",
)


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def pool():
    import asyncpg

    async def _init(conn):
        await conn.set_type_codec("jsonb", encoder=json.dumps, decoder=json.loads, schema="pg_catalog")
        await conn.set_type_codec("json",  encoder=json.dumps, decoder=json.loads, schema="pg_catalog")

    p = await asyncpg.create_pool(DATABASE_URL, init=_init)
    yield p
    await p.close()


@pytest_asyncio.fixture(loop_scope="module")
async def clean_user(pool):
    from src.db.queries import delete_user

    ref = f"eviden_{uuid.uuid4().hex[:8]}"
    yield ref
    await delete_user(pool, ref)


# ── helpers ───────────────────────────────────────────────────────────────────

def _fake_judge() -> JudgeClient:
    entry = {"score": 0.5, "confidence": 0.8, "evidence_turns": [0], "tom_tag": None}
    data = {d.value: dict(entry) for d in Dimension}
    data["ES"]["score"] = None
    payload = json.dumps(data)
    return JudgeClient(generate=lambda s, u: payload, fallback=None, sleep=lambda _: None)


def _turns(n: int) -> list[dict]:
    out = []
    for i in range(n):
        # a SCAFFOLD then an accept-run, so deterministic neurons fire + surrender
        human = "walk me through it step by step, include the cost analysis" if i == 0 else "ok"
        out.append({"role": "user", "text": human, "turn_index": i * 2})
        out.append({"role": "assistant", "text": "a long enough ai reply here", "turn_index": i * 2 + 1})
    return out


def _partner() -> dict:
    return {"family": "openai", "model_id": "gpt-4o", "era_key": "2024-01"}


async def _ingest(pool, user_ref, conv_id, n):
    from src.db.queries import upsert_chat
    return await upsert_chat(
        pool, user_ref=user_ref, conversation_id=conv_id, source="chatgpt_live",
        partner_model=_partner(), turns=_turns(n), turn_count=n * 2,
    )


def _session(chat_id, turns: list[dict]) -> CanonicalSession:
    t = [
        Turn(index=r["turn_index"], role=("human" if r["role"] == "user" else "ai"), text=r["text"])
        for r in turns
    ]
    return CanonicalSession(
        session_id=str(chat_id), source="chatgpt_export",
        partner_model=PartnerModel(family="openai"), turns=t,
    )


# ── P1 / P2: opaque subject identity ──────────────────────────────────────────

@pytest.mark.asyncio(loop_scope="module")
async def test_subject_id_is_opaque_and_stable(pool, clean_user):
    a = await _ingest(pool, clean_user, "conv_a", 3)
    b = await _ingest(pool, clean_user, "conv_b", 3)

    sid_a = await pool.fetchval("SELECT subject_id FROM raw_chats WHERE id = $1", a["id"])
    sid_b = await pool.fetchval("SELECT subject_id FROM raw_chats WHERE id = $1", b["id"])
    assert sid_a is not None
    assert sid_a == sid_b, "same user_ref → same opaque subject across chats"

    mapped = await pool.fetchval(
        "SELECT subject_id FROM subjects WHERE user_ref = $1", clean_user
    )
    assert mapped == sid_a, "subjects table holds the user_ref ↔ subject_id mapping"

    # a different user_ref gets a different subject
    other = f"{clean_user}_x"
    try:
        o = await _ingest(pool, other, "conv_o", 2)
        sid_o = await pool.fetchval("SELECT subject_id FROM raw_chats WHERE id = $1", o["id"])
        assert sid_o != sid_a, "distinct user_refs must not share a subject"
    finally:
        from src.db.queries import delete_user
        await delete_user(pool, other)


@pytest.mark.asyncio(loop_scope="module")
async def test_reingest_heals_a_null_subject_id(pool, clean_user):
    # a row left unmapped by a pre-Track-2 write path (or the migrate-before-deploy
    # window) must self-heal on the next ingest — without minting a 2nd subject.
    row = await _ingest(pool, clean_user, "conv_heal", 2)
    chat_id = row["id"]
    await pool.execute("UPDATE raw_chats SET subject_id = NULL WHERE id = $1", chat_id)
    assert await pool.fetchval("SELECT subject_id FROM raw_chats WHERE id=$1", chat_id) is None

    again = await _ingest(pool, clean_user, "conv_heal", 2)
    assert again["id"] == chat_id, "must be the same row (idempotent)"
    healed = await pool.fetchval("SELECT subject_id FROM raw_chats WHERE id=$1", chat_id)
    mapped = await pool.fetchval("SELECT subject_id FROM subjects WHERE user_ref=$1", clean_user)
    assert healed is not None and healed == mapped, "re-ingest restores the mapping"
    n_subj = await pool.fetchval("SELECT COUNT(*) FROM subjects WHERE user_ref=$1", clean_user)
    assert n_subj == 1, "heal must not mint a duplicate subject"


@pytest.mark.asyncio(loop_scope="module")
async def test_subject_id_is_not_derived_from_user_ref(pool, clean_user):
    await _ingest(pool, clean_user, "conv_c", 2)
    sid = await pool.fetchval("SELECT subject_id FROM subjects WHERE user_ref = $1", clean_user)

    # it must be a real UUID, and must NOT be any obvious deterministic function
    # of user_ref (md5/sha1/sha256 namespaced as a UUID) — it is random (#16, Q1/Q2)
    s = str(sid)
    assert uuid.UUID(s)
    forbidden = {
        uuid.UUID(hashlib.md5(clean_user.encode()).hexdigest()),
        uuid.UUID(bytes=hashlib.sha256(clean_user.encode()).digest()[:16]),
        uuid.uuid5(uuid.NAMESPACE_URL, clean_user),
        uuid.uuid5(uuid.NAMESPACE_DNS, clean_user),
    }
    assert uuid.UUID(s) not in forbidden, "subject_id must be random, never derived from PII"


# ── P3: Track-1 + Track-2 artifacts persist ───────────────────────────────────

@pytest.mark.asyncio(loop_scope="module")
async def test_artifacts_persist_for_a_scored_chat(pool, clean_user):
    from src.db.queries import (
        replace_neuron_firings,
        replace_turn_state,
        upsert_csl,
        upsert_judge_run,
        upsert_question_quality,
        upsert_reliance,
        upsert_score,
    )

    turns = _turns(4)
    row = await _ingest(pool, clean_user, "conv_score", 4)
    chat_id = row["id"]

    run = score_session_with_artifacts(_session(chat_id, turns), judge=_fake_judge())
    full = json.loads(run.response.model_dump_json(by_alias=True))

    async with pool.acquire() as conn:
        await upsert_score(
            conn, chat_id=chat_id, prompt_version="test", tier=full["tier"],
            profile=full["profile"], composite=full.get("composite"),
            state_strip=full.get("state_strip"), state_validity=full.get("state_validity"),
            flags=full.get("flags"), reaction_signatures=full.get("reaction_signatures"),
            regime_overlay=full.get("regime_overlay"), sustainability=full.get("sustainability"),
            report=full.get("report"), raw_profile=None, telemetry_metrics=run.telemetry_metrics,
            event_log=run.event_log, provenance=run.provenance,
        )
        await upsert_judge_run(conn, chat_id=chat_id, judge_run=run.judge_run)
        n_firings = await replace_neuron_firings(conn, chat_id=chat_id, rows=run.neuron_firings)
        n_turns = await replace_turn_state(conn, chat_id=chat_id, rows=run.turn_state)
        # migration 011 — per-chat artifact blobs the pipeline builds but used to drop
        await upsert_csl(conn, chat_id=chat_id, csl=run.csl)
        await upsert_question_quality(conn, chat_id=chat_id, question_quality=run.question_quality)
        await upsert_reliance(conn, chat_id=chat_id, reliance=run.reliance)

    assert n_firings > 0 and n_turns > 0

    # provenance columns are queryable on scores (not buried in a blob)
    prov = await pool.fetchrow(
        "SELECT framework_version, judge_model_id, event_log FROM scores WHERE chat_id = $1",
        chat_id,
    )
    assert prov["framework_version"] and prov["judge_model_id"]
    assert prov["event_log"] is not None

    # judge audit trail retained
    jr = await pool.fetchrow("SELECT raw_response FROM judge_runs WHERE chat_id = $1", chat_id)
    assert jr["raw_response"], "literal judge output must be persisted"

    # migration-011 artifact blobs landed on the scores row (descriptive/evidence
    # only — never an ARI score). They are non-null dicts, never silently dropped.
    art = await pool.fetchrow(
        "SELECT csl, question_quality, reliance FROM scores WHERE chat_id = $1", chat_id
    )
    for col in ("csl", "question_quality", "reliance"):
        assert art[col] is not None, f"{col} artifact must persist, not be discarded"

    # per-turn precision landed; NULL = N/A, never fabricated
    ts = await pool.fetch(
        "SELECT turn_index, pi_t, cascade_flags FROM turn_state WHERE chat_id = $1 ORDER BY turn_index",
        chat_id,
    )
    assert len(ts) == 4
    assert all(r["pi_t"] is None or 0.0 < r["pi_t"] <= 1.0 for r in ts)


# ── P3b: migration-011 artifact blobs round-trip with no data loss ─────────────
# JSONB normalises key order + whitespace, so raw-string byte identity is NOT a
# property it can give. The provable, meaningful round-trip is: the read-back dict
# equals the written dict, and a CANONICAL (sort_keys) re-serialisation is
# byte-identical — i.e. nothing was dropped, reordered into loss, or mutated.

def _canon(obj) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


@pytest.mark.asyncio(loop_scope="module")
async def test_artifact_blobs_round_trip_cleanly(pool, clean_user):
    from src.db.queries import (
        get_score_row,
        upsert_csl,
        upsert_question_quality,
        upsert_reliance,
        upsert_score,
    )

    turns = _turns(4)
    row = await _ingest(pool, clean_user, "conv_roundtrip", 4)
    chat_id = row["id"]

    # the scores row must exist first — the upserts UPDATE it (as the worker does)
    run = score_session_with_artifacts(_session(chat_id, turns), judge=_fake_judge())
    full = json.loads(run.response.model_dump_json(by_alias=True))
    async with pool.acquire() as conn:
        await upsert_score(
            conn, chat_id=chat_id, prompt_version="test", tier=full["tier"],
            profile=full["profile"], composite=full.get("composite"),
            state_strip=full.get("state_strip"), state_validity=full.get("state_validity"),
            flags=full.get("flags"), reaction_signatures=full.get("reaction_signatures"),
            regime_overlay=full.get("regime_overlay"), sustainability=full.get("sustainability"),
            report=full.get("report"), raw_profile=None, telemetry_metrics=run.telemetry_metrics,
            event_log=run.event_log, provenance=run.provenance,
        )

    # Case 1 — round-trip the REAL pipeline artifacts the worker would persist.
    async with pool.acquire() as conn:
        await upsert_csl(conn, chat_id=chat_id, csl=run.csl)
        await upsert_question_quality(conn, chat_id=chat_id, question_quality=run.question_quality)
        await upsert_reliance(conn, chat_id=chat_id, reliance=run.reliance)

    back = await get_score_row(pool, chat_id)
    for col, original in (
        ("csl", run.csl),
        ("question_quality", run.question_quality),
        ("reliance", run.reliance),
    ):
        assert back[col] == original, f"{col} dict must round-trip equal"
        assert _canon(back[col]) == _canon(original), f"{col} must round-trip byte-identical (canonical)"

    # Case 2 — an adversarial blob: nested dicts/lists, unicode, floats, bools,
    # null, AND keys written in deliberately non-sorted order. JSONB will reorder
    # the stored keys; the canonical comparison proves nothing was lost.
    adversarial = {
        "zeta": {"nested": [1, 2, {"inner": "café ☕ — naïve"}], "f": 0.123456789},
        "alpha": [True, False, None, "x"],
        "mid": "Pattern detected — not proven without retention probe.",
        "num": -42,
    }
    async with pool.acquire() as conn:
        await upsert_csl(conn, chat_id=chat_id, csl=adversarial)
    back2 = await get_score_row(pool, chat_id)
    assert back2["csl"] == adversarial, "adversarial blob must deep-equal on read-back"
    assert _canon(back2["csl"]) == _canon(adversarial), "adversarial blob: no data lost via JSONB"

    # Case 3 — the CSL failure sentinel and the None→{} coalescing contract.
    async with pool.acquire() as conn:
        await upsert_csl(conn, chat_id=chat_id, csl={"status": "error"})
        await upsert_reliance(conn, chat_id=chat_id, reliance=None)
    back3 = await get_score_row(pool, chat_id)
    assert back3["csl"] == {"status": "error"}, "CSL error sentinel must persist verbatim"
    assert back3["reliance"] == {}, "None artifact coalesces to {} — never NULL/dropped"


# ── P4: deletion purges subject + all evidence ────────────────────────────────

@pytest.mark.asyncio(loop_scope="module")
async def test_delete_user_purges_subject_and_evidence(pool):
    from src.db.queries import (
        delete_user,
        replace_neuron_firings,
        replace_turn_state,
        upsert_judge_run,
    )

    ref = f"eviden_del_{uuid.uuid4().hex[:8]}"
    turns = _turns(3)
    row = await _ingest(pool, ref, "conv_del", 3)
    chat_id = row["id"]
    run = score_session_with_artifacts(_session(chat_id, turns), judge=_fake_judge())

    async with pool.acquire() as conn:
        await upsert_judge_run(conn, chat_id=chat_id, judge_run=run.judge_run)
        await replace_neuron_firings(conn, chat_id=chat_id, rows=run.neuron_firings)
        await replace_turn_state(conn, chat_id=chat_id, rows=run.turn_state)

    await delete_user(pool, ref)

    assert await pool.fetchval("SELECT COUNT(*) FROM subjects WHERE user_ref = $1", ref) == 0
    for table in ("turn_state", "neuron_firings", "judge_runs"):
        remaining = await pool.fetchval(
            f"SELECT COUNT(*) FROM {table} WHERE chat_id = $1", chat_id
        )
        assert remaining == 0, f"{table} must cascade-delete with the chat"
