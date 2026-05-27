import { Hono } from "hono";
import { z } from "zod";
import { TurnSchema } from "@synergy/schemas";
import { scoreChatDirect } from "@synergy/judge";
import type { JudgeConfig } from "@synergy/judge";

// Production judge configuration — matches Phase 1 validated baseline.
// Do not change these without running calibration first.
const PRODUCTION_CONFIG: Partial<JudgeConfig> = {
  rubric_version: "0.2_highband_fix",
  prompt_version: "holistic_v5",
  ec_two_pass: false,
  use_boundary_chunker: false,
};

const ScoreRequestSchema = z.object({
  chat_id: z.string().optional(),
  platform: z.enum(["chatgpt", "claude.ai", "gemini"]),
  turns: z.array(TurnSchema).min(2, "Need at least 2 turns (one user + one assistant)"),
});

const app = new Hono();

// ── Auth middleware ────────────────────────────────────────────────────────────
// Set SCORE_API_KEY env var to enable auth. Omit for local dev.
app.use("/score", async (c, next) => {
  const apiKey = process.env["SCORE_API_KEY"];
  if (apiKey) {
    const auth = c.req.header("Authorization");
    if (auth !== `Bearer ${apiKey}`) {
      return c.json({ error: "Unauthorized", code: "auth_required" }, 401);
    }
  }
  return next();
});

// ── GET /health ────────────────────────────────────────────────────────────────
app.get("/health", (c) =>
  c.json({ status: "ok", rubric_version: PRODUCTION_CONFIG.rubric_version }),
);

// ── POST /score ────────────────────────────────────────────────────────────────
// Accept a chat, return 8-dimensional holistic scores.
//
// Request body:
//   { "chat_id": "optional-your-uuid", "platform": "chatgpt"|"claude.ai"|"gemini", "turns": [...] }
//
// Response 200:
//   { "chat_id", "rubric_version", "scored_at", "dimensions": { AL, PR, AUI, EC, CS, CD, ES, CA } }
//
// Latency: 20–60s depending on chat length (synchronous Gemini calls).
app.post("/score", async (c) => {
  let body: unknown;
  try {
    body = await c.req.json();
  } catch {
    return c.json({ error: "Invalid JSON body", code: "bad_request" }, 400);
  }

  const parsed = ScoreRequestSchema.safeParse(body);
  if (!parsed.success) {
    return c.json(
      { error: parsed.error.flatten().fieldErrors, code: "validation_error" },
      400,
    );
  }

  const { chat_id, platform, turns } = parsed.data;

  let result;
  try {
    result = await scoreChatDirect(
      { ...(chat_id !== undefined && { chat_id }), platform, turns },
      PRODUCTION_CONFIG,
    );
  } catch (err) {
    return c.json({ error: String(err), code: "scoring_error" }, 500);
  }

  if (!result.holistic_output) {
    return c.json(
      { error: "Judge returned no holistic output", code: "scoring_error" },
      500,
    );
  }

  return c.json({
    chat_id: result.chat_id,
    rubric_version: result.holistic_output.rubric_version,
    scored_at: result.holistic_output.scored_at,
    dimensions: result.holistic_output.dimensions,
  });
});

export default app;
