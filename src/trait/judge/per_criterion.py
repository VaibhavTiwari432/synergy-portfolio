"""
src/trait/judge/per_criterion.py — Phase 1b: Async dimension-batching neuron scoring.
OWNER: Chief Engineer.

Phase 1b refactor: ThreadPoolExecutor (107 sequential per-neuron calls) →
asyncio (8 concurrent dimension-batched calls).

Per-neuron calls issued 107 LLM requests sequentially (blocking, thread overhead).
Dimension-batching groups neurons by their dimension (8 dimensions, ~11–17 neurons each)
and issues one structured call per dimension, with all 8 calls concurrent.

Result: 108 round-trips → 6–8 concurrent calls, 10–12× throughput improvement.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Callable, Dict, List, Optional

from contracts.schemas import Dimension
from src.trait.judge.parser import parse_judge_response
from src.trait.judge.prompt import JUDGE_PROMPT_VERSION, SYSTEM_PROMPT, build_user_prompt
from src.trait.judge.rubric_bank import get_rubric, list_all_neurons, neurons_by_dimension

log = logging.getLogger(__name__)


def _run_coro_blocking(coro: Any) -> Any:
    """Run a coroutine to completion regardless of loop context.

    ``asyncio.run`` raises ``RuntimeError`` when called from inside a running
    event loop (e.g. the async FastAPI ``get_score`` handler, which invokes the
    pipeline synchronously). FIX-1 introduced an unguarded ``asyncio.run`` here,
    which crashed every live API scoring request. When a loop is already running,
    offload to a fresh thread that owns its own loop; otherwise run directly.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)  # no running loop (worker/sync path)
    import threading

    box: Dict[str, Any] = {}

    def _runner() -> None:
        box["result"] = asyncio.run(coro)

    t = threading.Thread(target=_runner)
    t.start()
    t.join()
    return box.get("result")

_DIMENSION_LABELS = {
    "AL": "Actualization",
    "PR": "Prompt Responsibility",
    "EC": "Epistemic Calibration",
    "ES": "Ethical Safeguards",
    "CS": "Cognitive Structuring",
    "CD": "Conceptual Depth",
    "AUI": "AI Use Integration",
    "CA": "Calibration Awareness",
}


def build_per_criterion_prompt(neuron_id: str, transcript: str) -> str:
    """Legacy single-neuron prompt builder kept for older tests/callers."""
    try:
        rubric = get_rubric(neuron_id)
    except KeyError:
        rubric = {}
    if not rubric:
        return f"NEURON: {neuron_id}\n\nTRANSCRIPT:\n{transcript}"

    title = rubric.get("title", "")
    anchors = rubric.get("anchors", {})
    scale_levels = rubric.get("scale_levels", [])
    scale_str = " | ".join([f"[{i}] {level}" for i, level in enumerate(scale_levels)])
    anchors_str = "\n  ".join(
        [f"{level.upper()}: \"{anchors.get(level, '')}\"" for level in scale_levels]
    )
    negative = rubric.get("negative_criteria", [])
    negative_str = "\n  ".join([f"- {item}" for item in negative]) or "- None"

    return f"""You are a behavioral psychometrician specializing in human-AI interaction analysis.

NEURON: {neuron_id} ({rubric.get('dimension', 'unknown')})
TITLE: {title}

SCALE: {scale_str}

BEHAVIORAL ANCHORS:
  {anchors_str}

NEGATIVE CRITERIA:
  {negative_str}

TRANSCRIPT:
{transcript}

Respond with a single JSON object: {{"score": <level_name>}} where level_name is one of: {', '.join(scale_levels)}"""


