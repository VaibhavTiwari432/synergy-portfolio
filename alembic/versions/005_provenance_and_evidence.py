"""Track 1 — stop irreversible loss: provenance + per-neuron firings + judge audit.

Three coupled additions so a score can be reproduced, validated, and audited
after the transcript purges (~30 days, unrecoverable):

  - scores: provenance columns (framework/schema/contract_table versions,
    code_git_sha, judge_model_id/version) + event_log JSONB (full N-FIRE log so
    reaction_signatures can be recomputed when the taxonomy is revised).
  - neuron_firings: queryable per-neuron matrix (for EFA at corpus scale).
    NULL value = N/A (no opportunity); 0.0 = observed 0-of-N. NEVER 0 for absent.
  - judge_runs: literal judge output + model identity + per-dim confidence.

Provenance/firings/judge data are queried ACROSS the corpus, so they are
normalized columns/tables — not JSONB blobs. event_log is read per-chat only,
so it stays JSONB.

Revision ID: 005
Revises: 004
Create Date: 2026-06-17
"""

from __future__ import annotations

from alembic import op

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── provenance columns on scores (queryable across instrument revisions) ──
    op.execute("ALTER TABLE scores ADD COLUMN IF NOT EXISTS event_log JSONB")
    op.execute("ALTER TABLE scores ADD COLUMN IF NOT EXISTS framework_version TEXT")
    op.execute("ALTER TABLE scores ADD COLUMN IF NOT EXISTS schema_version TEXT")
    op.execute("ALTER TABLE scores ADD COLUMN IF NOT EXISTS contract_table_version TEXT")
    op.execute("ALTER TABLE scores ADD COLUMN IF NOT EXISTS code_git_sha TEXT")
    op.execute("ALTER TABLE scores ADD COLUMN IF NOT EXISTS judge_model_id TEXT")
    op.execute("ALTER TABLE scores ADD COLUMN IF NOT EXISTS judge_model_version TEXT")

    # ── per-neuron firing matrix ──
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS neuron_firings (
            id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            chat_id                  UUID NOT NULL REFERENCES raw_chats(id) ON DELETE CASCADE,
            neuron_code              TEXT NOT NULL,
            dimension                TEXT,
            value                    DOUBLE PRECISION,        -- NULL = N/A; 0.0 = observed 0-of-N
            applicable_opportunities INTEGER NOT NULL DEFAULT 0,
            n_eff                    DOUBLE PRECISION NOT NULL DEFAULT 0,
            evidence_turn_indices    INTEGER[] DEFAULT '{}',
            extractor_version        TEXT,
            created_at               TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE(chat_id, neuron_code)
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_neuron_firings_chat_id ON neuron_firings(chat_id)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_neuron_firings_neuron_code ON neuron_firings(neuron_code)"
    )

    # ── judge audit trail ──
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS judge_runs (
            id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            chat_id                  UUID NOT NULL REFERENCES raw_chats(id) ON DELETE CASCADE,
            raw_response             TEXT,
            judge_model_id           TEXT,
            judge_model_version      TEXT,
            judge_family             TEXT,
            prompt_version           TEXT,
            per_dimension_confidence JSONB,
            judge_unavailable        BOOLEAN DEFAULT false,
            judge_family_conflict    BOOLEAN DEFAULT false,
            created_at               TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE(chat_id)
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_judge_runs_chat_id ON judge_runs(chat_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS judge_runs CASCADE")
    op.execute("DROP TABLE IF EXISTS neuron_firings CASCADE")
    op.execute("ALTER TABLE scores DROP COLUMN IF EXISTS judge_model_version")
    op.execute("ALTER TABLE scores DROP COLUMN IF EXISTS judge_model_id")
    op.execute("ALTER TABLE scores DROP COLUMN IF EXISTS code_git_sha")
    op.execute("ALTER TABLE scores DROP COLUMN IF EXISTS contract_table_version")
    op.execute("ALTER TABLE scores DROP COLUMN IF EXISTS schema_version")
    op.execute("ALTER TABLE scores DROP COLUMN IF EXISTS framework_version")
    op.execute("ALTER TABLE scores DROP COLUMN IF EXISTS event_log")
