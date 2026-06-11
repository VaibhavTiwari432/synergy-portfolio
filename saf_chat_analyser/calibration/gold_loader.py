"""
Calibration — Gold Chat Loader.

Loads gold-standard annotated chats and extracts human dimension scores
for MAE calibration. Compatible with both the old schema (text field)
and the new schema (content field).

Band → float mapping (midpoint of each 0-1 band):
  low            → 0.25
  mid            → 0.55
  high           → 0.80
  not_applicable → None  (excluded from MAE, not zero)
"""

from __future__ import annotations

import json
from pathlib import Path

from saf_chat_analyser.src.parser.transcript_parser import Turn

BAND_TO_FLOAT: dict[str, float | None] = {
    "low":            0.25,
    "mid":            0.55,
    "high":           0.80,
    "not_applicable": None,
}

DIMS = ["AL", "PR", "EC", "ES", "CS", "CD", "AUI", "CA"]

# Paths — relative to package root
_DEFAULT_GOLD_DIR = Path(__file__).parents[2] / "gold_standard" / "chats"
_ALT_GOLD_DIR = Path(__file__).parents[2] / "data" / "gold_chats"


def load_gold_chat(
    path: str | Path,
) -> tuple[list[Turn], dict[str, float | None]]:
    """
    Load one gold chat file.

    Returns:
        (list[Turn], human_scores) where human_scores maps dim → float | None.
        Uses the first annotation entry if multiple annotators are present.
    """
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)

    turns = _to_turns(raw)
    scores = _extract_scores(raw)
    return turns, scores


def _to_turns(raw: dict) -> list[Turn]:
    turns: list[Turn] = []
    for t in raw.get("turns", []):
        role_raw = t.get("role", "")
        role = "human" if role_raw in ("user", "human") else "ai"
        # Accept both 'content' (new) and 'text' (old schema)
        content = (t.get("content") or t.get("text") or "").strip()
        if not content:
            continue
        turns.append(
            Turn(
                index=t.get("turn_index", t.get("index", len(turns))),
                role=role,
                content=content,
                word_count=len(content.split()),
            )
        )
    return turns


def _extract_scores(raw: dict) -> dict[str, float | None]:
    annotations = raw.get("annotations", [])
    if not annotations:
        return {d: None for d in DIMS}
    bands = annotations[0].get("bands", {})
    return {
        dim: BAND_TO_FLOAT.get(bands.get(dim, "not_applicable"))
        for dim in DIMS
    }


def load_all_gold_chats(
    gold_dir: str | Path | None = None,
) -> list[tuple[str, list[Turn], dict[str, float | None]]]:
    """
    Load all gc-*.json files from the gold directory.

    Returns list of (chat_id, turns, human_scores) sorted by chat_id.
    Falls back to the alternative directory if the primary doesn't exist.
    """
    if gold_dir is None:
        gold_dir = _DEFAULT_GOLD_DIR if _DEFAULT_GOLD_DIR.exists() else _ALT_GOLD_DIR
    gold_dir = Path(gold_dir)
    if not gold_dir.exists():
        raise FileNotFoundError(
            f"Gold chat directory not found: {gold_dir}. "
            "Place annotated gc-*.json files there."
        )

    results = []
    for path in sorted(gold_dir.glob("gc-*.json")):
        turns, scores = load_gold_chat(path)
        raw = json.loads(path.read_text(encoding="utf-8"))
        chat_id = raw.get("id") or raw.get("chat_id") or path.stem
        results.append((str(chat_id), turns, scores))
    return results
