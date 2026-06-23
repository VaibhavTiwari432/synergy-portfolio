"""
scripts/discovery/_common.py — shared helpers for the discovery-pass scripts.
OWNER: Chief Engineer.

The discovery pass is a mechanical self-audit (v3.21 Part 5 / §3). Each script is
NON-BLOCKING: it prints findings as warnings and exits 0 even when it finds
something — the CI job surfaces the warning, it never fails the build. A real hit
becomes a ready-to-paste `P-NNN [AUTO-PROPOSED]` stub printed to stdout (CI must
not mutate the tracked PROPOSALS.md without a commit, so we emit the stub rather
than write it in place).

Offline by design: the probes that need a score use a deterministic fake judge —
no network, no DB, no API keys — so they run on a clean CI checkout.
"""

from __future__ import annotations

import json
import pathlib

REPO = pathlib.Path(__file__).resolve().parents[2]


def warn(msg: str) -> None:
    print(f"::warning:: [discovery] {msg}")


def info(msg: str) -> None:
    print(f"[discovery] {msg}")


def proposal_stub(title: str, finding: str, domain: str) -> None:
    """Print a paste-ready AUTO-PROPOSED stub for PROPOSALS.md."""
    print(
        "\n--- AUTO-PROPOSED (paste into PROPOSALS.md, assign a P-NNN) ---\n"
        f"## P-NNN [AUTO-PROPOSED] — {title}\n"
        f"Found by: discovery harness.\n"
        f"Domain: {domain}.\n"
        f"Finding: {finding}\n"
        f"Status: AUTO-PROPOSED — needs CE triage.\n"
        "----------------------------------------------------------------\n"
    )


def fake_judge():
    """Deterministic offline judge: 0.5 every dim, ES absent (never zero, #12)."""
    from contracts.schemas import Dimension
    from src.trait.judge.client import JudgeClient

    entry = {"score": 0.5, "confidence": 0.8, "evidence_turns": [0], "tom_tag": None}
    data = {d.value: dict(entry) for d in Dimension}
    data["ES"]["score"] = None
    payload = json.dumps(data)
    return JudgeClient(generate=lambda s, u: payload, fallback=None, sleep=lambda _: None)


def first_gold_session():
    """Parse the first available anonymized gold chat into a CanonicalSession."""
    from src.ingestion.adapters import gold_json

    gold_dir = REPO / "data" / "gold" / "chats_anonymized"
    path = sorted(gold_dir.glob("gc-*.json"))[0]
    return gold_json.parse(json.loads(path.read_text(encoding="utf-8")))
