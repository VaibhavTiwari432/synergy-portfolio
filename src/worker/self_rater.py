"""
src/worker/self_rater.py — side-channel model self-rating. OWNER: Chief Engineer.

Fires AFTER scoring, async and non-blocking.
Uses a SERVER-SIDE OpenAI API key (OPENAI_API_KEY env secret), passed in by the
worker. Per-user keys never enter the corpus (Track 0 credential-at-rest fix).
Key absent or malformed JSON → skip silently, set status='skipped'.
Batch calls: 1-second delay between them (never fire all at once).
Result stored as self_rating_raw — NEVER shown to user in any form (#10).

Non-negotiables enforced here:
  - Key never appears in logs or error messages (#key-safety).
  - self_rating_raw never surfaced through any API path.
  - 1-second delay between bulk calls.
  - Skips silently when key is absent.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
from uuid import UUID

import asyncpg

from src.db.queries import update_self_rating, upsert_turn_model_rating

SELF_RATING_PROMPT_VERSION = "v1.0"
SELF_RATING_PROMPT_PATH = Path(__file__).parent.parent.parent / "contracts" / "self_rating_prompt.txt"
SELF_RATING_MODEL = os.environ.get("SELF_RATING_MODEL", "gpt-4o-mini")

log = logging.getLogger(__name__)

_prompt_template: str | None = None


def _get_prompt_template() -> str:
    global _prompt_template
    if _prompt_template is None:
        _prompt_template = SELF_RATING_PROMPT_PATH.read_text(encoding="utf-8")
    return _prompt_template


def _build_transcript(turns: list[dict]) -> str:
    lines: list[str] = []
    for t in turns:
        role = t.get("role", "user")
        label = "Human" if role in ("user", "human") else "AI"
        lines.append(f"{label}: {t.get('text', '')}")
    return "\n\n".join(lines)


def _human_turn_indices(turns: list[dict]) -> list[int]:
    indices: list[int] = []
    for i, turn in enumerate(turns):
        role = turn.get("role", "user")
        if role in ("user", "human"):
            indices.append(int(turn.get("turn_index", turn.get("index", i))))
    return indices


async def _request_rating(openai_key: str, transcript: str) -> dict:
    from openai import AsyncOpenAI

    prompt = _get_prompt_template().replace("{transcript}", transcript)
    client = AsyncOpenAI(api_key=openai_key)
    response = await client.chat.completions.create(
        model=SELF_RATING_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        max_tokens=256,
    )
    raw_text = response.choices[0].message.content or ""
    return json.loads(raw_text)


async def request_self_rating(
    pool: asyncpg.Pool,
    chat_id: UUID,
    turns: list[dict],
    openai_key: str | None,
) -> None:
    """Entry point called from the scorer after scoring completes.

    If openai_key is absent: mark skipped immediately.
    If the model returns malformed JSON: store null, mark skipped.
    """
    if not openai_key:
        await update_self_rating(
            pool,
            chat_id=chat_id,
            self_rating_raw=None,
            self_rating_prompt_version=None,
            status="skipped",
        )
        return

    await _rate_with_delay(pool, chat_id, turns, openai_key)


async def _rate_with_delay(
    pool: asyncpg.Pool,
    chat_id: UUID,
    turns: list[dict],
    openai_key: str,
) -> None:
    """1-second guard so bulk imports don't fire all calls simultaneously."""
    await asyncio.sleep(1)

    try:
        transcript = _build_transcript(turns)
        rating = await _request_rating(openai_key, transcript)

        # Key never logged — pass directly, never format into a log string
        await update_self_rating(
            pool,
            chat_id=chat_id,
            self_rating_raw=rating,
            self_rating_prompt_version=SELF_RATING_PROMPT_VERSION,
            status="received",
        )
        log.info("[SELF-RATER] received rating for %s", chat_id)

        for turn_index in _human_turn_indices(turns):
            prefix = [
                turn for turn in turns
                if int(turn.get("turn_index", turn.get("index", 0))) <= turn_index
            ]
            try:
                turn_rating = await _request_rating(openai_key, _build_transcript(prefix))
                await upsert_turn_model_rating(
                    pool,
                    chat_id=chat_id,
                    turn_index=turn_index,
                    rating_raw=turn_rating,
                    prompt_version=SELF_RATING_PROMPT_VERSION,
                    status="received",
                )
            except json.JSONDecodeError:
                await upsert_turn_model_rating(
                    pool,
                    chat_id=chat_id,
                    turn_index=turn_index,
                    rating_raw=None,
                    prompt_version=SELF_RATING_PROMPT_VERSION,
                    status="skipped",
                )
            await asyncio.sleep(1)

    except json.JSONDecodeError:
        log.warning("[SELF-RATER] malformed JSON from model for %s — skipping", chat_id)
        await update_self_rating(
            pool,
            chat_id=chat_id,
            self_rating_raw=None,
            self_rating_prompt_version=SELF_RATING_PROMPT_VERSION,
            status="skipped",
        )
    except Exception as exc:
        # Log the class name only — never the key or the full exception message
        # in case it contains the key in a repr
        log.warning(
            "[SELF-RATER] %s for chat %s — skipping",
            type(exc).__name__, chat_id,
        )
        await update_self_rating(
            pool,
            chat_id=chat_id,
            self_rating_raw=None,
            self_rating_prompt_version=SELF_RATING_PROMPT_VERSION,
            status="skipped",
        )
