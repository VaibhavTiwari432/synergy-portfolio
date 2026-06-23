"""
src/db/queries.py — all Postgres read/write operations. OWNER: Chief Engineer.

Every function takes a pool or connection as its first argument.
No business logic lives here — just raw SQL + parameter binding.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from typing import Any
from uuid import UUID

import asyncpg


# ── secret hygiene ───────────────────────────────────────────────────────────

#: metadata keys stripped before any write — credentials never persist (Track 0)
_SECRET_METADATA_KEYS = ("openai_api_key", "openai_key", "api_key")

#: value-shape guard (D-019): catches a credential that arrives under an
#: UNEXPECTED key name, which the name-only strip above would miss. Matches
#: well-known provider credential prefixes ONLY — distinctive enough that
#: content hashes (hex), UUIDs, and conversation ids never false-positive.
_SECRET_VALUE_RE = re.compile(
    r"""(?x)^(?:
        sk-[A-Za-z0-9_\-]{12,}        # OpenAI / OpenRouter (sk-, sk-or-, sk-proj-)
      | AKIA[0-9A-Z]{16}              # AWS access key id
      | AIza[0-9A-Za-z_\-]{20,}       # Google API key
      | gh[posru]_[0-9A-Za-z]{20,}    # GitHub tokens (ghp_/gho_/ghs_/ghr_/ghu_)
      | xox[baprs]-[0-9A-Za-z\-]{10,} # Slack tokens
    )""",
)


def _is_secret_shaped(value: Any) -> bool:
    """True iff a string value looks like a known provider credential."""
    return isinstance(value, str) and _SECRET_VALUE_RE.match(value.strip()) is not None


def scrub_secrets(metadata: dict | None) -> dict:
    """Return a copy of metadata with credentials removed. The OpenAI key used to
    ride in telemetry.metadata; it must never be written to the corpus at rest —
    the self-rater now reads a server-side env secret instead.

    Two layers (D-019): strip the known credential KEY NAMES, and drop any VALUE
    that matches a provider key shape regardless of its key — so a secret renamed
    to an unexpected field can no longer slip past the name list."""
    if not isinstance(metadata, dict):
        return {}
    return {
        k: v
        for k, v in metadata.items()
        if k not in _SECRET_METADATA_KEYS and not _is_secret_shaped(v)
    }


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


def canonicalize_turn_indexes(turns: list[dict]) -> list[dict]:
    """Return turns with dense, list-order turn_index values.

    Extension DOM strategies can change, and a broken bridge may send duplicate
    or sparse indexes. The payload list order is the source of truth at ingest;
    database uniqueness and downstream evidence joins require dense indexes.
    """
    return [{**turn, "turn_index": idx} for idx, turn in enumerate(turns)]


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


def _intent_tag(text: str, role: str) -> str:
    value = str(text or "").strip().lower()
    if role == "assistant":
        return "response"
    if not value:
        return "empty"
    if "?" in value:
        return "question"
    if any(marker in value for marker in ("fix", "debug", "error", "wrong", "not working")):
        return "debug"
    if any(marker in value for marker in ("compare", "evaluate", "review", "critique", "analyze", "analyse")):
        return "evaluate"
    if any(marker in value for marker in ("create", "build", "write", "generate", "make")):
        return "create"
    if any(marker in value for marker in ("change", "update", "refine", "improve", "modify")):
        return "refine"
    if value in {"ok", "okay", "yes", "no", "thanks", "thank you"}:
        return "ack"
    return "other"


def derive_turn_event_log(turns: list[dict]) -> list[dict]:
    timestamps = [
        int(t["timestamp_ms"])
        for t in turns
        if isinstance(t.get("timestamp_ms"), int)
    ]
    base_ts = min(timestamps) if timestamps else None
    rows: list[dict] = []
    for idx, turn in enumerate(turns):
        role = str(turn.get("role") or "").lower()
        text = str(turn.get("text") or "")
        timestamp = turn.get("timestamp_ms")
        offset = (
            int(timestamp) - base_ts
            if isinstance(timestamp, int) and base_ts is not None
            else None
        )
        rows.append({
            "turn_index": idx,
            "role": role,
            "char_count": len(text),
            "timestamp_offset_ms": offset,
            "intent_tag": _intent_tag(text, role),
        })
    return rows


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
    is_minor: bool = False,
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
             expected_turn_count, captured_turn_count, capture_complete, is_minor)
        VALUES ($1, $2, $3, $4, $5, $6, $7, (SELECT subject_id FROM subj),
                $8, $9, $10, $11)
        ON CONFLICT (user_ref, conversation_id) DO UPDATE
            SET turns        = CASE
                    WHEN EXCLUDED.turn_count >= raw_chats.turn_count
                    THEN EXCLUDED.turns
                    ELSE raw_chats.turns
                END,
                turn_count   = GREATEST(raw_chats.turn_count, EXCLUDED.turn_count),
                source       = CASE
                    WHEN EXCLUDED.turn_count >= raw_chats.turn_count
                    THEN EXCLUDED.source
                    ELSE raw_chats.source
                END,
                content_hash = CASE
                    WHEN EXCLUDED.turn_count >= raw_chats.turn_count
                    THEN EXCLUDED.content_hash
                    ELSE raw_chats.content_hash
                END,
                subject_id   = COALESCE(raw_chats.subject_id, EXCLUDED.subject_id),
                expected_turn_count = CASE
                    WHEN EXCLUDED.turn_count >= raw_chats.turn_count
                    THEN EXCLUDED.expected_turn_count
                    ELSE raw_chats.expected_turn_count
                END,
                captured_turn_count = CASE
                    WHEN EXCLUDED.turn_count >= raw_chats.turn_count
                    THEN EXCLUDED.captured_turn_count
                    ELSE raw_chats.captured_turn_count
                END,
                capture_complete    = CASE
                    WHEN EXCLUDED.turn_count >= raw_chats.turn_count
                    THEN EXCLUDED.capture_complete
                    ELSE raw_chats.capture_complete
                END,
                -- is_minor is a SAFETY flag (#15): sticky-true. Once a chat is
                -- flagged minor it never silently reverts on a later ingest that
                -- omits/clears the flag — a non-minor → minor transition is allowed,
                -- the reverse is not.
                is_minor = raw_chats.is_minor OR EXCLUDED.is_minor,
                status = CASE
                    WHEN EXCLUDED.turn_count < raw_chats.turn_count
                    THEN raw_chats.status
                    WHEN raw_chats.content_hash IS DISTINCT FROM EXCLUDED.content_hash
                    THEN 'pending'              -- transcript changed → re-queue
                    WHEN raw_chats.status = 'failed'
                    THEN 'pending'              -- explicit retry after failed score
                    ELSE raw_chats.status       -- identical re-ingest → leave it
                END,
                scoring_started_at = CASE
                    WHEN EXCLUDED.turn_count < raw_chats.turn_count
                    THEN raw_chats.scoring_started_at
                    WHEN raw_chats.content_hash IS DISTINCT FROM EXCLUDED.content_hash
                      OR raw_chats.status = 'failed'
                    THEN NULL
                    ELSE raw_chats.scoring_started_at
                END
        RETURNING id, status, captured_at, content_hash, turn_count
        """,
        user_ref, conversation_id, source, partner_model, turns, turn_count, content_hash,
        expected_turn_count, captured_turn_count, capture_complete, is_minor,
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


