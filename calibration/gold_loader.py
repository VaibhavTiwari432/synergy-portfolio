"""
calibration/gold_loader.py — gold corpus loader. OWNER: Chief Engineer.

Loads the 26-chat regression corpus (ADR-0003) with band targets:
low → 0.25, mid → 0.55, high → 0.80, not_applicable → None (excluded from
MAE, never zero) — the v1 mapping, kept verbatim so the ratchet compares
like-for-like. Judge-family conflicts (D-001) and the carried v1 OCR
exclusions are surfaced per chat so the runner can slice honestly.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from contracts.schemas import CanonicalSession, Dimension
from src.ingestion.adapters.gold_json import parse as parse_gold

GOLD_DIR = Path(__file__).resolve().parents[1] / "data" / "gold"

#: v1 band mapping (centre of each band's range) — frozen for ratchet continuity
BAND_TO_FLOAT: dict[str, float | None] = {
    "low": 0.25,
    "mid": 0.55,
    "high": 0.80,
    "not_applicable": None,
}


@dataclass(frozen=True)
class GoldChat:
    session: CanonicalSession
    targets: dict[Dimension, float | None]
    judge_family_conflict: bool   # D-001: excluded from the headline MAE
    ocr_excluded: bool            # carried v1 flag (in-chat calibration_excluded)


def _bands_of(raw: dict[str, Any]) -> dict[str, str]:
    annotations = raw.get("annotations")
    if isinstance(annotations, list):
        annotations = annotations[0] if annotations else {}
    if not isinstance(annotations, dict):
        return {}
    return annotations.get("bands", {}) or {}


def _targets_of(raw: dict[str, Any]) -> dict[Dimension, float | None]:
    bands = _bands_of(raw)
    return {
        dim: BAND_TO_FLOAT.get(bands.get(dim.value, "not_applicable"))
        for dim in Dimension
    }


@lru_cache(maxsize=1)
def _conflict_ids() -> frozenset[str]:
    metadata = json.loads((GOLD_DIR / "metadata.json").read_text(encoding="utf-8"))
    return frozenset(metadata["regression_suite"]["judge_family_conflicts"])


def load_gold_corpus(gold_dir: Path | None = None) -> list[GoldChat]:
    directory = (gold_dir or GOLD_DIR) / "chats"
    conflicts = _conflict_ids()
    corpus: list[GoldChat] = []
    for path in sorted(directory.glob("gc-*.json")):
        raw = json.loads(path.read_text(encoding="utf-8"))
        session = parse_gold(raw)
        corpus.append(
            GoldChat(
                session=session,
                targets=_targets_of(raw),
                judge_family_conflict=session.session_id in conflicts,
                ocr_excluded=bool(raw.get("calibration_excluded")),
            )
        )
    return corpus
