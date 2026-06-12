"""
calibration/runner.py — the MAE ratchet (release gate). OWNER: Chief Engineer.

Ratchet (brief §2.3, non-negotiable #18): overall MAE ≤ 0.2994; per-dimension
≤ 0.375 with EC TRACKED SEPARATELY (EC is a data problem — #19; it reports
but does not gate). Per D-001 the runner reports TWO numbers:

- headline: the judge-family-clean set (gc-003/016/018 excluded)
- shadow:   all 26 chats — the like-for-like comparison with the v1.3
            baseline (which included the conflicted chats)

The ratchet gate fires on the SHADOW number (same corpus as v1.3); the
headline is the going-forward reference once re-judging lands. Pairs where
the gold target is None (not_applicable) or the prediction is None
(N/A / INSUFFICIENT_SAMPLE) are excluded from MAE — absent ≠ zero — and the
absent-prediction count is reported as coverage.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from contracts.schemas import CanonicalSession, Dimension
from calibration.gold_loader import GoldChat, load_gold_corpus

MAE_RATCHET = 0.2994
PER_DIM_TARGET = 0.375

#: a scorer maps a session to per-dimension predictions in [0,1] (None = N/A)
ScoreFn = Callable[[CanonicalSession], dict[Dimension, float | None]]

REPORTS_DIR = Path(__file__).resolve().parent / "reports"


@dataclass
class ChatRow:
    chat_id: str
    judge_family_conflict: bool
    ocr_excluded: bool
    abs_errors: dict[str, float] = field(default_factory=dict)
    missing_predictions: list[str] = field(default_factory=list)


def _mae(rows: list[ChatRow]) -> tuple[float | None, dict[str, float | None]]:
    by_dim: dict[str, list[float]] = {d.value: [] for d in Dimension}
    for row in rows:
        for dim, err in row.abs_errors.items():
            by_dim[dim].append(err)
    per_dim = {
        dim: (sum(errs) / len(errs) if errs else None) for dim, errs in by_dim.items()
    }
    all_errors = [e for errs in by_dim.values() for e in errs]
    overall = sum(all_errors) / len(all_errors) if all_errors else None
    return overall, per_dim


def run_calibration(
    score_fn: ScoreFn,
    corpus: list[GoldChat] | None = None,
) -> dict:
    corpus = corpus if corpus is not None else load_gold_corpus()
    rows: list[ChatRow] = []

    for gold in corpus:
        row = ChatRow(
            chat_id=gold.session.session_id,
            judge_family_conflict=gold.judge_family_conflict,
            ocr_excluded=gold.ocr_excluded,
        )
        predictions = score_fn(gold.session)
        for dim in Dimension:
            target = gold.targets[dim]
            if target is None:
                continue  # not_applicable gold — excluded, never zero
            pred = predictions.get(dim)
            if pred is None:
                row.missing_predictions.append(dim.value)
                continue
            row.abs_errors[dim.value] = abs(pred - target)
        rows.append(row)

    shadow_overall, shadow_per_dim = _mae(rows)
    headline_rows = [r for r in rows if not r.judge_family_conflict]
    headline_overall, headline_per_dim = _mae(headline_rows)

    # the gate: shadow corpus (v1.3-comparable); EC tracked separately (#19)
    gating_dims = {
        d: m for d, m in (shadow_per_dim or {}).items() if d != Dimension.EC.value
    }
    ratchet_passed = (
        shadow_overall is not None
        and shadow_overall <= MAE_RATCHET
        and all(m is None or m <= PER_DIM_TARGET for m in gating_dims.values())
    )

    return {
        "ratchet": MAE_RATCHET,
        "ratchet_passed": ratchet_passed,
        "shadow": {
            "n_chats": len(rows),
            "overall_mae": shadow_overall,
            "per_dim_mae": shadow_per_dim,
        },
        "headline": {
            "n_chats": len(headline_rows),
            "overall_mae": headline_overall,
            "per_dim_mae": headline_per_dim,
            "excluded_conflicts": [r.chat_id for r in rows if r.judge_family_conflict],
        },
        "ec_tracked_separately": {
            "shadow_mae": (shadow_per_dim or {}).get(Dimension.EC.value),
            "headline_mae": (headline_per_dim or {}).get(Dimension.EC.value),
        },
        "coverage": {
            r.chat_id: {"missing": r.missing_predictions}
            for r in rows
            if r.missing_predictions
        },
        "per_chat": [
            {
                "chat_id": r.chat_id,
                "judge_family_conflict": r.judge_family_conflict,
                "ocr_excluded": r.ocr_excluded,
                "abs_errors": r.abs_errors,
            }
            for r in rows
        ],
    }


def main() -> None:  # pragma: no cover — CLI; needs a judge API key
    from src.api.pipeline import judge_score_fn

    result = run_calibration(judge_score_fn())
    REPORTS_DIR.mkdir(exist_ok=True)
    out = REPORTS_DIR / f"calibration_{time.strftime('%Y%m%d_%H%M%S')}.json"
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("ratchet_passed", "shadow", "headline")}, indent=2))
    print(f"report: {out}")


if __name__ == "__main__":  # pragma: no cover
    main()
