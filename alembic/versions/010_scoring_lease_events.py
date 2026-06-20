"""Watchdog audit: scoring_lease_events — observable lease-timeout resets.

A chat that enters status='scoring' but is never finalized (the worker crashed or
hung mid-score) must be reset to 'pending' so it re-queues. The lease watchdog
(src/worker/scorer.py) does that on a timer; EVERY reset is recorded here so the
state change is observable — never silent.

This is deliberately NOT the per-turn event_log (migration 008): that table is
turn-scoped (turn_index / role / char_count / intent_tag, UNIQUE(chat_id,
turn_index)) and a lease reset is not a conversation turn. A reset is a
worker-lifecycle event and gets its own first-class, queryable record.

Revision ID: 010
Revises: 009
Create Date: 2026-06-18
"""

from __future__ import annotations

from alembic import op

revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS scoring_lease_events (
            id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            chat_id            UUID NOT NULL REFERENCES raw_chats(id) ON DELETE CASCADE,
            conversation_id    TEXT,
            reason             TEXT NOT NULL,
            previous_status    TEXT NOT NULL,
            scoring_started_at TIMESTAMPTZ,
            lease_age_seconds  BIGINT,
            created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_scoring_lease_events_chat_id "
        "ON scoring_lease_events(chat_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_scoring_lease_events_created_at "
        "ON scoring_lease_events(created_at DESC)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS scoring_lease_events")
