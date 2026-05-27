# Step 2: Full Calibration Run — Instruction

This document is the pre-flight checklist and run plan for the full 18-chat
calibration run. Do not start until gc-001 v4 has been reviewed and judged
ready for Step 2.

---

## Prerequisites

### 1. v4 prompt must be approved

The holistic prompt (v4) was finalized after gc-001 testing. Before running
Step 2, confirm:

- gc-001 v4 within-2-delta ≥ 70% ✓
- CA, CD reasoning text shows judge applying Case 1 / magnitude rule correctly
- EC reasoning text shows judge is not uplifting for editorial pushback turns
- Resolve CS risk from v4 run: if v4 reasoning text shows the magnitude guidance
  pushing CS to low mechanically (same rule applied identically to CA/CD without
  reading content), remove the magnitude fallback from the prompt before running
  Step 2. The reasoning text is the gate — do not proceed to 18 chats if CS
  shows mechanical application.

### 2. Retry backoff for 429s

The current `withRetry` in `scorer.ts` makes 3 attempts with no delay between
them. For a single chat this is fine. For 18 sequential chats consuming ~100+
calls in one session, consecutive 429s will fail the run if retries fire
immediately against a still-exhausted rate limit.

Before running Step 2, add a sleep to `withRetry` that backs off on 429
responses. The API error body includes `retryDelay` (observed: 20–40 seconds).
A simple fixed delay of 45 seconds between retry attempts on a 429 is
sufficient. Non-429 errors should not sleep.

### 3. Daily quota headroom

Free tier: **20 req/day** for gemini-2.5-flash (not 250 — confirmed against
live API errors on 2026-05-23). At ~5 calls per chat, max 4 chats per day
on the free tier. Step 2 (18 chats, ~110 calls) requires either a paid API
key or spreading across 5+ days using `--resume-from`.

Do not run Step 2 if quota used so far today exceeds 15. Start fresh at the
beginning of a quota day.

---

## Chat set

**21 total gold chats. 3 excluded. 18 included.**

| Excluded | Reason |
|----------|--------|
| gc-004   | OCR-sourced transcript — text quality too low for reliable scoring |
| gc-012   | OCR data quality — same basis as gc-004 and gc-013; excluded after audit |
| gc-013   | OCR-sourced transcript — text quality too low for reliable scoring |

Included chats: gc-001, gc-002, gc-003, gc-005, gc-006, gc-007, gc-008,
gc-009, gc-010, gc-011, gc-016, gc-017, gc-018, gc-019, gc-020, gc-021,
gc-022, gc-023.

**gc-023 note:** Included but likely long — will be sampled to `MAX_SAMPLED_FRAMES`
(currently 9). Verify frame count in dry-run output.

All chats load from `gold_standard/chats_anonymized/`. Originals in
`gold_standard/chats/` are never sent to the API.

---

## Pre-run: change the safety cap

`MAX_CALLS_PER_RUN` in `run_calibration.ts` is currently `2000`. Lower it to
`150` before the Step 2 run.

```typescript
const MAX_CALLS_PER_RUN = 150;
```

Rebuild after the change:

```
pnpm --filter @synergy/judge build
pnpm --filter calibration build
```

Rationale: 18 chats × 10 calls max each = 180. With `MAX_SAMPLED_FRAMES = 9`
and typical chat lengths, the realistic estimate is ~100–120. A cap of 150
allows headroom above the estimate while still hard-stopping if something
is wrong (infinite retry loop, mis-counted chats, etc.).

Revert `MAX_CALLS_PER_RUN` to `2000` after the run if needed for future
single-chat testing.

---

## Step 1 — Dry-run

Run the dry-run pass first. This makes zero API calls and prints the estimated
call count per chat plus the holistic prompt (using placeholder frame data).

```
pnpm --filter calibration calibrate -- --dry-run
```

**Check before proceeding:**

1. Total estimated calls ≤ 150. If over, investigate which chats are producing
   unexpectedly high frame counts.
2. All 18 chats appear in the output (not 17, not 19).
3. No chat shows 0 frames — that means the chunker failed on an edge case.
4. gc-023 frame count is reasonable (≤ 9 sampled from however many total).

If the dry-run estimate is between 150 and 175, consider whether to exclude
one more long chat or raise `MAX_CALLS_PER_RUN` to 175 with explicit sign-off.
Do not raise it above 200.

---

## Step 2 — Live run

```
GEMINI_API_KEY=<key> pnpm --filter calibration calibrate
```

