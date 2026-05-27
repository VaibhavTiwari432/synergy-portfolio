/**
 * Holistic prompt Variant A — tie-break removed.
 *
 * Identical to the production v5 holistic prompt except the sentence
 * "When in doubt between Case 1 and Case 3, prefer Case 1." is deleted.
 *
 * Rationale: error analysis shows the tie-break is a corpus-wide suppressor
 * biasing 6 of 7 dimensions negative. This variant tests whether removing it
 * recovers high-band chats without re-introducing mid-bias on passive sessions.
 *
 * DO NOT promote to production without running tiebreak_comparison and getting
 * explicit human sign-off.
 */
import { buildHolisticPrompt } from "../../prompt.js";
import type { ScoredFrameSummary } from "../../types.js";
import type { JudgeOutput } from "@synergy/schemas";

const TIEBREAK_SENTENCE = " When in doubt between Case 1 and Case 3, prefer Case 1.";

export function buildHolisticPromptVariantA(
  frameSummaries: ScoredFrameSummary[],
  frameOutputs: JudgeOutput[],
  aggregateWeighted: Record<string, { delta: number | null; band: string }>,
): string {
  return buildHolisticPrompt(frameSummaries, frameOutputs, aggregateWeighted).replace(
    TIEBREAK_SENTENCE,
    "",
  );
}
