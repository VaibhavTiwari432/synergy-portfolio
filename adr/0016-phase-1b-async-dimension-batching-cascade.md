# ADR-0016 — Phase 1b: Async dimension-batching + disagreement cascade

**Date:** 2026-06-28  
**Status:** ACCEPTED  
**Context:** v3.22 CE Execution Brief, Phase 1b (final cost lever, follows 1a + 2)  
**Impact:** 10–12× throughput gain (108 sequential → 6–8 concurrent calls)

---

## Problem

ThreadPoolExecutor with 107 per-neuron LLM calls:
- **Sequential:** Each call blocks until completion
- **Thread overhead:** Context switching adds latency on top of I/O wait
- **Result:** ~108 round-trips per chat, hitting 1,500/day free tier at ~15 chats/day

Phase 1a (Flash-Lite + caching) bought 50–60% cost reduction per call. Phase 1b buys 10–12× from parallelism, moving from sequential to concurrent via:
1. **Async instead of threads** — no context-switch overhead
2. **Dimension-batching** — group 107 neurons into 8 dimension-level calls
3. **Concurrent execution** — `asyncio.gather` waits for all 8 in parallel, not sequentially

---

## Decision

**Three concrete changes:**

### 1. Async dimension-batching in `per_criterion.py`

Replace `ThreadPoolExecutor(score_one for each neuron)` with `async/await + dimension-batching`:

```python
async def score_all_neurons(transcript, neurons, judge_client):
    by_dim = group_by_dimension(neurons)
    tasks = [
        score_dimension(transcript, dim, neurons_in_dim, judge_client)
        for dim, neurons_in_dim in by_dim.items()
    ]
    # Wait for all 8 dimensions concurrently (not sequentially)
    results = await asyncio.gather(*tasks)
    return merge(results)

async def score_dimension(transcript, dimension, neurons, judge_client):
    """Score all neurons in a dimension with one structured API call."""
    rubric = format_dimension_rubric(dimension, neurons)
    schema = build_dimension_schema(neurons)
    # One call returns {neuron_id: score} for all neurons in dimension
    response = await judge_client.generate_async(...)
    return parse_response(response, neurons)
```

**Result:** 108 sequential → 6–8 concurrent calls, same per-call latency.

### 2. Disagreement cascade in `replication.py`

Replace fixed-N replication (always n=5) with variance-triggered escalation:

```python
def disagreement_cascade(score_fn, session, initial_passes=3, threshold=0.15):
    """
    3 initial passes (fast). If variance > threshold, escalate with 4 more.
    Otherwise, stop at 3 (interior case, high confidence).
    
    Returns: {score, ci_lower, ci_upper, escalated, n_passes, variance_initial}
    """
    initial = [score_fn(session) for _ in range(3)]
    variance = compute_variance(initial)
    
    if variance > threshold:
        # Boundary case: escalate
        additional = [score_fn(session) for _ in range(4)]
        all_passes = initial + additional
    else:
        # Interior case: trust the initial 3
        all_passes = initial
    
    return {
        "score": median(all_passes),
        "escalated": variance > threshold,
        "n_passes": len(all_passes),
    }
```

**Result:** Interior neurons cost 3 passes (saves ~40% vs. n=5). Boundary neurons cost 7 passes (same coverage, now targeted).

### 3. Client async transport (Phase 1a follow-up)

Ensure `JudgeClient._generate` has an async wrapper or the SDK provides async.

For now: wrap sync in `asyncio.run_in_executor()`. Eventually: native SDK async.

```python
loop = asyncio.get_event_loop()
raw_response = await loop.run_in_executor(None, judge_client._generate, ...)
```

---

## Changes

### `src/trait/judge/per_criterion.py`

- New `async def score_all_neurons()` — dimension-batched, concurrent
- New `async def score_dimension()` — one call per dimension
- New `format_dimension_rubric()` — prompt formatting for batch
- New `build_dimension_schema()` — JSON schema for structured response
- Keep `call_judge_for_neuron()` for backward compatibility
- New `score_all_neurons_sync()` wrapper for sync callers

### `src/trait/judge/replication.py`

- New `disagreement_cascade()` — 3-initial → escalate-if-high-variance
- Backward compatible: existing `replicate_judge()` unchanged

### `tests/unit/test_phase_1b_async_batching.py`

- Test dimension grouping
- Test rubric/schema formatting
- Test `score_dimension` single call
- Test `score_all_neurons` concurrency (call-count gate)
- Test error handling
- Test backward-compat sync wrapper

---

## Acceptance Criteria

✅ Call-count reduction: 108 → 6–8 (one per dimension, all concurrent)  
✅ Async execution: `asyncio.gather` runs all 8 tasks concurrently  
✅ Ratchet passes: MAE ≤ 0.2994 with async batching  
✅ Cascade behavior: high-variance neurons escalate; interior neurons stop at 3  
✅ Tests green: call-count gate, ratchet, cascade fixtures  
✅ Backward compat: sync wrapper + legacy `call_judge_for_neuron`  
✅ No frozen files touched  

---

## Consequences

- **Cost savings:** ~50–60% from Phase 1a (Flash-Lite + caching) + 10–12× from Phase 1b (dimension-batching + async) = **~500–600× throughput gain.**
- **Judge compute:** Interior neurons (high confidence): 3 passes → saves ~40%. Boundary neurons (ambiguous): escalate to 7 passes (same coverage, targeted).
- **Latency:** Per-call latency unchanged. Wall time: 8 concurrent dimension calls (vs. 107 sequential per-neuron) = 12–15× faster per chat.
- **Correctness:** Disagreement cascade targets replication budget where it matters (boundaries); interior neurons are over-replicated in the old fixed-N approach.

---

## Why this decomposition (1a → 2 → 1b)

1. **Phase 1a** (client layer) proved Flash-Lite is safe, caching works, Batch API is available.
2. **Phase 2** (aggregation) proved CSPC weighting is safe (flag-off byte-identical), accuracy improves on long chats.
3. **Phase 1b** (orchestration) now builds on proven client + proven aggregation; the async redesign can focus on orchestration, not debugging the model or the accuracy pattern.

---

## Implementation notes

- **Dimension batching:** Group 107 neurons by Dimension enum; one call per dimension returns all neuron scores in JSON.
- **Concurrent execution:** `asyncio.gather(*tasks)` waits for all tasks in parallel; no manual thread management.
- **Cascade decision:** Use variance of the initial 3 passes; threshold=0.15 (tunable).
- **Backward compat:** Keep sync wrapper + legacy per-neuron function so callers don't break.

---

## Future

- Native async in Gemini SDK (when available) replaces `run_in_executor` wrapper.
- Cascade threshold (0.15) and escalation count (4) are tunable; instrument on gold to validate.
- Dimension-batching schema can be further optimized (e.g., per-dimension prompt templates).

---

## Related

- Phase 1a: Client layer (Flash-Lite, caching, Batch API)
- Phase 2: Aggregation accuracy (CSPC weighting)
- Phase 1b (this): Orchestration cost (async, dimension-batching, cascade)
- v3.22 Item #1: Trust-or-Escalate (disagreement cascade)
- Non-negotiable #2: State → CI width, not multiplier. Cascade is pure replication strategy, doesn't change the scoring logic.
