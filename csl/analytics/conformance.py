"""
csl/analytics/conformance.py — Process-Mining Conformance Checking (Item #9)

Purpose: Compute session fitness against expected interaction model.

G3: replaces the cyclic-modulo matching algorithm (which gives false-perfect fitness
for any repeating sequence) with a proper ordered-subsequence token-replay.

The token-replay algorithm:
  - Walk the expected model as a finite sequence (not cyclic).
  - For each observed event, advance the model pointer if the event matches.
  - Fitness = matched_tokens / max(len(expected), len(observed)).
  - Missing tokens (expected not consumed) and spurious tokens (observed with no
    model match) are counted separately, preserving interpretability.

This is the standard Petri-net token-replay fitness metric projected onto a linear
process model, without the pm4py dependency. A cyclic trace now scores < 1.0 unless
it genuinely matches the expected sequence.
"""

from __future__ import annotations

from typing import Dict, List, Any, Optional


def conformance_check_session(
    session_id: str,
    event_sequence: List[str],
    expected_sequence: Optional[List[str]] = None,
    archetype_gate: Optional[float] = None,
) -> Dict[str, Any]:
    """Check conformance via ordered-subsequence token-replay.

    G3: replaces cyclic-modulo matching (false-perfect-fit bug) with a linear
    token-replay that penalises out-of-order and missing model steps.

    Args:
        session_id: Session identifier
        event_sequence: Ordered list of observed events/activities
        expected_sequence: Linear expected model (default: Frame→Generate→Verify→Integrate)
        archetype_gate: Optional archetype-specific fitness threshold (G5 hook);
                        if None, uses the default >0.8 heuristic.

    Returns:
        {fitness_score, missing_tokens, spurious_tokens, deviations, interpretation}
    """
    if expected_sequence is None:
        expected_sequence = [
            "frame_problem",
            "generate_solutions",
            "verify_solutions",
            "integrate_learning",
        ]

    if not event_sequence:
        return {
            "session_id": session_id,
            "fitness_score": 0.0,
            "missing_tokens": len(expected_sequence),
            "spurious_tokens": 0,
            "deviations": [],
            "n_events": 0,
            "interpretation": "No events",
        }

    # Token-replay: advance model pointer greedily on each match
    model_ptr = 0
    matched = 0
    spurious = 0
    deviations: list[dict] = []

    for obs_event in event_sequence:
        if model_ptr < len(expected_sequence) and obs_event == expected_sequence[model_ptr]:
            matched += 1
            model_ptr += 1
        else:
            spurious += 1
            deviations.append({
                "observed": obs_event,
                "expected_at": expected_sequence[model_ptr] if model_ptr < len(expected_sequence) else None,
                "model_position": model_ptr,
            })

    missing = len(expected_sequence) - model_ptr  # unconsumed model steps

    # Fitness: matched / (expected consumed + spurious); penalises both gaps
    denom = max(len(expected_sequence), len(event_sequence))
    fitness_score = round(matched / denom, 4) if denom > 0 else 0.0

    gate = archetype_gate if archetype_gate is not None else 0.8
    interpretation = f"Good fit (>{gate:.0%})" if fitness_score > gate else "Deviations detected"

    return {
        "session_id": session_id,
        "fitness_score": fitness_score,
        "matched_tokens": matched,
        "missing_tokens": missing,
        "spurious_tokens": spurious,
        "n_events": len(event_sequence),
        "n_deviations": len(deviations),
        "deviations": deviations,
        "interpretation": interpretation,
    }


def load_archetype_gate(archetype_id: str) -> Optional[float]:
    """G5: look up the archetype-specific conformance threshold from baseline_capability_specs.yaml.

    Returns the parsed gate (e.g. 0.769 for '≥10/13') or None if not found.
    The BCS YAML stores gates as human-readable strings like 'Must show ≥10/13 capabilities';
    this parser extracts the fraction and returns it as a float.
    """
    import re
    from pathlib import Path
    import yaml  # type: ignore

    bcs_path = Path(__file__).parent.parent.parent / "contracts" / "baseline_capability_specs.yaml"
    if not bcs_path.exists():
        return None
    with bcs_path.open("r", encoding="utf-8") as f:
        bcs = yaml.safe_load(f)

    for arch in bcs.get("archetypes", []):
        if arch.get("archetype_id") == archetype_id:
            gate_str = arch.get("conformance_gate", "")
            m = re.search(r"≥\s*(\d+)\s*/\s*(\d+)", gate_str)
            if m:
                return round(int(m.group(1)) / int(m.group(2)), 4)
            m2 = re.search(r"(\d+(?:\.\d+)?)\s*%", gate_str)
            if m2:
                return round(float(m2.group(1)) / 100, 4)
    return None


if __name__ == '__main__':
    print("Process mining conformance module loaded.")
