/**
 * save_prompt_samples.ts
 *
 * Generates and saves the scoring prompt for human review before approving
 * live API calls.
 *
 * Outputs to apps/judge/logs/dry_run_samples/:
 *   score_frame0_gc001.md  — scoring prompt for the first 8-turn frame
 *
 * Run:
 *   node dist/save_prompt_samples.js
 */

import { writeFileSync, mkdirSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { loadRubric } from "@synergy/rubric";
import type { Turn } from "@synergy/schemas";
import { loadGoldChat } from "./judge.js";
import { buildScoringPrompt } from "./prompt.js";

const __dirname = dirname(fileURLToPath(import.meta.url));
const OUT_DIR = join(__dirname, "../logs/dry_run_samples");

function sanitize(turns: Turn[]): Turn[] {
  return turns.filter((t) => t.content.trim().length > 0);
}

function meta(label: string, tokens: number, chars: number): string {
  return `<!-- ${label} | ~${tokens} prompt tokens | ${chars} chars -->\n\n`;
}

function estimateTokens(text: string): number {
  return Math.ceil(text.length / 4);
}

async function main(): Promise<void> {
  process.stdout.write(`OUT_DIR: ${OUT_DIR}\n`);
  mkdirSync(OUT_DIR, { recursive: true });

  const anchors = loadRubric("0.1");
  const chat = loadGoldChat("gc-001");
  const turns = sanitize(chat.turns);

  process.stdout.write(
    `gc-001: ${turns.length} usable turns  platform: ${chat.platform}\n`,
  );

  const frame0 = turns.slice(0, 8);
  const prompt = buildScoringPrompt(anchors, chat.platform, frame0);
  const outFile = join(OUT_DIR, "score_frame0_gc001.md");
  writeFileSync(
    outFile,
    meta("Score — frame 0 — turns 0–7", estimateTokens(prompt), prompt.length) + prompt,
    "utf8",
  );
  process.stdout.write(
    `Saved score_frame0_gc001.md  (~${estimateTokens(prompt)} tokens, ${prompt.length} chars)\n`,
  );

  process.stdout.write(`\nAll samples in: apps/judge/logs/dry_run_samples/\n`);
}

main().catch((err: unknown) => {
  process.stderr.write(String(err) + "\n");
  process.exit(1);
});
