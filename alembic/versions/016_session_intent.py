"""Phase C.1 (D-013 Track 3): persist session intent at score-time.

session_intent is the dominant Phase across human turns (EXPLORE/REFINE/EXTRACT/
EVALUATE), with session_intent_confidence = that phase's share of classified
turns. It reuses the existing frozen Phase construct — it introduces NO new
intent ontology (#1) and conditions NO score (#2). Tier R1 research data:
captured + queryable for later validation, never a live claim.

Both columns are nullable: an empty/unclassifiable session stores NULL (absent ≠
zero, #12), and rows scored before this migration read NULL.

Revision ID: 016
Revises: 015
Create Date: 2026-06-23
"""

from __future__ import annotations

from alembic import op

revision = "016"
down_revision = "015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE scores ADD COLUMN IF NOT EXISTS session_intent TEXT")
    op.execute(
        "ALTER TABLE scores ADD COLUMN IF NOT EXISTS session_intent_confidence FLOAT"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE scores DROP COLUMN IF EXISTS session_intent_confidence")
    op.execute("ALTER TABLE scores DROP COLUMN IF EXISTS session_intent")
