"""
calibration/drift_check.py — frozen-anchor re-score for judge-drift detection.
OWNER: Chief Engineer.

Runs the current judge on the FROZEN gold anchor set, compares overall MAE to the
ratchet baseline, and produces a drift_runs row. A MAE rise > DRIFT_THRESHOLD on
the anchor set = judge drift (the instrument moved), NOT subject change. This is a
CI/cron job — it never blocks a user request, and drift_detected=True is a
WARNING signal, not a release block (CLAUDE.md #18; v3.21 §8.6).

The drift COMPUTE is a pure function over an injected score_fn (the same seam the
calibration runner uses), so it is testable offline without a live judge.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from contracts.schemas import CanonicalSession, Dimension
from calibration.gold_loader import GoldChat, load_gold_corpus
from calibration.runner import run_calibration

#: The frozen anchor set. NEVER add/remove a chat without a new ADR — the whole
#: point is that the instrument is measured against an unchanging stimulus. These
#: deliberately exclude the judge-family-conflict chats (gc-003/016/018, ADR-0002).
ANCHOR_CHAT_IDS: list[str] = [
    "gc-001", "gc-002", "gc-004", "gc-005", "gc-006",
    "gc-007", "gc-008", "gc-009", "gc-010", "gc-011",
]

#: MAE rise above the ratchet baseline (on the anchor set) that flags drift.
DRIFT_THRESHOLD = 0.05

#: Where the ratchet baseline MAE is read from when not supplied explicitly.
_BASELINE_RESULTS = Path(__file__).parent / "results" / "stage2_rejudged.json"


def baseline_mae_from_results(path: Path = _BASELINE_RESULTS) -> float | None:
    """The frozen ratchet baseline overall MAE (shadow pool). None if absent."""
    if not path.exists():
        return None
    data = json.loads(path.read_text())
    return data.get("shadow", {}).get("overall_mae")


def compute_drift(
    score_fn: Callable[[CanonicalSession], dict[Dimension, float | None]],
    *,
    baseline_mae: float | None,
    judge_model_id: str,
    prompt_version: str,
    corpus: list[GoldChat] | None = None,
    anchors: list[str] | None = None,
    threshold: float = DRIFT_THRESHOLD,
) -> dict:
    """Re-score the anchor set with score_fn and compare MAE to baseline_mae.

    Pure: no DB, no network beyond whatever score_fn does. Returns a dict shaped
    for `insert_drift_run`. drift_detected is True only when both MAEs are present
    AND (anchor_mae - baseline_mae) > threshold — a missing baseline or an
    unscorable anchor set yields drift_detected=None (unknown, never a false
    'no drift'; absent ≠ zero, #12)."""
    anchor_ids = anchors or ANCHOR_CHAT_IDS
    full = corpus or load_gold_corpus()
    wanted = set(anchor_ids)
    anchor_corpus = [g for g in full if g.session.session_id in wanted]

    result = run_calibration(score_fn, anchor_corpus)
    mae_overall = result["shadow"]["overall_mae"]
    mae_per_dim = result["shadow"]["per_dim_mae"]

    if mae_overall is None or baseline_mae is None:
        drift_detected: bool | None = None
        note = (
            "indeterminate — "
            + ("anchor set unscorable" if mae_overall is None else "no baseline MAE")
        )
    else:
        delta = mae_overall - baseline_mae
        drift_detected = delta > threshold
        note = (
            f"anchor MAE {mae_overall:.4f} vs baseline {baseline_mae:.4f} "
            f"(Δ={delta:+.4f}, threshold {threshold:.2f}) → "
            + ("DRIFT" if drift_detected else "stable")
        )

    return {
        "judge_model_id": judge_model_id,
        "prompt_version": prompt_version,
        "anchor_set": list(anchor_ids),
        "mae_overall": mae_overall,
        "mae_per_dimension": mae_per_dim,
        "baseline_mae": baseline_mae,
        "drift_detected": drift_detected,
        "drift_note": note,
    }
