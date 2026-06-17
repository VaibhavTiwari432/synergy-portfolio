"""Capture audit split: derived event_log + raw_transcripts retention flag.

Revision ID: 008
Revises: 007
Create Date: 2026-06-17
"""

from __future__ import annotations

from alembic import op

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS event_log (
            id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            chat_id             UUID NOT NULL REFERENCES raw_chats(id) ON DELETE CASCADE,
            conversation_id     TEXT NOT NULL,
            turn_index          INTEGER NOT NULL,
            role                TEXT NOT NULL,
            char_count          INTEGER NOT NULL,
            timestamp_offset_ms INTEGER,
            intent_tag          TEXT NOT NULL,
            captured_at         TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE(chat_id, turn_index)
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS raw_transcripts (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            chat_id         UUID NOT NULL REFERENCES raw_chats(id) ON DELETE CASCADE,
            conversation_id TEXT NOT NULL,
            turn_index      INTEGER NOT NULL,
            role            TEXT NOT NULL,
            text            TEXT NOT NULL,
            retention_flag  TEXT NOT NULL DEFAULT 'retain',
            captured_at     TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE(chat_id, turn_index)
        )
    """)

    op.execute("CREATE INDEX IF NOT EXISTS idx_event_log_conversation_id ON event_log(conversation_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_event_log_chat_id ON event_log(chat_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_raw_transcripts_conversation_id ON raw_transcripts(conversation_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_raw_transcripts_chat_id ON raw_transcripts(chat_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS raw_transcripts")
    op.execute("DROP TABLE IF EXISTS event_log")