No `--limit` flag. Runs all 18 included chats.

The run is **sequential** — one chat scores completely before the next starts.
This is the existing behavior of the `for` loop in `runCalibration`. Do not
parallelize: the free tier rate limit is per-minute as well as per-day, and
parallel calls will produce a cascade of 429s that eat retries and quota.

**Expected runtime:** ~30–60 minutes depending on API latency and backoff
events. Do not interrupt mid-run. If a chat fails after 3 retry attempts, the
harness logs the error, records it as `status: "failed"` in the report, and
continues to the next chat. A partial result is better than no result.

**Monitor stderr** for token counts and retry events:
```
[tokens] prompt=5700 output=923 total=6623
[retry 1/3] Score frame 1 (gc-007): ...
```

Retry events are normal for occasional 429 bursts. Three consecutive retries
failing on the same frame means the quota is exhausted — stop the run, check
remaining quota, and resume the next day with a `--limit` trick to skip
already-scored chats (not currently supported; add if needed).

---

## Step 3 — Output

The run writes to:

```
calibration/reports/phase1_gemini.json
```

After the run completes successfully, copy to the canonical name:

```
cp calibration/reports/phase1_gemini.json \
   calibration/reports/phase1_gemini_full.json
```

Preserve `phase1_gemini.json` in place — it is the live state of the last full
run and is used as the baseline for any re-runs.

---

## What to report after the run

### 1. Phase 1 exit criteria

```
Phase 1 exit criteria:
  Structural validity : PASS / FAIL
  Within 2 delta      : XX.X%  (threshold: 70%)
  Overall             : PASSED / NOT PASSED
```

If structural validity fails (any chat `status: "failed"`), identify which
chats failed before looking at the metric numbers. A single failed chat can
distort the aggregate.

### 2. Per-dimension MAE and within-2-delta %

Report the `per_dimension` block from the JSON. Eight rows, four columns:
`dim | mae | band_accuracy | within_2_delta | sample_count`.

Dimensions with `sample_count = 0` have no human annotations with observable
signal — they do not count for or against the exit criteria.

### 3. Problem chat flags

For each chat in `chat_results`, count how many dimensions have
`absolute_errors[dim] > 2.0`. Flag any chat where that count is ≥ 3.

These are the chats where the judge is structurally wrong on multiple
dimensions simultaneously — likely a rubric interpretation failure or a chat
type the frame-level scorer has not seen. Inspect them manually before
concluding anything about the overall metric.

Suggested query against the report JSON:

```javascript
report.chat_results
  .filter(r => r.status === "scored")
  .map(r => ({
    id: r.chat_id,
    bad_dims: Object.entries(r.absolute_errors)
      .filter(([, e]) => e !== null && e > 2.0)
      .map(([d]) => d)
  }))
  .filter(r => r.bad_dims.length >= 3)
```

### 4. Holistic reasoning spot-check

Pick 2–3 chats at random from the non-flagged set and read their
`holistic_output.dimensions` reasoning fields. Confirm the judge is applying
the three corrective cases rather than generating generic text. If the
reasoning text is indistinguishable from a template, the holistic pass is not
synthesizing — it is confabulating, and the metric numbers cannot be trusted.

---

## Pass / fail decision

| Outcome | Decision |
|---------|----------|
| Within-2-delta ≥ 70%, no structural failures, reasoning text is substantive | Phase 1 PASSED — proceed to Phase 2 planning |
| Within-2-delta ≥ 70% but ≥ 3 problem chats flagged | Inspect problem chats before declaring Phase 1 passed |
| Within-2-delta 60–69% | Do not proceed. Diagnose which dimensions are failing and whether it is a prompt problem or a rubric interpretation problem |
| Within-2-delta < 60% | Regression. Do not proceed. Re-run gc-001 in isolation to check whether the prompt degraded |
| Any chat with structural failure | Fix the parsing or chunking issue before measuring metrics |

---

## Constants to verify before running

| Constant | Current value | Step 2 value |
|----------|---------------|-------------|
| `MAX_CALLS_PER_RUN` | 2000 | **150** |
| `MAX_SAMPLED_FRAMES` | 9 | 9 (no change) |
| `MAX_RESPONSE_TOKENS` | 8192 | 8192 (no change) |
| `GOLD_CHATS_SUBDIR` | `"chats_anonymized"` | no change |
| `GEMINI_MODEL` | `"gemini-2.5-flash"` | no change |
| `WITHIN_2_THRESHOLD` | 0.70 | no change |
