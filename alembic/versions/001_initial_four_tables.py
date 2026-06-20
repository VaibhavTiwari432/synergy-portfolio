"""Initial four-table schema (Scope B — EXTENSION_BUILD_PROMPT.md §1).

Revision ID: 001
Revises:
Create Date: 2026-06-14
"""

from __future__ import annotations

from alembic import op

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS raw_chats (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_ref        TEXT NOT NULL,
            conversation_id TEXT NOT NULL,
            source          TEXT NOT NULL,
            partner_model   JSONB NOT NULL,
            turns           JSONB NOT NULL,
            turn_count      INTEGER NOT NULL,
            captured_at     TIMESTAMPTZ DEFAULT NOW(),
            status          TEXT DEFAULT 'pending',
            UNIQUE(user_ref, conversation_id)
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS telemetry (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            chat_id         UUID NOT NULL REFERENCES raw_chats(id) ON DELETE CASCADE,
            dwell_ms        INTEGER[],
            copy_events     INTEGER[],
            edit_detected   BOOLEAN[],
            selector_health TEXT,
            capture_mode    TEXT NOT NULL,
            imported_at     TIMESTAMPTZ DEFAULT NOW(),
            metadata        JSONB DEFAULT '{}'
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS scores (
            id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            chat_id                  UUID NOT NULL REFERENCES raw_chats(id) ON DELETE CASCADE,
            scored_at                TIMESTAMPTZ DEFAULT NOW(),
            prompt_version           TEXT NOT NULL,
            tier                     INTEGER NOT NULL,
            profile                  JSONB NOT NULL,
            raw_profile              JSONB,
            composite                JSONB,
            state_strip              JSONB,
            state_validity           JSONB,
            flags                    JSONB,
            reaction_signatures      JSONB,
            regime_overlay           JSONB,
            sustainability           JSONB,
            telemetry_metrics        JSONB,
            report                   JSONB,
            self_rating_raw          JSONB,
            self_rating_prompt_version TEXT,
            self_rating_at           TIMESTAMPTZ,
            self_rating_status       TEXT DEFAULT 'pending',
            UNIQUE(chat_id)
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS feedback (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            chat_id         UUID NOT NULL REFERENCES raw_chats(id) ON DELETE CASCADE,
            user_ref        TEXT NOT NULL,
            match_rating    TEXT NOT NULL,
            comment         TEXT,
            scores_snapshot JSONB NOT NULL,
            submitted_at    TIMESTAMPTZ DEFAULT NOW()
        )
    """)

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

    op.execute("CREATE INDEX IF NOT EXISTS idx_raw_chats_user_ref ON raw_chats(user_ref)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_raw_chats_status ON raw_chats(status)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_raw_chats_captured_at ON raw_chats(captured_at)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_scores_chat_id ON scores(chat_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_feedback_user_ref ON feedback(user_ref)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_turn_feedback_user_ref ON turn_feedback(user_ref)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_turn_model_ratings_chat_id ON turn_model_ratings(chat_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS feedback CASCADE")
    op.execute("DROP TABLE IF EXISTS turn_feedback CASCADE")
    op.execute("DROP TABLE IF EXISTS turn_model_ratings CASCADE")
    op.execute("DROP TABLE IF EXISTS scores CASCADE")
    op.execute("DROP TABLE IF EXISTS telemetry CASCADE")
    op.execute("DROP TABLE IF EXISTS raw_chats CASCADE")
