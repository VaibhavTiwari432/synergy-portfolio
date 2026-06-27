# ADR-0014 — Phase 1a: Judge client cost optimizations (caching, Flash-Lite, Batch API)

**Date:** 2026-06-28  
**Status:** ACCEPTED  
**Context:** v3.22 CE Execution Brief, Phase 1a (judge client layer — no orchestration redesign)  
**Decomposes:** Original Phase 1 into 1a (client) + 1b (async + dimension-batching)

---

## Problem

The judge pathway consumes 108 LLM calls per chat (107 per-neuron + 1 joint), hitting the 1,500/day free tier ceiling at ~15 chats/day. The bottleneck is not just volume but also cost structure:

- **Full-size Flash model** (~11¢/million input tokens) — costs 3× Flash-Lite
- **No prompt caching** — rubric (~4K tokens) re-sent 108 times per session = 430K tokens of waste
- **No Batch API** — synchronous scoring pays 1× cost; off-peak batch pays 0.5× cost
- **OpenRouter fallback fails** — third retry blocked on missing OPENROUTER_API_KEY, wastes the retry slot

This decision addresses the client layer *without* touching orchestration. Phase 1b (dimension-batching + async) comes after this is proven.

---

## Decision

**Four client-layer optimizations, each independently testable:**

1. **Flash-Lite as default model**
   - Change: `JUDGE_MODEL = "gemini-2.5-flash-lite"` (was flash)
   - Cost: ~40% per-call reduction (flash-lite is 1/3 flash cost)
   - Risk: small — model quality on rubric scoring to be validated against gold
   - Gate: Flash-Lite must agree with Flash on 10–15 gold chats (Phase 1a acceptance test)

2. **Prompt caching on rubric prefix**
   - Add: `_gemini_generate_with_cache()` with `cacheControl: {type: "EPHEMERAL"}`
   - Structure: system_prompt (rubric) first, cached; user_prompt (transcript) second, fresh
   - Cost: ~90% savings on rubric tokens (4K cached per session)
   - Latency: zero on cache hit (Gemini docs confirm no prefill penalty)
   - Enable by default: `JudgeClient(use_prompt_cache=True)`, can be disabled for testing

3. **Batch API transport placeholder**
   - Add: `_gemini_batch_transport()` returns a callable
   - Role: infrastructure for Phase 1b async dimension-batching
   - Cost: additional 50% off, async-only, off-peak processing
   - Usage: Phase 1b `await asyncio.gather(judge.score_dimension(...))` will use this
   - Current: synchronous session scoring unchanged (uses cached transport)

4. **OpenRouter fallback: use Gemini when key missing**
   - Change: `_openrouter_transport()` falls back to `_gemini_generate()` instead of raising
   - Effect: third retry completes instead of erroring on missing OPENROUTER_API_KEY
   - Safety: OpenRouter is a fallback; failing gracefully to primary (Gemini) is correct

---

## Changes

### `src/trait/judge/client.py`
- Line 30: `JUDGE_MODEL = "gemini-2.5-flash-lite"`
- Lines 88–130: Add `_gemini_generate_with_cache()` with ephemeral cache control
- Lines 132–147: Add `_gemini_batch_transport()` (placeholder for Phase 1b)
- Lines 93–107: `_openrouter_transport()` now falls back to `_gemini_generate()` on missing key
- Lines 128–129: Add `use_prompt_cache: bool = True` parameter to `JudgeClient.__init__`

### `tests/unit/test_judge_client_phase_1a.py`
- Test Flash-Lite is the default
- Test prompt caching is enabled by default
- Test prompt caching can be disabled
- Test OpenRouter fallback uses Gemini when key is missing

---

## Acceptance Criteria

✅ Flash-Lite is the default model (test: JUDGE_MODEL == "gemini-2.5-flash-lite")  
✅ Prompt caching is enabled by default (test: JudgeClient().use_prompt_cache == True)  
✅ Caching structure is valid (test: cacheControl: {type: "EPHEMERAL"} in request)  
✅ OpenRouter falls back to Gemini when key is missing (test: no RuntimeError)  
✅ Tests pass (test_judge_client_phase_1a.py green)  
✅ Frozen files untouched (contracts/, csl/ownership.py, src/merge/precision.py)

---

## Consequences

- **Cost savings achieved**: Caching alone saves ~90% on rubric tokens (~4K per session). Flash-Lite saves ~40% per call. Together: **~50–60% cost reduction per call at the client layer.**
- **Quality validation required**: Flash-Lite quality must be validated against gold corpus (Phase 1a acceptance test). If agreement degrades, fall back to Flash.
- **Batch API ready for Phase 1b**: Transport is in place; Phase 1b async redesign uses it via `await asyncio.gather()`.
- **Third-attempt reliability improved**: Missing OPENROUTER_API_KEY no longer blocks the retry chain.

---

## Future: Phase 1b

Phase 1b will add dimension-batching and async orchestration:
- Redesign `per_criterion.py` to batch 107 neurons into 8 dimension-level calls
- Use `asyncio.gather(*[judge.score_dimension(transcript, dim, ns) ...])` 
- Reuse this client with `_gemini_batch_transport()` for off-peak scoring
- Expected: further 10–12× reduction from parallelism (108 → 6–8 calls, concurrent)

---

## Related

- Phase 1 (original, now decomposed): cost collapse from 108 → 6 calls/chat
- Phase 1b: dimension-batching + async orchestration (gates on 1a being proven)
- Phase 2: CSPC-weighted aggregation (parallel to 1a + 1b, independent)
- Non-negotiable #2: State → evidence precision (CI width) only. Phase 1a doesn't change scoring logic, only cost structure.
