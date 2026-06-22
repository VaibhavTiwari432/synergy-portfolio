"""
src/worker/scorer.py — background scoring worker. OWNER: Chief Engineer.

Polls raw_chats for status='pending' rows, claims them atomically,
calls score_session() by DIRECT IMPORT (not via HTTP), writes full
ScoreResponse back to the scores table, then triggers the self-rater
as a non-blocking async task.

Entry point:  python -m src.worker.scorer

Poll interval is configurable via WORKER_POLL_INTERVAL (seconds, default 3).
On failure: status → 'failed', error logged, worker continues.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from uuid import UUID

import asyncpg

from contracts.schemas import CanonicalSession, PartnerModel, Turn
from src.db.connection import get_pool, init_pool
from src.db.queries import (
    capture_completeness_error,
    capture_validation_error,
    claim_pending_batch,
    get_telemetry_for_chat,
    mark_scored,
    replace_neuron_firings,
    replace_turn_state,
    reset_expired_scoring_leases,
    set_chat_status,
    upsert_csl,
    upsert_judge_run,
    upsert_question_quality,
    upsert_reliance,
    upsert_score,
)
from src.trait.judge.prompt import JUDGE_PROMPT_VERSION

POLL_INTERVAL: int = int(os.environ.get("WORKER_POLL_INTERVAL", "3"))

# Heartbeat (Audit Track 4): the worker emits a liveness log every
# WORKER_HEARTBEAT_SECONDS and, if WORKER_HEARTBEAT_FILE is set, touches that file
# with a UTC timestamp — so ops can detect a silently-dead worker.
HEARTBEAT_INTERVAL: int = int(os.environ.get("WORKER_HEARTBEAT_SECONDS", "30"))
HEARTBEAT_FILE: str | None = os.environ.get("WORKER_HEARTBEAT_FILE") or None

# Lease watchdog (stuck-scoring recovery). A chat enters status='scoring' when a
# worker claims it; if that worker crashes or hangs before finalizing, the row is
# wedged. The watchdog resets such rows to 'pending' after LEASE_TIMEOUT_SECONDS
# and records every reset in scoring_lease_events (reason='lease_timeout'). The
# default (600 s) must exceed the longest legitimate single-chat scoring time so a
# slow-but-live score is never reset out from under itself.
LEASE_TIMEOUT_SECONDS: int = int(os.environ.get("LEASE_TIMEOUT_SECONDS", "600"))
# How often the watchdog checks. Default = a quarter of the lease, clamped to
# [30 s, 300 s] so a check always lands well within the lease window.
LEASE_WATCHDOG_INTERVAL: int = int(
    os.environ.get(
        "LEASE_WATCHDOG_INTERVAL",
        str(max(30, min(300, LEASE_TIMEOUT_SECONDS // 4))),
    )
)

#: metadata keys that must never enter the corpus or a scoring session (Track 0)
_SECRET_METADATA_KEYS = frozenset({"openai_api_key", "openai_key", "api_key"})

log = logging.getLogger(__name__)


# ── session reconstruction ──────────────────────────────────────────────────

def _build_canonical_session(
    chat: asyncpg.Record, telemetry: asyncpg.Record | None = None
) -> CanonicalSession:
    """Reconstruct a CanonicalSession from a raw_chats DB row.

    Extension sends turns as {role, text, timestamp_ms, turn_index}.
    CanonicalSession.Turn uses index (not turn_index) and role values
    'human'/'ai' (not 'user'/'assistant').
    """
    turns_raw: list[dict] = chat["turns"]  # asyncpg parses JSONB → list[dict]
    partner_raw: dict = chat["partner_model"]

    turns: list[Turn] = []
    for raw in turns_raw:
        role = raw.get("role", "human")
        if role in ("user",):
            role = "human"
        elif role in ("assistant",):
            role = "ai"

        ts: datetime | None = None
        ts_ms = raw.get("timestamp_ms")
        if ts_ms is not None:
            ts = datetime.fromtimestamp(ts_ms / 1000.0, tz=timezone.utc)

        turns.append(Turn(
            index=raw.get("turn_index", raw.get("index", len(turns))),
            role=role,
            text=raw.get("text", ""),
            timestamp=ts,
        ))

    partner_model = PartnerModel.model_validate(partner_raw)
    metadata: dict = {}
    if telemetry is not None:
        tel_metadata = telemetry["metadata"] if isinstance(telemetry["metadata"], dict) else {}
        # Track 0: never surface secrets into the scoring session, even if a
        # stale row predates the ingest-time scrub.
        metadata.update({k: v for k, v in tel_metadata.items() if k not in _SECRET_METADATA_KEYS})
        metadata["telemetry"] = {
            "dwell_ms": telemetry["dwell_ms"],
            "copy_events": telemetry["copy_events"],
            "edit_detected": telemetry["edit_detected"],
            "selector_health": telemetry["selector_health"],
            "capture_mode": telemetry["capture_mode"],
        }

    return CanonicalSession(
        session_id=str(chat["id"]),
        source="chatgpt_export",   # both chatgpt_history and chatgpt_live map here
        partner_model=partner_model,
        turns=turns,
        user_ref=chat["user_ref"],
        detected_tier=2 if telemetry is not None else 1,
        metadata=metadata,
        # D-022 (#15): carry the persisted minor flag into scoring so enforce()
        # receives the true value. claim_pending_batch RETURNING * supplies the
        # column; a legacy row predating migration 014 reads as False (adult).
        is_minor=bool(chat.get("is_minor", False)),
    )


# ── scoring ─────────────────────────────────────────────────────────────────

async def _score_one(pool: asyncpg.Pool, chat: asyncpg.Record) -> None:
    chat_id: UUID = chat["id"]
    try:
        invalid_reason = capture_validation_error(chat["turns"])
        if invalid_reason is not None:
            log.warning(
                "[WORKER] refusing to score structurally invalid capture %s: %s",
                chat_id,
                invalid_reason,
            )
            async with pool.acquire() as conn:
                await set_chat_status(conn, chat_id, "failed")
            return

        # Defense in depth (ADR-0007): ingest quarantines proven-incomplete
        # captures, but re-check here so a manually inserted / legacy row that
        # claims completeness it doesn't have never reaches the scorer. captured
        # is re-derived from the stored turns (ground truth), not read from the
        # scalar column — the count that matters is what we will actually score.
        incomplete_reason = capture_completeness_error(
            expected_turn_count=chat.get("expected_turn_count"),
            captured_turn_count=len(chat["turns"]),
            capture_complete=chat.get("capture_complete"),
        )
        if incomplete_reason is not None:
            log.warning(
                "[WORKER] refusing to score incomplete capture %s: %s",
                chat_id,
                incomplete_reason,
            )
            async with pool.acquire() as conn:
                await set_chat_status(conn, chat_id, "failed")
            return

        telemetry = await get_telemetry_for_chat(pool, chat_id)
        session = _build_canonical_session(chat, telemetry)

        # Direct import — NOT via HTTP (EXTENSION_BUILD_PROMPT.md §2)
        from src.api.pipeline import score_session_with_artifacts
        run = await asyncio.to_thread(score_session_with_artifacts, session)
        result = run.response

        full: dict = json.loads(result.model_dump_json(by_alias=True))
        raw_profile = {
            dim.value: json.loads(score.model_dump_json(by_alias=True))
            for dim, score in run.raw_profile.items()
        }

        async with pool.acquire() as conn:
            await upsert_score(
                conn,
                chat_id=chat_id,
                prompt_version=JUDGE_PROMPT_VERSION,
                tier=full["tier"],
                profile=full["profile"],
                composite=full.get("composite"),
                state_strip=full.get("state_strip"),
                state_validity=full.get("state_validity"),
                flags=full.get("flags"),
                reaction_signatures=full.get("reaction_signatures"),
                regime_overlay=full.get("regime_overlay"),
                sustainability=full.get("sustainability"),
                report=full.get("report"),
                raw_profile=raw_profile,
                telemetry_metrics=run.telemetry_metrics,
                event_log=run.event_log,
                provenance=run.provenance,
            )
            # Track 1: persist the evidence + judge audit trail alongside the score
            # so a chat can be reproduced/re-analysed after the transcript purges.
            await upsert_judge_run(conn, chat_id=chat_id, judge_run=run.judge_run)
            await replace_neuron_firings(conn, chat_id=chat_id, rows=run.neuron_firings)
            # Track 2: per-turn state strip + per-turn precision, persisted now.
            await replace_turn_state(conn, chat_id=chat_id, rows=run.turn_state)
            # Per-chat artifact blobs the pipeline builds but previously discarded
            # (migration 011). Descriptive/evidence layers only — never ARI scores;
            # a CSL chain error stores {"status": "error"} and never blocks finalize.
            await upsert_csl(conn, chat_id=chat_id, csl=run.csl)
            await upsert_question_quality(
                conn, chat_id=chat_id, question_quality=run.question_quality
            )
            await upsert_reliance(conn, chat_id=chat_id, reliance=run.reliance)
            # Finalize only if the transcript we scored is still current. If a
            # newer ingest reset this row to 'pending' mid-scoring, this is a
            # no-op and the chat will be re-scored against the newer turns.
            finalized = await mark_scored(conn, chat_id, chat.get("content_hash"))

        if not finalized:
            log.info(
                "[WORKER] chat %s superseded during scoring — left pending for re-score",
                chat_id,
            )
            return

        log.info("[WORKER] scored chat %s", chat_id)

        # Self-rating is async, non-blocking — launch and forget
        asyncio.create_task(_trigger_self_rater(pool, chat_id, chat))

    except Exception as exc:
        log.error("[WORKER] scoring failed for %s: %s", chat_id, exc, exc_info=True)
        async with pool.acquire() as conn:
            await set_chat_status(conn, chat_id, "failed")


async def _trigger_self_rater(
    pool: asyncpg.Pool, chat_id: UUID, chat: asyncpg.Record
) -> None:
    """Hand off to the self-rater with the SERVER-SIDE OpenAI key (env secret).

    Track 0 (credential-at-rest fix): the key is read from the OPENAI_API_KEY
    environment variable, NEVER from telemetry.metadata — per-user keys no
    longer enter the corpus at rest. Absent env var → self-rater marks the row
    'skipped' gracefully. Key is never logged."""
    try:
        openai_key = os.environ.get("OPENAI_API_KEY") or None

        from src.worker.self_rater import request_self_rating
        await request_self_rating(pool, chat_id, chat["turns"], openai_key)
    except Exception as exc:
        log.warning("[WORKER] self-rater trigger failed for %s: %s", chat_id, exc)


# ── lease watchdog ─────────────────────────────────────────────────────────────

async def _lease_watchdog(pool: asyncpg.Pool) -> None:
    """Periodically reset chats wedged in 'scoring' past the lease back to 'pending'.

    Runs alongside the poll loop. Every reset is BOTH persisted to
    scoring_lease_events (durable, queryable) AND logged at WARNING (visible in the
    worker's stream) — there is no path where a chat silently leaves 'scoring'. Any
    error in the check is logged with a stack trace and the loop continues; the
    watchdog must never take the worker down.
    """
    log.info(
        "[WATCHDOG] lease timeout %ds — checking every %ds",
        LEASE_TIMEOUT_SECONDS,
        LEASE_WATCHDOG_INTERVAL,
    )
    while True:
        try:
            async with pool.acquire() as conn:
                async with conn.transaction():
                    reset = await reset_expired_scoring_leases(
                        conn, lease_timeout_seconds=LEASE_TIMEOUT_SECONDS
                    )
            for row in reset:
                log.warning(
                    "[WATCHDOG] reset chat %s (conversation %s) scoring→pending "
                    "after %ss stuck — reason=lease_timeout",
                    row["id"],
                    row["conversation_id"],
                    row["lease_age_seconds"],
                )
        except Exception as exc:
            log.error("[WATCHDOG] lease check failed: %s", exc, exc_info=True)

        await asyncio.sleep(LEASE_WATCHDOG_INTERVAL)


# ── main loop ────────────────────────────────────────────────────────────────

async def _poll_loop(pool: asyncpg.Pool) -> None:
    while True:
        try:
            async with pool.acquire() as conn:
                batch = await claim_pending_batch(conn)

            if batch:
                log.info("[WORKER] claimed %d chat(s)", len(batch))
                await asyncio.gather(*(_score_one(pool, chat) for chat in batch))

        except Exception as exc:
            log.error("[WORKER] poll error: %s", exc, exc_info=True)

        await asyncio.sleep(POLL_INTERVAL)


async def _heartbeat_loop() -> None:
    """Liveness signal so a silently-dead worker is detectable (Track 4)."""
    import time
    while True:
        ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        log.info("[WORKER] heartbeat %s (poll=%ds)", ts, POLL_INTERVAL)
        if HEARTBEAT_FILE:
            try:
                with open(HEARTBEAT_FILE, "w", encoding="utf-8") as fh:
                    fh.write(ts)
            except Exception as exc:  # heartbeat file is best-effort, never fatal
                log.warning("[WORKER] heartbeat file write failed: %s", exc)
        await asyncio.sleep(HEARTBEAT_INTERVAL)


async def run() -> None:
    from src.startup_checks import check_any_env, check_db, check_env
    check_env(
        component="worker",
        required=[],
        optional=["DATABASE_URL", "OPENAI_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY"],
    )
    if not check_any_env(
        component="worker",
        names=["GEMINI_API_KEY", "GOOGLE_API_KEY"],
        purpose="judge scoring",
    ):
        raise SystemExit(2)
    await init_pool()
    pool = get_pool()
    await check_db(pool)  # startup connectivity probe (logs verdict)
    log.info("[WORKER] started — poll interval %ds, heartbeat %ds", POLL_INTERVAL, HEARTBEAT_INTERVAL)
    # Poll loop, lease watchdog, and heartbeat run concurrently; if any coroutine
    # ever raises out of its own try/except (it shouldn't), gather surfaces it
    # loudly rather than leaving a half-dead worker.
    await asyncio.gather(_poll_loop(pool), _lease_watchdog(pool), _heartbeat_loop())


if __name__ == "__main__":
    from src.logging_config import configure_logging
    configure_logging()
    asyncio.run(run())
