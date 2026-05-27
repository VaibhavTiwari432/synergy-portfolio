/**
 * anonymize.ts
 *
 * Produces gold_standard/chats_anonymized/ from gold_standard/chats/.
 * Originals are never modified.
 *
 * Redactions applied:
 *   gc-001  turn 0   : "Alright Vaibhav —" → "Alright [STUDENT] —"
 *   gc-018  turn 71  : Gemini UI footer block → [GEMINI_UI_REDACTED]
 *   gc-021  all turns: email pdorpmpu@... → [EMAIL_REDACTED]
 *                      postal address → [ADDRESS_REDACTED]
 *                      PIN code → [PIN_REDACTED]
 *   gc-022  turns 8-12: "Anurag Srivastava" → [PROFESSOR_NAME]
 *                       "ABV-IIITM" → [INSTITUTION]
 *                       "Advanced Materials Research Group (AMRG)" → [RESEARCH_GROUP]
 *   gc-023  turn 4   : "Shivansh Yadav" → [FOUNDER_NAME]
 *
 * Generic: all email addresses → [EMAIL_REDACTED] (catches any we missed)
 *
 * Run: node dist_anon/anonymize.js
 * Or:  npx tsx anonymize.ts   (if tsx is installed)
 */

import { readFileSync, writeFileSync, mkdirSync, readdirSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import type { GoldChat } from "../packages/schemas/src/index.js";

const __dirname = dirname(fileURLToPath(import.meta.url));
const CHATS_DIR = join(__dirname, "chats");
const OUT_DIR = join(__dirname, "chats_anonymized");

// ── Targeted redaction rules ──────────────────────────────────────────────────
// Each rule is { chatId?, pattern, replacement } — chatId scopes it to one file.

interface Rule {
  chatId?: string;
  pattern: RegExp;
  replacement: string;
}

const RULES: Rule[] = [
  // Generic: all email addresses (catches any residual hits)
  {
    pattern: /[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}/g,
    replacement: "[EMAIL_REDACTED]",
  },

  // gc-001: student addressed by first name in AI response
  {
    chatId: "gc-001",
    pattern: /Alright Vaibhav\s*[—–-]/g,
    replacement: "Alright [STUDENT] —",
  },

  // gc-018: Gemini UI footer block that leaked into export
  {
    chatId: "gc-018",
    pattern: /Google Account\s*\nVaibhav Tiwari\s*\nvt1445388@gmail\.com\s*\nCopy public link\s*\nReport/g,
    replacement: "[GEMINI_UI_REDACTED]",
  },
  {
    chatId: "gc-018",
    pattern: /Vaibhav Tiwari/g,
    replacement: "[STUDENT_NAME]",
  },

  // gc-021: postal addresses and PIN codes in work certificate
  {
    chatId: "gc-021",
    pattern: /BAMOREKALAN,\s*DIST\.\s*SHIVPURI\s*\(M\.P\.\)/gi,
    replacement: "[ADDRESS_REDACTED]",
  },
  {
    chatId: "gc-021",
    pattern: /102\s*Dream Apartment,\s*Thatipur,\s*Gwalior\s*474002\s*\(M\.P\.\)/gi,
    replacement: "[ADDRESS_REDACTED]",
  },
  {
    chatId: "gc-021",
    pattern: /Pin:\s*473585/gi,
    replacement: "Pin: [PIN_REDACTED]",
  },

  // gc-022: professor name and institution in journal cover letter
  {
    chatId: "gc-022",
    pattern: /Anurag Srivastava/g,
    replacement: "[PROFESSOR_NAME]",
  },
  {
    chatId: "gc-022",
    pattern: /ABV[-–]IIITM/g,
    replacement: "[INSTITUTION]",
  },
  {
    chatId: "gc-022",
    pattern: /Advanced Materials Research Group\s*\(AMRG\)/g,
    replacement: "[RESEARCH_GROUP]",
  },
  {
    chatId: "gc-022",
    pattern: /\bAMRG\b/g,
    replacement: "[RESEARCH_GROUP]",
  },

  // gc-023: founder's full name in app description (name may span a line break)
  {
    chatId: "gc-023",
    pattern: /Shivansh[\s\n]+Yadav/g,
    replacement: "[FOUNDER_NAME]",
  },

  // gc-028: name of private individual whose contact details were requested
  {
    chatId: "gc-028",
    pattern: /Anuska Patil/g,
    replacement: "[PERSON_NAME]",
  },
];

// ── Processing ────────────────────────────────────────────────────────────────

function redactContent(content: string, chatId: string): string {
  let out = content;
  for (const rule of RULES) {
    if (rule.chatId !== undefined && rule.chatId !== chatId) continue;
    // Reset lastIndex for global regexes used across multiple calls
    rule.pattern.lastIndex = 0;
    out = out.replace(rule.pattern, rule.replacement);
    rule.pattern.lastIndex = 0;
  }
  return out;
}

function anonymizeChat(chat: GoldChat, chatId: string): GoldChat {
  const redactedTurns = chat.turns.map((turn) => ({
    ...turn,
    content: redactContent(turn.content, chatId),
  }));
  return { ...chat, turns: redactedTurns };
}

function main(): void {
  mkdirSync(OUT_DIR, { recursive: true });

  const files = readdirSync(CHATS_DIR).filter((f) => f.endsWith(".json"));
  let processed = 0;
  let redactionCount = 0;

  for (const file of files) {
    const chatId = file.replace(".json", "");
    const inPath = join(CHATS_DIR, file);
    const outPath = join(OUT_DIR, file);

    const raw = JSON.parse(readFileSync(inPath, "utf8")) as GoldChat;
    const anon = anonymizeChat(raw, chatId);

    // Count actual changes
    const rawStr = JSON.stringify(raw);
    const anonStr = JSON.stringify(anon, null, 2);
    const changed = rawStr !== JSON.stringify(anon);
    if (changed) redactionCount++;

    writeFileSync(outPath, anonStr, "utf8");
    const marker = changed ? " ← redacted" : "";
    process.stdout.write(`  ${file}${marker}\n`);
    processed++;
  }

  process.stdout.write(
    `\nDone. ${processed} chats written to chats_anonymized/  (${redactionCount} had redactions)\n`,
  );
}

main();
