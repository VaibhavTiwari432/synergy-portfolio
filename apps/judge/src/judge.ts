import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { randomUUID } from "node:crypto";
import { GoldChatSchema, type Turn } from "@synergy/schemas";
import { loadRubric } from "@synergy/rubric";
import { createProvider } from "./providers/index.js";
import { chunkTurns } from "./chunker.js";
import { scoreFrames, scoreHolistic, scoreECTwoPass, computeWeightedAggregate } from "./scorer.js";
import type { DryRunCall, JudgeConfig, ScoredChat } from "./types.js";

export const DEFAULT_CONFIG: JudgeConfig = {
  provider: "gemini",
  dry_run: false,
  default_model: "gemini-2.5-flash",
  rubric_version: "0.1",
  prompt_version: "0.1",
  max_turns_per_frame: 8,
  max_retries: 3,
};

function findGoldStandardDir(start: string, subdir: string): string {
  let current = start;
  while (true) {
    const candidate = join(current, "gold_standard", subdir);
    if (existsSync(candidate)) return candidate;
    const parent = dirname(current);
    if (parent === current) {
      throw new Error(
        `judgeChat: could not find gold_standard/${subdir} from ${start}`,
      );
    }
    current = parent;
  }
}

export function loadGoldChat(
  chatId: string,
  subdir = "chats",
): ReturnType<typeof GoldChatSchema.parse> {
  const goldDir = findGoldStandardDir(process.cwd(), subdir);
  const filePath = join(goldDir, `${chatId}.json`);

  let raw: unknown;
  try {
    raw = JSON.parse(readFileSync(filePath, "utf8"));
  } catch (err) {
    throw new Error(`loadGoldChat: cannot read ${filePath}: ${String(err)}`);
  }

  const result = GoldChatSchema.safeParse(raw);
  if (!result.success) {
    throw new Error(
      `loadGoldChat: ${chatId}.json failed GoldChat validation: ${result.error.message}`,
    );
  }
  return result.data;
}

function sanitizeTurns(turns: Turn[]): Turn[] {
  return turns.filter((t) => t.content.trim().length > 0);
}

/**
 * Select first⌊max/3⌋ + middle⌊max/3⌋ + last⌊max/3⌋ frames.
 * Returns all frames unchanged when frames.length <= max.
 */
function sampleFrames<T>(frames: T[], max: number): T[] {
  if (frames.length <= max) return frames;
  const n = frames.length;
  const third = Math.floor(max / 3);
  const firstIdx = Array.from({ length: third }, (_, i) => i);
  const lastIdx = Array.from({ length: third }, (_, i) => n - third + i);
  const mid = Math.floor(n / 2);
  const midStart = mid - Math.floor(third / 2);
  const midIdx = Array.from({ length: third }, (_, i) => midStart + i);
  const unique = [...new Set([...firstIdx, ...midIdx, ...lastIdx])].sort((a, b) => a - b);
  return unique.map((i) => frames[i] as T);
}

export interface ScoreDirectInput {
  chat_id?: string;
  platform: "chatgpt" | "claude.ai" | "gemini";
  turns: Turn[];
}

