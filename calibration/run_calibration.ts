/**
 * run_calibration.ts
 *
 * Runs all non-excluded gold-standard chats through the Synergy judge
 * (Gemini 2.5 Flash, single-pass) and computes per-dimension metrics
 * against human annotations.
 *
 * Phase 1 exit criteria:
 *   1. All chats produce structurally valid JudgeOutput for every frame.
 *   2. 70%+ of (chat, dimension) pairs are within 2 delta points of human gold.
 *
 * Usage:
 *   node dist/run_calibration.js [--dry-run] [--limit N] [--resume-from CHAT_ID]
 *
 * --limit N            Score only the first N chats (for pipeline validation).
 * --resume-from ID     Skip all chats that sort before CHAT_ID (e.g. gc-003 skips
 *                      gc-001, gc-002). Also loads any results already present in the
 *                      output file and skips chats already scored there.
 *
 * Incremental persistence: after each chat completes (frame scoring + holistic pass),
 * its ChatResult is appended to the output file immediately. If the run is interrupted,
 * already-scored chats survive. Resume with --resume-from to pick up where it left off.
 * The in-memory accumulated array is authoritative; disk is the durability layer.
 *
 * Output:
 *   calibration/reports/phase1_gemini.json              (full run)
 *   calibration/reports/phase1_gemini_from_<ID>.json    (resume run)
 *   calibration/reports/phase1_gemini_limit<N>.json     (limited run)
 */

