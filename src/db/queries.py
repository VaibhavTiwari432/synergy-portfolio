"""
src/db/queries.py — all Postgres read/write operations. OWNER: Chief Engineer.

Every function takes a pool or connection as its first argument.
No business logic lives here — just raw SQL + parameter binding.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any
from uuid import UUID

import asyncpg


# ── secret hygiene ───────────────────────────────────────────────────────────

#: metadata keys stripped before any write — credentials never persist (Track 0)
_SECRET_METADATA_KEYS = ("openai_api_key", "openai_key", "api_key")


def scrub_secrets(metadata: dict | None) -> dict:
    """Return a copy of metadata with credential keys removed. The OpenAI key
    used to ride in telemetry.metadata; it must never be written to the corpus
    at rest — the self-rater now reads a server-side env secret instead."""
    if not isinstance(metadata, dict):
        return {}
    return {k: v for k, v in metadata.items() if k not in _SECRET_METADATA_KEYS}


# ── content hashing ────────────────────────────────────────────────────────────

def hash_turns(turns: list[dict]) -> str:
    """Stable SHA-256 over (role, text) pairs. Drives D-006 re-score detection:
    identical transcript → same hash → upsert leaves status untouched."""
    payload = json.dumps(
        [(t.get("role"), t.get("text", "")) for t in turns],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def capture_validation_error(turns: list[dict]) -> str | None:
    """Return a reason when a transcript is structurally unsafe to score.

    This is intentionally small and mechanical: it only checks whether the DB
    has enough user/assistant structure to represent a real ChatGPT exchange.
    Semantic quality belongs in the scorer; missing turns must stop at ingest.
    """
    if not turns:
        return "capture has no turns"

    counts = {"user": 0, "assistant": 0}
    for turn in turns:
        role = str(turn.get("role") or "").lower()
        text = str(turn.get("text") or "").strip()
        if not text:
            continue
        if role in ("human", "user"):
            counts["user"] += 1
        elif role in ("ai", "assistant"):
            counts["assistant"] += 1
        else:
            return f"unsupported turn role: {role or '<empty>'}"

    if counts["user"] == 0:
        return "capture has no user turns"
    if counts["assistant"] == 0:
        return "capture has no assistant turns"
    if abs(counts["user"] - counts["assistant"]) > 1:
        return (
            "capture turn roles are imbalanced "
            f"(user={counts['user']}, assistant={counts['assistant']})"
        )
    return None


def capture_completeness_error(
    *,
    expected_turn_count: int | None,
    captured_turn_count: int | None,
    capture_complete: bool | None,
) -> str | None:
    """Return a reason when an interception capture is PROVEN incomplete (D-015 / ADR-0007).

    The false-vs-null distinction is load-bearing:
      - capture_complete is False → the bridge ran the active-path walk and proved
        the capture incomplete (counts disagree / broken chain / unsettled stream).
        QUARANTINE: a wrong score is worse than no score.
      - capture_complete is None  → completeness UNKNOWN (the scroll-probe / dom-live
        fallback paths, which cannot prove completeness). Defer to the role-balance
        gate; do NOT quarantine, or the hardened fallback would never score.
      - capture_complete is True  → proven complete; still cross-check the counts so
        a truthy flag can't smuggle a truncated transcript past the gate (the DB
        CHECK constraint in migration 007 enforces the same invariant at rest).

    captured > expected is fine: the live-streamed tail (D-015 §6) legitimately
    extends past the intercepted history count. Only captured < expected is truncation.
    """
    if capture_complete is False:
        if expected_turn_count is not None and captured_turn_count is not None:
            return (
                f"capture proven incomplete (captured {captured_turn_count} "
                f"of {expected_turn_count} turns)"
            )
        return "capture proven incomplete"
    if (
        expected_turn_count is not None
        and captured_turn_count is not None
        and captured_turn_count < expected_turn_count
    ):
        return (
            f"capture truncated (captured {captured_turn_count} "
            f"of {expected_turn_count} turns)"
        )
    return None


def reconcile_captured_count(*, turns_len: int, client_captured: int | None) -> int:
    """Server-derive the authoritative captured turn count (ADR-0007 / D-015).

    `captured_turn_count` arrives from the client, but the completeness gate must
    not trust a client scalar — a payload could claim captured=10 while delivering
    only 3 turns and slip a truncated transcript past the gate (the DB CHECK can't
    compare a scalar to the JSONB array). So the count USED by the gate and stored
    on the row is always len(turns). If the client also sent a count and it
    disagrees with the turns it actually delivered, that is a broken/dishonest
    bridge → ValueError (surfaced as 422 at the router).

    NOTE (honest limitation): `expected_turn_count` remains a bridge claim the
    server cannot independently verify — the server receives the extracted turns,
    not the raw mapping tree. The server-derived `captured` is the half of the
    invariant the server CAN enforce; trust in `expected` is inherent to the
    extraction boundary and is mitigated by the interceptor running in the page's
    own realm (it reports the page's own payload, not a fabricated one)."""
    if client_captured is not None and client_captured != turns_len:
        raise ValueError(
            f"captured_turn_count ({client_captured}) does not match the "
            f"{turns_len} turns delivered"
        )
    return turns_len


# ── raw_chats ──────────────────────────────────────────────────────────────────

async def upsert_chat(
    pool: asyncpg.Pool,
    *,
    user_ref: str,
    conversation_id: str,
    source: str,
    partner_model: dict,
    turns: list[dict],
    turn_count: int,
    expected_turn_count: int | None = None,
    captured_turn_count: int | None = None,
    capture_complete: bool | None = None,
) -> dict[str, Any]:
    """Insert or update (idempotent on user_ref + conversation_id).

    Status is reset to 'pending' when the transcript content changed OR the
    previous attempt failed. That lets "Analyse now" retry a failed score without
    requiring the user to edit the chat, while identical successful re-ingests
    (panel reopen, telemetry-only snapshot) remain no-ops.

    Two-layer capture gate (D-015 / ADR-0007): the structural role-balance gate
    (capture_validation_error) AND the completeness gate (capture_completeness_error)
    both raise ValueError → HTTP 422 at the router → never enters 'pending'. The
    completeness columns are persisted on accepted rows; the migration-007 CHECK
    constraint backstops the invariant at rest."""
    invalid_reason = capture_validation_error(turns)
    if invalid_reason is not None:
        raise ValueError(f"invalid capture: {invalid_reason}")

    incomplete_reason = capture_completeness_error(
        expected_turn_count=expected_turn_count,
        captured_turn_count=captured_turn_count,
        capture_complete=capture_complete,
    )
    if incomplete_reason is not None:
        raise ValueError(f"invalid capture: {incomplete_reason}")

    content_hash = hash_turns(turns)
    # Resolve (or mint) the opaque subject_id for this user_ref in the same
    # statement, so every chat is keyed to a random subject token at write time
    # (Track 2). subject_id is stable per user_ref; the COALESCE on the conflict
    # path self-heals any row that somehow still carries a NULL subject_id (e.g.
    # the deploy window where migration 006 ran before this code shipped) without
    # ever overwriting an existing mapping.
    row = await pool.fetchrow(
        """
        WITH subj AS (
            INSERT INTO subjects (user_ref) VALUES ($1)
            ON CONFLICT (user_ref) DO UPDATE SET user_ref = EXCLUDED.user_ref
            RETURNING subject_id
        )
        INSERT INTO raw_chats
            (user_ref, conversation_id, source, partner_model, turns, turn_count,
             content_hash, subject_id,
             expected_turn_count, captured_turn_count, capture_complete)
        VALUES ($1, $2, $3, $4, $5, $6, $7, (SELECT subject_id FROM subj),
                $8, $9, $10)
        ON CONFLICT (user_ref, conversation_id) DO UPDATE
            SET turns        = EXCLUDED.turns,
                turn_count   = EXCLUDED.turn_count,
                source       = EXCLUDED.source,
                content_hash = EXCLUDED.content_hash,
                subject_id   = COALESCE(raw_chats.subject_id, EXCLUDED.subject_id),
                expected_turn_count = EXCLUDED.expected_turn_count,
                captured_turn_count = EXCLUDED.captured_turn_count,
                capture_complete    = EXCLUDED.capture_complete,
                status = CASE
                    WHEN raw_chats.content_hash IS DISTINCT FROM EXCLUDED.content_hash
                    THEN 'pending'              -- transcript changed → re-queue
                    WHEN raw_chats.status = 'failed'
                    THEN 'pending'              -- explicit retry after failed score
                    ELSE raw_chats.status       -- identical re-ingest → leave it
                END,
                scoring_started_at = CASE
                    WHEN raw_chats.content_hash IS DISTINCT FROM EXCLUDED.content_hash
                      OR raw_chats.status = 'failed'
                    THEN NULL
                    ELSE raw_chats.scoring_started_at
                END
        RETURNING id, status, captured_at, content_hash
        """,
        user_ref, conversation_id, source, partner_model, turns, turn_count, content_hash,
        expected_turn_count, captured_turn_count, capture_complete,
    )
    return dict(row)


async def upsert_telemetry(
    pool: asyncpg.Pool,
    *,
    chat_id: UUID,
    dwell_ms: list[int] | None,
    copy_events: list[int] | None,
    edit_detected: list[bool] | None,
    selector_health: str | None,
    capture_mode: str,
    metadata: dict,
) -> None:
    metadata = scrub_secrets(metadata)  # Track 0: never persist credentials
    await pool.execute(
        """
        INSERT INTO telemetry
            (chat_id, dwell_ms, copy_events, edit_detected,
             selector_health, capture_mode, metadata)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        ON CONFLICT (chat_id) DO UPDATE SET
            dwell_ms        = EXCLUDED.dwell_ms,
            copy_events     = EXCLUDED.copy_events,
            edit_detected   = EXCLUDED.edit_detected,
            selector_health = EXCLUDED.selector_health,
            capture_mode    = EXCLUDED.capture_mode,
            metadata        = EXCLUDED.metadata,
            imported_at     = NOW()
        """,
        chat_id, dwell_ms, copy_events, edit_detected,
        selector_health, capture_mode, metadata,
    )


async def get_telemetry_for_chat(
    pool_or_conn: asyncpg.Pool | asyncpg.Connection, chat_id: UUID
) -> asyncpg.Record | None:
    return await pool_or_conn.fetchrow(
        """
        SELECT dwell_ms, copy_events, edit_detected, selector_health, capture_mode, metadata
        FROM telemetry
        WHERE chat_id = $1
        ORDER BY imported_at DESC
        LIMIT 1
        """,
        chat_id,
    )


async def get_chats_for_user(pool: asyncpg.Pool, user_ref: str) -> list[asyncpg.Record]:
    return await pool.fetch(
        """
        SELECT id, conversation_id, source, turn_count, captured_at, status
        FROM raw_chats
        WHERE user_ref = $1
        ORDER BY captured_at DESC
        """,
        user_ref,
    )


_SCORING_LEASE = "5 minutes"


async def claim_pending_batch(
    conn: asyncpg.Connection, batch_size: int = 5
) -> list[asyncpg.Record]:
    """Atomically claim up to batch_size chats for scoring.

    Picks up genuine 'pending' rows AND reclaims 'scoring' rows whose lease has
    expired — a worker that died mid-scoring (e.g. dev restart) no longer wedges
    a chat forever. FOR UPDATE SKIP LOCKED keeps concurrent workers disjoint."""
    return await conn.fetch(
        f"""
        UPDATE raw_chats SET status = 'scoring', scoring_started_at = NOW()
        WHERE id IN (
            SELECT id FROM raw_chats
            WHERE status = 'pending'
               OR (status = 'scoring'
                   AND scoring_started_at < NOW() - INTERVAL '{_SCORING_LEASE}')
            ORDER BY captured_at ASC
            LIMIT $1
            FOR UPDATE SKIP LOCKED
        )
        RETURNING *
        """,
        batch_size,
    )


async def mark_scored(
    conn: asyncpg.Connection, chat_id: UUID, scored_hash: str | None
) -> int:
    """Finalize scoring ONLY if the transcript we scored is still current.

    Optimistic concurrency: if a new ingest changed content_hash (and reset the
    row to 'pending') while we were scoring, this matches 0 rows and the row
    stays pending → it gets re-scored against the newer transcript. Returns the
    number of rows updated (1 = finalized, 0 = superseded mid-scoring)."""
    result = await conn.execute(
        """
        UPDATE raw_chats
        SET status = 'scored', scoring_started_at = NULL
        WHERE id = $1
          AND status = 'scoring'
          AND content_hash IS NOT DISTINCT FROM $2
        """,
        chat_id, scored_hash,
    )
    # asyncpg returns a command tag like "UPDATE 1"
    return int(result.split()[-1]) if result else 0


async def set_chat_status(
    conn: asyncpg.Connection, chat_id: UUID, status: str
) -> None:
    """Set a terminal/explicit status and clear the scoring lease."""
    await conn.execute(
        "UPDATE raw_chats SET status = $1, scoring_started_at = NULL WHERE id = $2",
        status, chat_id,
    )


# ── scores ─────────────────────────────────────────────────────────────────────

async def upsert_score(
    conn: asyncpg.Connection,
    *,
    chat_id: UUID,
    prompt_version: str,
    tier: int,
    profile: dict,
    composite: dict | None,
    state_strip: list | None,
    state_validity: dict | None,
    flags: dict | None,
    reaction_signatures: dict | None,
    regime_overlay: dict | None,
    sustainability: dict | None,
    report: dict | None,
    raw_profile: dict | None = None,
    telemetry_metrics: dict | None = None,
    event_log: list | None = None,
    provenance: dict | None = None,
) -> None:
    prov = provenance or {}
    await conn.execute(
        """
        INSERT INTO scores (
            chat_id, prompt_version, tier, profile, composite,
            state_strip, state_validity, flags, reaction_signatures,
            regime_overlay, sustainability, report, raw_profile, telemetry_metrics,
            event_log, framework_version, schema_version, contract_table_version,
            code_git_sha, judge_model_id, judge_model_version
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14,
                  $15, $16, $17, $18, $19, $20, $21)
        ON CONFLICT (chat_id) DO UPDATE SET
            prompt_version         = EXCLUDED.prompt_version,
            tier                   = EXCLUDED.tier,
            profile                = EXCLUDED.profile,
            raw_profile            = EXCLUDED.raw_profile,
            composite              = EXCLUDED.composite,
            state_strip            = EXCLUDED.state_strip,
            state_validity         = EXCLUDED.state_validity,
            flags                  = EXCLUDED.flags,
            reaction_signatures    = EXCLUDED.reaction_signatures,
            regime_overlay         = EXCLUDED.regime_overlay,
            sustainability         = EXCLUDED.sustainability,
            telemetry_metrics      = EXCLUDED.telemetry_metrics,
            report                 = EXCLUDED.report,
            event_log              = EXCLUDED.event_log,
            framework_version      = EXCLUDED.framework_version,
            schema_version         = EXCLUDED.schema_version,
            contract_table_version = EXCLUDED.contract_table_version,
            code_git_sha           = EXCLUDED.code_git_sha,
            judge_model_id         = EXCLUDED.judge_model_id,
            judge_model_version    = EXCLUDED.judge_model_version,
            scored_at              = NOW()
        """,
        chat_id, prompt_version, tier, profile, composite,
        state_strip, state_validity, flags, reaction_signatures,
        regime_overlay, sustainability, report, raw_profile, telemetry_metrics,
        event_log,
        prov.get("framework_version"), prov.get("schema_version"),
        prov.get("contract_table_version"), prov.get("code_git_sha"),
        prov.get("judge_model_id"), prov.get("judge_model_version"),
    )


async def get_score_row(
    pool: asyncpg.Pool, chat_id: UUID
) -> asyncpg.Record | None:
    return await pool.fetchrow(
        "SELECT * FROM scores WHERE chat_id = $1", chat_id
    )


async def get_scored_score_row(
    pool: asyncpg.Pool, *, chat_id: UUID, user_ref: str
) -> asyncpg.Record | None:
    """Return a score only when the owning raw chat is still valid/scored."""
    return await pool.fetchrow(
        """
        SELECT s.*
        FROM scores s
        JOIN raw_chats rc ON rc.id = s.chat_id
        WHERE s.chat_id = $1
          AND rc.user_ref = $2
          AND rc.status = 'scored'
        """,
        chat_id,
        user_ref,
    )


# ── judge_runs (raw judge audit trail, Track 1) ─────────────────────────────────

async def upsert_judge_run(
    conn: asyncpg.Connection, *, chat_id: UUID, judge_run: dict
) -> None:
    """Persist the literal judge output + model identity + per-dim confidence.
    One current row per chat (re-score overwrites)."""
    await conn.execute(
        """
        INSERT INTO judge_runs (
            chat_id, raw_response, judge_model_id, judge_model_version,
            judge_family, prompt_version, per_dimension_confidence,
            judge_unavailable, judge_family_conflict
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        ON CONFLICT (chat_id) DO UPDATE SET
            raw_response             = EXCLUDED.raw_response,
            judge_model_id           = EXCLUDED.judge_model_id,
            judge_model_version      = EXCLUDED.judge_model_version,
            judge_family             = EXCLUDED.judge_family,
            prompt_version           = EXCLUDED.prompt_version,
            per_dimension_confidence = EXCLUDED.per_dimension_confidence,
            judge_unavailable        = EXCLUDED.judge_unavailable,
            judge_family_conflict    = EXCLUDED.judge_family_conflict,
            created_at               = NOW()
        """,
        chat_id,
        judge_run.get("raw_response"),
        judge_run.get("judge_model_id"),
        judge_run.get("judge_model_version"),
        judge_run.get("judge_family"),
        judge_run.get("prompt_version"),
        judge_run.get("per_dimension_confidence"),
        bool(judge_run.get("judge_unavailable", False)),
        bool(judge_run.get("judge_family_conflict", False)),
    )


# ── neuron_firings (per-neuron matrix for EFA, Track 1) ─────────────────────────

async def replace_neuron_firings(
    conn: asyncpg.Connection, *, chat_id: UUID, rows: list[dict]
) -> int:
    """Replace this chat's per-neuron firing rows (delete-then-insert so a
    re-score never leaves stale neurons). NULL value = N/A; 0.0 = observed
    0-of-N. Returns rows written."""
    await conn.execute("DELETE FROM neuron_firings WHERE chat_id = $1", chat_id)
    if not rows:
        return 0
    await conn.executemany(
        """
        INSERT INTO neuron_firings (
            chat_id, neuron_code, dimension, value,
            applicable_opportunities, n_eff, evidence_turn_indices, extractor_version
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        """,
        [
            (
                chat_id,
                r["neuron_code"],
                r.get("dimension"),
                r.get("value"),
                int(r.get("applicable_opportunities", 0)),
                float(r.get("n_eff", 0.0)),
                list(r.get("evidence_turn_indices", [])),
                r.get("extractor_version"),
            )
            for r in rows
        ],
    )
    return len(rows)


# ── turn_state (per-turn state strip + per-turn precision, Track 2) ──────────────

async def replace_turn_state(
    conn: asyncpg.Connection, *, chat_id: UUID, rows: list[dict]
) -> int:
    """Replace this chat's per-turn state rows (delete-then-insert so a re-score
    never leaves stale turns). pi_t NULL = N/A (no assessable state, #12).
    Returns rows written."""
    await conn.execute("DELETE FROM turn_state WHERE chat_id = $1", chat_id)
    if not rows:
        return 0
    await conn.executemany(
        """
        INSERT INTO turn_state (
            chat_id, turn_index, load, epistemic, metacog, tom_signal,
            a_t, confidence, pi_t, cascade_flags
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
        """,
        [
            (
                chat_id,
                int(r["turn_index"]),
                r.get("load"),
                r.get("epistemic"),
                r.get("metacog"),
                r.get("tom_signal"),
                r.get("a_t"),
                float(r.get("confidence", 0.0)),
                r.get("precision"),
                list(r.get("cascade_flags", [])),
            )
            for r in rows
        ],
    )
    return len(rows)


async def update_self_rating(
    pool: asyncpg.Pool,
    *,
    chat_id: UUID,
    self_rating_raw: dict | None,
    self_rating_prompt_version: str | None,
    status: str,
) -> None:
    await pool.execute(
        """
        UPDATE scores SET
            self_rating_raw            = $1,
            self_rating_prompt_version = $2,
            self_rating_at             = NOW(),
            self_rating_status         = $3
        WHERE chat_id = $4
        """,
        self_rating_raw, self_rating_prompt_version, status, chat_id,
    )


async def upsert_turn_model_rating(
    pool: asyncpg.Pool,
    *,
    chat_id: UUID,
    turn_index: int,
    rating_raw: dict | None,
    prompt_version: str | None,
    status: str,
) -> None:
    await pool.execute(
        """
        INSERT INTO turn_model_ratings
            (chat_id, turn_index, rating_raw, prompt_version, status)
        VALUES ($1, $2, $3, $4, $5)
        ON CONFLICT (chat_id, turn_index) DO UPDATE SET
            rating_raw     = EXCLUDED.rating_raw,
            prompt_version = EXCLUDED.prompt_version,
            status         = EXCLUDED.status,
            rated_at       = NOW()
        """,
        chat_id, turn_index, rating_raw, prompt_version, status,
    )


async def get_turn_model_ratings(
    pool: asyncpg.Pool, chat_id: UUID
) -> list[asyncpg.Record]:
    return await pool.fetch(
        """
        SELECT turn_index, rating_raw, prompt_version, status, rated_at
        FROM turn_model_ratings
        WHERE chat_id = $1
        ORDER BY turn_index ASC
        """,
        chat_id,
    )


async def get_all_scores_for_user(
    pool: asyncpg.Pool, user_ref: str
) -> list[asyncpg.Record]:
    """All scored chats for a user, ordered by capture time."""
    return await pool.fetch(
        """
        SELECT s.*, rc.captured_at, rc.conversation_id
        FROM scores s
        JOIN raw_chats rc ON rc.id = s.chat_id
        WHERE rc.user_ref = $1
          AND rc.status = 'scored'
        ORDER BY rc.captured_at ASC
        """,
        user_ref,
    )


# ── feedback ───────────────────────────────────────────────────────────────────

async def insert_feedback(
    pool: asyncpg.Pool,
    *,
    chat_id: UUID,
    user_ref: str,
    match_rating: str,
    comment: str | None,
    scores_snapshot: dict,
) -> None:
    await pool.execute(
        """
        INSERT INTO feedback (chat_id, user_ref, match_rating, comment, scores_snapshot)
        VALUES ($1, $2, $3, $4, $5)
        """,
        chat_id, user_ref, match_rating, comment, scores_snapshot,
    )


async def insert_turn_feedback(
    pool: asyncpg.Pool,
    *,
    chat_id: UUID,
    user_ref: str,
    turn_index: int,
    match_rating: str,
    dimension_scores: dict | None,
    comment: str | None,
    scores_snapshot: dict,
) -> None:
    await pool.execute(
        """
        INSERT INTO turn_feedback (
            chat_id, user_ref, turn_index, match_rating,
            dimension_scores, comment, scores_snapshot
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        """,
        chat_id, user_ref, turn_index, match_rating,
        dimension_scores, comment, scores_snapshot,
    )


async def get_turn_feedback(
    pool: asyncpg.Pool, chat_id: UUID
) -> list[asyncpg.Record]:
    return await pool.fetch(
        """
        SELECT turn_index, match_rating, dimension_scores, comment, submitted_at
        FROM turn_feedback
        WHERE chat_id = $1
        ORDER BY turn_index ASC, submitted_at ASC
        """,
        chat_id,
    )


async def feedback_given(pool: asyncpg.Pool, chat_id: UUID) -> bool:
    row = await pool.fetchrow(
        "SELECT 1 FROM feedback WHERE chat_id = $1 LIMIT 1", chat_id
    )
    return row is not None


# ── data dignity ───────────────────────────────────────────────────────────────

async def delete_user(pool: asyncpg.Pool, user_ref: str) -> int:
    """CASCADE propagates to telemetry, scores, feedback, turn_state, neuron_firings
    and judge_runs automatically. The opaque subject mapping is removed too, so no
    user_ref ↔ subject_id link survives a deletion (data dignity, #16).
    Returns number of raw_chats rows deleted."""
    result = await pool.execute(
        "DELETE FROM raw_chats WHERE user_ref = $1", user_ref
    )
    # drop the subject row as well — its only reason to exist was this user_ref
    await pool.execute("DELETE FROM subjects WHERE user_ref = $1", user_ref)
    # result is like "DELETE 3" — extract the count
    parts = result.split()
    return int(parts[1]) if len(parts) == 2 else 0


async def count_rows_for_user(pool: asyncpg.Pool, user_ref: str) -> dict[str, int]:
    """Used by cascade-deletion tests to verify all four tables are empty."""
    chats = await pool.fetchval(
        "SELECT COUNT(*) FROM raw_chats WHERE user_ref = $1", user_ref
    )
    tel = await pool.fetchval(
        """
        SELECT COUNT(*) FROM telemetry t
        JOIN raw_chats rc ON rc.id = t.chat_id
        WHERE rc.user_ref = $1
        """,
        user_ref,
    )
    sc = await pool.fetchval(
        """
        SELECT COUNT(*) FROM scores s
        JOIN raw_chats rc ON rc.id = s.chat_id
        WHERE rc.user_ref = $1
        """,
        user_ref,
    )
    fb = await pool.fetchval(
        "SELECT COUNT(*) FROM feedback WHERE user_ref = $1", user_ref
    )
    tfb = await pool.fetchval(
        "SELECT COUNT(*) FROM turn_feedback WHERE user_ref = $1", user_ref
    )
    return {
        "raw_chats": chats,
        "telemetry": tel,
        "scores": sc,
        "feedback": fb + tfb,
    }
