import { z } from "zod";
import {
  DimensionScoreSchema,
  JudgeOutputSchema,
  DIMENSION_CODES,
  deriveBand,
  type DimensionCode,
  type DimensionScore,
  type JudgeOutput,
  type TaskFrame,
  type RubricAnchor,
  type Turn,
} from "@synergy/schemas";
import type { LLMProvider } from "./providers/index.js";
import { buildScoringPrompt, buildHolisticPrompt, buildECTwoPassPrompt } from "./prompt.js";
import type {
  DryRunCall,
  JudgeConfig,
  HolisticDimensionScore,
  HolisticJudgeOutput,
  ScoredFrameSummary,
} from "./types.js";

// ── Raw API response shape ────────────────────────────────────────────────────

const RawDimSchema = z.object({
  delta: z.number().min(-2).max(2).nullable(),
  evidence_quote: z.string().nullable(),
  evidence_turn_index: z.number().nullable(),
  // Model returns null confidence when delta is null — normalize to 0.
  confidence: z.number().min(0).max(1).nullable().transform((v) => v ?? 0),
  rationale: z.string().min(1),
});

const RawScoreSchema = z.object({
  dimensions: z.object({
    AL: RawDimSchema,
    PR: RawDimSchema,
    AUI: RawDimSchema,
    EC: RawDimSchema,
    CS: RawDimSchema,
    CD: RawDimSchema,
    ES: RawDimSchema,
    CA: RawDimSchema,
  }),
});

// Schema for cs_split: CS replaced by CS_INT and CS_ORI.
const RawScoreSplitSchema = z.object({
  dimensions: z.object({
    AL: RawDimSchema,
    PR: RawDimSchema,
    AUI: RawDimSchema,
    EC: RawDimSchema,
    CS_INT: RawDimSchema,
    CS_ORI: RawDimSchema,
    CD: RawDimSchema,
    ES: RawDimSchema,
    CA: RawDimSchema,
  }),
});

// ── Helpers ───────────────────────────────────────────────────────────────────

function estimateTokens(text: string): number {
  return Math.ceil(text.length / 4);
}

