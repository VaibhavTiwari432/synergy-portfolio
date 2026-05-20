import { z } from "zod";

// ── Constants ─────────────────────────────────────────────────────────────────

export const DIMENSION_CODES = [
  "AL", "PR", "AUI", "EC", "CS", "CD", "ES", "CA",
] as const satisfies readonly string[];

// Thresholds for server-side band derivation from delta.
// Changing these requires a new rubric version — see ADR 0001.
export const BAND_THRESHOLDS = {
  LOW_MAX: -0.67,   // delta <= LOW_MAX  → "low"
  HIGH_MIN: +0.67,  // delta >= HIGH_MIN → "high"
} as const;

// Minimum applicable frames before archetype_confidence is populated.
// OPEN: may need adjustment after calibration (see spec §11, item 6).
export const MIN_FRAMES_FOR_ARCHETYPE = 10;

// ── Primitives ────────────────────────────────────────────────────────────────

export const DimensionCodeSchema = z.enum([
  "AL", "PR", "AUI", "EC", "CS", "CD", "ES", "CA",
]);
export type DimensionCode = z.infer<typeof DimensionCodeSchema>;

export const BandSchema = z.enum(["low", "mid", "high"]);
export type Band = z.infer<typeof BandSchema>;

export const BandWithNASchema = z.enum(["low", "mid", "high", "not_applicable"]);
export type BandWithNA = z.infer<typeof BandWithNASchema>;

// ── deriveBand ────────────────────────────────────────────────────────────────
// Server-side only. Exported so the API validation layer can call it without
// re-implementing the threshold logic.

export function deriveBand(delta: number): Band {
  if (delta <= BAND_THRESHOLDS.LOW_MAX) return "low";
  if (delta >= BAND_THRESHOLDS.HIGH_MIN) return "high";
  return "mid";
}

// ── Shared helper ─────────────────────────────────────────────────────────────
// Builds a Zod object with exactly the 8 DimensionCode keys.

function dimensionRecord<T extends z.ZodTypeAny>(schema: T) {
  return z.object({
    AL: schema, PR: schema, AUI: schema, EC: schema,
    CS: schema, CD: schema, ES: schema,  CA: schema,
  });
}

// ── RubricAnchor ──────────────────────────────────────────────────────────────

export const RubricAnchorSchema = z.object({
  dimension: DimensionCodeSchema,
  band: BandSchema,
  label: z.string().min(1),
  description: z.string().min(1),
  positive_signals: z.array(z.string()).min(1),
  negative_signals: z.array(z.string()).min(1),
  example_chat_snippet: z.string().min(1),
  synthetic: z.boolean(),
});
export type RubricAnchor = z.infer<typeof RubricAnchorSchema>;

// ── Turn ──────────────────────────────────────────────────────────────────────

export const TurnSchema = z.object({
  role: z.enum(["user", "assistant"]),
  content: z.string().min(1),
  turn_index: z.number().int().min(0),
  timestamp_ms: z.number().int().nullable(),
});
export type Turn = z.infer<typeof TurnSchema>;

// ── TaskFrame ─────────────────────────────────────────────────────────────────

export const TaskFrameSchema = z.object({
  id: z.string().uuid(),
  chat_id: z.string().min(1),
  platform: z.enum(["chatgpt", "claude.ai", "gemini"]),
  user_id: z.string().min(1),
  turns: z.array(TurnSchema).min(2),
  chunk_index: z.number().int().min(0),
  captured_at: z.string().datetime({ offset: true }),
  rubric_version: z.string().min(1),
});
export type TaskFrame = z.infer<typeof TaskFrameSchema>;

// ── DimensionScore ─────────────────────────────────────────────────────────────
//
// band must be consistent with delta:
//   delta null   → band must be "not_applicable"
//   delta number → band must equal deriveBand(delta)
//
// This invariant is enforced by the server validation layer. The Zod refine
// here validates data coming *out* of the server (stored records, API responses).

export const DimensionScoreSchema = z.object({
  delta: z.number().min(-2).max(2).nullable(),
  band: BandWithNASchema,
  evidence_quote: z.string().nullable(),
  evidence_turn_index: z.number().int().min(0).nullable(),
  confidence: z.number().min(0).max(1),
  rationale: z.string().min(1),
}).refine(
  (d) => {
    if (d.delta === null) return d.band === "not_applicable";
    return d.band === deriveBand(d.delta);
  },
  { message: "band must match BAND_THRESHOLDS derivation from delta" },
);
export type DimensionScore = z.infer<typeof DimensionScoreSchema>;

// ── JudgeOutput ───────────────────────────────────────────────────────────────

export const JudgeOutputSchema = z.object({
  task_frame_id: z.string().uuid(),
  judge_model: z.string().min(1),
  judge_prompt_version: z.string().min(1),
  rubric_version: z.string().min(1),
  dimensions: dimensionRecord(DimensionScoreSchema),
  scored_at: z.string().datetime({ offset: true }),
});
export type JudgeOutput = z.infer<typeof JudgeOutputSchema>;

// ── AggregatedScore ───────────────────────────────────────────────────────────
//
// score must be non-null iff status is "scored".

export const AggregatedScoreSchema = z.object({
  score: z.number().min(0).max(10).nullable(),
  status: z.enum(["scored", "not_applicable", "insufficient_data"]),
  confidence: z.number().min(0).max(1),
  sample_size: z.number().int().min(0),
  applicable_sample_size: z.number().int().min(0),
  trend_7d: z.number().nullable(),
  last_evidence_quote: z.string().nullable(),
}).refine(
  (a) => (a.status === "scored") === (a.score !== null),
  { message: "score must be non-null iff status is 'scored'" },
);
export type AggregatedScore = z.infer<typeof AggregatedScoreSchema>;

// ── Portfolio ─────────────────────────────────────────────────────────────────

export const PortfolioSchema = z.object({
  user_id: z.string().min(1),
  current_scores: dimensionRecord(AggregatedScoreSchema),
  total_frames_scored: z.number().int().min(0),
  archetype: z.string().nullable(),
  archetype_confidence: z.number().min(0).max(1).nullable(),
  last_updated: z.string().datetime({ offset: true }),
  rubric_version: z.string().min(1),
});
export type Portfolio = z.infer<typeof PortfolioSchema>;

// ── GoldChatAnnotation ────────────────────────────────────────────────────────

export const GoldChatAnnotationSchema = z.object({
  scorer_id: z.string().min(1),
  bands: dimensionRecord(BandWithNASchema),
  notes: dimensionRecord(z.string()),
  scored_at: z.string().datetime({ offset: true }),
});
export type GoldChatAnnotation = z.infer<typeof GoldChatAnnotationSchema>;

// ── GoldChat ──────────────────────────────────────────────────────────────────

export const GoldChatSchema = z.object({
  id: z.string().min(1),
  platform: z.enum(["chatgpt", "claude.ai", "gemini"]),
  turns: z.array(TurnSchema).min(1),
  annotations: z.array(GoldChatAnnotationSchema).min(1),
  rubric_version: z.string().min(1),
});
export type GoldChat = z.infer<typeof GoldChatSchema>;