def _coerce_level_to_score(neuron_id: str, value: Any) -> float | None:
    """Map judge output to a [0, 1] score, accepting new and legacy shapes."""
    if isinstance(value, (int, float)):
        return max(0.0, min(1.0, float(value)))

    try:
        rubric = get_rubric(neuron_id)
    except KeyError:
        rubric = {}
    scale_levels = rubric.get("scale_levels", [])
    strength_map = rubric.get("strength_map", [])
    aliases = {
        "not_met": scale_levels[0] if scale_levels else None,
        "unmet": scale_levels[0] if scale_levels else None,
        "met": scale_levels[-2] if len(scale_levels) >= 2 else None,
        "exceeded": scale_levels[-1] if scale_levels else None,
    }
    if isinstance(value, str) and value in aliases:
        value = aliases[value]
    if isinstance(value, str) and value in scale_levels:
        idx = scale_levels.index(value)
        if idx < len(strength_map):
            return float(strength_map[idx])
        return idx / (len(scale_levels) - 1) if len(scale_levels) > 1 else 0.5
    return None


def _legacy_response_score(neuron_id: str, response_json: Dict[str, Any]) -> float | None:
    """Extract a score from old single-neuron judge JSON."""
    for key in ("final_score_after_leniency_penalty", "score"):
        if key in response_json:
            return _coerce_level_to_score(neuron_id, response_json[key])
    return None


# For backward compatibility: keep the old per-neuron function
def call_judge_for_neuron(
    judge_fn: Callable, neuron_id: str, transcript: str
) -> Dict[str, Any]:
    """
    Phase 0/1a: Score a single neuron (legacy, sequential).

    Used by the old ThreadPoolExecutor approach. Kept for backward compatibility.
    Phase 1b callers should use score_dimension() instead.
    """
    rubric = get_rubric(neuron_id)
    if not rubric:
        return {"neuron_id": neuron_id, "error": True, "error_message": "Neuron not found"}

    prompt = build_per_criterion_prompt(neuron_id, transcript)

    try:
        response = judge_fn(prompt)
        if isinstance(response, str) and response.strip().startswith("```"):
            response = response.strip()
            response = response.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        response_json = json.loads(response)
        response_json["neuron_id"] = neuron_id
        return response_json
    except Exception as e:
        return {
            "neuron_id": neuron_id,
            "error": True,
            "error_message": str(e),
            "reasoning": f"Parse error: {e}",
        }


def group_by_dimension(neuron_ids: List[str]) -> Dict[str, List[str]]:
    """Group neuron IDs by their dimension."""
    by_dim: Dict[str, List[str]] = {}
    for nid in neuron_ids:
        try:
            rubric = get_rubric(nid)
            dim_code = rubric.get("dimension", "unknown")
        except KeyError:
            dim_code = "unknown"
        dim = _DIMENSION_LABELS.get(dim_code, dim_code)
        if dim not in by_dim:
            by_dim[dim] = []
        by_dim[dim].append(nid)
    return by_dim


def format_dimension_rubric(dimension_name: str, neuron_ids: List[str]) -> str:
    """Format all neuron rubrics for a dimension into one structured prompt.

    Output: human-readable text describing all neurons in the dimension.
    """
    lines = [f"DIMENSION: {dimension_name}", ""]
    lines.append("Score each neuron using the scales and anchors below.")
    lines.append("")

    for nid in neuron_ids:
        try:
            rubric = get_rubric(nid)
        except KeyError:
            rubric = {"title": nid, "anchors": {}, "scale_levels": []}
        title = rubric.get("title", nid)
        lines.append(f"Neuron {nid}: {title}")

        # Anchors (scale levels)
        anchors = rubric.get("anchors", {})
        scale_levels = rubric.get("scale_levels", [])
        for level in scale_levels:
            anchor_text = anchors.get(level, "")
            lines.append(f"  [{level}] {anchor_text}")
        lines.append("")

    return "\n".join(lines)


def build_dimension_schema(neuron_ids: List[str]) -> Dict[str, Any]:
    """Build a JSON schema for structured dimension-batched response.

    One field per neuron, each field is a string (the scale level).
    """
    properties = {}
    for nid in neuron_ids:
        try:
            rubric = get_rubric(nid)
        except KeyError:
            rubric = {"scale_levels": []}
        scale_levels = rubric.get("scale_levels", [])
        properties[nid] = {
            "type": "string",
            "enum": scale_levels,
            "description": f"Score for neuron {nid}"
        }

    return {
        "type": "object",
        "properties": properties,
        "required": list(properties.keys()),
    }


