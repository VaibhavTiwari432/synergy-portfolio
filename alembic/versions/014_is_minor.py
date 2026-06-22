"""D-022: persist is_minor on raw_chats so scoring-path minor protection is enforced.

Minor protection (#15: no bare composite / peer rank / debt score to minors) is
applied at score time via `enforce(response, is_minor=session.is_minor)`
(pipeline.py). But the LIVE ingest path never carried is_minor: raw_chats had no
column, upsert_chat did not accept one, and the worker's _build_canonical_session
built a CanonicalSession without it — so it defaulted False and every live-scored
chat was treated as a non-minor. This column closes that gap; the flag is set
during extension onboarding and threads ingest → raw_chats → worker → enforce.

NOT NULL DEFAULT FALSE: existing rows (and any ingest that omits the field) are
non-minor, matching the prior behaviour exactly — this is additive and safe.

Revision ID: 014
Revises: 013
Create Date: 2026-06-23
"""

from __future__ import annotations

from alembic import op

revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE raw_chats "
        "ADD COLUMN IF NOT EXISTS is_minor BOOLEAN NOT NULL DEFAULT FALSE"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE raw_chats DROP COLUMN IF EXISTS is_minor")
