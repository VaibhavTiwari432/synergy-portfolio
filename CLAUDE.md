# Synergy Portfolio Analyzer — CLAUDE.md

This file is read by Claude Code at the start of every session. Treat it as authoritative.

## What this project is

A browser-extension-based system that observes a user's chats with ChatGPT or Claude.ai and silently scores their AI-collaboration quality across 8 dimensions (AL, PR, AUI, EC, CS, CD, ES, CA). Scores accumulate into a per-user portfolio with archetype classification and targeted drills.

Phase II of the broader **Sangillence Insight System (SIS)**. Phase I was the SOBO'25 cognitive test (already shipped). This is the live-chat synergy layer.

## The spec is the source of truth

**Read `SYNERGY_PORTFOLIO_SPEC.md` at the start of every session.** It contains:

- All 8 dimensional definitions and rubric anchors (§4)
- Canonical TypeScript schemas for TaskFrame, JudgeOutput, Portfolio, RubricAnchor (§3)
- Architecture diagram (§5)
- Judge prompt template (§6)
- API contracts (§7)
- Sequential build plan with exit criteria per phase (§10)

If you can't find an answer in the spec, **do not invent one** — surface it to the human and ask.

## Decision protocol

The spec uses three markers. Honor them strictly:

- `LOCKED:` — final decision. Do not propose changing it without explicit human instruction.
- `OPEN:` — pending human decision. Do not invent an answer. Halt and ask.
- `EVIDENCE:` — real-world anchor. Keep it visible in implementation so we can audit later.

If you find yourself about to guess on an `OPEN:` item, stop and ask in chat instead.

## Build phases — current status

We are currently in **Phase 0: Calibration Foundation**. The next deliverables, in order:

1. `rubric_v0.1.json` — versioned JSON file derived from spec §4 (all 24 anchors: 8 dims × 3 bands)
2. 20 hand-scored chat transcripts (`gold_standard/*.json`) — human work, not code
3. `packages/schemas` — TypeScript types from spec §3 with Zod runtime validators
4. `gold_standard_loader.ts` — utility to load gold chats

**Do not proceed to Phase 1 (judge service) before Phase 0 deliverables exist.** Even if it seems faster to start coding the judge first, calibration without a gold standard is unverifiable.

## Tech stack (locked unless human reverses)

- **Language:** TypeScript everywhere (backend, extension, scripts)
- **Runtime:** Node.js 20 LTS or newer
- **Package manager:** pnpm (workspaces for monorepo)
- **Validation:** Zod for all schemas — every JSON I/O must be validated, never raw-trusted
- **Database:** PostgreSQL 16+ (use Supabase for hosted, Docker for local dev)
- **Queue:** BullMQ on Redis for chunk processing
- **API framework:** Hono (lightweight, runs on Node and edge) — or Express if Hono unfamiliar
- **LLM SDK:** `@anthropic-ai/sdk` for Claude judge calls; `openai` package if we test GPT judge
- **Extension:** Chrome Manifest V3, React + Vite for sidebar UI
- **Testing:** Vitest for unit, Playwright for extension E2E

## Repo layout (target — build incrementally)

```
synergy-portfolio/
├── CLAUDE.md                           # this file
├── SYNERGY_PORTFOLIO_SPEC.md           # canonical spec
├── .claudeignore
├── pnpm-workspace.yaml
├── package.json
├── apps/
│   ├── api/                            # Hono API server
│   ├── judge/                          # judge service worker
│   └── extension/                      # Chrome extension
├── packages/
│   ├── schemas/                        # Zod schemas — single source of types
│   ├── rubric/                         # versioned rubric JSON + loader
│   └── shared/                         # shared utils
├── gold_standard/                      # hand-scored chats (not code, but versioned)
│   ├── README.md
│   └── chats/
├── calibration/                        # scripts to run judge against gold standard
│   └── reports/
└── docs/
    └── decisions/                      # ADRs for every LOCKED decision
```

## Coding conventions

- **No `any` types.** If you need to type something you don't know, use `unknown` and narrow it.
- **No console.log in production paths.** Use a real logger (pino).
- **No top-level await in library code.** Only in scripts.
- **Validate at boundaries.** Every API input, every LLM output, every DB row coming back gets Zod-validated.
- **One function, one job.** If a function name needs "And" in it, split it.
- **Tests live next to source:** `judge.ts` ↔ `judge.test.ts`.

## What NOT to do

- **Don't add features not in the spec.** If a feature seems useful but isn't in `SYNERGY_PORTFOLIO_SPEC.md`, propose it in chat and wait for explicit approval before building.
- **Don't fabricate calibration numbers.** When the spec mentions thresholds (e.g. MAE ≤ 1.5, IRR ≥ 0.6), those are targets, not claims. Don't write code that "demonstrates" hitting them without running real evaluation.
- **Don't call paid LLM APIs without explicit human approval per session.** The first time per session, ask: "this will call the Anthropic API and cost approx ~$X — proceed?" Cache aggressively.
- **Don't pretend to know what's in the spec without re-reading it.** If a session is long, re-read the relevant section before making decisions about it.
- **When proposing a schema change, always quote the existing definition verbatim first.** "I think the current schema is X" is not acceptable — open the file and quote it. Paraphrase-by-default is how hallucinated definitions slip through.
- **When the human describes spec content from memory, do not assume their memory is accurate.** Quote the file and compare. If they disagree, flag it and ask which is correct before proceeding. This applies symmetrically — the spec author can misremember their own spec.
- **Don't write the Chrome extension scraper before Phase 2 is complete.** Backend first, extension last — order matters because the backend's contract must stabilize before the scraper depends on it.

## Communication style

- Be honest about uncertainty. "I'm not sure whether to use X or Y because the spec doesn't say" is better than guessing.
- When you complete a task, summarize what changed and what's untested.
- When you hit something ambiguous, ask one focused question, not a list of five.
- Prefer plain prose over status emoji. This is a real-world project, not a demo.

## How to start a fresh session

When the human says "continue from where we left off," do this:

1. Read this file.
2. Read `SYNERGY_PORTFOLIO_SPEC.md` (full, not just sections).
3. Check `docs/decisions/` for any ADRs added since last session.
4. Run `git log --oneline -20` to see what's been done.
5. Then summarize: "Last commit was X. Spec says next deliverable is Y. Should I start there?"

Do not start coding until the human confirms.
