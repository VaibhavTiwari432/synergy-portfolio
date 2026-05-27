import type { JudgeOutput, BoundaryDecision } from "@synergy/schemas";

export interface DryRunCall {
  pass: "score" | "holistic" | "ec_two_pass";
  model: string;
  frame_index?: number;
  turn_range?: [number, number];
  estimated_prompt_tokens: number;
  prompt_preview: string;
}

export interface HolisticDimensionScore {
  delta: number | null;
  band: string;
  confidence: number;
  reasoning: string;
}

export interface HolisticJudgeOutput {
  judge_model: string;
  rubric_version: string;
  dimensions: Record<string, HolisticDimensionScore>;
  aggregate_weighted: Record<string, { delta: number | null; band: string }>;
  scored_at: string;
}

export interface ScoredFrameSummary {
  task_frame_id: string;
  chunk_index: number;
  turn_count: number;
  turn_range: [number, number];
}

export interface ScoredChat {
  chat_id: string;
  /** Frames actually scored (after sampling, if applied). */
  frame_count: number;
  /** Total frames produced by the chunker before any sampling. */
  total_frames: number;
  /** Metadata for each scored frame, aligned with frame_outputs by task_frame_id. */
  frame_summaries: ScoredFrameSummary[];
  frame_outputs: JudgeOutput[];
  dry_run_calls: DryRunCall[];
  /** Holistic judgment pass — replaces aggregate_weighted as final score. Absent in dry-run. */
  holistic_output?: HolisticJudgeOutput;
  /**
   * EC delta from Pass 1.5 (two-pass EC scoring, ADR 0004). Present when ec_two_pass is enabled.
   * This value is replicated to frame_outputs[].dimensions.EC before the holistic pass.
   */
  ec_two_pass_delta?: number | null;
  /** Boundary decisions from the Haiku classifier. Present when use_boundary_chunker is enabled. */
  chunk_boundaries?: BoundaryDecision[];
}

export interface JudgeConfig {
  provider: "gemini" | "anthropic";
  dry_run: boolean;
  default_model: string;
  rubric_version: string;
  prompt_version: string;
  max_turns_per_frame: number;
  max_retries: number;
  /** If set, caps max_tokens per API call (response tokens). */
  max_response_tokens?: number;
  /**
   * If set and the chat produces more frames than this, sample first⌊N/3⌋ + middle⌊N/3⌋ + last⌊N/3⌋
   * frames instead of scoring all of them.
   */
  max_sampled_frames?: number;
  /**
   * Subdirectory under gold_standard/ to load chats from.
   * Default "chats". Set to "chats_anonymized" for calibration runs.
   */
  gold_chats_subdir?: string;
  /**
   * Optional override for the holistic prompt builder. When set, the scorer
   * calls this instead of the default buildHolisticPrompt. Used for A/B testing
   * experimental prompt variants without modifying production code.
   */
  holisticPromptBuilder?: (
    frameSummaries: ScoredFrameSummary[],
    frameOutputs: JudgeOutput[],
    aggregateWeighted: Record<string, { delta: number | null; band: string }>,
  ) => string;
  /**
   * Option 2: Move CS out of per-frame scoring. Frame pass sets CS=null.
   * Holistic pass scores CS from full conversation turns with explicit context.
   * Feature flag — does not affect production scoring when false/absent.
   */
  cs_holistic_only?: boolean;
  /**
   * Option 3: Decompose CS into CS_INT (weaving) and CS_ORI (origination).
   * Frame pass scores both sub-dimensions; their average is reported as CS.
   * Holistic pass scores CS from the averaged aggregate normally.
   * Feature flag — does not affect production scoring when false/absent.
   */
  cs_split?: boolean;
  /**
   * Two-pass EC scoring (ADR 0004). When true:
   *   Pass 1: score 7 non-EC dimensions per frame (EC=null in frame output).
   *   Pass 1.5: score EC using full conversation context — one additional API call per chat.
   * EC delta from Pass 1.5 replaces the null EC values in frame_outputs before holistic scoring.
   */
  ec_two_pass?: boolean;
  /**
   * Goal-boundary chunker (ADR 0005). When true, uses claude-haiku-4-5 to detect
   * natural goal/topic boundaries between frames. Hard 8-turn cap still applies as ceiling.
   * When false or absent, fixed-window chunking is used.
   */
  use_boundary_chunker?: boolean;
  /**
   * When use_boundary_chunker is true, append each BoundaryDecision as a JSONL line
   * to this file path. Required by ADR 0005 for calibration audit trail.
   */
  boundary_log_path?: string;
}
