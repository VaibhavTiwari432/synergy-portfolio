"""Track 0 — purge OpenAI credentials from telemetry.metadata at rest.

The extension used to ship the user's OpenAI key inside the ingest metadata,
which landed in telemetry.metadata JSONB. That is a credential-at-rest / DPDP
problem. Code now (a) stops sending the key from the extension, (b) scrubs
secret keys at the ingest write boundary, and (c) sources the self-rater key
from a server-side OPENAI_API_KEY env secret. This migration cleans the rows
already written before those fixes.

Irreversible by design: a purged secret cannot (and must not) be restored, so
downgrade is a no-op that says so. Removing a credential is not a schema change.

Revision ID: 004
Revises: 003
Create Date: 2026-06-17
"""

from __future__ import annotations

from alembic import op

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None

_SECRET_KEYS = ("openai_api_key", "openai_key", "api_key")


def upgrade() -> None:
    # Strip each known credential key from the JSONB document in place.
    for key in _SECRET_KEYS:
        op.execute(
            f"""
            UPDATE telemetry
            SET metadata = metadata - '{key}'
            WHERE metadata ? '{key}'
            """
        )


def downgrade() -> None:
    # Purged credentials are gone for good — there is nothing to restore, and
    # restoring a secret would be a regression, not a rollback.
    pass