// Gemini occasionally wraps JSON in ```json ... ``` fences despite instructions.
// Also handles truncated responses where the closing ``` never arrives.
function stripMarkdownFences(raw: string): string {
  const trimmed = raw.trim();
  // Full fence: ```json\n...\n```
  const full = trimmed.match(/^```(?:json)?\s*\n([\s\S]*?)\n?```\s*$/);
  if (full?.[1] !== undefined) return full[1].trim();
  // Opening fence only (truncated output): strip the opening line and return rest
  const open = trimmed.match(/^```(?:json)?\s*\n([\s\S]*)$/);
  if (open?.[1] !== undefined) return open[1].trim();
  return trimmed;
}

function toDimensionScore(raw: z.infer<typeof RawDimSchema>): DimensionScore {
  const band =
    raw.delta === null ? ("not_applicable" as const) : deriveBand(raw.delta);

  const score: DimensionScore = {
    delta: raw.delta,
    band,
    evidence_quote: raw.evidence_quote,
    evidence_turn_index:
      raw.evidence_turn_index !== null
        ? Math.floor(raw.evidence_turn_index)
        : null,
    confidence: raw.confidence,
    rationale: raw.rationale,
  };

  DimensionScoreSchema.parse(score);
  return score;
}

function placeholderDim(): DimensionScore {
  return {
    delta: 0,
    band: "mid",
    evidence_quote: null,
    evidence_turn_index: null,
    confidence: 0,
    rationale: "[dry-run placeholder]",
  };
}

function placeholderAllDims(): Record<DimensionCode, DimensionScore> {
  const p = placeholderDim();
  return { AL: p, PR: p, AUI: p, EC: p, CS: p, CD: p, ES: p, CA: p };
}

// Merge two CS sub-dimension scores into a single CS DimensionScore.
// Average delta and confidence; prefer CS_INT evidence; combine rationale.
function mergeCSSubDims(
  csInt: z.infer<typeof RawDimSchema>,
  csOri: z.infer<typeof RawDimSchema>,
): z.infer<typeof RawDimSchema> {
  let mergedDelta: number | null;
  if (csInt.delta !== null && csOri.delta !== null) {
    mergedDelta = (csInt.delta + csOri.delta) / 2;
  } else {
    mergedDelta = csInt.delta ?? csOri.delta;
  }

  const mergedConfidence = (csInt.confidence + csOri.confidence) / 2;
  const mergedRationale =
    `CS_INT(${csInt.delta?.toFixed(1) ?? "null"}): ${csInt.rationale} | ` +
    `CS_ORI(${csOri.delta?.toFixed(1) ?? "null"}): ${csOri.rationale}`;

  return {
    delta: mergedDelta,
    evidence_quote: csInt.evidence_quote ?? csOri.evidence_quote,
    evidence_turn_index: csInt.evidence_turn_index ?? csOri.evidence_turn_index,
    confidence: mergedConfidence,
    rationale: mergedRationale,
  };
}

async function withRetry<T>(
  fn: () => Promise<T>,
  maxRetries: number,
  label: string,
): Promise<T> {
  let lastError: unknown;
  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    try {
      return await fn();
    } catch (err) {
      lastError = err;
      if (attempt < maxRetries) {
        process.stderr.write(
          `  [retry ${attempt}/${maxRetries}] ${label}: ${String(err)}\n`,
        );
        // Only sleep on 429 rate-limit responses — other errors retry immediately.
        if (String(err).includes("429")) {
          process.stderr.write(`  [backoff] 429 rate limit — waiting 45s\n`);
          await new Promise((resolve) => setTimeout(resolve, 45_000));
        }
      }
    }
  }
  throw new Error(
    `${label}: failed after ${maxRetries} attempts. Last: ${String(lastError)}`,
  );
}

// ── Single-pass scoring ───────────────────────────────────────────────────────

async function scoreFrame(
  frame: TaskFrame,
  anchors: RubricAnchor[],
  provider: LLMProvider | null,
  config: JudgeConfig,
  dryRunCalls: DryRunCall[],
): Promise<Record<DimensionCode, DimensionScore>> {
  const scoringOpts = {
    ...(config.cs_holistic_only && { csHolisticOnly: true as const }),
    ...(config.cs_split && { csSplit: true as const }),
    ...(config.ec_two_pass && { ecTwoPass: true as const }),
  };
  const prompt = buildScoringPrompt(anchors, frame.platform, frame.turns, scoringOpts);

  if (config.dry_run) {
    dryRunCalls.push({
      pass: "score",
      model: config.default_model,
      frame_index: frame.chunk_index,
      turn_range: [
        frame.turns[0]?.turn_index ?? 0,
        frame.turns[frame.turns.length - 1]?.turn_index ?? 0,
      ],
      estimated_prompt_tokens: estimateTokens(prompt),
      prompt_preview: prompt.slice(0, 600) + (prompt.length > 600 ? "\n..." : ""),
    });
    return placeholderAllDims();
  }

  if (!provider) {
    throw new Error("scoreFrame: provider is null in live mode");
  }

  const maxTokens = config.max_response_tokens ?? 4096;

  return withRetry(
    async () => {
      const raw = await provider.complete(prompt, maxTokens);
      const cleaned = stripMarkdownFences(raw);

      if (config.cs_split) {
        const parsed = RawScoreSplitSchema.parse(JSON.parse(cleaned));
        const d = parsed.dimensions;
        const csMerged = mergeCSSubDims(d.CS_INT, d.CS_ORI);
        return {
          AL: toDimensionScore(d.AL),
          PR: toDimensionScore(d.PR),
          AUI: toDimensionScore(d.AUI),
          EC: toDimensionScore(d.EC),
          CS: toDimensionScore(csMerged),
          CD: toDimensionScore(d.CD),
          ES: toDimensionScore(d.ES),
          CA: toDimensionScore(d.CA),
        };
      }

      const parsed = RawScoreSchema.parse(JSON.parse(cleaned));
      const d = parsed.dimensions;
      return {
        AL: toDimensionScore(d.AL),
        PR: toDimensionScore(d.PR),
        AUI: toDimensionScore(d.AUI),
        EC: toDimensionScore(d.EC),
        CS: toDimensionScore(d.CS),
        CD: toDimensionScore(d.CD),
        ES: toDimensionScore(d.ES),
        CA: toDimensionScore(d.CA),
      };
    },
    config.max_retries,
    `Score frame ${frame.chunk_index} (${frame.chat_id})`,
  );
}

// ── Holistic-pass schemas ─────────────────────────────────────────────────────

const RawHolisticDimSchema = z.object({
  delta: z.number().min(-2).max(2).nullable(),
  confidence: z.number().min(0).max(1).nullable().transform((v) => v ?? 0),
  reasoning: z.string().min(1),
});

const RawHolisticSchema = z.object({
  dimensions: z.object({
    AL: RawHolisticDimSchema,
    PR: RawHolisticDimSchema,
    AUI: RawHolisticDimSchema,
    EC: RawHolisticDimSchema,
    CS: RawHolisticDimSchema,
    CD: RawHolisticDimSchema,
    ES: RawHolisticDimSchema,
    CA: RawHolisticDimSchema,
  }),
});

// ── Public API ────────────────────────────────────────────────────────────────

export interface ScoreFramesResult {
  outputs: JudgeOutput[];
}

export async function scoreFrames(
  frames: TaskFrame[],
  anchors: RubricAnchor[],
  provider: LLMProvider | null,
  config: JudgeConfig,
  dryRunCalls: DryRunCall[],
): Promise<ScoreFramesResult> {
  const scoredAt = new Date().toISOString();
  const outputs: JudgeOutput[] = [];

  for (const frame of frames) {
    const dims = await scoreFrame(frame, anchors, provider, config, dryRunCalls);
    const output: JudgeOutput = {
      task_frame_id: frame.id,
      judge_model: config.default_model,
      judge_prompt_version: config.prompt_version,
      rubric_version: config.rubric_version,
      dimensions: dims,
      scored_at: scoredAt,
    };
    JudgeOutputSchema.parse(output);
    outputs.push(output);
  }

  return { outputs };
}

export function computeWeightedAggregate(
  frameSummaries: ScoredFrameSummary[],
  frameOutputs: JudgeOutput[],
): Record<string, { delta: number | null; band: string }> {
  const turnCounts = new Map(
    frameSummaries.map((f) => [f.task_frame_id, Math.max(1, f.turn_count)]),
  );
  const out: Record<string, { delta: number | null; band: string }> = {};

  for (const dim of DIMENSION_CODES) {
    let weightedSum = 0;
    let totalWeight = 0;

    for (const frame of frameOutputs) {
      const score = (frame.dimensions as Record<string, { delta: number | null }>)[dim];
      if (score?.delta !== null && score?.delta !== undefined) {
        const weight = turnCounts.get(frame.task_frame_id) ?? 1;
        weightedSum += score.delta * weight;
        totalWeight += weight;
      }
    }

    out[dim] =
      totalWeight > 0
        ? { delta: weightedSum / totalWeight, band: deriveBand(weightedSum / totalWeight) }
        : { delta: null, band: "not_applicable" };
  }

  return out;
}

// ── EC two-pass (Pass 1.5) ────────────────────────────────────────────────────

const RawECPassSchema = z.object({
  EC: RawDimSchema,
});

export async function scoreECTwoPass(
  turns: Turn[],
  platform: string,
  anchors: RubricAnchor[],
  frameSummaries: ScoredFrameSummary[],
  frameOutputs: JudgeOutput[],
  provider: LLMProvider | null,
  config: JudgeConfig,
  dryRunCalls: DryRunCall[],
): Promise<DimensionScore> {
  const prompt = buildECTwoPassPrompt(turns, platform, anchors, frameSummaries, frameOutputs);

  if (config.dry_run) {
    dryRunCalls.push({
      pass: "ec_two_pass",
      model: config.default_model,
      estimated_prompt_tokens: estimateTokens(prompt),
      prompt_preview: prompt.slice(0, 600) + (prompt.length > 600 ? "\n..." : ""),
    });
    return placeholderDim();
  }

  if (!provider) {
    throw new Error("scoreECTwoPass: provider is null in live mode");
  }

  const maxTokens = config.max_response_tokens ?? 4096;

  return withRetry(
    async () => {
      const raw = await provider.complete(prompt, maxTokens);
      const parsed = RawECPassSchema.parse(JSON.parse(stripMarkdownFences(raw)));
      return toDimensionScore(parsed.EC);
    },
    config.max_retries,
    `EC two-pass (${config.default_model})`,
  );
}

export async function scoreHolistic(
  frameSummaries: ScoredFrameSummary[],
  frameOutputs: JudgeOutput[],
  aggregateWeighted: Record<string, { delta: number | null; band: string }>,
  provider: LLMProvider | null,
  config: JudgeConfig,
  dryRunCalls: DryRunCall[],
  allTurns?: Turn[],
): Promise<HolisticJudgeOutput | undefined> {
  // Build holistic prompt — cs_holistic_only and cs_split each get targeted
  // options; both are mutually exclusive with the tiebreak variant builders.
  let prompt: string;
  if (config.cs_holistic_only && allTurns) {
    prompt = buildHolisticPrompt(frameSummaries, frameOutputs, aggregateWeighted, {
      csFullContext: allTurns,
    });
  } else if (config.cs_split) {
    prompt = buildHolisticPrompt(frameSummaries, frameOutputs, aggregateWeighted, {
      csSplitNote: true,
    });
  } else {
    const builder = config.holisticPromptBuilder ?? buildHolisticPrompt;
    prompt = builder(frameSummaries, frameOutputs, aggregateWeighted);
  }

  if (config.dry_run) {
    dryRunCalls.push({
      pass: "holistic",
      model: config.default_model,
      estimated_prompt_tokens: estimateTokens(prompt),
      prompt_preview: prompt,
    });
    return undefined;
  }

  if (!provider) {
    throw new Error("scoreHolistic: provider is null in live mode");
  }

  const maxTokens = config.max_response_tokens ?? 4096;
  const HOLISTIC_DIMS = ["AL", "PR", "AUI", "EC", "CS", "CD", "ES", "CA"] as const;

  return withRetry(
    async () => {
      const raw = await provider.complete(prompt, maxTokens);
      const parsed = RawHolisticSchema.parse(JSON.parse(stripMarkdownFences(raw)));
      const d = parsed.dimensions;
      const dims: Record<string, HolisticDimensionScore> = {};
      for (const dim of HOLISTIC_DIMS) {
        const raw_dim = d[dim];
        dims[dim] = {
          delta: raw_dim.delta,
          band: raw_dim.delta === null ? "not_applicable" : deriveBand(raw_dim.delta),
          confidence: raw_dim.confidence,
          reasoning: raw_dim.reasoning,
        };
      }
      return {
        judge_model: config.default_model,
        rubric_version: config.rubric_version,
        dimensions: dims,
        aggregate_weighted: aggregateWeighted,
        scored_at: new Date().toISOString(),
      };
    },
    config.max_retries,
    `Holistic pass (${config.default_model})`,
  );
}
