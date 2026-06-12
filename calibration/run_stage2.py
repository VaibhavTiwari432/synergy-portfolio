"""Stage-2 initial calibration run (CE utility, not part of the API).

Scores all 26 gold chats through the full pipeline with the real judge,
saves per-chat predictions incrementally (re-runnable: cached chats are not
re-judged), and writes the headline/shadow MAE report.

Usage:  python -m calibration.run_stage2 [--only gc-003 gc-016 ...]
Output: calibration/results/stage2_initial.json (+ predictions cache)
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from contracts.schemas import Dimension
from calibration.gold_loader import load_gold_corpus
from calibration.runner import run_calibration

RESULTS_DIR = Path(__file__).resolve().parent / "results"
CACHE_PATH = RESULTS_DIR / "stage2_predictions_cache.json"
REPORT_PATH = RESULTS_DIR / "stage2_initial.json"

#: pause between judge calls — keeps free-tier RPM limits comfortable
INTER_CHAT_DELAY_S = 5.0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", nargs="*", default=None,
                        help="re-judge only these chat ids (cache is kept for the rest)")
    args = parser.parse_args()

    from src.api.pipeline import score_session  # late: needs API key in env

    RESULTS_DIR.mkdir(exist_ok=True)
    cache: dict[str, dict] = {}
    if CACHE_PATH.exists():
        cache = json.loads(CACHE_PATH.read_text(encoding="utf-8"))

    corpus = load_gold_corpus()

    for gold in corpus:
        chat_id = gold.session.session_id
        if args.only is not None:
            needs_run = chat_id in args.only  # explicit selection re-judges
        else:
            needs_run = chat_id not in cache
        if not needs_run:
            print(f"{chat_id}: cached", flush=True)
            continue

        start = time.time()
        response = score_session(gold.session)
        predictions = {
            dim.value: (score.value if score.value is not None else None)
            for dim, score in response.profile.items()
        }
        cache[chat_id] = {
            "predictions": predictions,
            "judge_unavailable": response.flags.judge_unavailable,
            "judge_family_conflict": response.flags.judge_family_conflict,
            "elapsed_s": round(time.time() - start, 1),
        }
        CACHE_PATH.write_text(json.dumps(cache, indent=2), encoding="utf-8")
        status = "JUDGE-UNAVAILABLE" if response.flags.judge_unavailable else "ok"
        print(f"{chat_id}: {status} in {cache[chat_id]['elapsed_s']}s", flush=True)
        time.sleep(INTER_CHAT_DELAY_S)

    # MAE from the cache (no further judge calls)
    def cached_score_fn(session):
        row = cache.get(session.session_id, {}).get("predictions", {})
        return {dim: row.get(dim.value) for dim in Dimension}

    result = run_calibration(cached_score_fn, corpus)
    result["judge_unavailable_chats"] = [
        cid for cid, row in cache.items() if row.get("judge_unavailable")
    ]
    REPORT_PATH.write_text(json.dumps(result, indent=2), encoding="utf-8")

    print(json.dumps(
        {k: result[k] for k in ("ratchet_passed", "shadow", "headline", "ec_tracked_separately")},
        indent=2,
    ))
    print(f"report: {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
