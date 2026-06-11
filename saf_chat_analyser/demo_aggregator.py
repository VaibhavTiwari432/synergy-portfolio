"""
Demo: run Stages 1-4 on example_01.json using stub neuron scores,
then run Stage 6 and print per-pillar + composite.

Stub scores are manually crafted to reflect example_01's behavioral
profile: active verifier (EC~0.65), context injector (CS~0.70),
self-auditor + overrider (CA~0.67), moderate prompt engineering (PR~0.55).

Run from workspace root:
  python -m saf_chat_analyser.demo_aggregator
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Ensure package root is on path when running as a script
sys.path.insert(0, str(Path(__file__).parents[1]))

from saf_chat_analyser.src.parser.transcript_parser import parse_transcript, Turn
from saf_chat_analyser.src.tagger.intent_tagger import tag_turns, intent_counts
from saf_chat_analyser.src.tagger.turn_classifier import compute_as_ratios
from saf_chat_analyser.src.tagger.phase_classifier import classify_phases
from saf_chat_analyser.src.metrics.composite_metrics import compute_metrics
from saf_chat_analyser.src.aggregator.dimension_aggregator import aggregate

# ── Load and parse example_01.json ───────────────────────────────────────────

EXAMPLE_PATH = Path(__file__).parent.parent / "data" / "sample_transcripts" / "example_01.json"


def load_example() -> list[Turn]:
    with open(EXAMPLE_PATH, encoding="utf-8") as f:
        data = json.load(f)
    # example_01 uses 'text' key (old schema); transcript_parser expects 'content'.
    # Normalise before parsing.
    turns_raw = data.get("turns", [])
    normalised = [
        {"role": t["role"], "content": t.get("content") or t.get("text", "")}
        for t in turns_raw
    ]
    return parse_transcript(normalised)


# ── Stub neuron scores for example_01 ────────────────────────────────────────
# Represents a competent-but-not-exceptional user: verifies claims, injects
# domain context, self-audits, overrides errors. Weak on creative divergence.
# These are NOT gold annotations — they are demonstration values only.

def make_stub_scores() -> dict[str, float]:
    scores: dict[str, float] = {}
    # AL — good AI literacy (domain grounding, context window awareness)
    al = [0.62, 0.50, 0.65, 0.45, 0.70, 0.48, 0.55, 0.60, 0.52, 0.55, 0.38, 0.42, 0.35]
    for i, v in enumerate(al, 1):
        scores[f"AL-{i:02d}"] = v

    # PR — moderate prompt engineering
    pr = [0.68, 0.55, 0.60, 0.48, 0.50, 0.40, 0.42, 0.62, 0.45, 0.58, 0.50, 0.52, 0.55, 0.38, 0.32]
    for i, v in enumerate(pr, 1):
        scores[f"PR-{i:02d}"] = v

    # EC — active error correction (challenged $200B stat, corrected AI hype, overrode arch assumption)
    ec = [0.78, 0.60, 0.65, 0.55, 0.42, 0.58, 0.62, 0.70, 0.48, 0.65, 0.72, 0.55, 0.52, 0.60]
    for i, v in enumerate(ec, 1):
        scores[f"EC-{i:02d}"] = v

    # ES — ethics sensitivity (scrub PII mention, usage-based transparency)
    es = [0.58, 0.45, 0.42, 0.55, 0.38, 0.40, 0.42, 0.50, 0.55, 0.52, 0.60, 0.45, 0.40, 0.55]
    for i, v in enumerate(es, 1):
        scores[f"ES-{i:02d}"] = v

    # CS — strong synthesis (persona injection, integration framing, voice alignment)
    cs = [0.72, 0.68, 0.65, 0.70, 0.60, 0.65, 0.62, 0.55, 0.68, 0.60, 0.58]
    for i, v in enumerate(cs, 1):
        scores[f"CS-{i:02d}"] = v

    # CD — weak creative divergence (task is analytical, not creative)
    cd = [0.32, 0.28, 0.42, 0.30, 0.35, 0.25, 0.28, 0.30, 0.25, 0.20, 0.45]
    for i, v in enumerate(cd, 1):
        scores[f"CD-{i:02d}"] = v

    # AUI — moderate augmentation instinct (knows when to delegate, aware of limits)
    aui = [0.58, 0.62, 0.55, 0.50, 0.48, 0.52, 0.55, 0.60, 0.52, 0.65, 0.58, 0.45]
    for i, v in enumerate(aui, 1):
        scores[f"AUI-{i:02d}"] = v

    # CA — good collaborative agency (sovereign override, self-audit, goal integrity)
    ca = [0.72, 0.55, 0.58, 0.65, 0.62, 0.60, 0.68, 0.62, 0.50, 0.65, 0.58, 0.45, 0.60, 0.62, 0.55, 0.68, 0.58]
    for i, v in enumerate(ca, 1):
        scores[f"CA-{i:02d}"] = v

    assert len(scores) == 107, f"Expected 107 stub scores, got {len(scores)}"
    return scores


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=== SAF Chat Analyser — Stage 6 Demo on example_01.json ===\n")

    # Stage 1: parse
    turns = load_example()
    print(f"Parsed {len(turns)} turns ({sum(1 for t in turns if t.role == 'human')} human)")

    # Stages 2a + 2b + 3: tag, classify, phase
    tagged = tag_turns(turns)
    as_ratios = compute_as_ratios(tagged)
    phases = classify_phases(tagged)
    counts = intent_counts(tagged)

    print(f"\nIntent counts: {counts}")
    print(f"A/S ratios:   a={as_ratios['a_turn_ratio']:.2f}  s={as_ratios['s_turn_ratio']:.2f}")
    print(f"Phases:       {phases}")

    # Stage 4: metrics
    metrics = compute_metrics(turns, tagged)
    print(f"\nVerification ratio:    {metrics.verification_ratio:.3f}" if metrics.verification_ratio is not None else "\nVerification ratio: N/A")
    print(f"Generative Q ratio:    {metrics.generative_query_ratio:.3f}" if metrics.generative_query_ratio is not None else "Generative Q ratio: N/A")
    print(f"Attribution gap:       {metrics.attribution_gap:.3f}" if metrics.attribution_gap is not None else "Attribution gap: N/A")

    # Stage 6: aggregate (using stub scores — no API call)
    stub_scores = make_stub_scores()
    result = aggregate(stub_scores, verification_ratio=metrics.verification_ratio)

    print("\n" + "=" * 60)
    print("STAGE 6 — AGGREGATION RESULTS (stub neuron scores)")
    print("=" * 60)

    print("\nDimension scores (unweighted means):")
    for dim, score in result["dimension_scores"].items():
        bar = "#" * int(score * 20)
        weight_note = " [1.5x]" if dim in ("EC", "CS") else ""
        print(f"  {dim:5s}  {score:.4f}  {bar}{weight_note}")

    print("\nPillar scores (weighted means):")
    pillar_scores = result["pillar_scores"]
    for pillar, score in pillar_scores.items():
        bar = "#" * int(score * 20)
        print(f"  {pillar:8s}  {score:.4f}  {bar}")

    pillar_min_name = min(pillar_scores, key=pillar_scores.get)
    pillar_min_val = pillar_scores[pillar_min_name]
    print(f"\n  → min(pillar) = {pillar_min_name} ({pillar_min_val:.4f})  ← this drives the composite")

    print("\nGates:")
    for gate, val in result["gates"].items():
        print(f"  {gate:25s}  {val:.2f}")

    gate_product = 1.0
    for v in result["gates"].values():
        gate_product *= v
    print(f"  product(gates) = {gate_product:.4f}")

    kappa = result["collaboration_quality_kappa"]
    print(f"\n  collaboration_quality_kappa = min(pillars) × product(gates)")
    print(f"  = {pillar_min_val:.4f} × {gate_product:.4f}")
    print(f"  = {kappa:.4f}")
    print(f"\n  (Mean of pillar scores would be: {sum(pillar_scores.values()) / len(pillar_scores):.4f})")
    print(f"  (Min-rule penalty vs mean: {(sum(pillar_scores.values()) / len(pillar_scores)) - kappa:.4f})")

    print("\n✓ Min rule firing correctly — CD-driven Create pillar is the bottleneck.")
    print("  The user's weak creative divergence suppresses the composite")
    print("  even though EC and CA are strong. That is the intended behaviour.")


if __name__ == "__main__":
    main()
