"""B (v3.23) — MAE-ratchet regression + deterministic diagnostics on the gold corpus.

Reuses the REAL stack — nothing here invents an API:
  - calibration.runner.run_calibration  (the MAE ratchet, non-negotiable #18)
  - calibration.gold_loader.load_gold_corpus  (gold.session is a CanonicalSession)
  - src.classifier.grain_router / provenance_classifier  (FIX-0 / FIX-0.5)
  - src.aggregate.eligibility_gate via pipeline._scorable_judge_neurons  (ADR-0019)

Split of concerns:
  * Diagnostics (gate effect, neuron-grain split, per-session synergy-context,
    provenance distribution) are DETERMINISTIC — no judge, no spend. Runnable now.
  * The MAE ratchet needs a score_fn; live = pipeline.judge_score_fn() (real
    Gemini spend, --live-judge). Omit it and only diagnostics run.

This is a REGRESSION + DIAGNOSTICS run, NOT validation: no synergy_index, no
"corpus go/no-go" verdict from the 26-chat pilot set (addendum #2, non-neg #3/#4).

Reality notes vs the kickoff:
  - grain_router classifies NEURONS, not turns — the grain split is over the 98
    judge-typed neurons (static) + a per-session synergy-context boolean. There is
    no "% of turns EXECUTION/DELEGATION/SYNERGY".
  - baseline judge calls = 98/chat (judge-typed), not 107 — the 9 deterministic
    neurons are not judge calls and are never gated.
  - on the 0.1.0-scaffold (permissive) matrix gate_effect is 0% by construction;
    it goes >0% only once cells are tightened (Vaibhav, §7 Q1).
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from calibration.gold_loader import GoldChat, load_gold_corpus
from calibration.runner import MAE_RATCHET, run_calibration
from contracts.schemas import Dimension
from src.api.pipeline import _scorable_judge_neurons, judge_score_fn
from src.classifier.grain_router import classify_grain, session_is_synergy_context
from src.classifier.provenance_classifier import (
    ProvenanceClass,
    classify_session_turns,
)
from src.trait.judge.rubric_bank import JUDGE_TYPED_NEURONS, get_rubric
from src.trait.phase_classifier import classify_phases
from src.trait.tagger import tag_turns

N_JUDGE_TYPED = len(JUDGE_TYPED_NEURONS)  # 98 — the gate's universe and cost baseline


def neuron_grain_split() -> dict[str, int]:
    """Static grain class of each of the 98 judge-typed neurons (corpus-independent)."""
    counts: Counter[str] = Counter()
    for nid in JUDGE_TYPED_NEURONS:
        counts[classify_grain(nid, get_rubric(nid).get("title")).value] += 1
    return dict(counts)


def _session_provenance(session) -> Counter:
    """Per-human-turn provenance, via the SAME canonical classifier the live
    pipeline uses (classify_session_turns — each human turn vs prior AI turns +
    copy-event telemetry). ponytail: O(turns) classify, but each call is a
    Levenshtein over large texts — seconds on long chats; fine for a one-shot
    measurement, not for unit tests (those run a small corpus slice)."""
    tally: Counter[str] = Counter()
    for decision in classify_session_turns(session).values():
        tally[decision.label.value] += 1
    return tally


def collect_diagnostics(corpus: list[GoldChat]) -> dict:
    """Deterministic diagnostics — no judge calls, no spend."""
    baseline_calls = N_JUDGE_TYPED * len(corpus)
    actual_calls = 0
    synergy_context_chats = 0
    provenance: Counter[str] = Counter()
    per_chat = []

    for gold in corpus:
        session = gold.session
        tags = tag_turns(session)
        phases = classify_phases(session, tags)

        scorable = _scorable_judge_neurons(tags)  # None = legacy all-neuron path
        n_scorable = N_JUDGE_TYPED if scorable is None else len(scorable)
        actual_calls += n_scorable

        is_synergy = session_is_synergy_context(tags, phases)
        synergy_context_chats += int(is_synergy)

        prov = _session_provenance(session)
        provenance.update(prov)

        per_chat.append(
            {
                "chat_id": session.session_id,
                "scorable_neurons": n_scorable,
                "gate_applied": scorable is not None,
                "synergy_context": is_synergy,
                "provenance": dict(prov),
            }
        )

    reduction_pct = round(100.0 * (baseline_calls - actual_calls) / baseline_calls, 1) if baseline_calls else 0.0
    copy_paste = provenance.get(ProvenanceClass.COPY.value, 0) + provenance.get(ProvenanceClass.VERBATIM.value, 0)

    return {
        "n_chats": len(corpus),
        "gate_effect": {
            "baseline_judge_calls": baseline_calls,  # 98/chat — judge-typed only
            "actual_judge_calls": actual_calls,
            "cost_reduction_pct": reduction_pct,  # 0.0 on permissive scaffold
            "note": "0% until matrix cells tightened (ADR-0019 §7 Q1)",
        },
        "neuron_grain_split": neuron_grain_split(),
        "synergy_context_chats": synergy_context_chats,
        "provenance_distribution": dict(provenance),
        "copy_paste_detected": copy_paste,
        "per_chat": per_chat,
    }


def run(corpus: list[GoldChat] | None = None, score_fn=None) -> dict:
    """Diagnostics always; MAE ratchet only when a score_fn is supplied."""
    corpus = corpus if corpus is not None else load_gold_corpus()
    report = {
        "framing": "regression + diagnostics (NOT validation; no synergy_index)",
        "matrix_version": _matrix_version(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "diagnostics": collect_diagnostics(corpus),
    }
    if score_fn is not None:
        cal = run_calibration(score_fn, corpus)
        report["mae_ratchet"] = {
            "ratchet": MAE_RATCHET,
            "shadow_overall_mae": cal["shadow"]["overall_mae"],
            "ratchet_passed": cal["ratchet_passed"],
            "coverage_pct": cal["shadow"]["coverage_pct"],
            "ec_tracked_separately": cal["ec_tracked_separately"],
        }
    return report


def _matrix_version() -> str:
    import yaml

    p = Path(__file__).resolve().parents[1] / "contracts" / "neuron_task_eligibility.yaml"
    return yaml.safe_load(p.read_text(encoding="utf-8")).get("version", "unknown")


def _print_summary(report: dict) -> None:
    d = report["diagnostics"]
    g = d["gate_effect"]
    print("=" * 60)
    print("REGRESSION + DIAGNOSTICS REPORT")
    print("=" * 60)
    if "mae_ratchet" in report:
        m = report["mae_ratchet"]
        verdict = "PASS" if m["ratchet_passed"] else "FAIL"
        print(f"MAE ratchet:       {m['shadow_overall_mae']} (target <= {m['ratchet']})  {verdict}")
    else:
        print("MAE ratchet:       not run (no --live-judge / score_fn)")
    print(f"\nMatrix version:    {report['matrix_version']}")
    print(f"Gate effect:       {g['actual_judge_calls']}/{g['baseline_judge_calls']} judge "
          f"calls -> {g['cost_reduction_pct']}% reduction")
    print(f"                   ({g['note']})")
    print(f"\nNeuron-grain split (98 judge-typed, static):")
    for k, v in sorted(d["neuron_grain_split"].items(), key=lambda kv: -kv[1]):
        print(f"  {k:<18} {v}")
    print(f"\nSynergy-context chats: {d['synergy_context_chats']}/{d['n_chats']}")
    print(f"\nProvenance (per human turn):")
    for k, v in sorted(d["provenance_distribution"].items(), key=lambda kv: -kv[1]):
        print(f"  {k:<18} {v}")
    print(f"  copy/verbatim detected: {d['copy_paste_detected']}")
    print("=" * 60)


def main() -> None:  # pragma: no cover — CLI; --live-judge needs a judge API key
    ap = argparse.ArgumentParser(description="Gold-corpus regression + diagnostics (v3.23 B)")
    ap.add_argument("--live-judge", action="store_true",
                    help="run the MAE ratchet with fresh Gemini calls (real spend)")
    ap.add_argument("--output", default=None, help="write JSON report here (default: measurements/)")
    args = ap.parse_args()

    score_fn = judge_score_fn() if args.live_judge else None
    report = run(score_fn=score_fn)
    _print_summary(report)

    out = Path(args.output) if args.output else (
        Path(__file__).resolve().parents[1] / "measurements"
        / f"regression_diagnostics_{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}.json"
    )
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nSaved {out}")


if __name__ == "__main__":
    main()
