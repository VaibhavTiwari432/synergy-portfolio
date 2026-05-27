/**
 * extract_turns.ts
 *
 * One-time calibration utility. Reads each gc-*.json source PDF, parses
 * conversation turns, and writes them into the `turns` array.
 *
 * NEVER touches annotation fields — only `turns`.
 *
 * Usage: pnpm --filter @synergy/calibration build && pnpm --filter @synergy/calibration extract-turns
 */

import { createRequire } from "node:module";
import { existsSync, readFileSync, readdirSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
// pdf-parse v1 exports a plain function — use createRequire to load CJS from ESM
// eslint-disable-next-line @typescript-eslint/no-require-imports
const pdfParse = require("pdf-parse") as (
  buf: Buffer,
) => Promise<{ text: string; numpages: number }>;

const __dirname = dirname(fileURLToPath(import.meta.url));
const GOLD_DIR = join(__dirname, "../../../gold_standard/chats");

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface Turn {
  role: "user" | "assistant";
  content: string;
  turn_index: number;
  timestamp_ms: number | null;
}

interface GoldChatRaw {
  id: string;
  platform: string;
  turns: Turn[];
  annotations: unknown[];
  rubric_version: string;
}

type PdfFormat =
  | "gemini_ai_exporter"
  | "gemini_labels"
  | "gemini_web"
  | "chatgpt_exporter"
  | "chatgpt_web_url"
  | "heuristic"
  | "image";

// ---------------------------------------------------------------------------
// Format detection
// ---------------------------------------------------------------------------

function detectFormat(text: string): PdfFormat {
  if (!text || text.trim().length < 50) return "image";
  if (/\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\s*You Asked/.test(text))
    return "gemini_ai_exporter";
  if (/^User:\s*\n/m.test(text)) return "gemini_labels";
  if (/ You said\s*\n/.test(text)) return "gemini_web";
  if (/Powered by ChatGPT Exporter/.test(text)) return "chatgpt_exporter";
  if (/chatgpt\.com\/c\//.test(text)) return "chatgpt_web_url";
  return "heuristic";
}

// ---------------------------------------------------------------------------
// Shared helpers
// ---------------------------------------------------------------------------

function indexTurns(segments: { role: "user" | "assistant"; content: string }[]): Turn[] {
  return segments
    .filter((s) => s.content.trim().length > 0)
    .map((s, i) => ({
      role: s.role,
      content: s.content.trim(),
      turn_index: i,
      timestamp_ms: null,
    }));
}

/** Strip inline page markers common across several export formats. */
function stripPageArtifacts(text: string): string {
  return text
    .replace(/Exported with AI Exporter \d+ \/ \d+/g, "")
    .replace(/🚀\s*Powered by ChatGPT Exporter \d+ \/ \d+/g, "")
    .replace(/Printed using ChatGPT to PDF[^\n]*/g, "")
    .replace(/This is a copy of a shared ChatGPT conversation\s*/g, "")
    .replace(/Report conversation\s*/g, "")
    .replace(/Show more\s*/g, "")
    .replace(/\d+\/\d+\/\d{2,4},? \d+:\d+ [AP]M [^\n]+\nhttps:\/\/chatgpt\.com\/c\/[^\n]+/g, "")
    .replace(/https?:\/\/[^\s]+/g, "")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

// ---------------------------------------------------------------------------
// Format A — Gemini AI Exporter
// Pattern: <timestamp> You Asked\n<user>\nGemini X.X Name\n<ai>
// ---------------------------------------------------------------------------

function parseGeminiAiExporter(text: string): Turn[] {
  const clean = stripPageArtifacts(text);
  const userSplitRe = /\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\s*You Asked\s*\n/;
  const blocks = clean.split(userSplitRe).slice(1); // drop preamble

  const segments: { role: "user" | "assistant"; content: string }[] = [];
  const modelNameRe = /\nGemini[\s\S]{0,30}?\n/;

  for (const block of blocks) {
    const match = modelNameRe.exec(block);
    if (match) {
      const userText = block.slice(0, match.index).trim();
      const aiText = block.slice(match.index + match[0].length).trim();
      if (userText) segments.push({ role: "user", content: userText });
      if (aiText) segments.push({ role: "assistant", content: aiText });
    } else {
      // no model name found — treat whole block as user
      if (block.trim()) segments.push({ role: "user", content: block.trim() });
    }
  }

  return indexTurns(segments);
}

// ---------------------------------------------------------------------------
// Format B — Gemini User:/Gemini: labels
// ---------------------------------------------------------------------------

function parseGeminiLabels(text: string): Turn[] {
  const clean = stripPageArtifacts(text);
  // Split on explicit label lines
  const parts = clean.split(/\n(?=User:\s*\n|Gemini:\s*\n)/);

  const segments: { role: "user" | "assistant"; content: string }[] = [];
  for (const part of parts) {
    const userMatch = /^User:\s*\n([\s\S]*)/.exec(part);
    const geminiMatch = /^Gemini:\s*\n([\s\S]*)/.exec(part);
    if (userMatch) {
      segments.push({ role: "user", content: userMatch[1]?.trim() ?? "" });
    } else if (geminiMatch) {
      segments.push({ role: "assistant", content: geminiMatch[1]?.trim() ?? "" });
    }
  }

  return indexTurns(segments);
}

// ---------------------------------------------------------------------------
// Format C — Gemini web export "You said"
// Pattern: header ... \n You said \n<user>\n<ai>\n You said \n...
// ---------------------------------------------------------------------------

function parseGeminiWeb(text: string): Turn[] {
  const clean = stripPageArtifacts(text);
  // Split on " You said" markers
  const rawSections = clean.split(/ You said\s*\n/);
  // rawSections[0] is the header (title, URL, dates) — skip it
  const sections = rawSections.slice(1);

  const segments: { role: "user" | "assistant"; content: string }[] = [];
  for (const section of sections) {
    // Within each section: first paragraph = user, rest = AI
    const nlIdx = section.indexOf("\n\n");
    if (nlIdx !== -1) {
      const userText = section.slice(0, nlIdx).trim();
      const aiText = section.slice(nlIdx).trim();
      if (userText) segments.push({ role: "user", content: userText });
      if (aiText) segments.push({ role: "assistant", content: aiText });
    } else {
      // single block — treat as user
      if (section.trim()) segments.push({ role: "user", content: section.trim() });
    }
  }

  return indexTurns(segments);
}

// ---------------------------------------------------------------------------
// Format D — ChatGPT Exporter (timestamp lines alternate user/AI)
// ---------------------------------------------------------------------------

const CHATGPT_EXPORTER_TS_RE =
  /\d{1,2}\/\d{1,2}\/\d{4},?\s+\d{1,2}:\d{2}:\d{2}/g;

function parseChatGptExporter(text: string): Turn[] {
  const clean = stripPageArtifacts(text);

  // Split into segments at every timestamp; first segment may be the title
  const parts = clean.split(CHATGPT_EXPORTER_TS_RE);

  // parts[0] = title/preamble, parts[1..] alternate user / AI
  const conversationParts = parts.slice(1).map((p) => p.trim()).filter(Boolean);

  const segments: { role: "user" | "assistant"; content: string }[] = [];
  conversationParts.forEach((content, i) => {
    segments.push({ role: i % 2 === 0 ? "user" : "assistant", content });
  });

  return indexTurns(segments);
}

// ---------------------------------------------------------------------------
// Format E — ChatGPT web print with URL in page header
// Page header pattern: "<date> <time> <title>\nhttps://chatgpt.com/c/... N/M"
// Turns alternate; first content block is user.
// ---------------------------------------------------------------------------

const CHATGPT_WEB_HEADER_RE =
  /\d+\/\d+\/\d{2,4},?\s+\d+:\d+\s+[AP]M\s+[^\n]+\nhttps?:\/\/chatgpt\.com\/c\/[^\n]+/g;

function parseChatGptWebUrl(text: string): Turn[] {
  // Strip the page headers, leaving only conversation text
  const stripped = text.replace(CHATGPT_WEB_HEADER_RE, "\n\n").replace(/\n{3,}/g, "\n\n").trim();
  return parseHeuristic(stripped);
}

// ---------------------------------------------------------------------------
// Heuristic fallback — alternating paragraph blocks
// Works for: "shared chat", no-label, PDFCrowd, and anything else.
// ---------------------------------------------------------------------------

function parseHeuristic(text: string): Turn[] {
  const clean = stripPageArtifacts(text);

  // Split into paragraph blocks (double newline boundary)
  const rawBlocks = clean.split(/\n{2,}/).map((b) => b.trim()).filter((b) => b.length > 10);

  if (rawBlocks.length === 0) return [];

  // Merge very short consecutive blocks (< 80 chars) with the following block,
  // because user messages are often short but never that short on their own.
  const merged: string[] = [];
  let buf = "";
  for (const block of rawBlocks) {
    if (buf.length > 0 && buf.length < 80) {
      buf += "\n\n" + block;
    } else {
      if (buf.length > 0) merged.push(buf);
      buf = block;
    }
  }
  if (buf.length > 0) merged.push(buf);

  // Determine first role: if first block looks like AI (starts with affirmation
  // or is very long), treat as AI, otherwise user.
  const AI_OPENER_RE = /^(Sure|Great|Alright|Absolutely|Of course|Here'?s|Let me|I'll|I will|I can|I've|Happy to|Understood)/i;
  const firstIsAI = AI_OPENER_RE.test(merged[0] ?? "") && (merged[0]?.length ?? 0) > 300;

  const segments: { role: "user" | "assistant"; content: string }[] = merged.map(
    (content, i) => ({
      role: ((firstIsAI ? i + 1 : i) % 2 === 0 ? "user" : "assistant") as "user" | "assistant",
      content,
    }),
  );

  return indexTurns(segments);
}

// ---------------------------------------------------------------------------
// Main extraction dispatcher
// ---------------------------------------------------------------------------

async function extractTurnsFromPdf(pdfPath: string): Promise<{
  turns: Turn[];
  format: PdfFormat;
  pageCount: number;
}> {
  const buf = readFileSync(pdfPath);
  let text = "";
  let pageCount = 0;

  try {
    const result = await pdfParse(buf);
    text = result.text;
    pageCount = result.numpages;
  } catch {
    // pdf-parse can throw on some PDFs — treat as image
    return { turns: [], format: "image", pageCount: 0 };
  }

  const format = detectFormat(text);

  let turns: Turn[];
  switch (format) {
    case "image":
      turns = [];
      break;
    case "gemini_ai_exporter":
      turns = parseGeminiAiExporter(text);
      break;
    case "gemini_labels":
      turns = parseGeminiLabels(text);
      break;
    case "gemini_web":
      turns = parseGeminiWeb(text);
      break;
    case "chatgpt_exporter":
      turns = parseChatGptExporter(text);
      break;
    case "chatgpt_web_url":
      turns = parseChatGptWebUrl(text);
      break;
    default:
      turns = parseHeuristic(text);
  }

  return { turns, format, pageCount };
}

// ---------------------------------------------------------------------------
// Source PDF lookup
// ---------------------------------------------------------------------------

const PDF_MAP: Record<string, string> = {
  "gc-001": "Career - Google PM Strategy.pdf",
  "gc-002": "Pratik_ChatGPT.pdf",
  "gc-003": "Ritesh_Gemini.pdf",
  "gc-004": "Kartikeya_ChatGPT.pdf",
  "gc-005": "Darshit_Chat1.pdf",
  "gc-006": "Darshit_Chat2.pdf",
  "gc-007": "Darshit_Chat3.pdf",
  "gc-008": "Abhishek_1.pdf",
  "gc-009": "Abhishek_2.pdf",
  "gc-010": "Advitya_ChatGPT.pdf",
  "gc-011": "Akshita_ChatGPT.pdf",
  "gc-012": "Bharath_ChatGPT.pdf",
  "gc-013": "Jay_ChatGPT1.pdf",
  "gc-016": "Puransh_Gemini.pdf",
  "gc-017": "RamKrishna_ChatGPT.pdf",
  "gc-018": "Shreyas_Gemini.pdf",
  "gc-019": "Shreyash_ChatGPT.pdf",
  "gc-020": "Simran_ChatGPT.pdf",
  "gc-021": "Yatendra_ChatGPT.pdf",
  "gc-022": "rahul_chatgpt.pdf",
  "gc-023": "Shivansh_ChatGPT.pdf",
};

// ---------------------------------------------------------------------------
// Entry point
// ---------------------------------------------------------------------------

async function main(): Promise<void> {
  const jsonFiles = readdirSync(GOLD_DIR)
    .filter((f) => /^gc-\d{3}\.json$/.test(f))
    .sort();

  const report: string[] = ["# Turn Extraction Report\n"];

  for (const jsonFile of jsonFiles) {
    const chatId = jsonFile.replace(".json", "");
    const jsonPath = join(GOLD_DIR, jsonFile);
    const pdfName = PDF_MAP[chatId];

    if (!pdfName) {
      report.push(`## ${chatId}: SKIPPED — no PDF mapping`);
      continue;
    }

    const pdfPath = join(GOLD_DIR, pdfName);
    if (!existsSync(pdfPath)) {
      report.push(`## ${chatId}: SKIPPED — PDF not found (${pdfName})`);
      continue;
    }

    process.stdout.write(`${chatId}  extracting ${pdfName} ...`);

    const { turns, format, pageCount } = await extractTurnsFromPdf(pdfPath);

    if (format === "image" || turns.length === 0) {
      report.push(
        `## ${chatId}\n- PDF: ${pdfName}\n- Format: ${format}\n- Pages: ${pageCount}\n- Result: SKIPPED (image PDF or no turns extracted) — placeholder turns retained\n`,
      );
      process.stdout.write(" SKIPPED (image PDF)\n");
      continue;
    }

    // Read current JSON, replace only `turns`, write back
    const raw = JSON.parse(readFileSync(jsonPath, "utf8")) as GoldChatRaw;
    const updated: GoldChatRaw = { ...raw, turns };
    writeFileSync(jsonPath, JSON.stringify(updated, null, 2) + "\n", "utf8");

    const userCount = turns.filter((t) => t.role === "user").length;
    const aiCount = turns.filter((t) => t.role === "assistant").length;

    report.push(
      `## ${chatId}\n- PDF: ${pdfName}\n- Format: ${format}\n- Pages: ${pageCount}\n- Turns extracted: ${turns.length} (${userCount} user, ${aiCount} assistant)\n`,
    );
    process.stdout.write(` ${turns.length} turns (${format})\n`);
  }

  const reportPath = join(__dirname, "../../../calibration/audit/turn_extraction_report.md");
  writeFileSync(reportPath, report.join("\n"), "utf8");
  process.stdout.write(`\nReport written to calibration/audit/turn_extraction_report.md\n`);
}

main().catch((err: unknown) => {
  console.error(err);
  process.exit(1);
});
