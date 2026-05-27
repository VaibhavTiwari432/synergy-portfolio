import Anthropic from "@anthropic-ai/sdk";
import { appendFileSync, mkdirSync } from "node:fs";
import { dirname } from "node:path";
import { BoundaryDecisionSchema, type BoundaryDecision, type Turn } from "@synergy/schemas";

const HAIKU_MODEL = "claude-haiku-4-5-20251001";
const OPENROUTER_MODEL = "anthropic/claude-haiku-4-5";
const OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions";
const GEMINI_BOUNDARY_MODEL = "gemini-2.5-flash";
const GEMINI_URL = `https://generativelanguage.googleapis.com/v1beta/models/${GEMINI_BOUNDARY_MODEL}:generateContent`;

let _client: Anthropic | null = null;
let _keyIndex = 0;
let _keys: string[] | null = null;

function getKeys(): string[] {
  if (_keys === null) {
    const raw = process.env["ANTHROPIC_API_KEY"] ?? "";
    if (!raw) throw new Error("ANTHROPIC_API_KEY is not set.");
    _keys = raw.split(/[,;]/).map((k) => k.trim()).filter(Boolean);
    if (_keys.length === 0) throw new Error("ANTHROPIC_API_KEY is empty.");
  }
  return _keys;
}

function getCurrentKey(): string {
  const keys = getKeys();
  if (_keyIndex >= keys.length) throw new Error("All API keys exhausted (402 on each).");
  return keys[_keyIndex] as string;
}

function rotateKey(): boolean {
  _keyIndex++;
  _client = null; // reset SDK client for new key
  return _keyIndex < getKeys().length;
}

function getClient(): Anthropic {
  if (_client === null) {
    _client = new Anthropic({ apiKey: getCurrentKey() });
  }
  return _client;
}

function buildBoundaryPrompt(prevTurns: Turn[], nextTurns: Turn[]): string {
  const fmt = (turns: Turn[]) =>
    turns
      .map(
        (t) =>
          `[${t.turn_index}] ${t.role === "user" ? "User" : "Assistant"}: ${t.content.slice(0, 400)}`,
      )
      .join("\n\n");

  return `You are a conversation segmentation classifier. Determine whether the candidate turns begin a new goal or topic, or continue the previous one.

## Previous turns (end of current frame)

${fmt(prevTurns)}

## Candidate turns (potential start of next frame)

${fmt(nextTurns)}

Decision rules:
- new_goal: true  — candidate turns start a different task, question domain, or subject
- new_goal: false — candidate turns refine, follow up on, or continue the same goal

Respond with valid JSON only. No text outside the JSON.

{ "new_goal": <boolean> }`;
}