export async function scoreChatDirect(
  input: ScoreDirectInput,
  config: Partial<JudgeConfig> = {},
): Promise<ScoredChat> {
  const cfg: JudgeConfig = { ...DEFAULT_CONFIG, ...config };
  const chatId = input.chat_id ?? randomUUID();
  const turns = sanitizeTurns(input.turns);

  if (turns.length < 2) {
    throw new Error("scoreChatDirect: need at least 2 non-empty turns");
  }

  const anchors = loadRubric(cfg.rubric_version);
  const provider = createProvider(cfg);
  const dryRunCalls: DryRunCall[] = [];

  const { frames: allFrames, boundaries } = await chunkTurns(turns, chatId, input.platform, cfg);

  if (allFrames.length === 0) {
    throw new Error("scoreChatDirect: produced 0 frames after chunking");
  }

  const totalFrames = allFrames.length;
  const framesToScore =
    cfg.max_sampled_frames !== undefined
      ? sampleFrames(allFrames, cfg.max_sampled_frames)
      : allFrames;

  const { outputs } = await scoreFrames(framesToScore, anchors, provider, cfg, dryRunCalls);

  const frameSummaries = framesToScore.map((frame) => ({
    task_frame_id: frame.id,
    chunk_index: frame.chunk_index,
    turn_count: frame.turns.length,
    turn_range: [
      frame.turns[0]?.turn_index ?? 0,
      frame.turns[frame.turns.length - 1]?.turn_index ?? 0,
    ] as [number, number],
  }));

  const aggregateWeighted = computeWeightedAggregate(frameSummaries, outputs);

  const holisticOutput = await scoreHolistic(
    frameSummaries,
    outputs,
    aggregateWeighted,
    provider,
    cfg,
    dryRunCalls,
  );

  return {
    chat_id: chatId,
    frame_count: framesToScore.length,
    total_frames: totalFrames,
    frame_summaries: frameSummaries,
    frame_outputs: outputs,
    dry_run_calls: dryRunCalls,
    ...(holisticOutput !== undefined && { holistic_output: holisticOutput }),
    ...(boundaries.length > 0 && { chunk_boundaries: boundaries }),
  };
}

export async function judgeChat(
  chatId: string,
  config: Partial<JudgeConfig> = {},
): Promise<ScoredChat> {
  const cfg: JudgeConfig = { ...DEFAULT_CONFIG, ...config };

  const chat = loadGoldChat(chatId, cfg.gold_chats_subdir ?? "chats");
  const turns = sanitizeTurns(chat.turns);

  if (turns.length < 2) {
    throw new Error(`judgeChat: ${chatId} has fewer than 2 usable turns`);
  }

  const anchors = loadRubric(cfg.rubric_version);
  const provider = createProvider(cfg);

  const dryRunCalls: DryRunCall[] = [];

  const { frames: allFrames, boundaries } = await chunkTurns(turns, chatId, chat.platform, cfg);

  if (allFrames.length === 0) {
    throw new Error(`judgeChat: ${chatId} produced 0 frames after chunking`);
  }

  const totalFrames = allFrames.length;
  const framesToScore =
    cfg.max_sampled_frames !== undefined
      ? sampleFrames(allFrames, cfg.max_sampled_frames)
      : allFrames;

  const { outputs } = await scoreFrames(
    framesToScore,
    anchors,
    provider,
    cfg,
    dryRunCalls,
  );

  const frameSummaries = framesToScore.map((frame) => ({
    task_frame_id: frame.id,
    chunk_index: frame.chunk_index,
    turn_count: frame.turns.length,
    turn_range: [
      frame.turns[0]?.turn_index ?? 0,
      frame.turns[frame.turns.length - 1]?.turn_index ?? 0,
    ] as [number, number],
  }));

  // Pass 1.5: EC two-pass scoring (ADR 0004)
  let ecTwoPassDelta: number | null | undefined;
  if (cfg.ec_two_pass) {
    const ecScore = await scoreECTwoPass(
      turns,
      chat.platform,
      anchors,
      frameSummaries,
      outputs,
      provider,
      cfg,
      dryRunCalls,
    );
    // Replace EC in all frame outputs so the holistic pass sees pass-2 EC
    for (const output of outputs) {
      output.dimensions.EC = ecScore;
    }
    ecTwoPassDelta = ecScore.delta;
  }

  const aggregateWeighted = computeWeightedAggregate(frameSummaries, outputs);

  const holisticOutput = await scoreHolistic(
    frameSummaries,
    outputs,
    aggregateWeighted,
    provider,
    cfg,
    dryRunCalls,
    cfg.cs_holistic_only ? turns : undefined,
  );

  return {
    chat_id: chatId,
    frame_count: framesToScore.length,
    total_frames: totalFrames,
    frame_summaries: frameSummaries,
    frame_outputs: outputs,
    dry_run_calls: dryRunCalls,
    ...(holisticOutput !== undefined && { holistic_output: holisticOutput }),
    ...(ecTwoPassDelta !== undefined && { ec_two_pass_delta: ecTwoPassDelta }),
    ...(boundaries.length > 0 && { chunk_boundaries: boundaries }),
  };
}
