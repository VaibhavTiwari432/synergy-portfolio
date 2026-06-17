"""Store raw scoring artifacts and per-turn feedback/rating rows.

Revision ID: 002
Revises: 001
Create Date: 2026-06-16
"""

from __future__ import annotations

from alembic import op

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE scores ADD COLUMN IF NOT EXISTS raw_profile JSONB")
    op.execute("ALTER TABLE scores ADD COLUMN IF NOT EXISTS telemetry_metrics JSONB")

    op.execute("""
        CREATE TABLE IF NOT EXISTS turn_model_ratings (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            chat_id         UUID NOT NULL REFERENCES raw_chats(id) ON DELETE CASCADE,
            turn_index      INTEGER NOT NULL,
            rating_raw      JSONB,
            prompt_version  TEXT,
            status          TEXT NOT NULL DEFAULT 'pending',
            rated_at        TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE(chat_id, turn_index)
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS turn_feedback (
            id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            chat_id          UUID NOT NULL REFERENCES raw_chats(id) ON DELETE CASCADE,
            user_ref         TEXT NOT NULL,
            turn_index       INTEGER NOT NULL,
            match_rating     TEXT NOT NULL,
            dimension_scores JSONB,
            comment          TEXT,
            scores_snapshot  JSONB NOT NULL,
            submitted_at     TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_turn_feedback_user_ref ON turn_feedback(user_ref)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_turn_model_ratings_chat_id ON turn_model_ratings(chat_id)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS turn_feedback CASCADE")
    op.execute("DROP TABLE IF EXISTS turn_model_ratings CASCADE")
    op.execute("ALTER TABLE scores DROP COLUMN IF EXISTS telemetry_metrics")
    op.execute("ALTER TABLE scores DROP COLUMN IF EXISTS raw_profile")
