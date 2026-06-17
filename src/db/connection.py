"""
src/db/connection.py — async Postgres pool. OWNER: Chief Engineer.

One global pool shared by the FastAPI app and the scoring worker.
JSON/JSONB codecs are registered on every connection so callers can
pass Python dicts directly and receive them back without manual
json.dumps / json.loads.

DATABASE_URL env var overrides the default local-Docker DSN.
"""

from __future__ import annotations

import json
import logging
import os

import asyncpg

log = logging.getLogger(__name__)

DATABASE_URL: str = os.environ.get(
    "DATABASE_URL",
    "postgresql://saf:saf_local@localhost:5432/saf_brain",
)

_pool: asyncpg.Pool | None = None


async def _init_connection(conn: asyncpg.Connection) -> None:
    await conn.set_type_codec(
        "jsonb",
        encoder=json.dumps,
        decoder=json.loads,
        schema="pg_catalog",
    )
    await conn.set_type_codec(
        "json",
        encoder=json.dumps,
        decoder=json.loads,
        schema="pg_catalog",
    )


async def init_pool() -> None:
    global _pool
    _pool = await asyncpg.create_pool(DATABASE_URL, init=_init_connection)
    log.info("Postgres pool initialised (%s)", DATABASE_URL.split("@")[-1])


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("Postgres pool not initialised — call init_pool() first")
    return _pool


def get_pool_optional() -> asyncpg.Pool | None:
    """Returns None instead of raising — used by routes that degrade gracefully."""
    return _pool
