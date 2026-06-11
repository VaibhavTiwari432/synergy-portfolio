"""
SAF Chat Analyser — main entry point.

Runs the full 8-stage pipeline on a single transcript.
Requires GEMINI_API_KEY to be set in the environment for Stage 5.

Usage:
    python -m saf_chat_analyser.main --input chat.json [--session-id my-session]
    python -m saf_chat_analyser.main --input transcript.txt [--out result.json]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from saf_chat_analyser.src.parser.transcript_parser import parse_transcript
from saf_chat_analyser.src.tagger.intent_tagger import tag_turns, intent_counts
from saf_chat_analyser.src.tagger.turn_classifier import compute_as_ratios
from saf_chat_analyser.src.tagger.phase_classifier import classify_phases
from saf_chat_analyser.src.metrics.composite_metrics import compute_metrics
from saf_chat_analyser.src.scorer.gemini_judge import GeminiJudge
from saf_chat_analyser.src.aggregator.dimension_aggregator import aggregate
from saf_chat_analyser.src.flags.risk_evaluator import evaluate_flags
from saf_chat_analyser.src.output.formatter import format_output


def run_pipeline(
    raw_input: str | list,
    session_id: str | None = None,
    api_key: str | None = None,
) -> dict:
    """
    Execute all 8 stages on a single chat transcript.

    Args:
        raw_input:  JSON string, list of role/content dicts, or plaintext.
        session_id: Optional identifier; defaults to "session-<hash>".
        api_key:    Gemini API key; falls back to GEMINI_API_KEY env var.

    Returns:
        Full Tier-1 output dict with claims_boundary.
    """
    # Stage 1: parse
    turns = parse_transcript(raw_input)
    if not turns:
        raise ValueError("No turns parsed from input.")

    sid = session_id or f"session-{abs(hash(str(turns[:2])))}"

    # Stage 2a: intent tagging
    tagged = tag_turns(turns)

    # Stage 2b + 3 + 4: A/S classification, phase, metrics
    counts = intent_counts(tagged)
    phases = classify_phases(tagged)
    metrics = compute_metrics(turns, tagged)

    # Stage 5: Gemini judge (dual-granularity)
    judge = GeminiJudge(api_key=api_key)
    neuron_scores = judge.score(
        session_id=sid,
        turns=turns,
        tagged_turns=tagged,
        metrics=metrics,
        phase_distribution=phases,
        intent_counts=counts,
    )

    # Stage 6: aggregate (min × product(gates))
    agg = aggregate(neuron_scores, verification_ratio=metrics.verification_ratio)

    # Stage 7: risk flags
    flags = evaluate_flags(neuron_scores, metrics)

    # Stage 8: format output
    return format_output(
        session_id=sid,
        neuron_scores=neuron_scores,
        aggregation=agg,
        metrics=metrics,
        risk_flags=flags,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="SAF Chat Analyser — Tier 1 pipeline"
    )
    parser.add_argument(
        "--input", "-i", required=True,
        help="Path to transcript file (JSON array or plaintext).",
    )
    parser.add_argument(
        "--session-id", default=None,
        help="Session identifier (optional).",
    )
    parser.add_argument(
        "--out", "-o", default=None,
        help="Write JSON output to this file (default: stdout).",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    raw = input_path.read_text(encoding="utf-8")

    # Handle files that use the old 'text' field (e.g., gold chats)
    try:
        data = json.loads(raw)
        if isinstance(data, dict) and "turns" in data:
            # Normalise 'text' → 'content'
            turns_raw = data["turns"]
            raw = json.dumps([
                {"role": t["role"], "content": t.get("content") or t.get("text", "")}
                for t in turns_raw
            ])
    except (json.JSONDecodeError, KeyError, TypeError):
        pass  # plaintext or already correct format

    result = run_pipeline(raw, session_id=args.session_id)

    output_json = json.dumps(result, indent=2, ensure_ascii=False)
    if args.out:
        Path(args.out).write_text(output_json, encoding="utf-8")
        print(f"Output written to {args.out}")
    else:
        print(output_json)


if __name__ == "__main__":
    main()
