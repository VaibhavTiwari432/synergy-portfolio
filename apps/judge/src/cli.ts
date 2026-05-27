/**
 * CLI entry point for the judge service.
 *
 * Usage:
 *   node dist/cli.js --chat gc-001 [--dry-run] [--model gemini-2.5-flash] [--summary-only]
 *
 * --dry-run       Logs every intended API call without making real requests.
 * --summary-only  In dry-run mode, prints counts and totals only.
 */

import { judgeChat, DEFAULT_CONFIG } from "./judge.js";
import type { DryRunCall } from "./types.js";

// ── Argument parsing ──────────────────────────────────────────────────────────

function parseArgs(argv: string[]): {
  chatId: string;
  dryRun: boolean;
  model: string;
  summaryOnly: boolean;
} {
  const args = argv.slice(2);
  let chatId = "";
  let dryRun = false;
  let model = DEFAULT_CONFIG.default_model;
  let summaryOnly = false;

  for (let i = 0; i < args.length; i++) {
    const arg = args[i];
    if (arg === "--chat" && args[i + 1]) {
      chatId = args[++i] ?? "";
    } else if (arg === "--dry-run") {
      dryRun = true;
    } else if (arg === "--summary-only") {
      summaryOnly = true;
    } else if (arg === "--model" && args[i + 1]) {
      model = args[++i] ?? model;
    }
  }

  if (!chatId) {
    process.stderr.write("Usage: node dist/cli.js --chat <chat-id> [--dry-run] [--model <model>]\n");
    process.exit(1);
  }

  return { chatId, dryRun, model, summaryOnly };
}

// ── Printers ──────────────────────────────────────────────────────────────────

function printSection(title: string): void {
  const bar = "─".repeat(60);
  process.stdout.write(`\n${bar}\n  ${title}\n${bar}\n`);
}

function printDryRunCalls(calls: DryRunCall[], summaryOnly: boolean): void {
  const totalTokens = calls.reduce((sum, c) => sum + c.estimated_prompt_tokens, 0);

  printSection(`Dry-Run API Call Summary`);
  process.stdout.write(
    `  score calls : ${calls.length}  (~${totalTokens.toLocaleString()} estimated prompt tokens)\n`,
  );
  process.stdout.write(
    `  model       : ${calls[0]?.model ?? "n/a"}\n`,
  );

  if (summaryOnly) return;

  for (const call of calls) {
    const [lo, hi] = call.turn_range ?? [0, 0];
    const label = `score frame ${call.frame_index ?? 0} (turns ${lo}–${hi})`;

    process.stdout.write(
      `\n  ── ${label} ──\n` +
        `     model  : ${call.model}\n` +
        `     ~tokens: ${call.estimated_prompt_tokens}\n` +
        `     prompt preview:\n`,
    );

    const lines = call.prompt_preview.split("\n").slice(0, 8);
    for (const line of lines) {
      process.stdout.write(`       ${line}\n`);
    }
    if (call.prompt_preview.split("\n").length > 8) {
      process.stdout.write("       ...\n");
    }
  }
}

function printFrameSummary(
  frameCount: number,
  totalFrames: number,
  chatId: string,
  model: string,
): void {
  printSection(`Frame Summary`);
  process.stdout.write(`  chat          : ${chatId}\n`);
  process.stdout.write(`  model         : ${model}\n`);
  process.stdout.write(`  frames scored : ${frameCount}${totalFrames > frameCount ? ` (sampled from ${totalFrames})` : ""}\n`);
}

// ── Main ──────────────────────────────────────────────────────────────────────

async function main(): Promise<void> {
  (process.stdout as NodeJS.WriteStream & { reconfigure?: (opts: { encoding: string }) => void }).reconfigure?.({ encoding: "utf-8" });

  const { chatId, dryRun, model, summaryOnly } = parseArgs(process.argv);

  process.stdout.write(
    `\nSynergy Judge — ${dryRun ? "DRY RUN" : "LIVE"}${summaryOnly ? " (summary only)" : ""}\n` +
      `chat: ${chatId}  model: ${model}\n`,
  );

  const result = await judgeChat(chatId, {
    dry_run: dryRun,
    default_model: model,
  });

  printFrameSummary(result.frame_count, result.total_frames, chatId, model);
  printDryRunCalls(result.dry_run_calls, summaryOnly);

  if (!dryRun) {
    printSection("JudgeOutput (JSON)");
    process.stdout.write(JSON.stringify(result.frame_outputs, null, 2) + "\n");
  }
}

main().catch((err: unknown) => {
  process.stderr.write(`\nError: ${String(err)}\n`);
  process.exit(1);
});
