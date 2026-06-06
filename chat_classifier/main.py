"""
ARI Chat Classifier v2 — main pipeline entry point.

Stages:
  1  Parse        ingestion/parsers.py + RawChat.model_validate
  2  Tag          tagger/intent_tagger.py
  3  Phase        tagger/phase_classifier.py
  4  Metrics      scorer/composite_metrics.py
  5  Judge        scorer/gemini_judge.py
  6  Aggregate    aggregator/dimension_aggregator.py
  7  Risk flags   flags/risk_evaluator.py

Usage:
    python -m chat_classifier.main <path_to_transcript.json> [--source chatgpt|claude|plaintext]
"""

from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

from chat_classifier.aggregator.dimension_aggregator import aggregate
from chat_classifier.config import DIMENSION_WEIGHTS, PILLAR_MAP
from chat_classifier.flags.risk_evaluator import evaluate_flags
from chat_classifier.schemas import RawChat, SynergyReport
from chat_classifier.scorer.composite_metrics import compute_metrics
from chat_classifier.scorer.gemini_judge import GeminiJudge
from chat_classifier.tagger.intent_tagger import intent_counts, tag_chat
from chat_classifier.tagger.phase_classifier import classify_phases


def run(transcript_path: str | Path, source: str | None = None) -> SynergyReport:
    """
    Run the full 7-stage pipeline on a transcript file.

    transcript_path — path to JSON file.
    source          — parser hint: 'chatgpt', 'claude', 'plaintext'.
                      If None, the file must already be in RawChat format.
    """
    with open(transcript_path) as f:
        raw = json.load(f)

    # Stage 1: parse
    if source is not None:
        from chat_classifier.ingestion.parsers import parse
        chat = parse(source, raw)
    else:
        chat = RawChat.model_validate(raw)

    # Stage 2: intent tagging
    tagged = tag_chat(chat)
    counts = intent_counts(tagged)

    # Stage 3: phase classification
    phase_dist = classify_phases(tagged)

    # Stage 4: composite metrics
    metrics = compute_metrics(chat, tagged)

    # Stage 5: judge
    judge = GeminiJudge()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        judge_out = judge.score(chat, tagged, metrics, phase_dist, counts)
    missing_warn = next(
        (str(w.message) for w in caught if "missing" in str(w.message).lower()), None
    )

    # Stage 6: aggregate
    report = SynergyReport(
        session_id=chat.chat_id,
        transcript_turns=len(chat.turns),
        neuron_scores=judge_out.neuron_scores,
        composite_metrics=metrics,
        intent_tag_counts=counts,
        phase_distribution=phase_dist,
        coverage={
            "scored": sum(1 for v in judge_out.neuron_scores.values() if v > 0),
            "total": len(judge_out.neuron_scores),
        },
        confidence_note=missing_warn or "",
    )
    report = aggregate(judge_out.neuron_scores, report)

    # Stage 7: risk flags
    report.risk_flags = evaluate_flags(judge_out.neuron_scores, metrics)

    return report


def _print_report(report: SynergyReport) -> None:
    print("=" * 60)
    print("ARI SYNERGY REPORT — session: %s" % report.session_id)
    print("=" * 60)

    print("\nPHASE DISTRIBUTION")
    for phase, frac in report.phase_distribution.items():
        bar = "#" * int(frac * 24)
        print("  %-10s %5.1f%%  %s" % (phase, frac * 100, bar))

    print("\nCOMPOSITE METRICS")
    m = report.composite_metrics
    def _f(v): return "%.3f" % v if v is not None else "N/A"
    print("  verification_ratio       : %s" % _f(m.verification_ratio))
    print("  generative_query_ratio   : %s" % _f(m.generative_query_ratio))
    print("  attribution_gap          : %s" % _f(m.attribution_gap))
    print("  vr first->second half    : %s -> %s" % (_f(m.verification_ratio_first_half), _f(m.verification_ratio_second_half)))
    print("  session_turns            : %d" % m.session_turns)

    print("\nDIMENSION SCORES  (weighted / raw)")
    for dim in ["AL", "PR", "EC", "ES", "CS", "CD", "AUI", "CA"]:
        ws = report.dimension_scores.get(dim)
        w = DIMENSION_WEIGHTS[dim]
        tag = "[1.5x]" if w == 1.5 else "      "
        if ws is None:
            print("  %-5s %s  NOT SCORABLE" % (dim, tag))
        else:
            print("  %-5s %s  %.3f  (raw %.3f)" % (dim, tag, ws, ws / w))

    print("\nPILLAR SCORES")
    for pillar, dims in PILLAR_MAP.items():
        s = report.pillar_scores.get(pillar)
        print("  %-8s  %s  (%s)" % (pillar, ("%.3f" % s) if s is not None else "N/A", "+".join(dims)))

    g = report.synergy_score_kappa
    print("\n  g_synergy kappa = %s" % (("%.4f" % g) if g is not None else "N/A"))

    print("\nRISK FLAGS")
    for flag, value in report.risk_flags.items():
        marker = "TRIGGERED" if value else "clear"
        print("  %-35s %s" % (flag, marker))

    print("\nCOVERAGE: %d / %d neurons scored" % (report.coverage["scored"], report.coverage["total"]))
    if report.confidence_note:
        print("  Note: %s" % report.confidence_note[:120])

    print("=" * 60)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m chat_classifier.main <transcript.json> [source]")
        sys.exit(1)

    path = sys.argv[1]
    src = sys.argv[2] if len(sys.argv) > 2 else None
    report = run(path, src)
    _print_report(report)
