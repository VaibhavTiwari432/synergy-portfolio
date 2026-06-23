"""Phase F: drift_runs — frozen-anchor re-score history for judge-drift detection.

CLAUDE.md #18 (MAE ratchet) + v3.21 §8.6: re-score the frozen gold anchor set on
a schedule and compare MAE to the ratchet baseline. A MAE rise on the anchor set
means the INSTRUMENT moved (judge drift), not the subject — without this, a judge
version/prompt change is invisible. Each run records one row here.

This table backs a CI/cron job (calibration/drift_check.py); it never sits on a
user request path. drift_detected=True is a WARNING signal, not a release block.

Revision ID: 017
Revises: 016
Create Date: 2026-06-23
"""

from __future__ import annotations

from alembic import op

revision = "017"
down_revision = "016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS drift_runs (
            id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            run_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
            judge_model_id    TEXT NOT NULL,
            prompt_version    TEXT NOT NULL,
            anchor_set        TEXT[] NOT NULL,
            mae_overall       FLOAT,
            mae_per_dimension JSONB,
            baseline_mae      FLOAT,
            drift_detected    BOOLEAN,
            drift_note        TEXT
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_drift_runs_run_at ON drift_runs (run_at DESC)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS drift_runs")
