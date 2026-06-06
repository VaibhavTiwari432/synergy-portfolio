"""
Calibration Runner.

Runs all gold chats through the full pipeline, compares judge dimension
scores against human band scores, and reports per-dimension MAE and
overall mean MAE.

Target (from spec): MAE <= 1.5 on the 0-4 ordinal scale, which maps
to <= 0.375 on the 0.0-1.0 float scale (1.5 / 4.0 = 0.375).

Usage:
    python -m chat_classifier.calibration.runner
    python -m chat_classifier.calibration.runner --limit 5   # first 5 chats only
    python -m chat_classifier.calibration.runner --dry-run   # loader only, no API calls
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import warnings
from collections import defaultdict
from pathlib import Path

GOLD_DIR = Path(__file__).parent.parent.parent / "gold_standard" / "chats"
REPORT_DIR = Path(__file__).parent.parent.parent / "calibration" / "reports"
MAE_TARGET = 0.375   # 1.5 / 4.0 — spec target translated to float scale
DIMS = ["AL", "PR", "EC", "ES", "CS", "CD", "AUI", "CA"]


def run_calibration(limit: int | None = None, dry_run: bool = False) -> dict:
    """
    Run the calibration loop.

    Returns a results dict with per-chat and per-dimension scores.
    """
    import os
    from chat_classifier.calibration.gold_loader import load_all_gold_chats
    from chat_classifier.flags.risk_evaluator import evaluate_flags
    from chat_classifier.schemas import SynergyReport
    from chat_classifier.scorer.composite_metrics import compute_metrics
    from chat_classifier.scorer.gemini_judge import GeminiJudge
    from chat_classifier.aggregator.dimension_aggregator import aggregate
    from chat_classifier.tagger.intent_tagger import intent_counts, tag_chat
    from chat_classifier.tagger.phase_classifier import classify_phases
    from chat_classifier.config import DIMENSION_WEIGHTS

    gold = load_all_gold_chats(GOLD_DIR)
    if limit:
        gold = gold[:limit]

    print(f"Loaded {len(gold)} gold chats.")

    if dry_run:
        print("Dry-run: skipping API calls.")
        for chat_id, chat, human_scores in gold:
            print(f"  {chat_id}  turns={len(chat.turns)}  human={human_scores}")
        return {}

    judge = GeminiJudge()

    per_chat: list[dict] = []
    dim_errors: dict[str, list[float]] = defaultdict(list)

    for i, (chat_id, chat, human_scores) in enumerate(gold, 1):
        print(f"[{i}/{len(gold)}] {chat_id} ({len(chat.turns)} turns) ...", end=" ", flush=True)

        try:
            tagged = tag_chat(chat)
            counts = intent_counts(tagged)
            phase_dist = classify_phases(tagged)
            metrics = compute_metrics(chat, tagged)

            with warnings.catch_warnings(record=True):
                warnings.simplefilter("always")
                judge_out = judge.score(chat, tagged, metrics, phase_dist, counts)

            report = SynergyReport(
                session_id=chat_id,
                transcript_turns=len(chat.turns),
                neuron_scores=judge_out.neuron_scores,
                composite_metrics=metrics,
                intent_tag_counts=counts,
                phase_distribution=phase_dist,
                coverage={
                    "scored": sum(1 for v in judge_out.neuron_scores.values() if v > 0),
                    "total": len(judge_out.neuron_scores),
                },
            )
            report = aggregate(judge_out.neuron_scores, report)
            report.risk_flags = evaluate_flags(judge_out.neuron_scores, metrics)

            # Compute per-dimension MAE (raw, unweighted scores vs human bands)
            chat_errors: dict[str, float | None] = {}
            for dim in DIMS:
                human_val = human_scores.get(dim)
                if human_val is None:
                    chat_errors[dim] = None
                    continue
                w = DIMENSION_WEIGHTS[dim]
                judge_ws = report.dimension_scores.get(dim)
                if judge_ws is None:
                    chat_errors[dim] = None
                    continue
                judge_raw = judge_ws / w
                err = abs(judge_raw - human_val)
                chat_errors[dim] = round(err, 4)
                dim_errors[dim].append(err)

            per_chat.append({
                "chat_id": chat_id,
                "turns": len(chat.turns),
                "human_scores": human_scores,
                "judge_raw": {
                    dim: round(report.dimension_scores[dim] / DIMENSION_WEIGHTS[dim], 4)
                    if report.dimension_scores.get(dim) is not None else None
                    for dim in DIMS
                },
                "errors": chat_errors,
                "g_synergy": report.synergy_score_kappa,
                "risk_flags": report.risk_flags,
                "coverage": report.coverage["scored"],
            })
            print("ok  g_kappa=%.3f" % (report.synergy_score_kappa or 0))

        except Exception as exc:
            print(f"FAILED: {exc}")
            per_chat.append({"chat_id": chat_id, "error": str(exc)})

        # Brief pause between calls to avoid rate limits
        if i < len(gold):
            time.sleep(2)

    # Aggregate MAE per dimension
    dim_mae: dict[str, float | None] = {}
    for dim in DIMS:
        errs = dim_errors.get(dim, [])
        dim_mae[dim] = round(sum(errs) / len(errs), 4) if errs else None

    scorable_maes = [v for v in dim_mae.values() if v is not None]
    overall_mae = round(sum(scorable_maes) / len(scorable_maes), 4) if scorable_maes else None

    results = {
        "n_chats": len(per_chat),
        "mae_target": MAE_TARGET,
        "overall_mae": overall_mae,
        "target_met": (overall_mae is not None and overall_mae <= MAE_TARGET),
        "dim_mae": dim_mae,
        "per_chat": per_chat,
    }

    # Save report
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    from datetime import datetime
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = REPORT_DIR / f"calibration_{ts}.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"\nReport saved: {report_path}")

    return results


def print_summary(results: dict) -> None:
    if not results:
        return
    print("\n" + "=" * 56)
    print("CALIBRATION SUMMARY")
    print("=" * 56)
    print(f"  Chats scored  : {results['n_chats']}")
    print(f"  Overall MAE   : {results['overall_mae']}  (target <= {results['mae_target']})")
    print(f"  Target met    : {'YES' if results['target_met'] else 'NO'}")
    print()
    print("  DIM    MAE")
    print("  " + "-" * 20)
    for dim, mae in results["dim_mae"].items():
        marker = " <-- MISS" if mae is not None and mae > results["mae_target"] else ""
        print(f"  {dim:<5}  {('%.4f' % mae) if mae is not None else 'N/A'}{marker}")
    print("=" * 56)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ARI calibration runner")
    parser.add_argument("--limit", type=int, default=None, help="Run only first N chats")
    parser.add_argument("--dry-run", action="store_true", help="Loader only, no API calls")
    args = parser.parse_args()

    results = run_calibration(limit=args.limit, dry_run=args.dry_run)
    print_summary(results)
