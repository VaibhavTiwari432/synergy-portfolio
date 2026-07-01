"""Phase C.4: queryable research view over the persisted question-quality trio.

The EIG question-quality summary (mean_complexity / complexity_trend /
originality) is already persisted per chat in the `scores.question_quality` JSONB
blob (migration 011). This view surfaces the longitudinal trio as typed columns
for corpus-level research queries without re-parsing JSON at every call site.

RESEARCH-ONLY (Tier R1): a read-only projection of already-stored evidence. It
adds no neuron/dimension/pillar/latent (#1) and conditions no score (#2). The
blobs live on `scores`, NOT a separate `score_artifact_blobs` table (the latter
does not exist — migration 011 added JSONB columns to `scores`).

Revision ID: 015
Revises: 014
Create Date: 2026-06-23
"""

from __future__ import annotations

from alembic import op

revision = "015"
down_revision = "014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE VIEW research_question_quality AS
        SELECT
            chat_id,
            (csl->>'status') AS csl_status,
            (question_quality->'session_summary'->>'mean_complexity')::float
                AS mean_complexity,
            (question_quality->'session_summary'->>'complexity_trend')::float
                AS complexity_trend,
            (question_quality->'session_summary'->>'originality')::float
                AS originality
        FROM scores
        WHERE question_quality IS NOT NULL
        """
    )


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS research_question_quality")