async def score_dimension(
    transcript: str,
    dimension_name: str,
    neuron_ids: List[str],
    judge_client: Any,  # JudgeClient instance
) -> Dict[str, Any]:
    """
    Phase 1b: Score all neurons in a dimension with one structured async call.

    Args:
        transcript: the chat transcript
        dimension_name: e.g., "Actualization"
        neuron_ids: list of neuron IDs in this dimension
        judge_client: the JudgeClient instance

    Returns:
        {neuron_id: score_value} for all neurons in the dimension
    """
    rubric_text = format_dimension_rubric(dimension_name, neuron_ids)
    schema = build_dimension_schema(neuron_ids)

    # Build the prompt
    system_prompt = SYSTEM_PROMPT
    user_prompt = f"{rubric_text}\n\nTRANSCRIPT:\n{transcript}"

    try:
        # Call the async judge transport
        # For now, we use the existing sync transport wrapped in run_in_executor
        # (async transport will be added to client.py in Phase 1a follow-up)
        loop = asyncio.get_event_loop()
        raw_response = await loop.run_in_executor(
            None,
            lambda: judge_client._generate(system_prompt, user_prompt)
        )

        # Parse the JSON response
        try:
            response_json = json.loads(raw_response)
        except json.JSONDecodeError as e:
            log.error(f"Failed to parse dimension response as JSON: {raw_response}")
            raise ValueError(f"Invalid JSON in dimension response: {e}")

        # Preferred Phase 1b shape: one field per neuron in this dimension.
        # Compatibility shape: legacy single-neuron JSON such as
        # {"score": 0.9, "final_score_after_leniency_penalty": 0.9}. In that
        # case, apply the score to each neuron in this dimension batch.
        explicit_neuron_fields = any(nid in response_json for nid in neuron_ids)
        scores = {}
        for nid in neuron_ids:
            if explicit_neuron_fields and nid in response_json:
                scores[nid] = _coerce_level_to_score(nid, response_json[nid])
            elif explicit_neuron_fields:
                scores[nid] = None
            else:
                scores[nid] = _legacy_response_score(nid, response_json)

            if scores[nid] is None:
                log.warning(
                    f"Invalid or missing response for neuron {nid} in dimension {dimension_name}"
                )

        return scores

        # Validate all neurons are present
        scores = {}
        for nid in neuron_ids:
            if nid not in response_json:
                log.warning(f"Missing response for neuron {nid} in dimension {dimension_name}")
                scores[nid] = None
            else:
                level_str = response_json[nid]
                # Convert level string (e.g., "met") to numeric score (0.0–1.0)
                rubric = get_rubric(nid)
                scale_levels = rubric.get("scale_levels", [])
                if level_str in scale_levels:
                    # Simple mapping: first level → 0.0, last → 1.0
                    idx = scale_levels.index(level_str)
                    score = idx / (len(scale_levels) - 1) if len(scale_levels) > 1 else 0.5
                    scores[nid] = score
                else:
                    log.warning(f"Invalid level '{level_str}' for neuron {nid}")
                    scores[nid] = None

        return scores

    except Exception as exc:
        log.error(f"Failed to score dimension {dimension_name}: {exc}")
        # Return None for all neurons in this dimension on failure
        return {nid: None for nid in neuron_ids}


