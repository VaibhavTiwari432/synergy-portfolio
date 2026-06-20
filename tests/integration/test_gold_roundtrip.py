"""First integration target (brief §5 Stage 1 CE): every gold chat round-trips
losslessly through ingestion into the event log. OWNER: Chief Engineer.

Lossless means: turn count preserved, order preserved, text byte-identical,
role mapping bijective (user↔human, assistant↔ai), platform → partner family
correct — and the original gold turn list is reconstructable from the
CanonicalSession exactly.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.eventlog.writer import new_log
from src.ingestion.canonical import ingest

GOLD_DIR = Path(__file__).resolve().parents[2] / "data" / "gold" / "chats"
GOLD_FILES = sorted(GOLD_DIR.glob("gc-*.json"))

_ROLE_BACK = {"human": "user", "ai": "assistant"}
_FAMILY_EXPECTED = {"chatgpt": "openai", "gemini": "google", "claude": "anthropic"}


def test_gold_corpus_has_26_chats():
    assert len(GOLD_FILES) == 26  # ADR-0003: gc-014/gc-015 are rationale-only


@pytest.mark.parametrize("path", GOLD_FILES, ids=[p.stem for p in GOLD_FILES])
def test_gold_chat_round_trips_losslessly(path: Path):
    raw = json.loads(path.read_text(encoding="utf-8"))
    session = ingest(raw)

    # identity + provenance
    assert session.session_id == raw["id"] == path.stem
    assert session.source == "gold_json"
    assert session.partner_model.family == _FAMILY_EXPECTED[raw["platform"]]

    # losslessness: count, order, text, roles
    assert len(session.turns) == len(raw["turns"])
    reconstructed = [
        {"role": _ROLE_BACK[t.role], "content": t.text, "turn_index": t.index}
        for t in session.turns
    ]
    original = [
        {"role": rt["role"], "content": rt["content"], "turn_index": i}
        for i, rt in enumerate(raw["turns"])
    ]
    assert reconstructed == original

    # the event log materializes from the canonical session
    log = new_log(session)
    assert log.session_id == session.session_id
    assert len(log) == 0  # detectors fill it; turns are not events


def test_gold_corpus_partner_family_census():
    families: dict[str, list[str]] = {}
    for path in GOLD_FILES:
        raw = json.loads(path.read_text(encoding="utf-8"))
        session = ingest(raw)
        families.setdefault(session.partner_model.family, []).append(session.session_id)

    # judge family is google (Gemini): these chats conflict (ADR-0002 / D-001)
    assert sorted(families.get("google", [])) == ["gc-003", "gc-016", "gc-018"]
    assert len(families.get("openai", [])) == 23
    assert "anthropic" not in families
    assert "unknown" not in families
