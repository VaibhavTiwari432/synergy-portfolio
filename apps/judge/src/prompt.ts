import type { Turn, RubricAnchor, JudgeOutput } from "@synergy/schemas";
import { formatRubricText } from "./rubric_text.js";
import type { ScoredFrameSummary } from "./types.js";

export const ALL_DIMS = ["AL", "PR", "AUI", "EC", "CS", "CD", "ES", "CA"] as const;

const DIM_SCHEMA = `{
      "delta": <float -2.0 to +2.0, or null>,
      "evidence_quote": <string or null>,
      "evidence_turn_index": <integer or null>,
      "confidence": <float 0.0-1.0>,
      "rationale": "<one sentence citing specific evidence>"
    }`;

// ── CS sub-dimension rubric text (used only when cs_split is active) ──────────

const CS_INT_RUBRIC = `### CS_INT — Weaves AI output into own reasoning

Measures whether the candidate explicitly integrates AI output with their own reasoning, context, or constraints — or whether AI output passes through unmodified.

Delta scale: −2.0 = AI output passes verbatim to deliverable, no integration visible.
             +2.0 = candidate explicitly names what from AI output is kept, why, and layers own context into it.

Positive signals: explicitly references AI output while adapting it to own context; names what from AI response is being kept or changed; uses AI output as a building block, not a final product
Negative signals: AI output passes directly to work product or next turn without any visible integration step
Example: "Your structure is right, but given [own constraint], I need to rewrite section 2 specifically — keeping the framework but not the implementation assumptions."
`;

const CS_ORI_RUBRIC = `### CS_ORI — Introduces novel framing the AI did not suggest

Measures whether the candidate introduces a constraint, context, angle, or framing that the AI did not have and did not suggest.

Delta scale: −2.0 = all framing and decisions stay within the space the AI defined.
             +2.0 = candidate introduces multiple named constraints or angles the AI could not have had.

Positive signals: names a constraint the AI was not given when it generated the output; introduces domain knowledge the AI did not demonstrate; brings a stakeholder or context angle that reshapes what the AI suggested
Negative signals: all candidate decisions stay within the options the AI offered; candidate only accepts, rejects, or tweaks within AI-set bounds
Example: "Given our Q3 budget freeze [constraint AI wasn't told about], the timeline in your plan needs to shift — and since our team is async-first, the standup assumption in section 2 doesn't apply."
`;

function formatTurns(turns: Turn[]): string {
  return turns
    .map(
      (t) =>
        `[${t.turn_index}] ${t.role === "user" ? "User" : "Assistant"}: ${t.content}`,
    )
    .join("\n\n");
}

export interface ScoringPromptOptions {
  /** Option 2: instruct model to set CS=null in this pass; CS scored holistically. */
  csHolisticOnly?: boolean;
  /** Option 3: replace CS with CS_INT + CS_ORI in rubric and output schema. */
  csSplit?: boolean;
  /** ADR 0004: instruct model to set EC=null in this pass; EC scored with full context in Pass 1.5. */
  ecTwoPass?: boolean;
}