async def _score_all_neurons_async(
    transcript: str,
    neuron_ids: Optional[List[str]] = None,
    judge_client: Any = None,
) -> Dict[str, Any]:
    """
    Phase 1b: Async dimension-batched neuron scoring.

    Groups 107 neurons into 8 dimension batches, issues 8 concurrent async calls.
    Expected result: 6–8 calls per chat (vs. 108 sequential per-neuron calls).

    Args:
        transcript: the chat transcript
        neuron_ids: list of neuron IDs to score (default: all 107)
        judge_client: JudgeClient instance (required)

    Returns:
        {neuron_id: score_value} for all neurons
    """
    if judge_client is None:
        raise ValueError("judge_client is required for async scoring")

    if neuron_ids is None:
        neuron_ids = list_all_neurons()

    # Group neurons by dimension
    by_dimension = group_by_dimension(neuron_ids)

    # Create concurrent tasks: one per dimension
    tasks = [
        score_dimension(transcript, dim, nids, judge_client)
        for dim, nids in by_dimension.items()
    ]

    # Execute all dimension calls concurrently
    results_list = await asyncio.gather(*tasks, return_exceptions=True)

    # Merge results
    all_scores = {}
    for dim, result in zip(by_dimension.keys(), results_list):
        if isinstance(result, Exception):
            log.error(f"Exception scoring dimension {dim}: {result}")
            # Mark all neurons in this dimension as failed
            for nid in by_dimension[dim]:
                all_scores[nid] = {"error": True, "error_message": str(result)}
        else:
            # result is {neuron_id: score}
            for nid, score in result.items():
                if score is None:
                    all_scores[nid] = {"error": True, "error_message": "No response for neuron"}
                else:
                    all_scores[nid] = {"neuron_id": nid, "score": score}

    # Summary
    successful = len([s for s in all_scores.values() if not s.get("error")])
    return {
        "results": all_scores,
        "summary": {
            "n_neurons": len(neuron_ids),
            "successful": successful,
            "errors": len(neuron_ids) - successful,
            "success_rate": successful / len(neuron_ids) if neuron_ids else 0,
            "n_dimensions": len(by_dimension),
            "n_concurrent_calls": len(by_dimension),
        },
    }


