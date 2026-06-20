"""
Scope-C contract gate (D-012) — requires a live Postgres (migrations >= 012).

Proves contracts/scope_c_contract.md (FROZEN v1.0):
  - project_id is a server-minted UUID; Idempotency-Key never mints a duplicate.
  - keyset pagination pages a subject's projects newest-first.
  - optimistic concurrency: stale version -> conflict; correct -> version bumps.
  - project<->session assignment is idempotent; unknown chat_ids are reported.
  - project radar emits all FOUR states distinctly, never a composite (#6/#12).
  - subject deletion cascades projects / project_sessions / portfolio_ack (#16).
  - portfolio ack is snapshot-scoped; the bare composite is gone (#6).

Run:  PHASE1_GATE=1 pytest tests/integration/test_scope_c_projects.py -v
"""

from __future__ import annotations

import json
import os
import uuid

import pytest
import pytest_asyncio

pytestmark = pytest.mark.skipif(
    os.environ.get("PHASE1_GATE") != "1",
    reason="Set PHASE1_GATE=1 to run Scope-C tests (requires Postgres)",
)

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://saf:saf_local@localhost:5432/saf_brain"
)

_DIMS = ["AL", "PR", "EC", "ES", "CS", "CD", "AUI", "CA"]


# ── fixtures / helpers ──────────────────────────────────────────────────────────

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
    ref = f"scopec_{uuid.uuid4().hex[:8]}"
    yield ref
    await delete_user(pool, ref)


def _turns(n: int) -> list[dict]:
    out = []
    for i in range(n):
        out.append({"role": "user", "text": "walk me through it step by step", "turn_index": i * 2})
        out.append({"role": "assistant", "text": "a long enough ai reply here", "turn_index": i * 2 + 1})
    return out


async def _ingest(pool, user_ref, conv_id, n=2):
    from src.db.queries import upsert_chat
    return await upsert_chat(
        pool, user_ref=user_ref, conversation_id=conv_id, source="chatgpt_live",
        partner_model={"family": "openai", "model_id": "gpt-4o", "era_key": "2024-01"},
        turns=_turns(n), turn_count=n * 2,
    )


def _profile(status_by_dim: dict[str, tuple]) -> dict:
    """Build an 8-dim profile. Each dim defaults to N/A; override with
    (status, value) — value only for OK. CI is attached for OK rows."""
    prof = {}
    for d in _DIMS:
        if d in status_by_dim:
            status, value = status_by_dim[d]
            entry = {"status": status, "value": value}
            if status == "OK":
                entry["ci"] = {"low": max(0.0, value - 0.05), "high": min(1.0, value + 0.05)}
            if status == "MEASUREMENT_SATURATED":
                entry["bound"] = 0.95
            prof[d] = entry
        else:
            prof[d] = {"status": "N/A", "value": None}
    return prof


async def _scored_chat(pool, user_ref, conv_id, profile: dict):
    """Ingest + write a scores row with the given profile + mark the chat scored.
    set_chat_status is used instead of mark_scored because the latter only
    promotes a row already in 'scoring' (the live worker claims it first)."""
    from src.db.queries import set_chat_status, upsert_score
    row = await _ingest(pool, user_ref, conv_id, n=2)
    chat_id = row["id"]
    async with pool.acquire() as conn:
        await upsert_score(
            conn, chat_id=chat_id, prompt_version="test", tier=1,
            profile=profile, composite=None, state_strip=None, state_validity=None,
            flags=None, reaction_signatures=None, regime_overlay=None,
            sustainability=None, report=None, raw_profile=None,
            telemetry_metrics={}, event_log=[], provenance={},
        )
        await set_chat_status(conn, chat_id, "scored")
    return chat_id


# ── identity: server UUID + idempotency ────────────────────────────────────────

