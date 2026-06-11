"""
Calibration Runner.

Runs the pipeline (stages 1-6) against all gold chats and reports:
  - Per-dimension MAE (judge vs human band scores)
  - Overall MAE
  - EC N/A rate
  - Pass/fail against targets from §7.3

Current calibration targets (SAF §7.3, §7.4):
  Overall MAE ≤ 0.375    (currently 0.2994 — passing)
  EC MAE ≤ 0.300         (currently 0.4073 — failing; needs ≥40 gold chats)
  EC N/A rate ≤ 4/23

Usage:
    python -m saf_chat_analyser.calibration.runner [--gold-dir path]
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2]))

from saf_chat_analyser.calibration.gold_loader import load_all_gold_chats, DIMS
from saf_chat_analyser.src.tagger.intent_tagger import tag_turns, intent_counts
from saf_chat_analyser.src.tagger.phase_classifier import classify_phases
from saf_chat_analyser.src.metrics.composite_metrics import compute_metrics
from saf_chat_analyser.src.scorer.gemini_judge import GeminiJudge
from saf_chat_analyser.src.aggregator.dimension_aggregator import aggregate

# Calibration targets
_TARGET_MAE_OVERALL = 0.375
_TARGET_MAE_EC = 0.300
_TARGET_EC_NA_RATE = 4   # max N/A out of 23+ gold chats


def run_calibration(
    gold_dir: str | Path | None = None,
    api_key: str | None = None,
) -> dict:
    """
    Run judge against all gold chats and compute calibration metrics.

    Returns:
        Dict with overall_mae, per_dim_mae, ec_na_count, pass_fail.
    """
    chats = load_all_gold_chats(gold_dir)
    if not chats:
        raise RuntimeError("No gold chats found. Cannot run calibration.")

    judge = GeminiJudge(api_key=api_key)
    print(f"Calibrating against {len(chats)} gold chats...\n")

    per_dim_errors: dict[str, list[float]] = {d: [] for d in DIMS}
    ec_na_count = 0

    for chat_id, turns, human_scores in chats:
        print(f"  Scoring {chat_id}...", end=" ", flush=True)

        tagged = tag_turns(turns)
        phases = classify_phases(tagged)
        metrics = compute_metrics(turns, tagged)
        counts = intent_counts(tagged)

        neuron_scores = judge.score(
            session_id=chat_id,
            turns=turns,
            tagged_turns=tagged,
            metrics=metrics,
            phase_distribution=phases,
            intent_counts=counts,
        )

        agg = aggregate(neuron_scores, verification_ratio=metrics.verification_ratio)
        judge_dim = agg["dimension_scores"]

        # Compute per-dimension MAE against human band scores
        for dim in DIMS:
            h_score = human_scores.get(dim)
            j_score = judge_dim.get(dim)
            if h_score is None:
                if dim == "EC":
                    ec_na_count += 1
                continue
            if j_score is not None:
                per_dim_errors[dim].append(abs(j_score - h_score))

        print("done")

    # Aggregate results
    dim_maes: dict[str, float | None] = {}
    for dim in DIMS:
        errs = per_dim_errors[dim]
        dim_maes[dim] = round(sum(errs) / len(errs), 4) if errs else None

    overall_errors = [e for errs in per_dim_errors.values() for e in errs]
    overall_mae = round(sum(overall_errors) / len(overall_errors), 4) if overall_errors else None

    # Pass/fail assessment
    ec_mae = dim_maes.get("EC")
    pass_overall = overall_mae is not None and overall_mae <= _TARGET_MAE_OVERALL
    pass_ec = ec_mae is not None and ec_mae <= _TARGET_MAE_EC
    pass_ec_na = ec_na_count <= _TARGET_EC_NA_RATE

    return {
        "gold_chat_count": len(chats),
        "overall_mae": overall_mae,
        "per_dim_mae": dim_maes,
        "ec_na_count": ec_na_count,
        "pass_overall_mae": pass_overall,
        "pass_ec_mae": pass_ec,
        "pass_ec_na_rate": pass_ec_na,
    }


def _print_report(result: dict) -> None:
    print("\n" + "=" * 60)
    print("CALIBRATION REPORT")
    print("=" * 60)
    print(f"\nGold chats scored: {result['gold_chat_count']}")
    print(f"\nOverall MAE: {result['overall_mae']}  "
          f"(target <= {_TARGET_MAE_OVERALL})  "
          f"{'PASS' if result['pass_overall_mae'] else 'FAIL'}")
    print(f"\nPer-dimension MAE:")
    for dim, mae in result["per_dim_mae"].items():
        flag = ""
        if dim == "EC" and mae is not None:
            flag = f"  (target <= {_TARGET_MAE_EC}) {'PASS' if result['pass_ec_mae'] else 'FAIL'}"
        print(f"  {dim:5s}  {mae if mae is not None else 'N/A'}{flag}")
    print(f"\nEC N/A count: {result['ec_na_count']}  "
          f"(target <= {_TARGET_EC_NA_RATE})  "
          f"{'PASS' if result['pass_ec_na_rate'] else 'FAIL'}")
    print("\nNote: EC MAE target requires >=40 gold chats (§7.3).")


def main() -> None:
    parser = argparse.ArgumentParser(description="SAF Calibration Runner")
    parser.add_argument("--gold-dir", default=None, help="Path to gold chats directory.")
    args = parser.parse_args()

    result = run_calibration(gold_dir=args.gold_dir)
    _print_report(result)


if __name__ == "__main__":
    main()