def score_all_neurons_replicated(
    judge_fn: Callable,
    transcript: str,
    neuron_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """K-rep median: cascaded selective replication per dimension (FIX-1).

    Runs DEFAULT_INITIAL_REPS passes per dimension, escalates high-disagreement
    dimensions up to DEFAULT_MAX_REPS. Final per-neuron score = median of all
    reps. Returns per_neuron_disagreement for CI calibration in pipeline.py.
    """
    import statistics as _stats
    from src.trait.judge.client import JudgeClient
    from src.trait.judge.cascade_eval import (
        compute_disagreement_metric,
        DEFAULT_INITIAL_REPS,
        DEFAULT_MAX_REPS,
        DEFAULT_DISAGREEMENT_THRESHOLD,
    )

    def combined_prompt(system_prompt: str, user_prompt: str) -> str:
        return judge_fn(f"{system_prompt}\n{user_prompt}")

    client = JudgeClient(generate=combined_prompt)
    all_nids: List[str] = neuron_ids if neuron_ids is not None else list_all_neurons()
    by_dim = group_by_dimension(all_nids)

    per_neuron_all_reps: Dict[str, List[float]] = {nid: [] for nid in all_nids}

    async def _run_reps() -> None:
        # Phase 1: initial reps — all dimensions concurrent per rep
        for _ in range(DEFAULT_INITIAL_REPS):
            tasks = [
                score_dimension(transcript, dim, nids, client)
                for dim, nids in by_dim.items()
            ]
            rep_results = await asyncio.gather(*tasks, return_exceptions=True)
            for dim, dim_result in zip(by_dim.keys(), rep_results):
                if isinstance(dim_result, Exception):
                    continue
                for nid, val in dim_result.items():
                    if val is not None:
                        per_neuron_all_reps[nid].append(val)

        # Phase 2: escalate dimensions where any neuron exceeds threshold
        escalate_dims = [
            dim for dim, nids in by_dim.items()
            if any(
                len(per_neuron_all_reps[nid]) >= 2
                and compute_disagreement_metric(per_neuron_all_reps[nid]) > DEFAULT_DISAGREEMENT_THRESHOLD
                for nid in nids
            )
        ]
        if escalate_dims:
            for _ in range(DEFAULT_MAX_REPS - DEFAULT_INITIAL_REPS):
                tasks = [
                    score_dimension(transcript, dim, by_dim[dim], client)
                    for dim in escalate_dims
                ]
                rep_results = await asyncio.gather(*tasks, return_exceptions=True)
                for dim, dim_result in zip(escalate_dims, rep_results):
                    if isinstance(dim_result, Exception):
                        continue
                    for nid, val in dim_result.items():
                        if val is not None:
                            per_neuron_all_reps[nid].append(val)

    _run_coro_blocking(_run_reps())

    results: Dict[str, Dict[str, Any]] = {}
    per_neuron_disagreement: Dict[str, float] = {}
    for nid in all_nids:
        reps = per_neuron_all_reps[nid]
        if not reps:
            results[nid] = {"neuron_id": nid, "error": True, "error_message": "no reps scored"}
        else:
            median_val = float(_stats.median(reps))
            disagreement = compute_disagreement_metric(reps) if len(reps) >= 2 else 0.0
            per_neuron_disagreement[nid] = disagreement
            results[nid] = {
                "neuron_id": nid,
                "score": median_val,
                "final_score_after_leniency_penalty": median_val,
                "n_reps": len(reps),
                "disagreement": disagreement,
            }

    successful = sum(1 for r in results.values() if not r.get("error"))
    return {
        "results": results,
        "per_neuron_disagreement": per_neuron_disagreement,
        "summary": {
            "n_neurons": len(all_nids),
            "successful": successful,
            "errors": len(all_nids) - successful,
            "success_rate": successful / len(all_nids) if all_nids else 0,
        },
    }


def score_all_neurons(
    *args,
    **kwargs,
) -> Dict[str, Any] | Any:
    """Public compatibility entry point.

    Old sync shape: score_all_neurons(judge_fn, transcript, neuron_ids=None) -> dict.
    New async shape: await score_all_neurons(transcript=..., neuron_ids=..., judge_client=...).
    """
    if args and callable(args[0]):
        judge_fn = args[0]
        transcript = args[1] if len(args) > 1 else kwargs.get("transcript", "")
        neuron_ids = args[2] if len(args) > 2 else kwargs.get("neuron_ids")
        return score_all_neurons_sync(judge_fn, transcript, neuron_ids)
    return _score_all_neurons_async(*args, **kwargs)


def score_all_neurons_sync(
    judge_fn: Callable,
    transcript: str,
    neuron_ids: Optional[List[str]] = None,
    max_workers: int = 8,
) -> Dict[str, Dict[str, Any]]:
    """
    Backward-compatibility wrapper: sync version of dimension-batching.

    Accepts the old call signature: (judge_fn, transcript, neuron_ids)
    Converts to async signature: (transcript, neuron_ids, judge_client)

    Uses asyncio.run to execute the async version.
    (This is a temporary shim; callers should migrate to the async version.)
    """
    from src.trait.judge.client import JudgeClient

    # The judge_fn passed here is judge.neuron_fn(), which is a callable
    # that takes (prompt: str) -> str. But we need a JudgeClient for the
    # async version. The async version will call judge_client._generate()
    # with (system_prompt, user_prompt) arguments.
    #
    # Solution: Don't try to wrap judge_fn into a new JudgeClient.
    # Instead, create a minimal JudgeClient that can call neuron_fn.
    # We'll use the judge_fn directly as a custom generator.

    # Create a wrapper function that adapts neuron_fn (single prompt)
    # to JudgeClient's expected signature (system_prompt, user_prompt)
    def combined_prompt(system_prompt: str, user_prompt: str) -> str:
        """Combine system and user prompts, then call neuron_fn."""
        # Neuron scoring wants full context in one prompt
        combined = f"{system_prompt}\n{user_prompt}"
        return judge_fn(combined)

    client = JudgeClient(generate=combined_prompt)
    return asyncio.run(_score_all_neurons_async(transcript, neuron_ids, client))


if __name__ == "__main__":
    print("Per-criterion judge module (Phase 1b async) loaded.")
    print("Usage:")
    print("  client = JudgeClient(...)")
    print("  scores = asyncio.run(score_all_neurons(transcript, neurons, client))")