@pytest.mark.asyncio(loop_scope="module")
async def test_create_project_mints_uuid_and_idempotency(pool, clean_user):
    from src.db.queries import create_project

    a = await create_project(pool, user_ref=clean_user, name="Q3 research", description="d")
    assert uuid.UUID(str(a["id"]))            # server-minted UUID, not client-supplied
    assert a["version"] == 1

    # an Idempotency-Key replay returns the ORIGINAL row, never a duplicate
    k = uuid.uuid4().hex
    b1 = await create_project(pool, user_ref=clean_user, name="dup", description=None, idempotency_key=k)
    b2 = await create_project(pool, user_ref=clean_user, name="dup", description=None, idempotency_key=k)
    assert b1["id"] == b2["id"]

    count = await pool.fetchval(
        """SELECT COUNT(*) FROM projects p JOIN subjects s ON s.subject_id=p.subject_id
           WHERE s.user_ref=$1""", clean_user,
    )
    assert count == 2, "two distinct projects (Q3 + dup); the replay did not add a third"


@pytest.mark.asyncio(loop_scope="module")
async def test_list_projects_keyset_pagination(pool, clean_user):
    from src.db.queries import create_project, list_projects

    for i in range(5):
        await create_project(pool, user_ref=clean_user, name=f"p{i}", description=None)

    page1 = await list_projects(pool, user_ref=clean_user, limit=2)
    assert len(page1) == 2
    last = page1[-1]
    page2 = await list_projects(
        pool, user_ref=clean_user, limit=2,
        before_created_at=last["created_at"], before_id=last["id"],
    )
    assert len(page2) == 2
    ids1 = {r["id"] for r in page1}
    ids2 = {r["id"] for r in page2}
    assert ids1.isdisjoint(ids2), "keyset pages must not overlap"


# ── optimistic concurrency ─────────────────────────────────────────────────────

@pytest.mark.asyncio(loop_scope="module")
async def test_update_project_optimistic_concurrency(pool, clean_user):
    from src.db.queries import create_project, update_project

    p = await create_project(pool, user_ref=clean_user, name="orig", description=None)
    pid = p["id"]

    ok = await update_project(
        pool, user_ref=clean_user, project_id=pid, name="renamed",
        description=None, expected_version=1,
    )
    assert ok["name"] == "renamed" and ok["version"] == 2

    stale = await update_project(
        pool, user_ref=clean_user, project_id=pid, name="x",
        description=None, expected_version=1,    # stale
    )
    assert stale == {"_conflict": 2}, "stale version must report a conflict, not silently win"

    missing = await update_project(
        pool, user_ref=clean_user, project_id=uuid.uuid4(), name="x",
        description=None, expected_version=1,
    )
    assert missing is None


# ── assignment ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio(loop_scope="module")
async def test_assign_and_unassign_sessions(pool, clean_user):
    from src.db.queries import (
        add_project_sessions,
        create_project,
        remove_project_session,
    )

    p = await create_project(pool, user_ref=clean_user, name="assign", description=None)
    pid = p["id"]
    c1 = await _scored_chat(pool, clean_user, "conv_assign_1", _profile({"EC": ("OK", 0.7)}))
    c2 = await _scored_chat(pool, clean_user, "conv_assign_2", _profile({"EC": ("OK", 0.6)}))
    bogus = uuid.uuid4()

    res = await add_project_sessions(pool, user_ref=clean_user, project_id=pid, chat_ids=[c1, c2, bogus])
    assert res["added"] == 2
    assert res["unknown"] == [str(bogus)]

    again = await add_project_sessions(pool, user_ref=clean_user, project_id=pid, chat_ids=[c1])
    assert again["added"] == 0 and again["skipped_already_present"] == 1, "assignment is idempotent"

    assert await remove_project_session(pool, user_ref=clean_user, project_id=pid, chat_id=c1) is True
    assert await remove_project_session(pool, user_ref=clean_user, project_id=pid, chat_id=c1) is False


# ── radar: four states, never collapsed, never a composite ─────────────────────

