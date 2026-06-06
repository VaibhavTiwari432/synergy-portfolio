"""
Calibration — Gold Standard Loader.

Converts gold chat files (user/assistant turns, band annotations)
into the RawChat schema the pipeline consumes, and extracts human
band scores as comparable floats.

Band → float mapping (centre of each band's [0,1] range):
  low            → 0.25
  mid            → 0.55
  high           → 0.80
  not_applicable → None  (excluded from MAE, not zero)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from chat_classifier.schemas import RawChat, Turn

BAND_TO_FLOAT: dict[str, float | None] = {
    "low": 0.25,
    "mid": 0.55,
    "high": 0.80,
    "not_applicable": None,
}

DIMS = ["AL", "PR", "EC", "ES", "CS", "CD", "AUI", "CA"]


def load_gold_chat(path: str | Path) -> tuple[RawChat, dict[str, float | None]]:
    """
    Load a gold chat file.

    Returns:
        (RawChat, human_scores) where human_scores maps dimension → float | None.
        If multiple annotators exist, the first scorer_id is used.
    """
    import json

    with open(path, encoding="utf-8") as f:
        raw = json.load(f)

    chat = _to_raw_chat(raw)
    human_scores = _extract_scores(raw)
    return chat, human_scores


def _to_raw_chat(raw: dict[str, Any]) -> RawChat:
    """Convert gold format (user/assistant + content) to RawChat."""
    turns: list[Turn] = []
    for t in raw.get("turns", []):
        role_raw = t.get("role", "")
        role = "human" if role_raw == "user" else "ai"
        turns.append(
            Turn(
                index=t.get("turn_index", len(turns)),
                role=role,
                text=t.get("content", ""),
            )
        )
    platform = raw.get("platform", "chatgpt")
    return RawChat(
        chat_id=raw.get("id", "unknown"),
        source_model=platform,
        turns=turns,
    )


def _extract_scores(raw: dict[str, Any]) -> dict[str, float | None]:
    """
    Extract dimension scores from the first annotation entry.
    Returns a dict mapping each dimension to a float or None.
    """
    annotations = raw.get("annotations", [])
    if not annotations:
        return {d: None for d in DIMS}
    bands = annotations[0].get("bands", {})
    return {
        dim: BAND_TO_FLOAT.get(bands.get(dim, "not_applicable"))
        for dim in DIMS
    }


def load_all_gold_chats(
    gold_dir: str | Path,
) -> list[tuple[str, RawChat, dict[str, float | None]]]:
    """
    Load all gc-*.json files from gold_dir.

    Returns list of (chat_id, RawChat, human_scores) sorted by chat_id.
    """
    gold_dir = Path(gold_dir)
    results = []
    for path in sorted(gold_dir.glob("gc-*.json")):
        chat, scores = load_gold_chat(path)
        results.append((chat.chat_id, chat, scores))
    return results
