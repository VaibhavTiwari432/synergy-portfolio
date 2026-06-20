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
(N/A / INSUFFICIENT_SAMPLE) are excluded from MAE — absent ≠ zero.

D-002 coverage gate: a missing prediction is an ERROR, not a skip. A chat
where the judge was unavailable or returned fewer than MIN_VALID_DIMS valid
dimension scores is excluded from MAE entirely and counted against coverage.
Gate A = MAE ≤ 0.2994 AND headline-pool coverage ≥ COVERAGE_FLOOR_PCT — a
near-empty run can never pass on a lucky MAE.
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

#: D-002 coverage gate: a chat with fewer valid dimension scores than this is
#: a failed observation — excluded from MAE, counted against coverage
MIN_VALID_DIMS = 4
#: Gate A fails when headline-pool coverage drops below this, regardless of MAE
COVERAGE_FLOOR_PCT = 80.0

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
    excluded: dict[str, str] = {}  # chat_id -> exclusion reason (D-002)

    for gold in corpus:
        row = ChatRow(
            chat_id=gold.session.session_id,
            judge_family_conflict=gold.judge_family_conflict,
            ocr_excluded=gold.ocr_excluded,
        )
        predictions = score_fn(gold.session)

        # D-002 coverage gate: a chat whose judge produced fewer than
        # MIN_VALID_DIMS valid scores is not a partial observation — it is a
        # failed observation. Excluded from MAE, counted against coverage.
        valid_dims = sum(1 for dim in Dimension if predictions.get(dim) is not None)
        if valid_dims < MIN_VALID_DIMS:
            excluded[row.chat_id] = (
                f"only {valid_dims}/8 dimensions returned valid scores "
                f"(judge unavailable or degenerate output)"
            )
            rows.append(row)  # kept for per-chat reporting; no errors recorded
            continue

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

    scored_rows = [r for r in rows if r.chat_id not in excluded]
    shadow_overall, shadow_per_dim = _mae(scored_rows)
    headline_rows = [r for r in scored_rows if not r.judge_family_conflict]
    headline_overall, headline_per_dim = _mae(headline_rows)

    # coverage over the headline pool (D-002): scored ÷ pool
    headline_pool = [r for r in rows if not r.judge_family_conflict]
    shadow_pool = rows
    headline_coverage = (
        100.0 * len(headline_rows) / len(headline_pool) if headline_pool else 0.0
    )
    shadow_coverage = (
        100.0 * len(scored_rows) / len(shadow_pool) if shadow_pool else 0.0
    )

    # the gate: shadow corpus MAE (v1.3-comparable) + per-dim (EC tracked
    # separately, #19) + headline coverage floor (D-002)
    gating_dims = {
        d: m for d, m in (shadow_per_dim or {}).items() if d != Dimension.EC.value
    }
    ratchet_passed = (
        shadow_overall is not None
        and shadow_overall <= MAE_RATCHET
        and all(m is None or m <= PER_DIM_TARGET for m in gating_dims.values())
        and headline_coverage >= COVERAGE_FLOOR_PCT
    )

    return {
        "ratchet": MAE_RATCHET,
        "coverage_floor_pct": COVERAGE_FLOOR_PCT,
        "ratchet_passed": ratchet_passed,
        "shadow": {
            "n_chats": len(shadow_pool),
            "n_scored": len(scored_rows),
            "n_excluded": len(shadow_pool) - len(scored_rows),
            "coverage_pct": round(shadow_coverage, 1),
            "overall_mae": shadow_overall,
            "per_dim_mae": shadow_per_dim,
        },
        "headline": {
            "n_chats": len(headline_pool),
            "n_scored": len(headline_rows),
            "n_excluded": len(headline_pool) - len(headline_rows),
            "coverage_pct": round(headline_coverage, 1),
            "overall_mae": headline_overall,
            "per_dim_mae": headline_per_dim,
            "excluded_conflicts": [r.chat_id for r in rows if r.judge_family_conflict],
        },
        "ec_tracked_separately": {
            "shadow_mae": (shadow_per_dim or {}).get(Dimension.EC.value),
            "headline_mae": (headline_per_dim or {}).get(Dimension.EC.value),
        },
        "excluded_chats": excluded,
        "coverage": {
            r.chat_id: {"missing": r.missing_predictions}
            for r in scored_rows
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