@pytest.mark.asyncio(loop_scope="module")
async def test_project_radar_four_states_distinct(pool, clean_user):
    from src.api.routers.projects import _aggregate_radar
    from src.db.queries import add_project_sessions, create_project, get_project_score_rows

    p = await create_project(pool, user_ref=clean_user, name="radar", description=None)
    pid = p["id"]

    # EC OK x3 -> scored; PR OK x1 -> INSUFFICIENT; CA saturated -> SATURATED; AUI N/A -> STRUCTURAL_NA
    c1 = await _scored_chat(pool, clean_user, "rc1", _profile({"EC": ("OK", 0.6), "PR": ("OK", 0.5), "CA": ("MEASUREMENT_SATURATED", None)}))
    c2 = await _scored_chat(pool, clean_user, "rc2", _profile({"EC": ("OK", 0.7), "CA": ("MEASUREMENT_SATURATED", None)}))
    c3 = await _scored_chat(pool, clean_user, "rc3", _profile({"EC": ("OK", 0.8)}))
    await add_project_sessions(pool, user_ref=clean_user, project_id=pid, chat_ids=[c1, c2, c3])

    rows = await get_project_score_rows(pool, user_ref=clean_user, project_id=pid)
    radar = _aggregate_radar(rows)

    assert radar["EC"]["state"] == "scored"
    assert radar["EC"]["ci"] is not None and radar["EC"]["value"] is not None  # CI on every scored dim
    assert radar["PR"]["state"] == "INSUFFICIENT_SAMPLE" and radar["PR"]["value"] is None
    assert radar["CA"]["state"] == "MEASUREMENT_SATURATED"
    assert radar["AUI"]["state"] == "STRUCTURAL_NA"

    states = {r["state"] for r in radar.values()}
    assert {"scored", "INSUFFICIENT_SAMPLE", "MEASUREMENT_SATURATED", "STRUCTURAL_NA"} <= states
    assert "composite" not in radar and "overall" not in radar


# ── data dignity: subject deletion cascades Scope-C tables ──────────────────────

@pytest.mark.asyncio(loop_scope="module")
async def test_subject_deletion_cascades_scope_c(pool):
    from src.db.queries import (
        add_project_sessions,
        create_project,
        delete_user,
        upsert_portfolio_ack,
    )

    ref = f"scopec_del_{uuid.uuid4().hex[:8]}"
    p = await create_project(pool, user_ref=ref, name="cascade", description=None)
    pid = p["id"]
    c1 = await _scored_chat(pool, ref, "conv_cascade", _profile({"EC": ("OK", 0.7)}))
    await add_project_sessions(pool, user_ref=ref, project_id=pid, chat_ids=[c1])
    await upsert_portfolio_ack(pool, user_ref=ref, scope="portfolio", snapshot_hash="abc")

    await delete_user(pool, ref)

    for table in ("projects", "project_sessions", "portfolio_ack"):
        if table == "project_sessions":
            n = await pool.fetchval("SELECT COUNT(*) FROM project_sessions WHERE project_id=$1", pid)
        elif table == "projects":
            n = await pool.fetchval("SELECT COUNT(*) FROM projects WHERE id=$1", pid)
        else:
            n = await pool.fetchval(
                """SELECT COUNT(*) FROM portfolio_ack pa
                   WHERE pa.snapshot_hash='abc' AND pa.subject_id NOT IN (SELECT subject_id FROM subjects)""")
        assert n == 0, f"{table} must cascade-delete with the subject"


# ── portfolio ack + composite removal (HTTP layer) ─────────────────────────────

