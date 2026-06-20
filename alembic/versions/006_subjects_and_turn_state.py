"""Track 2 — opaque subject identity + per-turn state persistence.

Two additions that close recoverability gaps the score alone can't regenerate:

  - subjects: a random, opaque subject_id (gen_random_uuid) ↔ user_ref mapping.
    subject_id is NEVER derived from PII (not HMAC(user_ref) — user_ref may be a
    guessable email/name, which would leak and complicate deletion). raw_chats
    gains a subject_id FK so research can key on the opaque id while deletion of
    a subject CASCADEs to every chat (and onward to all child tables).
  - turn_state: one row per human turn — the per-turn state strip (load,
    epistemic, metacog, tom, a_t, confidence) PLUS per-turn precision π_t and the
    cascade flags that reduced it, computed at score time. π_t / cascade follow
    absent ≠ zero (#12): NULL precision = the turn had no assessable state.

Both are queried across the corpus → normalized tables, not JSONB blobs.

Revision ID: 006
Revises: 005
Create Date: 2026-06-17
"""

from __future__ import annotations

from alembic import op

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── opaque subject identity (random UUID, never derived from user_ref) ──
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS subjects (
            subject_id  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_ref    TEXT NOT NULL UNIQUE,
            created_at  TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )

    # raw_chats gains the FK. ON DELETE CASCADE: deleting a subject removes all
    # their chats (and child rows cascade onward) — clean, single-point deletion.
    op.execute(
        "ALTER TABLE raw_chats ADD COLUMN IF NOT EXISTS subject_id UUID "
        "REFERENCES subjects(subject_id) ON DELETE CASCADE"
    )

    # Backfill: one opaque subject per distinct existing user_ref, then map.
    op.execute(
        """
        INSERT INTO subjects (user_ref)
        SELECT DISTINCT user_ref FROM raw_chats
        WHERE user_ref IS NOT NULL
        ON CONFLICT (user_ref) DO NOTHING
        """
    )
    op.execute(
        """
        UPDATE raw_chats rc
        SET subject_id = s.subject_id
        FROM subjects s
        WHERE rc.user_ref = s.user_ref
          AND rc.subject_id IS NULL
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_raw_chats_subject_id ON raw_chats(subject_id)")

    # ── per-turn state strip (one row per human turn) ──
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS turn_state (
            id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            chat_id       UUID NOT NULL REFERENCES raw_chats(id) ON DELETE CASCADE,
            turn_index    INTEGER NOT NULL,
            load          TEXT,                    -- NULL = channel unavailable
            epistemic     DOUBLE PRECISION,        -- [-1, 1] or NULL
            metacog       TEXT,
            tom_signal    DOUBLE PRECISION,
            a_t           DOUBLE PRECISION,        -- Tier-2 telemetry proxy; NULL in Tier 1
            confidence    DOUBLE PRECISION NOT NULL DEFAULT 0,
            pi_t          DOUBLE PRECISION,        -- per-turn precision; NULL = N/A (#12)
            cascade_flags TEXT[] DEFAULT '{}',
            created_at    TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE(chat_id, turn_index)
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_turn_state_chat_id ON turn_state(chat_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS turn_state CASCADE")
    op.execute("DROP INDEX IF EXISTS idx_raw_chats_subject_id")
    op.execute("ALTER TABLE raw_chats DROP COLUMN IF EXISTS subject_id")
    op.execute("DROP TABLE IF EXISTS subjects CASCADE")
