/**
 * run_boundary_audit.ts
 *
 * Runs the claude-haiku-4-5 goal-boundary classifier on all 23 active gold chats
 * and produces a Markdown audit for human review. Does NOT run the full judge —
 * no Gemini calls are made.
 *
 * Usage:
 *   ANTHROPIC_API_KEY=<key> npx tsx run_boundary_audit.ts [--dry-run]
 *
 * --dry-run: list chats and simulate frame boundaries without calling the API.
 *
 * Output:
 *   calibration/reports/boundary_decisions_<YYYYMMDD>.jsonl  (one decision per line)
 *   calibration/reports/boundary_chunking_audit.md           (human review document)
 *
 * After reviewing the audit, do NOT run calibration with the boundary chunker
 * until the audit has been approved.
 */

import { writeFileSync, mkdirSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { loadGoldStandardChats } from "./gold_standard_loader.js";
import { classifyAllBoundaries } from "@synergy/judge";
import type { BoundaryDecision } from "@synergy/schemas";
import type { Turn } from "@synergy/schemas";

const MAX_TURNS_PER_FRAME = 8;
const GOLD_CHATS_SUBDIR = "chats_anonymized";

const __dirname = dirname(fileURLToPath(import.meta.url));
const REPORTS_DIR = join(__dirname, "../reports");

function sanitizeTurns(turns: Turn[]): Turn[] {
  return turns.filter((t) => t.content.trim().length > 0);
}

function computeFixedWindowFrameCount(turnCount: number, max: number): number {
  let count = 0;
  let start = 0;
  while (start < turnCount) {
    const end = Math.min(start + max, turnCount);
    if (end - start >= 2) count++;
    start = end;
  }
  return count;
}

function deriveBoundaryFrameBoundaries(
  turnCount: number,
  decisions: BoundaryDecision[],
  maxPerFrame: number,
): number[] {
  const boundaries: number[] = [0];
  let frameStart = 0;

  while (frameStart < turnCount) {
    const hardCap = Math.min(frameStart + maxPerFrame, turnCount);
    if (hardCap >= turnCount) break;

    const natural = decisions.find(
      (d) => d.new_goal && d.turn_index > frameStart && d.turn_index < hardCap,
    );
    const next = natural ? natural.turn_index : hardCap;
    boundaries.push(next);
    frameStart = next;
  }

  return boundaries;
}

async function main(): Promise<void> {
  const args = process.argv.slice(2);
  const dryRun = args.includes("--dry-run");

  const dateStr = new Date().toISOString().slice(0, 10).replace(/-/g, "");
  const jsonlPath = join(REPORTS_DIR, `boundary_decisions_${dateStr}.jsonl`);
  const auditPath = join(REPORTS_DIR, "boundary_chunking_audit.md");

  mkdirSync(REPORTS_DIR, { recursive: true });

  process.stdout.write(
    `Boundary chunking audit\n` +
      `Model  : claude-haiku-4-5-20251001 (temperature=0)\n` +
      `Mode   : ${dryRun ? "DRY-RUN (no API calls)" : "LIVE"}\n` +
      `Max    : ${MAX_TURNS_PER_FRAME} turns/frame\n` +
      `Source : gold_standard/${GOLD_CHATS_SUBDIR}/\n` +
      (dryRun ? `` : `JSONL   : ${jsonlPath}\n`) +
      `\n`,
  );

  const allChats = loadGoldStandardChats({ minChats: 20 });
  const chats = allChats.filter((c) => !c.calibration_excluded);
  process.stdout.write(`Gold chats: ${allChats.length} loaded, ${allChats.length - chats.length} excluded, ${chats.length} for audit\n\n`);

  interface ChatAuditResult {
    chatId: string;
    turnCount: number;
    decisions: BoundaryDecision[];
    frameBoundaries: number[];
    fixedWindowFrameCount: number;
  }

  const results: ChatAuditResult[] = [];

  for (const chat of chats) {
    process.stdout.write(`  ${chat.id}...`);
    const turns = sanitizeTurns(chat.turns);

    let decisions: BoundaryDecision[];

    if (dryRun) {
      decisions = [];
    } else {
      decisions = await classifyAllBoundaries(
        turns,
        chat.id,
        MAX_TURNS_PER_FRAME,
        jsonlPath,
      );
    }

    const frameBoundaries = deriveBoundaryFrameBoundaries(turns.length, decisions, MAX_TURNS_PER_FRAME);
    const fixedWindowFrameCount = computeFixedWindowFrameCount(turns.length, MAX_TURNS_PER_FRAME);
    const naturalBoundaries = decisions.filter((d) => d.new_goal).length;

    results.push({ chatId: chat.id, turnCount: turns.length, decisions, frameBoundaries, fixedWindowFrameCount });

    process.stdout.write(
      ` done — ${turns.length} turns, fixed=${fixedWindowFrameCount} frames, boundary=${frameBoundaries.length} frames, natural=${naturalBoundaries}\n`,
    );
  }

  // ── Write audit markdown ──────────────────────────────────────────────────

  const lines: string[] = [
    `# Boundary Chunking Audit`,
    ``,
    `**Date:** ${new Date().toISOString().slice(0, 10)}`,
    `**Model:** \`claude-haiku-4-5-20251001\` (temperature=0)`,
    `**Max turns/frame:** ${MAX_TURNS_PER_FRAME}`,
    `**Mode:** ${dryRun ? "DRY-RUN (no API calls — simulated only)" : "LIVE"}`,
    dryRun ? `` : `**JSONL:** \`${jsonlPath}\``,
    ``,
    `---`,
    ``,
    `## Review instructions`,
    ``,
    `For each chat, inspect the natural boundaries (new_goal=true) and verify:`,
    ``,
    `1. **Correct splits** — boundary makes semantic sense (candidate turns genuinely start a different task/goal)`,
    `2. **No over-splitting** — classifier is not marking follow-ups or clarifications as new goals`,
    `3. **No under-splitting** — classifier is not keeping clearly distinct topics in the same frame`,
    ``,
    `For each chat, mark the status column as one of:`,
    `- \`approved\` — boundaries look correct`,
    `- \`over-split\` — classifier split too aggressively`,
    `- \`under-split\` — classifier missed an obvious boundary`,
    `- \`flag\` — needs closer review before approving`,
    ``,
    `---`,
    ``,
    `## Summary`,
    ``,
    `| Chat | Turns | Fixed-window frames | Boundary frames | Natural boundaries | Status |`,
    `|------|:-----:|:-------------------:|:---------------:|:-----------------:|--------|`,
  ];

  for (const r of results) {
    const naturalBoundaries = r.decisions.filter((d) => d.new_goal).length;
    lines.push(
      `| ${r.chatId} | ${r.turnCount} | ${r.fixedWindowFrameCount} | ${r.frameBoundaries.length} | ${naturalBoundaries} | pending |`,
    );
  }

  lines.push(``, `---`, ``);
  lines.push(`## Per-Chat Details`, ``);

  for (const r of results) {
    lines.push(`### ${r.chatId} (${r.turnCount} turns)`, ``);

    if (r.decisions.length === 0) {
      const reason = dryRun ? "dry-run mode — no API calls made" : "no boundary checks performed (fits in single frame)";
      lines.push(`*${reason}*`, ``);
      lines.push(`Frame boundaries (fixed-window): 0 → ${r.turnCount}`, ``);
      continue;
    }

    lines.push(`**Frame boundaries:** [${r.frameBoundaries.join(", ")}] → ${r.frameBoundaries.length} frames`, ``);
    lines.push(`| Turn | new_goal | Context snippet |`);
    lines.push(`|:----:|:--------:|-----------------|`);

    for (const d of r.decisions) {
      const flag = d.new_goal ? "**YES** ←" : "no";
      const snippet = d.context_snippet.replace(/\|/g, "\\|").slice(0, 120);
      lines.push(`| ${d.turn_index} | ${flag} | \`${snippet}\` |`);
    }

    lines.push(``);
  }

  lines.push(`---`);
  lines.push(``);
  lines.push(`> **Pause — do not self-approve this audit.** Human review required before running calibration with \`--use-boundary-chunker\`.`);

  writeFileSync(auditPath, lines.join("\n"), "utf8");

  process.stdout.write(`\nAudit written to: ${auditPath}\n`);
  if (!dryRun) {
    process.stdout.write(`JSONL written to: ${jsonlPath}\n`);
  }
  process.stdout.write(`\nDone. Review the audit before running calibration with the boundary chunker.\n`);
}

main().catch((err: unknown) => {
  process.stderr.write(String(err) + "\n");
  process.exit(1);
});