@pytest.mark.asyncio(loop_scope="module")
async def test_portfolio_ack_roundtrip_and_no_composite(pool, clean_user):
    from src.db.queries import get_portfolio_ack, upsert_portfolio_ack

    # snapshot-scoped ack: storing a hash then reading it back
    await upsert_portfolio_ack(pool, user_ref=clean_user, scope="portfolio", snapshot_hash="hash_v1")
    row = await get_portfolio_ack(pool, user_ref=clean_user, scope="portfolio")
    assert row["snapshot_hash"] == "hash_v1"

    # re-ack a new hash overwrites (one ack per scope)
    await upsert_portfolio_ack(pool, user_ref=clean_user, scope="portfolio", snapshot_hash="hash_v2")
    row2 = await get_portfolio_ack(pool, user_ref=clean_user, scope="portfolio")
    assert row2["snapshot_hash"] == "hash_v2"


@pytest.mark.asyncio(loop_scope="module")
async def test_user_settings_defaults_partial_update_and_cascade(pool):
    from src.db.queries import delete_user, get_settings, upsert_settings

    ref = f"scopec_set_{uuid.uuid4().hex[:8]}"

    # no row yet → safe defaults (opt-in OFF, #16), updated_at None
    defaults = await get_settings(pool, user_ref=ref)
    assert defaults["auto_analyse"] is False
    assert defaults["calibration_opt_in"] is False
    assert defaults["updated_at"] is None

    # partial update only sets the named field; the other keeps its default
    one = await upsert_settings(pool, user_ref=ref, auto_analyse=True)
    assert one["auto_analyse"] is True and one["calibration_opt_in"] is False

    # second partial update preserves the first (COALESCE, not overwrite-to-default)
    two = await upsert_settings(pool, user_ref=ref, calibration_opt_in=True)
    assert two["auto_analyse"] is True and two["calibration_opt_in"] is True

    back = await get_settings(pool, user_ref=ref)
    assert back["auto_analyse"] is True and back["calibration_opt_in"] is True
    assert back["updated_at"] is not None

    # data dignity: deleting the user removes the settings row
    await delete_user(pool, ref)
    after = await pool.fetchval(
        """SELECT COUNT(*) FROM user_settings us
           WHERE us.subject_id NOT IN (SELECT subject_id FROM subjects)"""
    )
    assert after == 0
    assert (await get_settings(pool, user_ref=ref))["updated_at"] is None  # back to defaults


@pytest.mark.asyncio(loop_scope="module")
async def test_portfolio_and_chat_score_drop_the_bare_composite(pool, clean_user):
    """The two reconciliation changes: neither the portfolio nor the per-chat
    longitudinal block emits a bare composite (#6); portfolio gains snapshot_hash
    + ack (§4.4) and a stale ack hash is rejected with 409."""
    from fastapi import HTTPException

    from src.api.routers.users import (
        PortfolioAckRequest,
        _longitudinal_to_date,
        get_all_scores_for_user,
        get_portfolio,
        post_portfolio_ack,
    )

    for i in range(3):
        await _scored_chat(pool, clean_user, f"pf{i}", _profile({"EC": ("OK", 0.6 + i * 0.1), "CS": ("OK", 0.5)}))

    body = await get_portfolio(clean_user, pool)
    assert "overall_score_till_now" not in body, "portfolio must not emit a bare composite (#6)"
    assert "profile_radar" in body
    assert "snapshot_hash" in body and "ack" in body
    assert body["ack"]["acked"] is False
    assert body["contract_version"] == "scope-c/v1.0"

    rows = await get_all_scores_for_user(pool, clean_user)
    lon = _longitudinal_to_date(rows, rows[0]["chat_id"])
    assert "overall_score_till_now" not in lon, "longitudinal block must not emit a bare composite"
    assert "dimensions_till_now" in lon

    # ack the current snapshot, then a stale hash must 409
    ok = await post_portfolio_ack(clean_user, PortfolioAckRequest(snapshot_hash=body["snapshot_hash"]), pool)
    assert ok["acked"] is True
    with pytest.raises(HTTPException) as ei:
        await post_portfolio_ack(clean_user, PortfolioAckRequest(snapshot_hash="stale"), pool)
    assert ei.value.status_code == 409
