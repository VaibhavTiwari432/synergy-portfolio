"""
src/api/store.py — session/score persistence. OWNER: Chief Engineer.

SQLite via the stdlib, storing canonical sessions and score responses as JSON
blobs keyed by session_id. Postgres-ready in the sense that matters now: all
access goes through this one class, so swapping in SQLAlchemy models later
touches nothing else. Deletion propagates to derived rows (data dignity #16).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from contracts.schemas import CanonicalSession, ScoreResponse

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    user_ref   TEXT,
    session_json TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS scores (
    session_id TEXT PRIMARY KEY REFERENCES sessions(session_id) ON DELETE CASCADE,
    score_json TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_ref);
"""


class SessionStore:
    def __init__(self, path: str | Path = ":memory:") -> None:
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.executescript(_SCHEMA)

    # ── sessions ──
    def put_session(self, session: CanonicalSession) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO sessions (session_id, user_ref, session_json) VALUES (?, ?, ?)",
            (session.session_id, session.user_ref, session.model_dump_json()),
        )
        self._conn.commit()

    def get_session(self, session_id: str) -> CanonicalSession | None:
        row = self._conn.execute(
            "SELECT session_json FROM sessions WHERE session_id = ?", (session_id,)
        ).fetchone()
        return CanonicalSession.model_validate_json(row[0]) if row else None

    # ── scores ──
    def put_score(self, response: ScoreResponse) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO scores (session_id, score_json) VALUES (?, ?)",
            (response.session_id, response.model_dump_json(by_alias=True)),
        )
        self._conn.commit()

    def get_score(self, session_id: str) -> ScoreResponse | None:
        row = self._conn.execute(
            "SELECT score_json FROM scores WHERE session_id = ?", (session_id,)
        ).fetchone()
        return ScoreResponse.model_validate_json(row[0]) if row else None

    # ── trajectory support ──
    def scores_for_user(self, user_ref: str) -> list[ScoreResponse]:
        rows = self._conn.execute(
            "SELECT sc.score_json FROM scores sc JOIN sessions s USING(session_id) "
            "WHERE s.user_ref = ? ORDER BY s.created_at, s.session_id",
            (user_ref,),
        ).fetchall()
        return [ScoreResponse.model_validate_json(r[0]) for r in rows]

    # ── data dignity ──
    def delete_user(self, user_ref: str) -> int:
        """Deletion propagates: scores cascade with their sessions (#16)."""
        cur = self._conn.execute("DELETE FROM sessions WHERE user_ref = ?", (user_ref,))
        self._conn.commit()
        return cur.rowcount
