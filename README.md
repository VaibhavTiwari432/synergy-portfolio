# Synergy Portfolio Analyzer

Scores AI-collaboration quality across 8 dimensions by analysing a user's conversations with ChatGPT, Claude.ai, or Gemini. Part of the **Sangillence Insight System (SIS)**.

---

## What it does

A user's chat is submitted to the scorer. The scorer reads the conversation and returns 8 dimension scores describing *how well* the human collaborated with the AI — not what they talked about.

| Code | Dimension | What it measures |
|------|-----------|-----------------|
| AL | AI Literacy | Does the user understand what they're talking to? |
| PR | Prompt Reasoning | Quality of prompt construction per turn |
| AUI | Augmentation Instinct | Knowing when to use AI vs. handle solo |
| EC | Error Correction | Catching AI mistakes and hallucinations |
| CS | Contextual Synthesis | Weaving AI output with own knowledge |
| CD | Creative Divergence | Using AI to explore, not just confirm |
| ES | Ethics Sensitivity | Awareness of bias, harm, and attribution |
| CA | Collaborative Agency | Staying in the driver's seat |

Scores accumulate into a per-user **portfolio** with a 0–10 scale per dimension. Over time, the portfolio reveals an AI-collaboration archetype and surfaces targeted improvement drills.

---

## Architecture

```
Browser Extension (Chrome MV3)          ← Phase 3 — not yet built
        │
        │  POST /score  (chat turns)
        ▼
Score API  (apps/api — Hono + Node.js)  ← Phase 2 — API built, queue/DB pending
        │
        │  calls scoreChatDirect()
        ▼
Judge Service  (apps/judge — Gemini)    ← Phase 1 — COMPLETE ✓
        │
        ▼
PostgreSQL + BullMQ Queue               ← Phase 2 — not yet built
```

---

## Current status

| Phase | What | Status |
|-------|------|--------|
| 0 | Rubric + gold standard chats + schemas | **Complete** |
| 1 | Judge service (scorer) | **Complete** — 89.4% accuracy on 23 chats |
| 2 | Score API endpoint | **Complete** — `POST /score` live |
| 2 | Queue + database + portfolio | Not yet built |
| 3 | Chrome extension scraper | Not yet built |
| 4 | Drills + portfolio UI | Not yet specified |

---

## Repo structure

```
synergy-portfolio/
├── apps/
│   ├── api/              # Score API — POST /score endpoint (Hono)
│   ├── judge/            # Scorer — calls Gemini, returns 8 dimension scores
│   └── extension/        # Chrome extension — not yet built
├── packages/
│   ├── schemas/          # Zod schemas for all types (TaskFrame, JudgeOutput, Portfolio)
│   ├── rubric/           # Rubric JSON v0.2 — 24 anchors across 8 dimensions
│   └── shared/           # Shared utilities
├── gold_standard/        # 28 hand-scored reference chats used for calibration
├── calibration/          # Scripts to measure judge accuracy against gold standard
├── docs/
│   └── decisions/        # Architecture Decision Records (ADRs)
├── SYNERGY_PORTFOLIO_SPEC.md  # Full product + technical specification
└── CLAUDE.md             # AI session instructions
```

---

## Setup

**Requirements:** Node.js 20+, pnpm 8+

```bash
git clone https://github.com/VaibhavTiwari432/synergy-portfolio.git
cd synergy-portfolio
pnpm install
```

**Build:**

```bash
pnpm --filter @synergy/schemas build
pnpm --filter @synergy/rubric build
pnpm --filter @synergy/judge build
pnpm --filter @synergy/api build
```

**Environment variables:**

| Variable | Required | Description |
|---|---|---|
| `GEMINI_API_KEY` | Yes | Google AI Studio API key — the scorer calls Gemini 2.5 Flash |
| `SCORE_API_KEY` | Recommended | Secret token — clients send this in the `Authorization` header |
| `PORT` | No | Port for the API server (default: `3000`) |

---

## Running the Score API

```bash
GEMINI_API_KEY=your_key SCORE_API_KEY=your_secret node apps/api/dist/index.js
# → Score API listening on http://localhost:3000
```

---

## API reference

### `GET /health`

Liveness check. Returns `200` when the server is up.

```json
{ "status": "ok", "rubric_version": "0.2_highband_fix" }
```

---

### `POST /score`

Submit a chat for scoring. Returns 8 dimension scores.

**Headers:**
```
Authorization: Bearer <SCORE_API_KEY>
Content-Type: application/json
```

**Request body:**
```json
{
  "chat_id": "your-unique-id",
  "platform": "chatgpt",
  "turns": [
    { "role": "user",      "content": "Can you help me write a CV?", "turn_index": 0, "timestamp_ms": null },
    { "role": "assistant", "content": "Sure! Tell me about your background.", "turn_index": 1, "timestamp_ms": null },
    { "role": "user",      "content": "I have 2 years at a startup...", "turn_index": 2, "timestamp_ms": null }
  ]
}
```