import { writeFileSync, mkdirSync, existsSync, readFileSync, statSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { loadGoldStandardChats } from "./gold_standard_loader.js";
import { judgeChat, buildHolisticPromptVariantA, buildHolisticPromptVariantB } from "@synergy/judge";
import type { JudgeConfig, ScoredChat, HolisticJudgeOutput } from "@synergy/judge";
import type { GoldChat } from "@synergy/schemas";
import { DIMENSION_CODES, deriveBand, type JudgeOutput } from "@synergy/schemas";

// Chats are loaded from chats_anonymized/ — originals are never sent to Gemini.
const GOLD_CHATS_SUBDIR = "chats_anonymized";

// ── Safety caps ───────────────────────────────────────────────────────────────
const MAX_CALLS_PER_RUN = 150;
// 8192 gives gemini-2.5-flash enough room even when thinking tokens are active.
// The visible JSON response for 8 dimensions is ~600-900 tokens.
const MAX_RESPONSE_TOKENS = 8192;
const MAX_SAMPLED_FRAMES = 9;
// ─────────────────────────────────────────────────────────────────────────────

// Phase 1 exit criteria threshold: 70% of (chat, dim) pairs within 2 delta pts
const WITHIN_2_THRESHOLD = 0.70;

// Midpoint of each band's range on [-2, 2] split into equal thirds at ±0.67.
const BAND_CANONICAL: Record<string, number | null> = {
  low: -(4 / 3),   // ≈ -1.333
  mid: 0,
  high: 4 / 3,     // ≈  1.333
  not_applicable: null,
};

type DimCode = (typeof DIMENSION_CODES)[number];

const GEMINI_MODEL = "gemini-2.5-flash";

const __dirname = dirname(fileURLToPath(import.meta.url));
const REPORTS_DIR = join(__dirname, "../reports");

interface FailedJudgeRun {
  error: string;
}

function isFailedJudgeRun(result: ScoredChat | FailedJudgeRun): result is FailedJudgeRun {
  return "error" in result;
}

// ── Report types ──────────────────────────────────────────────────────────────

interface DimMetrics {
  mae: number | null;
  band_accuracy: number | null;
  within_2_delta: number | null;
  sample_count: number;
}

interface ChatResult {
  chat_id: string;
  frames_scored: number;
  frames_total: number;
  status: "scored" | "failed";
  error?: string;
  human_bands: Partial<Record<DimCode, string>>;
  judge_bands: Partial<Record<DimCode, string>>;
  judge_deltas: Partial<Record<DimCode, number | null>>;
  /** Bands from the turn-weighted aggregate — stored for comparison with holistic. */
  weighted_bands?: Partial<Record<DimCode, string>>;
  absolute_errors: Partial<Record<DimCode, number | null>>;
  frame_outputs?: JudgeOutput[];
  holistic_output?: HolisticJudgeOutput;
}

interface Phase1ExitCriteria {
  structural_validity: boolean;
  within_2_delta_pct: number | null;
  passed: boolean;
}

interface CalibrationReport {
  generated_at: string;
  model: string;
  rubric_version: string;
  dry_run: boolean;
  safety: {
    max_calls_cap: number;
    max_response_tokens: number;
    total_estimated_calls: number;
    call_cap_exceeded: boolean;
  };
  summary: {
    chats_evaluated: number;
    chats_excluded: number;
    chats_failed: number;
    overall_mae: number | null;
    overall_band_accuracy: number | null;
  };
  aggregation: {
    frame_delta_method: "holistic_pass_over_turn_weighted_aggregate";
    null_delta_handling: "excluded_from_dimension_average";
  };
  phase1_exit_criteria: Phase1ExitCriteria;
  per_dimension: Record<DimCode, DimMetrics>;
  chat_results: ChatResult[];
}

// ── Incremental persistence ───────────────────────────────────────────────────

function loadPreloadedResults(reportPath: string): ChatResult[] {
  if (!existsSync(reportPath)) return [];
  try {
    const parsed = JSON.parse(readFileSync(reportPath, "utf8")) as {
      chat_results?: ChatResult[];
    };
    return Array.isArray(parsed.chat_results) ? parsed.chat_results : [];
  } catch {
    return [];
  }
}

// Writes the full accumulated array to disk after each chat. The in-memory
// accumulatedResults array is authoritative; this is purely the durability layer.
function tryWriteIncremental(
  reportPath: string,
  accumulatedResults: ChatResult[],
  isDryRun: boolean,
  lastChatId: string,
): void {
  try {
    writeFileSync(
      reportPath,
      JSON.stringify({ chat_results: accumulatedResults }, null, 2),
      "utf8",
    );
    if (isDryRun) {
      const size = statSync(reportPath).size;
      process.stdout.write(
        `  [incremental] ${lastChatId} written — file is now ${size} bytes\n`,
      );
    }
  } catch (err) {
    process.stderr.write(
      `  [incremental write FAILED for ${lastChatId}]: ${String(err)}\n`,
    );
  }
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function holisticToScores(
  h: HolisticJudgeOutput,
): Record<DimCode, { delta: number | null; band: string }> {
  return Object.fromEntries(
    DIMENSION_CODES.map((d) => [
      d,
      { delta: h.dimensions[d]?.delta ?? null, band: h.dimensions[d]?.band ?? "not_applicable" },
    ]),
  ) as Record<DimCode, { delta: number | null; band: string }>;
}

function aggregateFrames(
  result: ScoredChat,
): Record<DimCode, { delta: number | null; band: string }> {
  const out = {} as Record<DimCode, { delta: number | null; band: string }>;
  const turnCounts = new Map(
    result.frame_summaries.map((frame) => [
      frame.task_frame_id,
      Math.max(1, frame.turn_count),
    ]),
  );

  for (const dim of DIMENSION_CODES) {
    let weightedDeltaSum = 0;
    let totalWeight = 0;

    for (const frame of result.frame_outputs) {
      const score = (
        frame.dimensions as Record<string, { delta: number | null }>
      )[dim];
      if (score?.delta !== null && score?.delta !== undefined) {
        const weight = turnCounts.get(frame.task_frame_id) ?? 1;
        weightedDeltaSum += score.delta * weight;
        totalWeight += weight;
      }
    }

    if (totalWeight > 0) {
      const avg = weightedDeltaSum / totalWeight;
      out[dim] = { delta: avg, band: deriveBand(avg) };
    } else {
      out[dim] = { delta: null, band: "not_applicable" };
    }
  }

  return out;
}

function computeAbsoluteErrors(
  humanBands: Record<string, string>,
  judgeScores: Record<DimCode, { delta: number | null; band: string }>,
): Record<DimCode, number | null> {
  const errors = {} as Record<DimCode, number | null>;

  for (const dim of DIMENSION_CODES) {
    const humanBand = humanBands[dim];
    const humanDelta = humanBand !== undefined ? (BAND_CANONICAL[humanBand] ?? null) : null;
    const judgeDelta = judgeScores[dim]?.delta ?? null;

    if (humanDelta === null || judgeDelta === null) {
      errors[dim] = null;
    } else {
      errors[dim] = Math.abs(judgeDelta - humanDelta);
    }
  }

  return errors;
}

// ── buildSingleChatResult ─────────────────────────────────────────────────────

function buildSingleChatResult(
  chat: GoldChat,
  result: ScoredChat | FailedJudgeRun | undefined,
  isDryRun: boolean,
): ChatResult {
  const human = chat.annotations[0];

  if (result === undefined) {
    return {
      chat_id: chat.id, frames_scored: 0, frames_total: 0,
      status: "failed", error: "not scored",
      human_bands: {}, judge_bands: {}, judge_deltas: {}, absolute_errors: {},
    };
  }

  if (isFailedJudgeRun(result)) {
    return {
      chat_id: chat.id, frames_scored: 0, frames_total: 0,
      status: "failed", error: result.error,
      human_bands: human ? { ...(human.bands as Record<DimCode, string>) } : {},
      judge_bands: {}, judge_deltas: {}, absolute_errors: {},
    };
  }

  if (!human) {
    return {
      chat_id: chat.id,
      frames_scored: result.frame_count, frames_total: result.total_frames,
      status: "failed", error: "no human annotation",
      human_bands: {}, judge_bands: {}, judge_deltas: {}, absolute_errors: {},
    };
  }

  const weightedScores = aggregateFrames(result);
  const judgeScores =
    !isDryRun && result.holistic_output
      ? holisticToScores(result.holistic_output)
      : weightedScores;
  const errors = isDryRun
    ? ({} as Record<DimCode, number | null>)
    : computeAbsoluteErrors(human.bands as Record<string, string>, judgeScores);

  return {
    chat_id: chat.id,
    frames_scored: result.frame_count,
    frames_total: result.total_frames,
    status: "scored",
    human_bands: { ...(human.bands as Record<DimCode, string>) },
    judge_bands: Object.fromEntries(
      DIMENSION_CODES.map((d) => [d, judgeScores[d]?.band ?? "not_applicable"]),
    ) as Record<DimCode, string>,
    judge_deltas: Object.fromEntries(
      DIMENSION_CODES.map((d) => [d, judgeScores[d]?.delta ?? null]),
    ) as Record<DimCode, number | null>,
    ...(!isDryRun && result.holistic_output && {
      weighted_bands: Object.fromEntries(
        DIMENSION_CODES.map((d) => [d, weightedScores[d]?.band ?? "not_applicable"]),
      ) as Record<DimCode, string>,
    }),
    absolute_errors: errors,
    ...(!isDryRun && { frame_outputs: result.frame_outputs }),
    ...(!isDryRun && result.holistic_output && { holistic_output: result.holistic_output }),
  };
}

// ── computeMetrics ────────────────────────────────────────────────────────────

function computeMetrics(chatResults: ChatResult[]): {
  overall_mae: number | null;
  overall_band_accuracy: number | null;
  within_2_delta_pct: number | null;
  per_dim: Record<DimCode, DimMetrics>;
} {
  const dimErrors: Record<DimCode, number[]> = {} as Record<DimCode, number[]>;
  const dimMatches: Record<DimCode, { hits: number; total: number }> =
    {} as Record<DimCode, { hits: number; total: number }>;
  const dimWithin2: Record<DimCode, { hits: number; total: number }> =
    {} as Record<DimCode, { hits: number; total: number }>;

  for (const dim of DIMENSION_CODES) {
    dimErrors[dim] = [];
    dimMatches[dim] = { hits: 0, total: 0 };
    dimWithin2[dim] = { hits: 0, total: 0 };
  }

  for (const result of chatResults) {
    if (result.status === "failed") continue;

    for (const dim of DIMENSION_CODES) {
      const humanBand = result.human_bands[dim];
      const judgeBand = result.judge_bands[dim];
      const err = result.absolute_errors[dim];

      if (
        humanBand !== undefined &&
        judgeBand !== undefined &&
        humanBand !== "not_applicable"
      ) {
        dimMatches[dim].total++;
        if (humanBand === judgeBand) dimMatches[dim].hits++;
      }

      if (err !== null && err !== undefined) {
        dimErrors[dim].push(err);
        dimWithin2[dim].total++;
        if (err <= 2) dimWithin2[dim].hits++;
      }
    }
  }

  let allErrors: number[] = [];
  let allHits = 0;
  let allTotal = 0;
  let within2Hits = 0;
  let within2Total = 0;
  const per_dim = {} as Record<DimCode, DimMetrics>;

  for (const dim of DIMENSION_CODES) {
    const errs = dimErrors[dim];
    const m = dimMatches[dim];
    const w2 = dimWithin2[dim];
    const mae = errs.length > 0 ? errs.reduce((a, b) => a + b, 0) / errs.length : null;
    const band_accuracy = m.total > 0 ? m.hits / m.total : null;
    const within_2_delta = w2.total > 0 ? w2.hits / w2.total : null;
    per_dim[dim] = { mae, band_accuracy, within_2_delta, sample_count: errs.length };
    allErrors = allErrors.concat(errs);
    allHits += m.hits;
    allTotal += m.total;
    within2Hits += w2.hits;
    within2Total += w2.total;
  }

  return {
    overall_mae: allErrors.length > 0 ? allErrors.reduce((a, b) => a + b, 0) / allErrors.length : null,
    overall_band_accuracy: allTotal > 0 ? allHits / allTotal : null,
    within_2_delta_pct: within2Total > 0 ? within2Hits / within2Total : null,
    per_dim,
  };
}

// ── buildReport ───────────────────────────────────────────────────────────────

function buildReport(
  chatResults: ChatResult[],
  excludedCount: number,
  rubricVersion: string,
  isDryRun: boolean,
  totalEstimatedCalls: number,
  capExceeded: boolean,
): CalibrationReport {
  const nullDimMetrics = Object.fromEntries(
    DIMENSION_CODES.map((d) => [
      d,
      { mae: null, band_accuracy: null, within_2_delta: null, sample_count: 0 },
    ]),
  ) as Record<DimCode, DimMetrics>;

  let overall_mae: number | null = null;
  let overall_band_accuracy: number | null = null;
  let per_dimension = nullDimMetrics;
  let phase1Exit: Phase1ExitCriteria = {
    structural_validity: false,
    within_2_delta_pct: null,
    passed: false,
  };

  if (!isDryRun) {
    const metrics = computeMetrics(chatResults);
    overall_mae = metrics.overall_mae;
    overall_band_accuracy = metrics.overall_band_accuracy;
    per_dimension = metrics.per_dim;

    const structurallyValid =
      chatResults.filter((r) => r.status === "scored").length > 0 &&
      chatResults.filter((r) => r.status === "failed").length === 0;
    const within2Pct = metrics.within_2_delta_pct;
    phase1Exit = {
      structural_validity: structurallyValid,
      within_2_delta_pct: within2Pct,
      passed:
        structurallyValid &&
        within2Pct !== null &&
        within2Pct >= WITHIN_2_THRESHOLD,
    };
  }

  return {
    generated_at: new Date().toISOString(),
    model: GEMINI_MODEL,
    rubric_version: rubricVersion,
    dry_run: isDryRun,
    safety: {
      max_calls_cap: MAX_CALLS_PER_RUN,
      max_response_tokens: MAX_RESPONSE_TOKENS,
      total_estimated_calls: totalEstimatedCalls,
      call_cap_exceeded: capExceeded,
    },
    summary: {
      chats_evaluated: chatResults.filter((r) => r.status === "scored").length,
      chats_excluded: excludedCount,
      chats_failed: chatResults.filter((r) => r.status === "failed").length,
      overall_mae,
      overall_band_accuracy,
    },
    aggregation: {
      frame_delta_method: "holistic_pass_over_turn_weighted_aggregate",
      null_delta_handling: "excluded_from_dimension_average",
    },
    phase1_exit_criteria: phase1Exit,
    per_dimension,
    chat_results: chatResults,
  };
}

// ── Main calibration run ──────────────────────────────────────────────────────

async function runCalibration(
  chats: GoldChat[],
  excludedCount: number,
  isDryRun: boolean,
  reportPath: string,
  preloadedChatResults: ChatResult[],
  holisticBuilder?: JudgeConfig["holisticPromptBuilder"],
  csOption?: "opt1" | "opt2" | "opt3",
  rubricVersionOverride?: string,
  ecTwoPass?: boolean,
  useBoundaryChunker?: boolean,
): Promise<CalibrationReport> {
  const rubricVersion = rubricVersionOverride ?? (csOption === "opt1" ? "0.2_cs_rewrite" : "0.1");
  const baseConfig: Partial<JudgeConfig> = {
    provider: "gemini",
    default_model: GEMINI_MODEL,
    rubric_version: rubricVersion,
    max_response_tokens: MAX_RESPONSE_TOKENS,
    max_sampled_frames: MAX_SAMPLED_FRAMES,
    gold_chats_subdir: GOLD_CHATS_SUBDIR,
    ...(holisticBuilder !== undefined && { holisticPromptBuilder: holisticBuilder }),
    ...(csOption === "opt2" && { cs_holistic_only: true }),
    ...(csOption === "opt3" && { cs_split: true }),
    ...(ecTwoPass && { ec_two_pass: true }),
    ...(useBoundaryChunker && {
      use_boundary_chunker: true,
      boundary_log_path: reportPath.replace(/\.json$/, "_boundary_decisions.jsonl"),
    }),
  };

  // In-memory accumulator: starts with any preloaded results, grows as each
  // chat finishes. This array is authoritative; disk writes are durability only.
  const accumulatedChatResults: ChatResult[] = [...preloadedChatResults];

  // ── Dry-run pass: always runs first to count estimated calls ──────────────
  process.stdout.write(`\nEstimating API calls (dry-run pass)...\n`);

  let totalEstimatedCalls = 0;
  const dryResults = new Map<string, ScoredChat>();

  for (const chat of chats) {
    const result = await judgeChat(chat.id, { ...baseConfig, dry_run: true });
    dryResults.set(chat.id, result);
    totalEstimatedCalls += result.dry_run_calls.length;
    const sampledNote =
      result.total_frames > result.frame_count
        ? ` (sampled ${result.frame_count}/${result.total_frames})`
        : "";
    process.stdout.write(
      `  ${chat.id}: ${result.total_frames} chunks${sampledNote}, ${result.dry_run_calls.length} estimated calls\n`,
    );
    const totalTurns = result.frame_summaries.reduce((s, f) => s + f.turn_count, 0);
    for (const fs of result.frame_summaries) {
      const weight = (fs.turn_count / totalTurns * 100).toFixed(1);
      process.stdout.write(
        `    frame ${fs.chunk_index}: turns ${fs.turn_range[0]}–${fs.turn_range[1]}` +
        ` (${fs.turn_count} turns, weight ${weight}%)\n`,
      );
    }
    const holisticCall = result.dry_run_calls.find((c) => c.pass === "holistic");
    if (holisticCall) {
      process.stdout.write(
        `\n  ── Holistic prompt (${holisticCall.estimated_prompt_tokens} est. tokens) ──\n` +
        holisticCall.prompt_preview +
        `\n  ── End holistic prompt ──\n\n`,
      );
    }

    // In dry-run mode, write each chat's result incrementally as estimation completes.
    if (isDryRun) {
      const chatResult = buildSingleChatResult(chat, result, true);
      accumulatedChatResults.push(chatResult);
      tryWriteIncremental(reportPath, accumulatedChatResults, true, chat.id);
    }
  }

  const capExceeded = totalEstimatedCalls > MAX_CALLS_PER_RUN;
  process.stdout.write(
    `  Total: ${totalEstimatedCalls} estimated calls` +
      (capExceeded
        ? ` — EXCEEDS CAP OF ${MAX_CALLS_PER_RUN}`
        : ` (within cap of ${MAX_CALLS_PER_RUN})`) +
      `\n`,
  );

  if (capExceeded && !isDryRun) {
    throw new Error(
      `Calibration aborted: estimated ${totalEstimatedCalls} calls for ${GEMINI_MODEL}, ` +
        `exceeds hard cap of ${MAX_CALLS_PER_RUN}. ` +
        `Increase MAX_CALLS_PER_RUN or add calibration_excluded to more chats.`,
    );
  }

  if (isDryRun) {
    return buildReport(accumulatedChatResults, excludedCount, rubricVersion, true, totalEstimatedCalls, capExceeded);
  }

  // ── Live scoring ──────────────────────────────────────────────────────────
  process.stdout.write(`\nLive scoring ${chats.length} chats on ${GEMINI_MODEL}...\n`);

  for (const chat of chats) {
    process.stdout.write(`  Scoring ${chat.id}...`);
    let chatResult: ChatResult;
    try {
      const result = await judgeChat(chat.id, { ...baseConfig, dry_run: false });
      const note =
        result.total_frames > result.frame_count
          ? `${result.frame_count}/${result.total_frames} frames sampled`
          : `${result.frame_count} frames`;
      process.stdout.write(` done (${note})\n`);
      chatResult = buildSingleChatResult(chat, result, false);
    } catch (err) {
      const message = String(err);
      process.stdout.write(` FAILED: ${message}\n`);
      chatResult = buildSingleChatResult(chat, { error: message }, false);
    }
    accumulatedChatResults.push(chatResult);
    tryWriteIncremental(reportPath, accumulatedChatResults, false, chat.id);
  }

  return buildReport(accumulatedChatResults, excludedCount, rubricVersion, false, totalEstimatedCalls, capExceeded);
}

// ── CLI ───────────────────────────────────────────────────────────────────────

async function main(): Promise<void> {
  const args = process.argv.slice(2);
  const dryRun = args.includes("--dry-run");

  const limitIdx = args.indexOf("--limit");
  const limit = limitIdx !== -1 ? parseInt(args[limitIdx + 1] ?? "0", 10) : undefined;
  if (limit !== undefined && (isNaN(limit) || limit < 1)) {
    process.stderr.write(`--limit must be a positive integer\n`);
    process.exit(1);
  }

  const resumeIdx = args.indexOf("--resume-from");
  const resumeFrom = resumeIdx !== -1 ? (args[resumeIdx + 1] ?? "") : undefined;
  if (resumeFrom !== undefined && !resumeFrom) {
    process.stderr.write(`--resume-from requires a chat ID argument (e.g. --resume-from gc-003)\n`);
    process.exit(1);
  }

  const variantIdx = args.indexOf("--variant");
  const variant = variantIdx !== -1 ? (args[variantIdx + 1] ?? "") : undefined;
  if (variant !== undefined && variant !== "a" && variant !== "b") {
    process.stderr.write(`--variant must be "a" or "b"\n`);
    process.exit(1);
  }

  const csOptionIdx = args.indexOf("--cs-option");
  const csOptionRaw = csOptionIdx !== -1 ? (args[csOptionIdx + 1] ?? "") : undefined;
  if (csOptionRaw !== undefined && !["opt1", "opt2", "opt3"].includes(csOptionRaw)) {
    process.stderr.write(`--cs-option must be "opt1", "opt2", or "opt3"\n`);
    process.exit(1);
  }
  const csOption = csOptionRaw as "opt1" | "opt2" | "opt3" | undefined;

  const rubricVersionIdx = args.indexOf("--rubric-version");
  const rubricVersionOverride = rubricVersionIdx !== -1 ? (args[rubricVersionIdx + 1] ?? "") : undefined;
  if (rubricVersionOverride !== undefined && !rubricVersionOverride) {
    process.stderr.write(`--rubric-version requires a version string (e.g. --rubric-version 0.2_highband_fix)\n`);
    process.exit(1);
  }

  const ecTwoPass = args.includes("--ec-two-pass");
  const useBoundaryChunker = args.includes("--use-boundary-chunker");

  const holisticPromptBuilder =
    variant === "a" ? buildHolisticPromptVariantA :
    variant === "b" ? buildHolisticPromptVariantB :
    undefined;

  const csOptionLabel =
    csOption === "opt1" ? "rubric rewrite (v0.2_cs_rewrite)" :
    csOption === "opt2" ? "CS holistic-only (CS_HOLISTIC_ONLY)" :
    csOption === "opt3" ? "CS split (CS_SPLIT)" :
    "none (production)";

  process.stdout.write(
    `Synergy calibration harness — Phase 1\n` +
      `Model  : ${GEMINI_MODEL}\n` +
      `Mode   : ${dryRun ? "DRY-RUN (no API calls)" : "LIVE"}\n` +
      `Chats  : ${limit !== undefined ? `limited to first ${limit}` : "all"}` +
      `${resumeFrom !== undefined ? ` (resuming from ${resumeFrom})` : ""}\n` +
      `Variant: ${variant !== undefined ? `holistic prompt variant ${variant.toUpperCase()}` : "v5 (production)"}\n` +
      `Rubric : ${rubricVersionOverride !== undefined ? `v${rubricVersionOverride}` : "v0.1 (production)"}\n` +
      `CS opt : ${csOptionLabel}\n` +
      `EC     : ${ecTwoPass ? "two-pass (ADR 0004)" : "single-pass (production)"}\n` +
      `Chunker: ${useBoundaryChunker ? "goal-boundary (ADR 0005)" : "fixed-window (production)"}\n` +
      `Source : gold_standard/${GOLD_CHATS_SUBDIR}/\n`,
  );

  const allChats = loadGoldStandardChats({ minChats: 20 });
  let chats = allChats.filter((c) => !c.calibration_excluded);
  const excludedCount = allChats.length - chats.length;

  if (resumeFrom !== undefined) {
    const startIdx = chats.findIndex((c) => c.id === resumeFrom);
    if (startIdx === -1) {
      process.stderr.write(`--resume-from: chat ID "${resumeFrom}" not found in included chat list\n`);
      process.exit(1);
    }
    chats = chats.slice(startIdx);
  }
  if (limit !== undefined) chats = chats.slice(0, limit);

  process.stdout.write(
    `\nGold chats: ${allChats.length} loaded, ${excludedCount} excluded, ${chats.length} for calibration\n`,
  );

  mkdirSync(REPORTS_DIR, { recursive: true });

  // Compute reportPath before scoring so incremental writes know where to go.
  const reportSuffix = (() => {
    const parts: string[] = [];
    if (rubricVersionOverride !== undefined) parts.push(`_rubric_${rubricVersionOverride.replace(/[^a-z0-9]/gi, "_")}`);
    if (ecTwoPass) parts.push(`_ec_twopass`);
    if (useBoundaryChunker) parts.push(`_boundary_chunker`);
    if (parts.length > 0) return parts.join("");
    if (csOption !== undefined) return `_cs_${csOption}`;
    if (variant !== undefined) return `_tiebreak_${variant.toUpperCase()}`;
    if (resumeFrom !== undefined) return `_from_${resumeFrom}`;
    if (limit !== undefined) return `_limit${limit}`;
    return "";
  })();
  const reportPath = join(REPORTS_DIR, `phase1_gemini${reportSuffix}.json`);

  // When resuming: load any results already in the output file and skip those chats.
  let preloadedChatResults: ChatResult[] = [];
  if (resumeFrom !== undefined) {
    const existing = loadPreloadedResults(reportPath);
    if (existing.length > 0) {
      const preloadedIds = new Set(existing.map((r) => r.chat_id));
      const skipped = chats.filter((c) => preloadedIds.has(c.id)).map((c) => c.id);
      chats = chats.filter((c) => !preloadedIds.has(c.id));
      preloadedChatResults = existing;
      process.stdout.write(
        `\nLoaded ${existing.length} preexisting results from ${reportPath}\n` +
        (skipped.length > 0 ? `  Skipping already-scored: [${skipped.join(", ")}]\n` : ""),
      );
    }
  }

  const report = await runCalibration(
    chats, excludedCount, dryRun, reportPath, preloadedChatResults, holisticPromptBuilder, csOption, rubricVersionOverride, ecTwoPass, useBoundaryChunker,
  );

  // Overwrite with the final CalibrationReport (includes computed metrics).
  writeFileSync(reportPath, JSON.stringify(report, null, 2), "utf8");
  process.stdout.write(`\nReport written to: ${reportPath}\n`);

  if (!dryRun) {
    const { overall_mae, overall_band_accuracy, chats_evaluated, chats_failed } = report.summary;
    const exit = report.phase1_exit_criteria;
    process.stdout.write(
      `  Chats evaluated  : ${chats_evaluated}  failed: ${chats_failed}\n` +
        `  Overall MAE      : ${overall_mae !== null ? overall_mae.toFixed(3) : "n/a"}\n` +
        `  Band accuracy    : ${overall_band_accuracy !== null ? (overall_band_accuracy * 100).toFixed(1) + "%" : "n/a"}\n` +
        `\nPhase 1 exit criteria:\n` +
        `  Structural validity : ${exit.structural_validity ? "PASS" : "FAIL"}\n` +
        `  Within 2 delta      : ${exit.within_2_delta_pct !== null ? (exit.within_2_delta_pct * 100).toFixed(1) + "%" : "n/a"} (threshold: ${(WITHIN_2_THRESHOLD * 100).toFixed(0)}%)\n` +
        `  Overall             : ${exit.passed ? "PASSED" : "NOT PASSED"}\n`,
    );
  }

  process.stdout.write(`\nDone.\n`);
}

main().catch((err: unknown) => {
  process.stderr.write(String(err) + "\n");
  process.exit(1);
});
