# Claude Code Judge Mid-Bias Handoff

Last updated: 2026-05-22

## What Changed

- Changed calibration aggregation in `calibration/run_calibration.ts` from equal-frame averaging to turn-weighted averaging.
  - Before: every scored frame contributed equally, so a 2-turn tail could dilute an 8-turn substantive frame.
  - Now: each non-null frame delta is weighted by the scored frame's `turn_count`.
  - Null deltas are excluded from that dimension's denominator.
- Added `frame_summaries` to `ScoredChat` in `apps/judge/src/types.ts` and populated it in `apps/judge/src/judge.ts`.
  - Includes `task_frame_id`, `chunk_index`, `turn_count`, and `turn_range`.
  - Calibration uses this metadata to weight frame outputs without changing `JudgeOutput`.
- Updated `apps/judge/src/prompt.ts` to reduce mid anchoring.
  - `0.0` now means observable mixed or genuinely mid-band behavior.
  - Insufficient/no observable signal should be `null`, not `0.0`.
  - The judge is told to score dominant behavior in the chunk and not mechanically average isolated moments with inactive turns.
- Added an `aggregation` metadata block to calibration reports so future reports state the frame aggregation method.
- Added actual judge failure messages to calibration reports instead of the generic `judgeChat threw`.

## Latest Attempt

- Attempted `pnpm --filter @synergy/calibration calibrate -- --limit 1` on 2026-05-22 after rebuilding.
- The run stopped before any Gemini scoring because this shell does not have `GEMINI_API_KEY`.
- `calibration/reports/phase1_gemini_limit1.json` was overwritten with the failed attempt and now records:
  - `aggregation.frame_delta_method = "turn_weighted_mean"`
  - `chat_results[0].error = "Error: GEMINI_API_KEY env var not set ..."`
- The previously open successful `phase1_gemini_limit1.json` appeared to be pre-mitigation evidence because it lacked the `aggregation` block and still showed equal-frame averages.

## Not Run

- Step 2 / full calibration was not run.
- No live Gemini completions were made in the latest attempt because provider setup failed before scoring.

## Verification

- `pnpm --filter @synergy/judge typecheck`
- `pnpm --filter @synergy/calibration typecheck`
- `pnpm --filter @synergy/judge build`
- `pnpm --filter @synergy/calibration build`
- `pnpm --filter @synergy/calibration calibrate -- --limit 1` reached dry-run call estimation, then failed cleanly with missing `GEMINI_API_KEY`.

## Next Recommended Check

Set `GEMINI_API_KEY` in the shell/session that runs calibration, then rerun only `pnpm --filter @synergy/calibration calibrate -- --limit 1` before scaling to the remaining chats. Inspect whether the final `judge_deltas` move away from artificial mid when short low-signal frames are present.
