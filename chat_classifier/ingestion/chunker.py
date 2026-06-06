"""
Phase 1 — 3-turn sliding-window chunker.
Produces a list of Chunk objects from a RawChat.

A Chunk carries its window of Turn objects plus a chunk_index for
downstream join back to ItemResponse.
"""

from __future__ import annotations

from chat_classifier.config import DEFAULT_STRIDE, DEFAULT_WINDOW_SIZE
from chat_classifier.schemas import Chunk, RawChat


def chunk(
    chat: RawChat,
    window: int = DEFAULT_WINDOW_SIZE,
    stride: int = DEFAULT_STRIDE,
) -> list[Chunk]:
    """
    Slice a RawChat into overlapping Chunk windows.

    Args:
        chat:   the normalised RawChat
        window: number of turns per chunk (default 3)
        stride: step size between chunk starts (default 1, i.e. full overlap)

    Returns:
        Ordered list of Chunk objects.
        A 20-turn chat with window=3, stride=1 yields 18 chunks
        (turns 0-2, 1-3, ..., 17-19).
        A chat with fewer turns than window yields a single chunk
        containing all turns.

    Edge cases:
        - Empty or single-turn chat: one chunk with all available turns.
        - window <= 0 or stride <= 0: raises ValueError.
    """
    if window <= 0:
        raise ValueError(f"window must be > 0, got {window}")
    if stride <= 0:
        raise ValueError(f"stride must be > 0, got {stride}")

    turns = chat.turns
    n = len(turns)

    if n == 0:
        return []

    chunks: list[Chunk] = []
    start = 0
    chunk_idx = 0

    while start < n:
        end = min(start + window - 1, n - 1)   # inclusive
        window_turns = turns[start : end + 1]
        chunks.append(
            Chunk(
                chunk_index=chunk_idx,
                turn_start=start,
                turn_end=end,
                turns=window_turns,
            )
        )
        chunk_idx += 1
        if end >= n - 1:
            break
        start += stride

    return chunks
