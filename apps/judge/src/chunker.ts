import { randomUUID } from "node:crypto";
import type { Turn, TaskFrame, BoundaryDecision } from "@synergy/schemas";
import type { JudgeConfig } from "./types.js";
import { classifyAllBoundaries } from "./boundary_classifier.js";

export interface ChunkTurnsResult {
  frames: TaskFrame[];
  boundaries: BoundaryDecision[];
}

export async function chunkTurns(
  turns: Turn[],
  chatId: string,
  platform: TaskFrame["platform"],
  config: JudgeConfig,
): Promise<ChunkTurnsResult> {
  const MAX = config.max_turns_per_frame;

  // Boundary chunker is skipped in dry-run — classifier makes live API calls
  if (config.use_boundary_chunker && !config.dry_run) {
    return chunkWithBoundaries(turns, chatId, platform, config, MAX, config.boundary_log_path);
  }

  // Fixed-window chunking (default, and always used in dry-run)
  const frames: TaskFrame[] = [];
  let frameStart = 0;
  let chunkIndex = 0;

  while (frameStart < turns.length) {
    const frameEnd = Math.min(frameStart + MAX, turns.length);
    const frameTurns = turns.slice(frameStart, frameEnd);
    if (frameTurns.length >= 2) {
      frames.push({
        id: randomUUID(),
        chat_id: chatId,
        platform,
        user_id: "calibration",
        turns: frameTurns,
        chunk_index: chunkIndex++,
        captured_at: new Date().toISOString(),
        rubric_version: config.rubric_version,
      });
    }
    frameStart = frameEnd;
  }

  return { frames, boundaries: [] };
}

async function chunkWithBoundaries(
  turns: Turn[],
  chatId: string,
  platform: TaskFrame["platform"],
  config: JudgeConfig,
  maxPerFrame: number,
  logPath?: string,
): Promise<ChunkTurnsResult> {
  const boundaries = await classifyAllBoundaries(turns, chatId, maxPerFrame, logPath);
  const frames: TaskFrame[] = [];
  let frameStart = 0;
  let chunkIndex = 0;

  while (frameStart < turns.length) {
    const hardCap = Math.min(frameStart + maxPerFrame, turns.length);

    // Find the earliest natural boundary before the hard cap
    const naturalBoundary = boundaries.find(
      (d) => d.new_goal && d.turn_index > frameStart && d.turn_index < hardCap,
    );
    const frameEnd = naturalBoundary ? naturalBoundary.turn_index : hardCap;

    const frameTurns = turns.slice(frameStart, frameEnd);
    if (frameTurns.length >= 2) {
      frames.push({
        id: randomUUID(),
        chat_id: chatId,
        platform,
        user_id: "calibration",
        turns: frameTurns,
        chunk_index: chunkIndex++,
        captured_at: new Date().toISOString(),
        rubric_version: config.rubric_version,
      });
    }
    frameStart = frameEnd;
  }

  return { frames, boundaries };
}
