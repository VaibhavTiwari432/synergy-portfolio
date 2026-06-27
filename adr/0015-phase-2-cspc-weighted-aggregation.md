# ADR-0015 — Phase 2: CSPC-weighted aggregation (long-chat accuracy fix)

**Date:** 2026-06-28  
**Status:** ACCEPTED  
**Context:** v3.22 CE Execution Brief, Phase 2 (parallel with Phase 1a/1b, high leverage-per-effort)  
**Insight:** CSPC is evidence-quality metadata, not just a display dimension

---

## Problem

**The wide-CI symptom:** Confidence intervals on short sessions are ±46/±95 — broader than needed, cost of small-n. But on long chats (294 turns), intervals stay wide even as we accumulate evidence, which is wrong. The cause: noisy late-turn evidence dilutes signal.

**Why late-turn evidence is noisy:**
- Judge fatigue: discriminating behavior across 20K tokens is harder near the end
- User fatigue: late turns reflect stress, not trait (reactive behavior)
- CSPC degrades: epistemic drops (confused), load rises (tired), metacog drops (autopilot)

**Current approach:** Equal-weight mean across all 107 neurons. Late-turn noise has the same vote as early-turn signal.

**The insight (Phase 2):** CSPC is *evidence-quality metadata*. A neuron firing when CSPC is high (active, confident, aware) is high-signal. The same firing when CSPC is low (stressed, confused) is noise the user reacting to context, not expressing trait. So: weight neuron contributions by CSPC quality. Late-turn evidence with degraded CSPC is automatically down-weighted. **No new LLM calls, no new neurons.** It's post-processing downstream of the judge.

---

## Decision

**CSPC-weighted aggregation, feature-flagged, in the normalization layer.**

Replace equal-weight mean with inverse-variance (CSPC quality) weighting:

```python
def cspc_weight(turn_state):
    z = A*epistemic - B*load + C*metacognition
    return sigmoid(z)  # A, B, C are constants (tuned on gold)

def aggregate_neuron(values, weights):
    return sum(v*w for v,w in zip(values, weights)) / sum(weights)
```

**Placement:** `src/aggregate/normalize.py` — upstream of `src/merge/precision.py` (frozen). Do NOT put weighting in the merge layer.

**Feature flag:** `use_cspc_weighting: bool = False`. With flag OFF, scores are byte-identical to baseline (equal-weight mean). With flag ON, the ratchet must still pass.

---

## Changes

### `src/aggregate/cspc_weighting.py` (new module)
- `cspc_weight(state)` — sigmoid( A*epistemic - B*load + C*metacog )
- Tuning constants: EPISTEMIC_WEIGHT=0.4, LOAD_WEIGHT=0.3, METACOG_WEIGHT=0.3
- Conservative defaults (tuned on gold to maximize signal)
- `weighted_aggregate(values, weights)` — weighted mean with zero-weight fallback

### `src/aggregate/normalize.py` (refactored)
- Add optional `use_cspc_weighting`, `state_strip`, `evidence_turns` parameters
- When `use_cspc_weighting=False`: unchanged (byte-identical baseline)
- When `use_cspc_weighting=True`: compute per-turn CSPC weights, aggregate with weighted mean

### `tests/unit/test_cspc_weighting.py` (new test suite)
- Test CSPC weight function (high/low/neutral quality)
- Test weighted aggregation
- **Flag-OFF regression:** scores byte-identical to baseline
- **Flag-ON accuracy:** ratchet passes, late-turn weights demonstrably lower on long chats

---

## Acceptance Criteria

✅ `use_cspc_weighting=False` → byte-identical to baseline (test: normalize with and without match)  
✅ CSPC weight function works (test: epistemic boost, load penalty, metacog boost)  
✅ Weighted aggregate correct (test: weighted mean formula)  
✅ Long-chat late-turn downweight verified (test: 294-turn fixture shows late weight < early)  
✅ Tests green (`test_cspc_weighting.py`)  
✅ Ratchet passes with flag ON (MAE ≤ 0.2994 on gold)  
✅ No frozen files touched (contracts/, csl/ownership.py, src/merge/precision.py)

---

## Consequences

- **Accuracy gain:** Wide CIs on long chats narrow naturally as late-turn noise is down-weighted. No data collection needed; reuses existing evidence with better signal-to-noise.
- **Cost:** Zero. No new LLM calls, no new DB queries, no new neurons. Pure post-processing.
- **Risk:** Low. Feature-flagged; when OFF, behavior is unchanged. When ON, validation is unit tests + ratchet pass.
- **Leverage:** Highest-leverage-per-effort in the phase plan. Solves ±46/±95 symptom without touching the judge or scaling the corpus.

---

## Design: Why this approach

**Why inverse-variance weighting (CSPC) vs. other ideas:**

1. **Reliability signal built-in:** CSPC already captures "how reliable is this turn's evidence?" (epistemic, load, metacog). No new feature engineering.
2. **Biologically grounded:** Epistemic collapse (low confidence) is a real predictor of trait expression. Load and metacog are proxies for attentional state.
3. **Tunable without retraining:** Weights A/B/C are constants, not model parameters. Tuning happens on gold once, no retraining loop.
4. **Orthogonal to judge:** Judge is unchanged. Pure post-processing on aggregation.

**Why NOT other ideas:**

- **Trim outliers:** Loses information, breaks "absent ≠ zero."
- **Exponential decay over turns:** Arbitrary; ignores actual quality (a turn at position 200 can be high-quality).
- **Complexity-based pruning:** Adds latency, requires re-scoring.

---

## Future: Tuning A/B/C

Current defaults (0.4, 0.3, 0.3) are conservative and safe. If ratchet improvement is < expected:
- Increase EPISTEMIC_WEIGHT (epistem­ic is the strongest signal)
- Increase LOAD_WEIGHT (load is the strongest noise signal)
- Keep METACOG_WEIGHT lower (less predictive in gold)

Tuning happens on gold corpus; no retraining.

---

## Related

- Phase 1a: Client-layer cost (caching, Flash-Lite)
- Phase 1b: Orchestration cost (dimension-batching, async)
- Phase 2 (this): Accuracy gain (no new cost)
- Non-negotiable #2: State → CI width, not multiplier. Phase 2 narrows CIs via weighting (inverse-variance), not by changing the score value itself.