export function buildScoringPrompt(
  anchors: RubricAnchor[],
  platform: string,
  turns: Turn[],
  options?: ScoringPromptOptions,
): string {
  const { csHolisticOnly = false, csSplit = false, ecTwoPass = false } = options ?? {};

  // Rubric section: exclude CS for holistic-only or split; exclude EC when ec_two_pass is active.
  const rubricExcludeDims: string[] = [];
  if (csHolisticOnly || csSplit) rubricExcludeDims.push("CS");
  if (ecTwoPass) rubricExcludeDims.push("EC");
  const rubricExclude = rubricExcludeDims.length > 0 ? rubricExcludeDims : undefined;
  let rubric = formatRubricText(anchors, undefined, rubricExclude);

  if (csSplit) {
    rubric += "\n" + CS_INT_RUBRIC + "\n" + CS_ORI_RUBRIC;
  }

  const turnsText = formatTurns(turns);

  // Output schema dims
  let outputDims: string[];
  if (csSplit) {
    outputDims = ["AL", "PR", "AUI", "EC", "CS_INT", "CS_ORI", "CD", "ES", "CA"];
  } else {
    outputDims = [...ALL_DIMS];
  }
  const schemaDims = outputDims.map((d) => `    "${d}": ${DIM_SCHEMA}`).join(",\n");

  // Score-all instruction line
  const scoreLine = csSplit
    ? `Score all 9 keys: AL, PR, AUI, EC, CS_INT, CS_ORI, CD, ES, CA.`
    : `Score all 8 dimensions: AL, PR, AUI, EC, CS, CD, ES, CA.`;

  // CS-specific instruction when holistic-only
  const csHolisticNote = csHolisticOnly
    ? `\nCS (Cognitive Synthesis): Set delta=null, evidence_quote=null, evidence_turn_index=null, confidence=0, rationale="CS excluded from frame pass — scored holistically with full context." Do NOT attempt to score CS from this frame.\n`
    : "";

  // EC-specific instruction when two-pass is active
  const ecTwoPassNote = ecTwoPass
    ? `\nEC (Error Correction): Set delta=null, evidence_quote=null, evidence_turn_index=null, confidence=0, rationale="EC excluded from frame pass — scored with full conversation context in Pass 1.5." Do NOT attempt to score EC from this frame.\n`
    : "";

  return `You are a calibrated scorer for the Synergy Portfolio Analyzer. Score one chunk (frame) of a human-AI conversation across 8 dimensions of AI-collaboration quality.

## Rubric

${rubric}

## Conversation to score

Platform: ${platform}
Turns:
${turnsText}

## Instructions

Score the HUMAN's behavior only. Do not score the AI's response quality.

${scoreLine}

Delta scale:
  -2.0  worst observable behavior (clearly and strongly low-band)
  -1.0  low-band, mild or partially mitigated
   0.0  observable mixed or genuinely mid-band behavior
  +1.0  high-band, present but not sustained throughout
  +2.0  best observable behavior (clearly and consistently high-band)

You may use any real value in [-2.0, +2.0].

Score the dominant HUMAN behavior in this chunk for each dimension. Do not mechanically average isolated moments with inactive turns. A single strong moment in an otherwise weak chunk should usually be mild (+0.5 to +1.0), not enough by itself to make the whole chunk strongly high. Likewise, a short low-signal tail should not be treated as mid-band evidence.

Set delta to null when there is no observable occasion or insufficient signal for a dimension in these turns. null means not_applicable — not a low score, and not mid-band. Use 0.0 only when there is observable evidence of genuinely mixed or mid-band behavior.
${csHolisticNote}${ecTwoPassNote}
For each dimension provide:
  evidence_quote       verbatim excerpt from the turns, or null if not_applicable
  evidence_turn_index  0-based turn index the quote comes from, or null
  confidence           0.0 (guessing) to 1.0 (certain)
  rationale            one sentence citing specific evidence

Do not include a "band" field — band is computed from delta by the server.
Respond with valid JSON only. No text outside the JSON.

{
  "dimensions": {
${schemaDims}
  }
}`;
}

export interface HolisticPromptOptions {
  /** Option 2: full conversation turns to include for CS scoring. */
  csFullContext?: Turn[];
  /** Option 3: note that CS is the average of CS_INT and CS_ORI sub-dimensions. */
  csSplitNote?: boolean;
}