async function classifyOne(
  prevTurns: Turn[],
  nextTurns: Turn[],
  chatId: string,
  turnIndex: number,
  logPath: string | undefined,
): Promise<BoundaryDecision> {
  const prompt = buildBoundaryPrompt(prevTurns, nextTurns);
  let raw: string;

  const geminiKey = process.env["GEMINI_API_KEY"];
  if (geminiKey) {
    // Use Gemini flash for boundary classification — same key used for main scoring
    const res = await fetch(`${GEMINI_URL}?key=${geminiKey}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        contents: [{ parts: [{ text: prompt }] }],
        generationConfig: { maxOutputTokens: 32, temperature: 0 },
      }),
    });
    if (!res.ok) throw new Error(`Gemini boundary classifier: ${res.status} ${await res.text()}`);
    const data = (await res.json()) as {
      candidates?: Array<{ content?: { parts?: Array<{ text?: string }> } }>;
    };
    raw = data.candidates?.[0]?.content?.parts?.[0]?.text?.trim() ?? '{"new_goal":false}';
  } else if (getCurrentKey().startsWith("sk-or-v1-")) {
    const body = JSON.stringify({
      model: OPENROUTER_MODEL,
      messages: [{ role: "user", content: prompt }],
      max_tokens: 32,
      temperature: 0,
    });
    const MAX_RETRIES = 6;
    let res: Response | null = null;
    for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
      res = await fetch(OPENROUTER_URL, {
        method: "POST",
        headers: { Authorization: `Bearer ${getCurrentKey()}`, "Content-Type": "application/json" },
        body,
      });
      if (res.ok) break;
      if (res.status === 402) {
        if (!rotateKey()) throw new Error("OpenRouter boundary classifier: all keys exhausted (402).");
        continue;
      }
      if (res.status === 429 && attempt < MAX_RETRIES) {
        let waitSecs = 20;
        try {
          const errJson = (await res.json()) as { error?: { metadata?: { retry_after_seconds?: number } } };
          waitSecs = errJson.error?.metadata?.retry_after_seconds ?? 20;
        } catch { /* ignore parse error, use default */ }
        await new Promise((r) => setTimeout(r, waitSecs * 1000 + 500));
        continue;
      }
      throw new Error(`OpenRouter boundary classifier: ${res.status} ${await res.text()}`);
    }
    if (!res || !res.ok) throw new Error("OpenRouter boundary classifier: max retries exceeded");
    const data = (await res.json()) as {
      choices?: Array<{ message?: { content?: string } }>;
    };
    raw = data.choices?.[0]?.message?.content?.trim() ?? '{"new_goal":false}';
  } else {
    const response = await getClient().messages.create({
      model: HAIKU_MODEL,
      max_tokens: 32,
      temperature: 0,
      messages: [{ role: "user", content: prompt }],
    });
    raw =
      response.content[0]?.type === "text"
        ? response.content[0].text.trim()
        : '{"new_goal":false}';
  }

  let newGoal = false;
  try {
    const parsed = JSON.parse(raw) as { new_goal?: unknown };
    newGoal = parsed.new_goal === true;
  } catch {
    // parse error — default to false (keep in current frame)
  }

  const contextSnippet = [...prevTurns.slice(-1), ...nextTurns.slice(0, 1)]
    .map((t) => `[${t.turn_index}] ${t.role}: ${t.content.slice(0, 80)}`)
    .join(" | ");

  const usedModel = process.env["GEMINI_API_KEY"]
    ? GEMINI_BOUNDARY_MODEL
    : getCurrentKey().startsWith("sk-or-v1-")
      ? OPENROUTER_MODEL
      : HAIKU_MODEL;
  const decision: BoundaryDecision = BoundaryDecisionSchema.parse({
    chat_id: chatId,
    turn_index: turnIndex,
    new_goal: newGoal,
    model: usedModel,
    context_snippet: contextSnippet,
  });

  if (logPath !== undefined) {
    try {
      mkdirSync(dirname(logPath), { recursive: true });
      appendFileSync(logPath, JSON.stringify(decision) + "\n", "utf8");
    } catch {
      // non-fatal logging failure
    }
  }

  return decision;
}

/**
 * Walks through turns and classifies potential frame boundaries.
 * Mimics the chunking algorithm: at each frame, scans from turn 2 up to
 * the hard cap looking for a natural boundary (new_goal=true).
 *
 * Returns all BoundaryDecision objects for every position that was checked.
 * Hard-cap splits are NOT included (those are implicit from maxTurnsPerFrame).
 */
export async function classifyAllBoundaries(
  turns: Turn[],
  chatId: string,
  maxTurnsPerFrame: number,
  logPath?: string,
): Promise<BoundaryDecision[]> {
  const allDecisions: BoundaryDecision[] = [];
  let frameStart = 0;

  while (frameStart < turns.length) {
    const hardCap = Math.min(frameStart + maxTurnsPerFrame, turns.length);

    // No boundary check needed if remaining turns fit in one frame
    if (hardCap >= turns.length) break;

    let naturalBoundaryFound = false;

    for (let pos = frameStart + 2; pos < hardCap; pos++) {
      const prevCtx = turns.slice(Math.max(frameStart, pos - 2), pos);
      const nextCtx = turns.slice(pos, Math.min(pos + 2, turns.length));

      if (nextCtx.length === 0) break;

      const decision = await classifyOne(prevCtx, nextCtx, chatId, pos, logPath);
      allDecisions.push(decision);

      if (decision.new_goal) {
        frameStart = pos;
        naturalBoundaryFound = true;
        break;
      }
    }

    if (!naturalBoundaryFound) {
      frameStart = hardCap;
    }
  }

  return allDecisions;
}