| Field | Type | Notes |
|---|---|---|
| `chat_id` | string (optional) | Your ID — echoed back in the response for correlation |
| `platform` | `"chatgpt"` \| `"claude.ai"` \| `"gemini"` | Platform the chat came from |
| `turns` | array | Minimum 2 turns. `turn_index` starts at 0 and increments. |

**Response `200`** (arrives in 20–60 seconds):
```json
{
  "chat_id": "your-unique-id",
  "rubric_version": "0.2_highband_fix",
  "scored_at": "2026-05-27T10:00:00.000Z",
  "dimensions": {
    "AL":  { "delta":  1.2,  "band": "high",           "confidence": 0.85, "reasoning": "User asked AI to flag uncertain claims." },
    "PR":  { "delta": -0.8,  "band": "low",             "confidence": 0.78, "reasoning": "One-line vague prompt, no constraints given." },
    "AUI": { "delta":  0.3,  "band": "mid",             "confidence": 0.71, "reasoning": "Reasonable use of AI but no explicit rationale stated." },
    "EC":  { "delta":  null, "band": "not_applicable",  "confidence": 0,    "reasoning": "No AI factual claims to verify in this chat." },
    "CS":  { "delta":  1.0,  "band": "high",            "confidence": 0.80, "reasoning": "User adapted AI output to their own context." },
    "CD":  { "delta": -1.5,  "band": "low",             "confidence": 0.90, "reasoning": "Used AI only to confirm a preset conclusion." },
    "ES":  { "delta":  null, "band": "not_applicable",  "confidence": 0,    "reasoning": "No ethical content present in this chat." },
    "CA":  { "delta":  0.5,  "band": "mid",             "confidence": 0.75, "reasoning": "Mostly followed AI framing with one redirection." }
  }
}
```

**Score interpretation:**

| Field | What it means |
|---|---|
| `delta` | Raw signal for this chat: −2.0 (worst) to +2.0 (best). `null` = not applicable. |
| `band` | `low` / `mid` / `high` / `not_applicable` — derived from delta |
| `confidence` | How certain the scorer is: 0.0 (guessing) to 1.0 (certain) |
| `reasoning` | One sentence citing what in the chat caused this score |

**Portfolio score (0–10):** Average `delta` across many chats → apply `(mean_delta + 2) × 2.5`. Store `delta` per chat; compute the 0–10 score in your backend when displaying the portfolio.

**Error responses:**

```json
400  { "error": { "turns": ["Need at least 2 turns"] }, "code": "validation_error" }
401  { "error": "Unauthorized", "code": "auth_required" }
500  { "error": "...", "code": "scoring_error" }
```

---

## For the team building the extension + backend

You only need to interact with one endpoint: `POST /score`.

**What you send:** the raw turns from the user's ChatGPT / Claude.ai conversation.

**What you get back:** 8 dimension scores to store in your database and display in the UI.

**What you store per chat:**
- `chat_id` — your own ID to link scores to the chat
- `dimensions[dim].delta` — the raw signal (average many of these for the portfolio)
- `dimensions[dim].band` — the label to show users
- `rubric_version` — so you know which version scored this chat (important when rubric updates)

**You do NOT need to:**
- Know anything about how the scorer works internally
- Manage the Gemini API key
- Handle rubric files or calibration data

**Latency:** 20–60 seconds per chat. Submit the chat asynchronously after the conversation ends — do not block the user waiting for a score.

---

## Tech stack

| Layer | Technology |
|---|---|
| Language | TypeScript (strict) |
| Runtime | Node.js 20 LTS |
| Package manager | pnpm workspaces |
| API framework | Hono |
| Validation | Zod (all API inputs and outputs) |
| Scorer model | Gemini 2.5 Flash (thinking disabled) |
| Fallback model | Claude Sonnet (Anthropic SDK — available, not yet calibrated) |
| Database (Phase 2) | PostgreSQL 16+ |
| Queue (Phase 2) | BullMQ on Redis |
| Extension (Phase 3) | Chrome Manifest V3, React + Vite |

---

## Calibration baseline (Phase 1)

The judge accuracy is measured against 23 hand-scored reference chats.

| Metric | Value |
|---|---|
| Overall within-2-delta | 89.4% |
| Overall MAE | 1.030 |
| Model | Gemini 2.5 Flash |
| Rubric | v0.2_highband_fix |
| Prompt | holistic v5 |

Full calibration report: `calibration/reports/PHASE1_FINAL_HANDOFF.md`

---

## Running calibration

```bash
# Score all 23 calibration chats and print accuracy metrics
GEMINI_API_KEY=your_key pnpm --filter calibration run calibrate

# Dry run (no API calls — estimates token counts only)
pnpm --filter calibration run calibrate -- --dry-run
```

---

## Contributing

- All types live in `packages/schemas` — never redeclare them locally
- Validate every API input and output with Zod
- No `any` types — use `unknown` and narrow
- No `console.log` in production paths
- Tests live next to source: `judge.ts` ↔ `judge.test.ts`
- Read `SYNERGY_PORTFOLIO_SPEC.md` before making any architectural decision
- Read `docs/decisions/` for why things are the way they are

---

## License

Private — Sangillence. Not for public distribution.