export function buildHolisticPrompt(
  frameSummaries: ScoredFrameSummary[],
  frameOutputs: JudgeOutput[],
  aggregateWeighted: Record<string, { delta: number | null; band: string }>,
  options?: HolisticPromptOptions,
): string {
  const { csFullContext, csSplitNote = false } = options ?? {};

  const framesByTaskId = new Map(frameOutputs.map((o) => [o.task_frame_id, o]));

  let frameText = "";
  for (const summary of frameSummaries) {
    const output = framesByTaskId.get(summary.task_frame_id);
    if (!output) continue;
    frameText += `\nFrame ${summary.chunk_index} (turns ${summary.turn_range[0]}–${summary.turn_range[1]}, ${summary.turn_count} turns):\n`;
    for (const dim of ALL_DIMS) {
      const score = (
        output.dimensions as Record<
          string,
          { delta: number | null; band: string; confidence: number; rationale: string }
        >
      )[dim];
      if (score) {
        const deltaStr = score.delta === null ? "null" : score.delta.toFixed(1);
        frameText += `  ${dim}: delta=${deltaStr} (${score.band}), conf=${score.confidence.toFixed(2)}, "${score.rationale}"\n`;
      }
    }
  }

  let aggregateText = "";
  for (const dim of ALL_DIMS) {
    const agg = aggregateWeighted[dim];
    if (agg) {
      const deltaStr = agg.delta === null ? "null" : agg.delta.toFixed(3);
      aggregateText += `  ${dim}: delta=${deltaStr} (${agg.band})\n`;
    }
  }

  const holSchemaDims = ALL_DIMS.map(
    (d) =>
      `    "${d}": { "delta": <float -2.0 to +2.0 or null>, "confidence": <float 0.0-1.0>, "reasoning": "<1-2 sentences>" }`,
  ).join(",\n");

  // Full turns section for cs_holistic_only
  const fullContextSection = csFullContext
    ? `## Full conversation turns (for CS scoring only)\n\nCS was not scored per-frame in this run. Use the turns below to score CS. For all other dimensions, use the per-frame scores above.\n\n${formatTurns(csFullContext)}\n\n`
    : "";

  // Dimension-specific constraints
  const ecConstraint = `EC (Error Catching) requires the student to identify factually incorrect, logically flawed, or hallucinated content from the AI. Editorial dissatisfaction ("too generic", "not specific enough", "I don't like this") is NOT error catching — it is prompt refinement (PR). Do not uplift EC for editorial pushback turns.`;

  const csHolisticConstraint = csFullContext
    ? `\nCS (Cognitive Synthesis): CS was excluded from the per-frame pass. The null values you see for CS in the per-frame scores are intentional — they do NOT indicate absence of signal. Score CS now from the full conversation turns provided above. Apply the standard CS rubric: high = candidate explicitly named a constraint AI lacked and adapted the output accordingly; low = AI output was routed directly to the work product unchanged. Use the same delta scale as other dimensions.`
    : "";

  const csSplitConstraint = csSplitNote
    ? `\nCS (Cognitive Synthesis): In this run, CS was scored per-frame as the average of two sub-dimensions — CS_INT (weaving AI output into own reasoning) and CS_ORI (introducing novel framing the AI did not have). The aggregate CS delta reflects that average. When making your holistic CS judgment, consider whether the candidate both integrated AI output into their reasoning AND introduced framing AI lacked, or only one — the average can mask a strong/weak split between the two.`
    : "";

  return `You are a calibrated scorer for the Synergy Portfolio Analyzer. You have already scored individual frames of a human-AI conversation. Now make one holistic judgment for the entire chat.

## Per-frame scores
${frameText}
## Turn-weighted aggregate (reference only — do not echo this)
${aggregateText}
${fullContextSection}## Your task

Make a holistic judgment for each of the 8 dimensions (AL, PR, AUI, EC, CS, CD, ES, CA). The weighted aggregate above is provided only as a reference. Your job is to apply three corrective judgments that arithmetic cannot make:

1. Mixed signal: If a dimension shows opposing scores across frames (e.g., −1.0 in one, +1.0 in another), determine the dominant pattern. A single improvement in an otherwise passive session is still low. A single lapse in an otherwise strong session is still high.

   Case 1 applies when low-band frames account for ≥60% of scored turn weight AND no more than one frame shows genuine high-band signal. When the split is ambiguous, examine the frame delta magnitude: a frame scored below −1.5 represents deeply low behavior that a single +1.0 frame does not neutralize. When in doubt between Case 1 and Case 3, prefer Case 1.

2. Absence as signal: If a dimension is scored at or near 0.0 across all frames with no active high-band behavior observed, treat that as low-band (negative delta), not mid-band. Reserve 0.0 for genuinely mixed or ambiguous evidence, not passive non-engagement.

3. Genuine mid: Reserve 0.0 only for real ambiguity — roughly balanced evidence of both high and low behavior with no clear dominant pattern. If the aggregate is 0.0 because opposing signals cancelled out, that is Case 1 (mixed signal), not Case 3.

When you have determined which case applies, assign delta as follows:

Case 1 (dominant low): assign delta between −1.5 and −2.0. Do not hedge toward 0. A delta of −0.5 is Case 3, not Case 1 — if you are calling Case 1, commit to it.
Case 2 (dominant high): assign delta between +1.5 and +2.0.
Case 3 (genuine mixed): assign delta between −0.5 and +0.5.

If your reasoning says "low behavior dominates" but your delta is −0.5, that is a contradiction. Resolve it by adjusting the delta to match your reasoning, not the other way around.

Dimension-specific constraints:
${ecConstraint}${csHolisticConstraint}${csSplitConstraint}

Set delta to null only when there is genuinely no observable signal for a dimension across the entire chat.

For each dimension provide:
  delta      final holistic delta: float -2.0 to +2.0, or null
  confidence 0.0 (guessing) to 1.0 (certain)
  reasoning  1-2 sentences stating which case applies and why

Do not include a "band" field — band is computed from delta by the server.
Respond with valid JSON only. No text outside the JSON.

{
  "dimensions": {
${holSchemaDims}
  }
}`;
}

