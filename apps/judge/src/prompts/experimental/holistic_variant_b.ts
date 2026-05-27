/**
 * Holistic prompt Variant B — tie-break replaced with a high-frame counter-weight.
 *
 * Identical to the production v5 holistic prompt except the sentence
 * "When in doubt between Case 1 and Case 3, prefer Case 1." is replaced with:
 * "If 2 or more frames in the conversation score in the high band on the same
 *  dimension, do not down-weight that dimension toward the mid band in the holistic
 *  synthesis."
 *
 * Rationale: the original tie-break over-suppresses sessions that have one weak frame
 * among multiple strong ones. This variant preserves the low-bias guard while adding
 * an explicit counter-weight that prevents single-frame anchoring on high-quality chats.
 *
 * DO NOT promote to production without running tiebreak_comparison and getting
 * explicit human sign-off.
 */
import { buildHolisticPrompt } from "../../prompt.js";
import type { ScoredFrameSummary } from "../../types.js";
import type { JudgeOutput } from "@synergy/schemas";

const TIEBREAK_SENTENCE = " When in doubt between Case 1 and Case 3, prefer Case 1.";

const COUNTER_WEIGHT =
  " If 2 or more frames in the conversation score in the high band on the same" +
  " dimension, do not down-weight that dimension toward the mid band in the holistic synthesis.";

export function buildHolisticPromptVariantB(
  frameSummaries: ScoredFrameSummary[],
  frameOutputs: JudgeOutput[],
  aggregateWeighted: Record<string, { delta: number | null; band: string }>,
): string {
  return buildHolisticPrompt(frameSummaries, frameOutputs, aggregateWeighted).replace(
    TIEBREAK_SENTENCE,
    COUNTER_WEIGHT,
  );
}
