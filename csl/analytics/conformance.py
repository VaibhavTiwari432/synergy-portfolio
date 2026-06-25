"""
csl/analytics/conformance.py — Process-Mining Conformance Checking (Item #9)

Purpose: Compute session fitness against expected interaction model.
"""

from __future__ import annotations

from typing import Dict, List, Any, Optional


def conformance_check_session(
    session_id: str,
    event_sequence: List[str],
    expected_sequence: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Check conformance of session against expected process sequence.

    Expected: Frame → Generate → Verify → Integrate

    Args:
        session_id: Session identifier
        event_sequence: Ordered list of events/activities
        expected_sequence: Expected model sequence (if None, uses default)

    Returns:
        {fitness_score, deviations, interpretation}
    """

    if expected_sequence is None:
        expected_sequence = [
            'frame_problem',
            'generate_solutions',
            'verify_solutions',
            'integrate_learning',
        ]

    if not event_sequence:
        return {
            'session_id': session_id,
            'fitness_score': 0.0,
            'deviations': [],
            'n_events': 0,
            'interpretation': 'No events',
        }

    # Simple conformance: count matches to expected sequence
    deviations = []
    matches = 0

    for i, event in enumerate(event_sequence):
        # Check if this event matches expected position (allowing some flexibility)
        expected_idx = i % len(expected_sequence)
        if event == expected_sequence[expected_idx]:
            matches += 1
        else:
            deviations.append({
                'position': i,
                'observed': event,
                'expected': expected_sequence[expected_idx],
            })

    # Fitness: percentage of events matching expected positions
    fitness_score = matches / len(event_sequence) if event_sequence else 0.0

    interpretation = 'Good fit (>0.8)' if fitness_score > 0.8 else 'Deviations detected'

    return {
        'session_id': session_id,
        'fitness_score': fitness_score,
        'n_events': len(event_sequence),
        'n_deviations': len(deviations),
        'deviations': deviations,
        'interpretation': interpretation,
    }


if __name__ == '__main__':
    print("Process mining conformance module loaded.")
