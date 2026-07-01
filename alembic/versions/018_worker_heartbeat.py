"""Worker liveness heartbeat — make a silently-dead scoring worker detectable.

A chat ingests fine while the API is up but never leaves 'pending' if the worker
process isn't running. The panel had no way to tell "scoring is slow" from
"nothing is draining the queue". The worker now upserts a heartbeat row every
beat; /v1/health reads the freshest one and reports worker = ok | down, which the
extension surfaces as an actionable banner instead of a stuck spinner.

One row per worker process (worker_id = host:pid) so multiple workers each keep
their own; readers take MAX(beat_at) = "is ANY worker alive". Dead workers' stale
rows are simply ignored by the freshness check.

Revision ID: 018
Revises: two_table_event_log
Create Date: 2026-06-27
"""

from __future__ import annotations

from alembic import op

revision = "018"
down_revision = "two_table_event_log"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS worker_heartbeat (
            worker_id  TEXT PRIMARY KEY,
            beat_at    TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS worker_heartbeat")
