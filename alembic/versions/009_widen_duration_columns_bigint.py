"""Widen duration/offset columns INTEGER → BIGINT (overflow fix).

A real capture can carry millisecond values that exceed PostgreSQL INT4
(max 2,147,483,647 ≈ 24.8 days):

  - telemetry.dwell_ms       — dwell is measured from the controller's page-load
                               clock; a long-lived ChatGPT tab produces a first-turn
                               dwell well past 24 days.
  - event_log.timestamp_offset_ms — the offset of each turn from the conversation's
                               first message. A LONG chat returned to over several
                               weeks spans more than INT4 ms.

When either overflowed, asyncpg raised DataError ("value out of int32 range") inside
upsert_telemetry / replace_capture_artifacts — an UNHANDLED exception surfaced as
HTTP 500 at /v1/ingest, and the extension's collector bag then re-POSTed the same
payload on every health poll (a self-sustaining flood of 500s). Short chats with
small offsets never hit the ceiling, which is why only long chats failed.

These are genuine durations/offsets, not corruption, so the fix is to widen the
columns rather than clamp. The change is transparent to the application: asyncpg
already binds Python ints, and BIGINT accepts the same values. No code change and
no server restart are required — `alembic upgrade head` against the live DB is
enough.

Revision ID: 009
Revises: 008
Create Date: 2026-06-18
"""

from __future__ import annotations

from alembic import op

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE telemetry "
        "ALTER COLUMN dwell_ms TYPE BIGINT[] USING dwell_ms::bigint[]"
    )
    op.execute(
        "ALTER TABLE event_log "
        "ALTER COLUMN timestamp_offset_ms TYPE BIGINT USING timestamp_offset_ms::bigint"
    )


def downgrade() -> None:
    # Lossy if any stored value exceeds INT4; acceptable for a downgrade path.
    op.execute(
        "ALTER TABLE event_log "
        "ALTER COLUMN timestamp_offset_ms TYPE INTEGER USING timestamp_offset_ms::integer"
    )
    op.execute(
        "ALTER TABLE telemetry "
        "ALTER COLUMN dwell_ms TYPE INTEGER[] USING dwell_ms::integer[]"
    )
