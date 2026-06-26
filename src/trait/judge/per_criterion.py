"""
src/trait/judge/per_criterion.py — Per-criterion judge calls (one per neuron)

ITEM #2 PART B: Independent judge calls for each of 107 neurons.

Purpose: Replace halo-contaminated joint prompts with independent calls per neuron,
each using anchored rubric to prevent central-tendency and leniency bias.

Fixes:
  - Halo contamination: joint prompts inflate all scores together
  - Central-tendency bias: broad scales compress scores toward middle
  - Leniency bias: judges default to positive without negative criteria check

Non-negotiables:
  - One call per neuron (107 calls/session)
  - Each call constrained to 3-5 scale levels
  - Negative criteria checked; leniency penalty applied
  - JSON response parsed and validated
"""

from __future__ import annotations

import json
import re
from typing import Dict, Any, Optional, List

from src.trait.judge.rubric_bank import get_rubric


def build_per_criterion_prompt(
    neuron_id: str,
    transcript: str,
    rubric_dict: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Build per-criterion judge prompt for a single neuron.

    Args:
        neuron_id: Neuron ID (e.g., 'EC-01')
        transcript: Session transcript
        rubric_dict: Override rubric (if None, loads from bank)

    Returns:
        Prompt string for the judge
    """

    if rubric_dict is None:
        rubric_dict = get_rubric(neuron_id)

    title = rubric_dict.get('title', '')
    dimension = rubric_dict.get('dimension', '')
    anchors = rubric_dict.get('anchors', {})
    negative_criteria = rubric_dict.get('negative_criteria', [])
    scale_levels = rubric_dict.get('scale_levels', [])

    # Format scale levels
    scale_str = ' | '.join([f'[{i}] {level}' for i, level in enumerate(scale_levels)])

    # Format anchors
    anchors_str = '\n  '.join(
        [f'{level.upper()}: "{anchors.get(level, "")}"' for level in scale_levels]
    )

    # Format negative criteria
    negcrit_str = '\n  '.join([f'- {crit}' for crit in negative_criteria])

    prompt = f"""You are a behavioral psychometrician specializing in human-AI interaction analysis.

NEURON: {neuron_id} ({dimension})
TITLE: {title}

SCALE: {scale_str}

BEHAVIORAL ANCHORS:
  {anchors_str}

NEGATIVE CRITERIA (penalize if present):
  {negcrit_str}

TRANSCRIPT:
{transcript}

TASK:
1. Read the transcript carefully.
2. Identify evidence (or absence thereof) for this specific neuron.
3. Select the best-fitting level: {' | '.join(scale_levels)}.
4. Check if negative criteria are present; if so, penalize by dropping score one level.
5. Provide reasoning in 2–3 sentences.
6. Rate your confidence (0.0–1.0).

OUTPUT:
Respond ONLY with valid JSON, no markdown:
{{
  "neuron_id": "{neuron_id}",
  "score": <integer level index: 0-{len(scale_levels)-1}>,
  "reasoning": "<2-3 sentences explaining your score>",
  "negative_criteria_present": <boolean>,
  "confidence": <0.0-1.0>,
  "final_score_after_leniency_penalty": <integer level index after penalty>
}}

Do not include code blocks, markdown, or any other formatting. Return only JSON.
"""

    return prompt


def call_judge_for_neuron(
    judge_fn,
    neuron_id: str,
    transcript: str,
    rubric_dict: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Make one judge call for a single neuron.

    Args:
        judge_fn: Callable that takes (prompt) and returns response string
        neuron_id: Neuron ID
        transcript: Session transcript
        rubric_dict: Optional override rubric

    Returns:
        Parsed response dict with:
            - neuron_id
            - score (0-N, where N is num scale levels - 1)
            - reasoning
            - negative_criteria_present
            - confidence
            - final_score_after_leniency_penalty
    """

    if rubric_dict is None:
        rubric_dict = get_rubric(neuron_id)

    prompt = build_per_criterion_prompt(neuron_id, transcript, rubric_dict)

    # Call judge
    response_text = judge_fn(prompt)

    # Parse JSON
    try:
        # Try to extract JSON from response (in case there's extra text)
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_match:
            response_json = json.loads(json_match.group())
        else:
            response_json = json.loads(response_text)
    except json.JSONDecodeError as e:
        # Fallback: return error response
        return {
            'neuron_id': neuron_id,
            'score': None,
            'reasoning': f'Parse error: {str(e)}',
            'negative_criteria_present': None,
            'confidence': 0.0,
            'final_score_after_leniency_penalty': None,
            'error': True,
        }

    # Validate response
    response_json['neuron_id'] = neuron_id

    return response_json


def score_all_neurons(
    judge_fn,
    transcript: str,
    neuron_ids: Optional[List[str]] = None,
    max_workers: int = 8,
) -> Dict[str, Dict[str, Any]]:
    """
    Score all neurons with per-criterion calls, running up to max_workers in parallel.

    Sequential scoring of 107 neurons sends the full transcript once per neuron;
    for large chats that can exceed 30+ minutes. Bounded thread parallelism reduces
    wall time to roughly ceil(107 / max_workers) × per_call_time while staying
    within typical Gemini rate limits (default 8 concurrent calls).
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    if neuron_ids is None:
        from src.trait.judge.rubric_bank import list_all_neurons
        neuron_ids = list_all_neurons()

    results: Dict[str, Dict[str, Any]] = {}
    error_count = 0

    def _score_one(nid: str) -> tuple[str, Dict[str, Any]]:
        try:
            return nid, call_judge_for_neuron(judge_fn, nid, transcript)
        except Exception as e:  # noqa: BLE001
            return nid, {'neuron_id': nid, 'error': True, 'error_message': str(e)}

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        for nid, result in (f.result() for f in as_completed(
            pool.submit(_score_one, nid) for nid in neuron_ids
        )):
            results[nid] = result
            if result.get('error'):
                error_count += 1

    successful = len([r for r in results.values() if not r.get('error')])
    return {
        'results': results,
        'summary': {
            'n_neurons': len(neuron_ids),
            'successful': successful,
            'errors': error_count,
            'success_rate': successful / len(neuron_ids) if neuron_ids else 0,
        },
    }


if __name__ == '__main__':
    print("Per-criterion judge module loaded.")
    print("Usage:")
    print("  from src.trait.judge.per_criterion import call_judge_for_neuron")
    print("  result = call_judge_for_neuron(judge_fn, 'EC-01', transcript)")
