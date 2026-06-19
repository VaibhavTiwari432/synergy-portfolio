"""Persist the per-chat artifact blobs the pipeline already produces but discarded.

score_session_with_artifacts builds three artifacts that were attached to the
in-memory ScoreRun but never written, so they were lost when the transcript
purged:

  - csl              : CSL (Cognitive Work Layer) per-ACF-level ownership +
                       emergence summary + 3-panel report (Phase 2 wiring).
  - question_quality : EIG question-quality features + neuron evidence (P5).
  - reliance         : appropriate-reliance metrics + EC-11 evidence rows (P11).

All three are RENDERED/EVIDENCE artifacts read per-chat (like event_log), not
queried across the corpus, so they are JSONB columns on scores rather than
normalized tables. Nullable: a score may exist before/without an artifact (e.g. a
CSL chain failure stores {"status": "error"} but never blocks the ARI score).

Revision ID: 011
Revises: 010
Create Date: 2026-06-19
"""

from __future__ import annotations

from alembic import op

revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE scores ADD COLUMN IF NOT EXISTS csl JSONB")
    op.execute("ALTER TABLE scores ADD COLUMN IF NOT EXISTS question_quality JSONB")
    op.execute("ALTER TABLE scores ADD COLUMN IF NOT EXISTS reliance JSONB")


def downgrade() -> None:
    op.execute("ALTER TABLE scores DROP COLUMN IF EXISTS reliance")
    op.execute("ALTER TABLE scores DROP COLUMN IF EXISTS question_quality")
    op.execute("ALTER TABLE scores DROP COLUMN IF EXISTS csl")
