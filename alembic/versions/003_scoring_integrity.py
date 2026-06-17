"""Scoring integrity: content_hash, scoring lease, telemetry uniqueness.

Covers three coupled fixes (CE bug triage 2026-06-16):
  - D-006  raw_chats.content_hash → upsert re-queues only on real transcript change
  - NEW    raw_chats.scoring_started_at → lease so stuck 'scoring' rows recover
  - D-006  UNIQUE(telemetry.chat_id) → upsert collapses to one current row per chat

Revision ID: 003
Revises: 002
Create Date: 2026-06-16
"""

from __future__ import annotations

from alembic import op

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── D-006 / stuck-scoring: new raw_chats columns ──
    op.execute("ALTER TABLE raw_chats ADD COLUMN IF NOT EXISTS content_hash TEXT")
    op.execute(
        "ALTER TABLE raw_chats ADD COLUMN IF NOT EXISTS scoring_started_at TIMESTAMPTZ"
    )
    # Reclaim any rows already wedged in 'scoring' from before the lease existed.
    op.execute("UPDATE raw_chats SET status = 'pending' WHERE status = 'scoring'")

    # ── D-006: one current telemetry row per chat ──
    # Dedupe existing rows before adding the constraint (keep newest per chat).
    op.execute(
        """
        DELETE FROM telemetry a USING telemetry b
        WHERE a.chat_id = b.chat_id AND a.imported_at < b.imported_at
        """
    )
    # Break exact-timestamp ties by physical row id.
    op.execute(
        """
        DELETE FROM telemetry a USING telemetry b
        WHERE a.chat_id = b.chat_id
          AND a.imported_at = b.imported_at
          AND a.ctid < b.ctid
        """
    )
    op.execute(
        "ALTER TABLE telemetry ADD CONSTRAINT uq_telemetry_chat_id UNIQUE (chat_id)"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE telemetry DROP CONSTRAINT IF EXISTS uq_telemetry_chat_id")
    op.execute("ALTER TABLE raw_chats DROP COLUMN IF EXISTS scoring_started_at")
    op.execute("ALTER TABLE raw_chats DROP COLUMN IF EXISTS content_hash")