async def replace_capture_artifacts(
    pool: asyncpg.Pool,
    *,
    chat_id: UUID,
    conversation_id: str,
    turns: list[dict],
    raw_retention_flag: str = "retain",
) -> None:
    event_rows = derive_turn_event_log(turns)
    raw_rows = [
        (
            chat_id,
            conversation_id,
            idx,
            str(turn.get("role") or "").lower(),
            str(turn.get("text") or ""),
            raw_retention_flag,
        )
        for idx, turn in enumerate(turns)
    ]

    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute("DELETE FROM event_log WHERE chat_id = $1", chat_id)
            await conn.execute("DELETE FROM raw_transcripts WHERE chat_id = $1", chat_id)
            if event_rows:
                await conn.executemany(
                    """
                    INSERT INTO event_log
                        (chat_id, conversation_id, turn_index, role, char_count,
                         timestamp_offset_ms, intent_tag)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    """,
                    [
                        (
                            chat_id,
                            conversation_id,
                            row["turn_index"],
                            row["role"],
                            row["char_count"],
                            row["timestamp_offset_ms"],
                            row["intent_tag"],
                        )
                        for row in event_rows
                    ],
                )
            if raw_rows:
                await conn.executemany(
                    """
                    INSERT INTO raw_transcripts
                        (chat_id, conversation_id, turn_index, role, text, retention_flag)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    """,
                    raw_rows,
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


async def reset_expired_scoring_leases(
    conn: asyncpg.Connection, *, lease_timeout_seconds: int
) -> list[asyncpg.Record]:
    """Reset chats stuck in 'scoring' past the lease back to 'pending'.

    A worker that claimed a chat (status → 'scoring') but never finalized it — it
    crashed or hung mid-score — would otherwise wedge that chat forever. This
    watchdog query resets every such row whose lease has exceeded
    `lease_timeout_seconds` and records the reset in scoring_lease_events with
    reason 'lease_timeout'.

    The reset AND its audit row are written in a SINGLE statement (one CTE chain),
    so the state change can never happen without a durable, observable record of it
    — and if the audit insert fails the whole statement rolls back, leaving the row
    'scoring' for the next tick rather than silently resetting it. `FOR UPDATE SKIP
    LOCKED` keeps the watchdog disjoint from concurrent workers / a second watchdog.

    Returns one row per reset ({id, conversation_id, lease_age_seconds}) so the
    caller can log each one — no silent failures.
    """
    return await conn.fetch(
        """
        WITH expired AS (
            SELECT id, conversation_id, scoring_started_at,
                   EXTRACT(EPOCH FROM (NOW() - scoring_started_at))::bigint
                       AS lease_age_seconds
            FROM raw_chats
            WHERE status = 'scoring'
              AND scoring_started_at IS NOT NULL
              AND scoring_started_at < NOW() - make_interval(secs => $1::double precision)
            FOR UPDATE SKIP LOCKED
        ),
        reset AS (
            UPDATE raw_chats
            SET status = 'pending', scoring_started_at = NULL
            WHERE id IN (SELECT id FROM expired)
        ),
        logged AS (
            INSERT INTO scoring_lease_events
                (chat_id, conversation_id, reason, previous_status,
                 scoring_started_at, lease_age_seconds)
            SELECT id, conversation_id, 'lease_timeout', 'scoring',
                   scoring_started_at, lease_age_seconds
            FROM expired
        )
        SELECT id, conversation_id, lease_age_seconds FROM expired
        """,
        int(lease_timeout_seconds),
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
    session_intent: str | None = None,
    session_intent_confidence: float | None = None,
) -> None:
    prov = provenance or {}
    await conn.execute(
        """
        INSERT INTO scores (
            chat_id, prompt_version, tier, profile, composite,
            state_strip, state_validity, flags, reaction_signatures,
            regime_overlay, sustainability, report, raw_profile, telemetry_metrics,
            event_log, framework_version, schema_version, contract_table_version,
            code_git_sha, judge_model_id, judge_model_version,
            session_intent, session_intent_confidence
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14,
                  $15, $16, $17, $18, $19, $20, $21, $22, $23)
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
            session_intent            = EXCLUDED.session_intent,
            session_intent_confidence = EXCLUDED.session_intent_confidence,
            scored_at              = NOW()
        """,
        chat_id, prompt_version, tier, profile, composite,
        state_strip, state_validity, flags, reaction_signatures,
        regime_overlay, sustainability, report, raw_profile, telemetry_metrics,
        event_log,
        prov.get("framework_version"), prov.get("schema_version"),
        prov.get("contract_table_version"), prov.get("code_git_sha"),
        prov.get("judge_model_id"), prov.get("judge_model_version"),
        session_intent, session_intent_confidence,
    )


async def insert_drift_run(
    conn: asyncpg.Connection,
    *,
    judge_model_id: str,
    prompt_version: str,
    anchor_set: list[str],
    mae_overall: float | None,
    mae_per_dimension: dict | None,
    baseline_mae: float | None,
    drift_detected: bool | None,
    drift_note: str | None,
) -> UUID:
    """Append one frozen-anchor drift-check result (Phase F). Append-only history;
    each scheduled run is a new row. Returns the new row id."""
    return await conn.fetchval(
        """
        INSERT INTO drift_runs (
            judge_model_id, prompt_version, anchor_set, mae_overall,
            mae_per_dimension, baseline_mae, drift_detected, drift_note
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        RETURNING id
        """,
        judge_model_id, prompt_version, anchor_set, mae_overall,
        mae_per_dimension, baseline_mae, drift_detected, drift_note,
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


# ── per-chat artifact blobs (CSL / EIG question-quality / reliance) ─────────────
# These UPDATE the scores row created by upsert_score (called first in the worker).
# Each overwrites unconditionally so a re-score never leaves a stale artifact.

async def upsert_csl(
    conn: asyncpg.Connection, *, chat_id: UUID, csl: dict | None
) -> None:
    """Persist the CSL artifact blob (ownership + emergence + 3-panel report).
    Parallel descriptive layer — never an ARI score; may be {"status": "error"}."""
    await conn.execute(
        "UPDATE scores SET csl = $2 WHERE chat_id = $1", chat_id, csl or {}
    )


async def upsert_question_quality(
    conn: asyncpg.Connection, *, chat_id: UUID, question_quality: dict | None
) -> None:
    """Persist the EIG question-quality features + neuron evidence (P5)."""
    await conn.execute(
        "UPDATE scores SET question_quality = $2 WHERE chat_id = $1",
        chat_id, question_quality or {},
    )


async def upsert_reliance(
    conn: asyncpg.Connection, *, chat_id: UUID, reliance: dict | None
) -> None:
    """Persist the appropriate-reliance metrics + EC-11 evidence rows (P11)."""
    await conn.execute(
        "UPDATE scores SET reliance = $2 WHERE chat_id = $1", chat_id, reliance or {}
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


# ── Scope-C: projects / sessions / portfolio ack (contract scope-c/v1.0) ───────
# project_id is server-minted (gen_random_uuid). saf_session_id is an ALIAS of
# raw_chats.id — project_sessions.chat_id IS the session id. Every read/mutation
# is scoped by user_ref → subject_id, so a caller only ever touches their own
# rows. Deletion of the subject (DELETE /v1/users/{ref}) cascades through these
# tables via the migration-012 FKs (#16 data dignity).


async def create_project(
    pool: asyncpg.Pool,
    *,
    user_ref: str,
    name: str,
    description: str | None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Insert a project, minting the subject if this user_ref has none yet.
    With an Idempotency-Key a repeat returns the ORIGINAL row (no duplicate),
    enforced by the (subject_id, idempotency_key) partial-unique index."""
    row = await pool.fetchrow(
        """
        WITH subj AS (
            INSERT INTO subjects (user_ref) VALUES ($1)
            ON CONFLICT (user_ref) DO UPDATE SET user_ref = EXCLUDED.user_ref
            RETURNING subject_id
        ),
        ins AS (
            INSERT INTO projects (subject_id, name, description, idempotency_key)
            SELECT subject_id, $2, $3, $4 FROM subj
            ON CONFLICT (subject_id, idempotency_key)
                WHERE idempotency_key IS NOT NULL
                DO NOTHING
            RETURNING id, name, description, version, created_at, updated_at
        )
        SELECT * FROM ins
        """,
        user_ref, name, description, idempotency_key,
    )
    if row is not None:
        return dict(row)
    # idempotent replay: the key already minted a project → return the original
    existing = await pool.fetchrow(
        """
        SELECT p.id, p.name, p.description, p.version, p.created_at, p.updated_at
        FROM projects p JOIN subjects s ON s.subject_id = p.subject_id
        WHERE s.user_ref = $1 AND p.idempotency_key = $2
        """,
        user_ref, idempotency_key,
    )
    return dict(existing) if existing else {}


async def list_projects(
    pool: asyncpg.Pool,
    *,
    user_ref: str,
    limit: int,
    before_created_at: datetime | None = None,
    before_id: UUID | None = None,
) -> list[dict[str, Any]]:
    """Keyset page of a subject's ACTIVE projects, newest first. The cursor is
    the last seen (created_at, id); offset pagination is never used (#scale)."""
    rows = await pool.fetch(
        """
        SELECT p.id, p.name, p.updated_at, p.created_at,
               (SELECT COUNT(*) FROM project_sessions ps WHERE ps.project_id = p.id)
                   AS session_count
        FROM projects p
        JOIN subjects s ON s.subject_id = p.subject_id
        WHERE s.user_ref = $1
          AND p.archived_at IS NULL
          AND ($2::timestamptz IS NULL OR (p.created_at, p.id) < ($2, $3))
        ORDER BY p.created_at DESC, p.id DESC
        LIMIT $4
        """,
        user_ref, before_created_at, before_id, limit,
    )
    return [dict(r) for r in rows]


async def get_project(
    pool: asyncpg.Pool, *, user_ref: str, project_id: UUID
) -> asyncpg.Record | None:
    return await pool.fetchrow(
        """
        SELECT p.id, p.subject_id, p.name, p.description, p.version,
               p.created_at, p.updated_at,
               (SELECT COUNT(*) FROM project_sessions ps WHERE ps.project_id = p.id)
                   AS session_count
        FROM projects p JOIN subjects s ON s.subject_id = p.subject_id
        WHERE s.user_ref = $1 AND p.id = $2 AND p.archived_at IS NULL
        """,
        user_ref, project_id,
    )


async def update_project(
    pool: asyncpg.Pool,
    *,
    user_ref: str,
    project_id: UUID,
    name: str | None,
    description: str | None,
    expected_version: int,
) -> dict[str, Any] | None:
    """Optimistic-concurrency update. Returns the new row dict on success,
    None when the project does not exist/own, or {"_conflict": current_version}
    when expected_version is stale (→ 409 at the router). NULL name/description
    means 'leave unchanged'."""
    row = await pool.fetchrow(
        """
        UPDATE projects p
        SET name        = COALESCE($4, p.name),
            description = COALESCE($5, p.description),
            version     = p.version + 1,
            updated_at  = now()
        FROM subjects s
        WHERE p.subject_id = s.subject_id
          AND s.user_ref = $1 AND p.id = $2 AND p.archived_at IS NULL
          AND p.version = $3
        RETURNING p.id, p.name, p.description, p.version, p.created_at, p.updated_at
        """,
        user_ref, project_id, expected_version, name, description,
    )
    if row is not None:
        return dict(row)
    current = await pool.fetchval(
        """
        SELECT p.version FROM projects p JOIN subjects s ON s.subject_id = p.subject_id
        WHERE s.user_ref = $1 AND p.id = $2 AND p.archived_at IS NULL
        """,
        user_ref, project_id,
    )
    if current is None:
        return None
    return {"_conflict": current}


async def delete_project(
    pool: asyncpg.Pool,
    *,
    user_ref: str,
    project_id: UUID,
    expected_version: int,
) -> dict[str, Any] | None:
    """Hard-delete a project (cascades its project_sessions, NOT the chats).
    Returns {"sessions_unlinked": N} on success, None when not found/owned, or
    {"_conflict": current_version} when expected_version is stale."""
    current = await pool.fetchrow(
        """
        SELECT p.version,
               (SELECT COUNT(*) FROM project_sessions ps WHERE ps.project_id = p.id)
                   AS session_count
        FROM projects p JOIN subjects s ON s.subject_id = p.subject_id
        WHERE s.user_ref = $1 AND p.id = $2 AND p.archived_at IS NULL
        """,
        user_ref, project_id,
    )
    if current is None:
        return None
    if current["version"] != expected_version:
        return {"_conflict": current["version"]}
    await pool.execute("DELETE FROM projects WHERE id = $1", project_id)
    return {"sessions_unlinked": current["session_count"]}


async def add_project_sessions(
    pool: asyncpg.Pool,
    *,
    user_ref: str,
    project_id: UUID,
    chat_ids: list[UUID],
) -> dict[str, Any] | None:
    """Idempotently link chats (== saf_session_ids) to a project. chat_ids not
    owned by this user are reported as 'unknown', never fatal. Returns None when
    the project itself is not found/owned (→ 404)."""
    owns = await pool.fetchval(
        """
        SELECT 1 FROM projects p JOIN subjects s ON s.subject_id = p.subject_id
        WHERE s.user_ref = $1 AND p.id = $2 AND p.archived_at IS NULL
        """,
        user_ref, project_id,
    )
    if owns is None:
        return None

    valid = await pool.fetch(
        "SELECT id FROM raw_chats WHERE user_ref = $1 AND id = ANY($2::uuid[])",
        user_ref, chat_ids,
    )
    valid_ids = [r["id"] for r in valid]
    valid_set = set(valid_ids)
    unknown = [str(c) for c in chat_ids if c not in valid_set]

    added_rows = await pool.fetch(
        """
        INSERT INTO project_sessions (project_id, chat_id)
        SELECT $1, x FROM unnest($2::uuid[]) AS x
        ON CONFLICT DO NOTHING
        RETURNING chat_id
        """,
        project_id, valid_ids,
    )
    added = len(added_rows)
    return {
        "added": added,
        "skipped_already_present": len(valid_ids) - added,
        "unknown": unknown,
    }


async def remove_project_session(
    pool: asyncpg.Pool, *, user_ref: str, project_id: UUID, chat_id: UUID
) -> bool:
    result = await pool.execute(
        """
        DELETE FROM project_sessions ps
        USING projects p, subjects s
        WHERE ps.project_id = p.id
          AND p.subject_id = s.subject_id
          AND s.user_ref = $1 AND p.id = $2 AND ps.chat_id = $3
        """,
        user_ref, project_id, chat_id,
    )
    parts = result.split()
    return len(parts) == 2 and parts[1] != "0"


async def get_project_score_rows(
    pool: asyncpg.Pool, *, user_ref: str, project_id: UUID
) -> list[asyncpg.Record]:
    """Scored-chat profiles linked to a project, for radar aggregation."""
    return await pool.fetch(
        """
        SELECT sc.profile, rc.captured_at
        FROM project_sessions ps
        JOIN projects p   ON p.id = ps.project_id
        JOIN subjects s   ON s.subject_id = p.subject_id
        JOIN scores sc    ON sc.chat_id = ps.chat_id
        JOIN raw_chats rc ON rc.id = ps.chat_id
        WHERE s.user_ref = $1 AND p.id = $2 AND rc.status = 'scored'
        ORDER BY rc.captured_at ASC
        """,
        user_ref, project_id,
    )


# ── user settings (S10: auto_analyse / calibration opt-in) ──────────────────────

#: server-side defaults when a subject has no settings row yet (opt-in = OFF, #16)
SETTINGS_DEFAULTS = {"auto_analyse": False, "calibration_opt_in": False}


async def get_settings(pool: asyncpg.Pool, *, user_ref: str) -> dict[str, Any]:
    """Return the user's settings, or the safe defaults when none are stored."""
    row = await pool.fetchrow(
        """
        SELECT us.auto_analyse, us.calibration_opt_in, us.updated_at
        FROM user_settings us JOIN subjects s ON s.subject_id = us.subject_id
        WHERE s.user_ref = $1
        """,
        user_ref,
    )
    if row is None:
        return {**SETTINGS_DEFAULTS, "updated_at": None}
    return {
        "auto_analyse": row["auto_analyse"],
        "calibration_opt_in": row["calibration_opt_in"],
        "updated_at": row["updated_at"].isoformat(),
    }


async def upsert_settings(
    pool: asyncpg.Pool,
    *,
    user_ref: str,
    auto_analyse: bool | None = None,
    calibration_opt_in: bool | None = None,
) -> dict[str, Any]:
    """Partial-update the user's settings (mints the subject if needed). NULL
    fields are left unchanged; absent row starts from SETTINGS_DEFAULTS."""
    row = await pool.fetchrow(
        """
        WITH subj AS (
            INSERT INTO subjects (user_ref) VALUES ($1)
            ON CONFLICT (user_ref) DO UPDATE SET user_ref = EXCLUDED.user_ref
            RETURNING subject_id
        )
        INSERT INTO user_settings (subject_id, auto_analyse, calibration_opt_in)
        SELECT subject_id,
               COALESCE($2, FALSE),
               COALESCE($3, FALSE)
        FROM subj
        ON CONFLICT (subject_id) DO UPDATE SET
            auto_analyse       = COALESCE($2, user_settings.auto_analyse),
            calibration_opt_in = COALESCE($3, user_settings.calibration_opt_in),
            updated_at         = now()
        RETURNING auto_analyse, calibration_opt_in, updated_at
        """,
        user_ref, auto_analyse, calibration_opt_in,
    )
    return {
        "auto_analyse": row["auto_analyse"],
        "calibration_opt_in": row["calibration_opt_in"],
        "updated_at": row["updated_at"].isoformat(),
    }


async def get_portfolio_ack(
    pool: asyncpg.Pool, *, user_ref: str, scope: str
) -> asyncpg.Record | None:
    return await pool.fetchrow(
        """
        SELECT pa.snapshot_hash, pa.acked_at
        FROM portfolio_ack pa JOIN subjects s ON s.subject_id = pa.subject_id
        WHERE s.user_ref = $1 AND pa.scope = $2
        """,
        user_ref, scope,
    )


async def upsert_portfolio_ack(
    pool: asyncpg.Pool, *, user_ref: str, scope: str, snapshot_hash: str
) -> dict[str, Any]:
    """Record that the user acknowledged a specific portfolio snapshot (by hash).
    Mints the subject if needed; re-acking a new hash overwrites the old ack."""
    row = await pool.fetchrow(
        """
        WITH subj AS (
            INSERT INTO subjects (user_ref) VALUES ($1)
            ON CONFLICT (user_ref) DO UPDATE SET user_ref = EXCLUDED.user_ref
            RETURNING subject_id
        )
        INSERT INTO portfolio_ack (subject_id, scope, snapshot_hash)
        SELECT subject_id, $2, $3 FROM subj
        ON CONFLICT (subject_id, scope) DO UPDATE
            SET snapshot_hash = EXCLUDED.snapshot_hash, acked_at = now()
        RETURNING acked_at
        """,
        user_ref, scope, snapshot_hash,
    )
    return dict(row)
