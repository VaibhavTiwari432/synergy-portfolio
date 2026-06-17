"""ADR-0007 / D-015 — capture completeness gate columns on raw_chats.

Conversation-JSON interception (the new primary capture path) yields an
authoritative expected turn count from the mapping's active path. We persist it
alongside what we actually captured, plus a tri-state completeness flag:

  - capture_complete = TRUE  → interception proved the capture complete.
  - capture_complete = FALSE → interception proved it incomplete (quarantined at
    ingest with HTTP 422; never stored as pending — so FALSE should not normally
    reach this table, but the column + CHECK make the invariant explicit).
  - capture_complete = NULL  → unknown (legacy rows + the scroll-probe / dom-live
    fallback paths, which cannot prove completeness). These defer to the existing
    role-balance gate.

The CHECK constraint enforces the invariant directly in the database — ingest is
NOT trusted as the only writer: a row may never claim capture_complete = TRUE
while it captured fewer turns than the mapping said to expect.

Additive + nullable, exactly like the Track-1/Track-2 columns: existing rows read
NULL and behave as before.

Revision ID: 007
Revises: 006
Create Date: 2026-06-17
"""

from __future__ import annotations

from alembic import op

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE raw_chats ADD COLUMN IF NOT EXISTS expected_turn_count INTEGER"
    )
    op.execute(
        "ALTER TABLE raw_chats ADD COLUMN IF NOT EXISTS captured_turn_count INTEGER"
    )
    op.execute(
        "ALTER TABLE raw_chats ADD COLUMN IF NOT EXISTS capture_complete BOOLEAN"
    )

    # The invariant, enforced at rest: a row cannot claim complete while it
    # captured fewer turns than expected. captured >= expected is allowed (the
    # live-streamed tail legitimately extends past the intercepted history).
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'raw_chats_capture_complete_consistent'
            ) THEN
                ALTER TABLE raw_chats ADD CONSTRAINT raw_chats_capture_complete_consistent
                CHECK (
                    NOT (
                        capture_complete IS TRUE
                        AND expected_turn_count IS NOT NULL
                        AND captured_turn_count IS NOT NULL
                        AND captured_turn_count < expected_turn_count
                    )
                );
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE raw_chats DROP CONSTRAINT IF EXISTS raw_chats_capture_complete_consistent"
    )
    op.execute("ALTER TABLE raw_chats DROP COLUMN IF EXISTS capture_complete")
    op.execute("ALTER TABLE raw_chats DROP COLUMN IF EXISTS captured_turn_count")
    op.execute("ALTER TABLE raw_chats DROP COLUMN IF EXISTS expected_turn_count")
