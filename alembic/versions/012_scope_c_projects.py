"""Scope-C contract (D-012): projects, project_sessions, portfolio_ack.

Freezes the project/session/portfolio-ack data model from
contracts/scope_c_contract.md (FROZEN v1.0). Identity decisions:

  - project_id      : server-minted random opaque UUID (gen_random_uuid()),
                      following the opaque-subject precedent (migration 006).
  - saf_session_id  : an ALIAS of raw_chats.id (chat_id) — NO new column, NO
                      mapping table. project_sessions.chat_id IS the session id.

Scalability invariants baked into the schema:
  - UUID PKs everywhere (shardable, no sequential leakage).
  - projects.version for optimistic concurrency (If-Match -> 409 at the router).
  - projects.(subject_id, idempotency_key) partial-unique → Idempotency-Key
    on create dedupes a double-tap without a separate idempotency store.
  - keyset-pagination index on (subject_id, archived_at, created_at desc, id).
  - project_sessions(chat_id) reverse-lookup index.
  - ON DELETE CASCADE on every FK so subject deletion (#16 data dignity)
    propagates: delete raw_chats -> project_sessions rows go; delete subject
    -> projects + portfolio_ack go (and their project_sessions via projects).

Revision ID: 012
Revises: 011
Create Date: 2026-06-20
"""

from __future__ import annotations

from alembic import op

revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS projects (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            subject_id      UUID NOT NULL REFERENCES subjects(subject_id) ON DELETE CASCADE,
            name            TEXT NOT NULL,
            description     TEXT,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            archived_at     TIMESTAMPTZ,
            version         INTEGER NOT NULL DEFAULT 1,
            idempotency_key TEXT
        )
        """
    )
    # keyset pagination of a subject's active projects (newest first)
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_projects_subject_keyset
        ON projects (subject_id, archived_at, created_at DESC, id)
        """
    )
    # Idempotency-Key dedupe: one project per (subject, key) when a key is sent.
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_projects_subject_idempotency
        ON projects (subject_id, idempotency_key)
        WHERE idempotency_key IS NOT NULL
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS project_sessions (
            project_id  UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            chat_id     UUID NOT NULL REFERENCES raw_chats(id) ON DELETE CASCADE,
            added_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (project_id, chat_id)
        )
        """
    )
    # reverse lookup: which projects is this chat in?
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_project_sessions_chat ON project_sessions(chat_id)"
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS portfolio_ack (
            subject_id      UUID NOT NULL REFERENCES subjects(subject_id) ON DELETE CASCADE,
            scope           TEXT NOT NULL,
            snapshot_hash   TEXT NOT NULL,
            acked_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (subject_id, scope)
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS portfolio_ack")
    op.execute("DROP TABLE IF EXISTS project_sessions")
    op.execute("DROP TABLE IF EXISTS projects")