// ── EC two-pass prompt (Pass 1.5) ─────────────────────────────────────────────

export function buildECTwoPassPrompt(
  turns: Turn[],
  platform: string,
  anchors: RubricAnchor[],
  frameSummaries: ScoredFrameSummary[],
  frameOutputs: JudgeOutput[],
): string {
  const ecRubric = formatRubricText(anchors, "EC");
  const turnsText = formatTurns(turns);

  const framesByTaskId = new Map(frameOutputs.map((o) => [o.task_frame_id, o]));
  let frameText = "";
  for (const summary of frameSummaries) {
    const output = framesByTaskId.get(summary.task_frame_id);
    if (!output) continue;
    frameText += `\nFrame ${summary.chunk_index} (turns ${summary.turn_range[0]}–${summary.turn_range[1]}):\n`;
    for (const dim of ALL_DIMS) {
      if (dim === "EC") continue;
      const score = (output.dimensions as Record<string, { delta: number | null; band: string; rationale: string }>)[dim];
      if (score) {
        const deltaStr = score.delta === null ? "null" : score.delta.toFixed(1);
        frameText += `  ${dim}: delta=${deltaStr} (${score.band}), "${score.rationale}"\n`;
      }
    }
    frameText += `  EC: null (excluded from frame pass — scored below)\n`;
  }

  const ecDimSchema = `  "EC": ${DIM_SCHEMA}`;

  return `You are a calibrated scorer for the Synergy Portfolio Analyzer. You have already scored individual frames of a human-AI conversation across 7 dimensions. Your task now is to score EC (Error Correction) using the full conversation context.

## EC Rubric

${ecRubric}

## Per-frame Pass 1 scores (EC intentionally excluded)

${frameText}
## Full conversation

Platform: ${platform}
Turns:
${turnsText}

## Instructions

Score EC ONLY. All other dimension scores are final.

EC measures whether the user caught AI mistakes, hallucinations, or logically flawed reasoning. You have the full conversation — use it to verify whether AI claims the user pushed back on were actually wrong.

EC (Error Catching) requires the user to identify factually incorrect, logically flawed, or hallucinated content from the AI. Editorial dissatisfaction ("too generic", "not specific enough", "I don't like this") is NOT error catching — it is prompt refinement (PR). Do not uplift EC for editorial pushback turns.

Delta scale:
  -2.0  no EC behavior — user accepts all AI output without verification
  -1.0  minimal EC — one pushback but no clear factual/logical error caught
   0.0  mixed — some genuine error detection but inconsistent
  +1.0  solid EC — user clearly identifies one or more AI errors
  +2.0  sustained EC — user consistently verifies and catches errors

Set delta to null ONLY when there was no occasion for error correction in the entire conversation (e.g., pure opinion or brainstorming where factual correctness is not applicable).

Provide:
  evidence_quote       verbatim excerpt from the turns, or null
  evidence_turn_index  0-based turn index, or null
  confidence           0.0 (guessing) to 1.0 (certain)
  rationale            one sentence citing specific evidence

Do not include a "band" field — band is computed from delta by the server.
Respond with valid JSON only. No text outside the JSON.

{
${ecDimSchema}
}`;
}
