"""S10 prerequisite: per-user settings (auto_analyse / calibration opt-in).

Backs GET/PATCH /v1/users/{ref}/settings (CODEX_AGENT_UI.md §8.1). Settings are
keyed to the opaque subject_id (not user_ref/PII), 1:1 with a subject, and
cascade-delete with the subject so a data deletion takes preferences with it
(#16 data dignity). Two booleans only — the "show notification dot" toggle is
extension-local (chrome.storage), not server state.

  - auto_analyse      : auto-score newly captured chats (default OFF).
  - calibration_opt_in: allow anonymised data into the calibration pool. Default
                        OFF — consent is opt-IN, never assumed (#16). Storing the
                        flag does not merge pools (#13); that gate lives elsewhere.

Revision ID: 013
Revises: 012
Create Date: 2026-06-20
"""

from __future__ import annotations

from alembic import op

revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS user_settings (
            subject_id        UUID PRIMARY KEY
                              REFERENCES subjects(subject_id) ON DELETE CASCADE,
            auto_analyse      BOOLEAN NOT NULL DEFAULT FALSE,
            calibration_opt_in BOOLEAN NOT NULL DEFAULT FALSE,
            updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS user_settings")
