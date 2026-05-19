# SYNERGY_PORTFOLIO_SPEC.md
# Synergy Portfolio Analyzer — Technical Specification

**Version:** v0.1
**Status:** Draft
**Last updated:** 2026-05-20
**Owner:** Sangillence (sangillence@gmail.com)

---

> This document is the canonical source of truth. Every schema, rubric anchor, API contract, and architectural decision derives from here. When code and spec conflict, the spec wins unless a formal ADR in `docs/decisions/` explicitly overrides a specific item. `CLAUDE.md` governs how Claude Code sessions use this document — defer to it for process rules.

---

## §1 Purpose & Scope

The Synergy Portfolio Analyzer (SPA) is Phase II of the Sangillence Insight System (SIS). Phase I — the SOBO'25 cognitive test — established a baseline measure of individual cognitive style. SPA extends this into live AI-interaction behavior: it observes a user's chats with ChatGPT or Claude.ai, scores each conversation chunk across 8 dimensions of AI-collaboration quality, and accumulates those scores into a per-user portfolio.

The portfolio drives two downstream features:
1. **Archetype classification** — a qualitative label summarizing the user's collaboration style.
2. **Targeted drills** — exercises surfaced by the extension to strengthen low-scoring dimensions.

SPA does not modify or intercept AI responses. It is a passive observer that post-processes already-completed turns.

---

## §2 The 8 Dimensions

LOCKED: These 8 codes and full names are fixed for v0.1. Re-labeling requires a new spec version and a new rubric JSON.

| Code | Full Name | One-line definition |
|------|-----------|---------------------|
| AL | AI Literacy | Does the user understand what they're talking to? |
| PR | Prompt Reasoning | Quality of prompt construction per turn. |
| AUI | Augmentation Instinct | Timing — when the user reaches for AI vs. handles solo. |
| EC | Error Correction | Catching AI mistakes, hallucinations, logical traps. |
| CS | Contextual Synthesis | Weaving AI output with own context, constraints, prior reasoning. |
| CD | Creative Divergence | Using AI to widen the option space vs. confirm preset conclusions. |
| ES | Ethics Sensitivity | Awareness of bias, harm, privacy, attribution, stakeholder impact. |
| CA | Collaborative Agency | Staying in the driver's seat — pushback, framing, ownership of decisions. |

Each dimension is assessed by the judge as a real-valued delta in [−2.0, +2.0]. Band (low / mid / high) is derived from delta by threshold — see §3 `DimensionScore`. For calibration, human scorers use band labels directly rather than numeric values.

---

## §3 Canonical Schemas (TypeScript)

These are the authoritative type definitions. `packages/schemas` must export both the TypeScript type and a Zod schema for each. All other packages import from `@synergy/schemas` — never redeclare types locally.

§3 holds TypeScript type declarations only. The corresponding Zod runtime schemas are the Phase 0 deliverable in `packages/schemas/`, kept in sync with these types via round-trip tests. The two must not diverge.

```typescript
// Dimension code union — used everywhere scores appear
export type DimensionCode = "AL" | "PR" | "AUI" | "EC" | "CS" | "CD" | "ES" | "CA";

export const DIMENSION_CODES: readonly DimensionCode[] = [
  "AL", "PR", "AUI", "EC", "CS", "CD", "ES", "CA"
] as const;

// Band thresholds used server-side to derive band from delta.
// Changing these values requires a new rubric version.
// See ADR docs/decisions/0001-delta-band-encoding.md for rationale.
export const BAND_THRESHOLDS = {
  LOW_MAX: -0.67,   // delta <= LOW_MAX  → "low"
  HIGH_MIN: +0.67,  // delta >= HIGH_MIN → "high"
                    // otherwise         → "mid"
} as const;

// Minimum applicable frames before archetype_confidence is populated.
// OPEN: this threshold may need adjustment after calibration. See §11, item 6.
export const MIN_FRAMES_FOR_ARCHETYPE = 10;

// A single scored band in the rubric — describes one band of one dimension.
// score_range is absent: the delta encoding uses real values, not integers.
export interface RubricAnchor {
  dimension: DimensionCode;
  band: "low" | "mid" | "high";  // string, consistent with DimensionScore.band
  label: string;                  // short human label, e.g. "Unanchored"
  description: string;            // 1–3 sentences describing this band
  positive_signals: string[];     // observable behaviors that indicate this band
  negative_signals: string[];     // observable behaviors that contradict this band
  example_chat_snippet: string;   // short illustrative example
  synthetic: boolean;             // true if constructed, false if from real data
}

// One turn in a conversation
export interface Turn {
  role: "user" | "assistant";
  content: string;
  turn_index: number;            // 0-based position in conversation
  timestamp_ms: number | null;   // epoch ms; null if platform did not expose it
}

// A chunk of conversation submitted for scoring
export interface TaskFrame {
  id: string;                    // UUID v4, assigned by API on receipt
  chat_id: string;               // platform-native conversation ID
  platform: "chatgpt" | "claude.ai";
  user_id: string;               // see §9
  turns: Turn[];                 // minimum 2 (at least 1 user + 1 assistant turn)
  chunk_index: number;           // 0-based; position of this chunk in the conversation
  captured_at: string;           // ISO 8601 UTC
  rubric_version: string;        // e.g. "0.1"
}

// Per-dimension judgment produced by the judge for one TaskFrame.
//
// delta is a real number in [-2.0, +2.0] representing this chunk's quality signal:
//   -2.0  worst observable behavior for this dimension
//    0.0  neutral / mid-band
//   +2.0  best observable behavior for this dimension
//   null  dimension is not_applicable for this conversation
//
// band is derived server-side from delta using BAND_THRESHOLDS:
//   delta <= LOW_MAX   → "low"
//   delta >= HIGH_MIN  → "high"
//   in between         → "mid"
//   delta null         → "not_applicable"
//
// The judge outputs delta only. band is never part of the judge's JSON output.
// It is computed and stored by the server at validation time.
export type DimensionScore = {
  delta: number | null;                    // -2.0 to +2.0; null = not_applicable
  band: "low" | "mid" | "high" | "not_applicable";  // derived from delta; not a judge output
  evidence_quote: string | null;           // verbatim excerpt from transcript; null when not_applicable
  evidence_turn_index: number | null;      // 0-based index into turns[]; null when not_applicable
  confidence: number;                      // 0..1; per-dimension judge confidence
  rationale: string;                       // one sentence citing observable evidence
};

// Judge output for one TaskFrame
export interface JudgeOutput {
  task_frame_id: string;
  judge_model: string;           // e.g. "claude-sonnet-4-6"
  judge_prompt_version: string;  // e.g. "0.1"
  rubric_version: string;
  dimensions: Record<DimensionCode, DimensionScore>;
  scored_at: string;             // ISO 8601 UTC
}

// Aggregated per-dimension score rolled up across all scored frames.
//
// Normalization: mean(delta) over applicable frames → range [-2, +2]
// Score on 0–10 scale: (mean_delta + 2) × 2.5
// Frames where delta is null (not_applicable) are excluded from the mean.
export type AggregatedScore = {
  score: number | null;               // 0..10; null when status !== "scored"
  status: "scored" | "not_applicable" | "insufficient_data";
  confidence: number;                 // 0..1; confidence-weighted mean of per-frame confidence
  sample_size: number;                // total frames judged
  applicable_sample_size: number;     // frames where delta was not null
  trend_7d: number | null;            // score delta over last 7 days; null when insufficient data
  last_evidence_quote: string | null; // most recent non-null evidence_quote
};

// Accumulated scores per user across all scored frames
export interface Portfolio {
  user_id: string;
  current_scores: Record<DimensionCode, AggregatedScore>;
  total_frames_scored: number;
  archetype: string | null;            // OPEN: archetype names TBD (see §11, item 2)
  archetype_confidence: number | null; // 0..1; null until MIN_FRAMES_FOR_ARCHETYPE applicable frames scored
  last_updated: string;                // ISO 8601 UTC
  rubric_version: string;
}

// A single human annotation of a gold-standard chat
export interface GoldChatAnnotation {
  scorer_id: string;
  bands: Record<DimensionCode, "low" | "mid" | "high" | "not_applicable">;
  notes: Record<DimensionCode, string>;  // one sentence of reasoning per dimension
  scored_at: string;                     // ISO 8601 UTC
}

// A hand-scored transcript used for calibration.
// annotations holds ≥1 human annotation. Multiple annotations enable inter-rater
// reliability analysis (Cohen's κ across scorers) without a schema migration.
export interface GoldChat {
  id: string;                    // short slug, e.g. "gc-001"
  platform: "chatgpt" | "claude.ai";
  turns: Turn[];
  annotations: GoldChatAnnotation[];  // length ≥ 1
  rubric_version: string;
}
```

LOCKED: Field names and types above are final for v0.1. Adding optional fields is allowed in a patch; removing or renaming requires a version bump.

---

## §4 Rubric Anchors

Each of the 8 dimensions has 3 scored bands: low, mid, and high. The full set of 24 anchors is encoded in `packages/rubric/rubric_v0.1.json` — the definitions below are the authoritative source for that file. All example snippets are synthetic.

---

### §4.1 AL — AI Literacy

*Does the user understand what they're talking to?*

**Band: low — Treats AI as oracle**
The user has no accurate model of what an LLM is or does. Asks it for live data, expects cross-session memory, or treats its output as verified fact without question.
- Positive signals: asks for current stock prices or real-time news as if AI has live access; expects memory of past sessions without providing context; cites AI output as fact in the same turn without verification
- Negative signals: acknowledges a knowledge cutoff; asks the AI to flag uncertain claims; notes the probabilistic nature of output
- Example (synthetic): "What's the latest on the court case? Just tell me the verdict." (asked as if the AI has live legal databases)

**Band: mid — Knows AI makes mistakes, doesn't work around it**
The user is aware that AI can be wrong and has a knowledge cutoff, but doesn't build that awareness into prompts. Verification happens after the fact if at all.
- Positive signals: tells someone "I'll double-check this"; knows about hallucination in the abstract; spot-checks in familiar domains
- Negative signals: designs prompts to elicit calibrated uncertainty; avoids delegating tasks AI reliably fails at
- Example (synthetic): User uses an AI-generated summary for a report but plans to "verify the numbers later." Does not ask AI to flag low-confidence claims.

**Band: high — Actively works around AI limitations in prompt design**
The user treats AI output as probabilistic and structures prompts accordingly — eliciting uncertainty, calibrating trust by domain, and avoiding tasks where AI error rate is high.
- Positive signals: "mark anything you're less than confident about with [?]"; uses AI for synthesis and generation, handles factual lookups elsewhere; assigns different trust levels to grammar help vs. medical claims
- Negative signals: treats all AI output as equally reliable
- Example (synthetic): "Draft a summary of this research — but flag any factual claim you're uncertain about so I can verify those separately before submitting."

---

### §4.2 PR — Prompt Reasoning

*Quality of prompt construction per turn.*

**Band: low — Unstructured requests**
Prompts are vague, missing constraints, and require the AI to guess scope, format, and success criteria. No examples, no audience, no rejection criteria.
- Positive signals: one-sentence requests with no context; "make this better," "help me with this"; accepts first output without comment on fit
- Negative signals: provides format, audience, word count, or a concrete example of the desired output
- Example (synthetic): "Can you improve my presentation?" (no topic, no audience, no length, no tone guidance)

**Band: mid — Partially constructed prompts**
Some constraints are provided but key dimensions are left open. Prompts produce usable but not optimal outputs.
- Positive signals: gives one constraint (tone, or length, or audience) but not others; specifies domain without goal
- Negative signals: fully specifies goal, format, constraints, and audience; or provides a worked example
- Example (synthetic): "Write a cold email for a software product. Keep it under 200 words." (no target persona, no product description, no call to action)

**Band: high — Systematically constructed prompts**
The user provides goal, constraints, format, audience, and — where helpful — a worked example or role assignment. First responses are consistently on-target.
- Positive signals: explicit role ("You are a senior engineer reviewing this for a non-technical audience"), worked example of desired output, stated rejection criteria, chain-of-thought elicitation for complex tasks
- Negative signals: vague or under-constrained requests
- Example (synthetic): "You're reviewing a data model for a product manager with no SQL background. Explain this schema in plain English: [schema]. Max 4 sentences. Avoid jargon. If you use a technical term, define it inline."

---

### §4.3 AUI — Augmentation Instinct

*Timing — when the user reaches for AI vs. handles solo.*

**Band: low — Undifferentiated delegation**
The user delegates everything to AI without distinguishing tasks by AI-appropriateness, or refuses AI help on tasks where it would clearly add value. No visible meta-reasoning about when AI should be involved.
- Positive signals: asks AI for irreducibly personal decisions ("should I take this job?"); delegates tasks requiring lived experience or moral judgment without qualification
- Negative signals: explicit reasoning about why this task is AI-appropriate; handles judgment calls solo while delegating synthesis
- Example (synthetic): "Should I break up with my partner? Here's the situation. What should I do?"

**Band: mid — Mostly appropriate, occasionally misses the line**
The user generally uses AI where it helps and handles high-stakes judgment calls solo, but doesn't articulate the delegation decision. Appropriateness is intuitive, not visible.
- Positive signals: sensible task allocation overall; occasional over-delegation in unfamiliar domains
- Negative signals: visible articulation of why this task is or isn't AI-appropriate
- Example (synthetic): User handles contract negotiation solo but uses AI to draft all communications, including one that requires careful diplomatic judgment they'd be better off owning.

**Band: high — Deliberate, visible augmentation reasoning**
The user shows explicit meta-reasoning about what to delegate to AI and what to handle solo. Routes tasks based on named criteria.
- Positive signals: "I'll have AI draft this but the framing decision is mine"; names which parts of a task are AI-appropriate vs. human-appropriate; separates generation (delegate) from evaluation (keep)
- Negative signals: no visible reasoning about task allocation
- Example (synthetic): "Help me research the options here — I want to understand the landscape. I'll make the final call myself since it involves stakeholders you don't have context on."

---

### §4.4 EC — Error Correction

*Catching AI mistakes, hallucinations, logical traps.*

**Band: low — No correction**
The user does not catch or address AI errors, factual mistakes, logical flaws, or misunderstood constraints. Errors propagate into the work.
- Positive signals: accepts outputs containing visible errors; does not re-read critically; takes AI output at face value
- Negative signals: explicitly identifies an error and asks for correction
- Example (synthetic): AI misidentifies a key concept; user quotes it back approvingly and builds on it.

**Band: mid — Reactive correction**
The user catches errors when they are obvious or personally familiar but does not actively hunt for them. Correction is incidental, not systematic.
- Positive signals: corrects errors in familiar domains; misses errors in unfamiliar ones
- Negative signals: runs systematic checks; asks AI to self-verify; tests claims against external sources
- Example (synthetic): User catches a date error in a domain they know well but misses a logical gap in unfamiliar territory.

**Band: high — Proactive correction**
The user treats AI output as a first draft requiring verification. Actively checks claims, asks the AI to self-verify, and corrects errors with explicit reasoning.
- Positive signals: "double-check this against X"; asks follow-up questions that probe the logic; cites specifically where and why the AI went wrong
- Negative signals: no checking behavior visible
- Example (synthetic): "You said X implies Y — I don't think that follows. Walk me through the step between them explicitly."

---

### §4.5 CS — Contextual Synthesis

*Weaving AI output with own context, constraints, prior reasoning.*

CS is about **content** — what comes out of the collaboration. The user integrates AI output with their own knowledge rather than treating AI output as a standalone deliverable. Distinguish from CA (stance): CS asks "what did the collaboration produce?", CA asks "who was driving?"

**Band: low — Passthrough — no synthesis**
The user takes AI output verbatim and uses it without filtering through their own context or constraints. AI output is the product.
- Positive signals: forwards AI output directly; no visible layering of own knowledge; output is "what AI said"
- Negative signals: explicitly adapts AI output to fit a constraint AI wasn't aware of; references prior reasoning when evaluating AI output
- Example (synthetic): User asks AI to write a team update email, receives it, and sends it without modification or review against what they actually know about the situation.

**Band: mid — Occasional filtering**
The user sometimes applies own context to modify or filter AI output, but integration is reactive rather than deliberate.
- Positive signals: adjusts AI output when it conflicts with something the user knows; adds own context when AI misses something obvious
- Negative signals: routinely and deliberately layers AI suggestions with own constraints before finalizing
- Example (synthetic): User asks AI for a project plan, notices the timeline ignores a known constraint, corrects that one item, but adopts the rest without checking against other known constraints.

**Band: high — Deliberate layering**
The user treats AI output as raw material and actively synthesizes it with own context, constraints, and prior reasoning. The final output is visibly the result of integration.
- Positive signals: "AI suggested X, but given Y [own constraint], I'm adapting it to Z"; references prior reasoning when evaluating new AI output; names which parts are being kept, modified, or discarded and why
- Negative signals: AI output goes directly to use without visible filtering
- Example (synthetic): "That structure works, but our team uses async updates not standups, so I'm keeping your section headers but rewriting the cadence assumptions throughout."

---

### §4.6 CD — Creative Divergence

*Using AI to widen the option space vs. confirm preset conclusions.*

**Band: low — Confirmatory use**
The user uses AI to validate or elaborate a predetermined conclusion. AI is treated as a "yes, and" machine. Rarely or never asks for alternatives or counterarguments.
- Positive signals: "I think X is right — can you explain why?"; asks for arguments supporting a position already held; dismisses AI suggestions that challenge the starting premise
- Negative signals: asks "what am I missing?"; requests counterarguments; acts on an AI suggestion that genuinely surprised them
- Example (synthetic): "I've decided to use PostgreSQL for this. Tell me why it's the right choice."

**Band: mid — Surface divergence**
The user occasionally asks for alternatives but selection tends to default back to the original direction. AI-generated options are enumerated but not genuinely recombined.
- Positive signals: "give me 3 options" but always picks the safest or most familiar one; asks for counterarguments but doesn't update based on them
- Negative signals: selects an option that genuinely surprised them; builds on an unexpected AI suggestion to reach somewhere new
- Example (synthetic): User asks for 3 approaches, gets them, says "I like option 1 best" — which was their original idea restated.

**Band: high — Active divergence and novel recombination**
The user explicitly uses AI to challenge assumptions, asks for perspectives they don't already hold, and recombines AI-generated ideas into directions not present in the original prompt. Willingness to follow an unexpected thread is visible.
- Positive signals: "what's the strongest argument against my approach?"; changes direction based on AI-surfaced information; asks "what would I be missing if I went with X?"
- High-band signal: novel recombination — user takes two AI-generated suggestions and synthesizes a third that neither contained. Merely asking "give me 3 options" and picking one does not reach this band.
- Negative signals: always returns to the original conclusion; never acts on a genuinely surprising AI output
- Example (synthetic): AI offers two structural options. User: "Neither is quite right, but combining the queue from option 1 with the validation approach from option 2 gives me something new." That synthesis — not merely choosing from offered options — is the high-band signal.

---

### §4.7 ES — Ethics Sensitivity

*Awareness of bias, harm, privacy, attribution, stakeholder impact.*

**Most conversations have no ethical occasion.** When no ethical content is present — no bias risk, no privacy concern, no harm vector, no attribution question — score this dimension `not_applicable`. A `not_applicable` result means there was nothing to observe, not that the user failed. A low score means ethical content was present and the user did not engage with it. Do not penalize ethically neutral conversations.

When ethical content IS present in the conversation:

**Band: low — No sensitivity when it matters**
Ethical dimensions are clearly present but the user doesn't notice or engage. Proceeds with potentially biased, harmful, or privacy-violating output without comment.
- Positive signals: asks AI to generate content about specific groups without requesting a bias check; shares identifying information about third parties without consideration; uses AI-generated content in contexts requiring attribution without noting AI involvement
- Negative signals: proactively raises an ethical concern; asks AI to check for bias or harmful implications
- Example (synthetic): User asks AI to generate performance review language for an employee, receives output with clearly gendered framing, and submits it without raising the issue.

**Band: mid — Notices obvious issues, misses subtle ones**
The user catches clear ethical problems (explicit offensive content, obvious privacy violations) but misses subtler ones (selection bias, stakeholder exclusion, indirect harms).
- Positive signals: flags overt bias or harm; approves content with less visible but present ethical issues
- Negative signals: surfaces a non-obvious ethical dimension unprompted
- Example (synthetic): User asks AI not to include a slur (catches obvious issue) but doesn't question whether the framing systematically disadvantages one demographic.

**Band: high — Proactive, non-obvious ethical engagement**
The user raises ethical considerations before being prompted — especially subtle ones. Treats ethics as a design constraint, not an afterthought.
- Positive signals: "before we finalize this, let's check if it could disadvantage any group"; explicitly names AI involvement when submitting AI-assisted work; asks "who does this affect who isn't in the room?"; considers second-order harms
- Negative signals: ethical engagement only in response to obvious red flags
- Example (synthetic): "This recommendation system will affect hiring decisions. Before we go further — what groups might it systematically under-recommend, and how would we detect that?"

---

### §4.8 CA — Collaborative Agency

*Staying in the driver's seat — pushback, framing, ownership of decisions.*

CA is about **stance** — who is driving the collaboration. Distinguish from CS (content): CA asks "who's driving?", CS asks "what came out of it?" A user can produce excellent synthesis (high CS) while passively following AI's framing (low CA).

**Band: low — Passive acceptance**
The user follows AI framing and conclusions without pushback. Lets AI set the agenda. Defers decisions to the AI.
- Positive signals: adopts AI's reframing of the problem without comment; asks "what should I choose?" and accepts the answer; does not push back when AI misunderstands the goal
- Negative signals: explicitly rejects AI framing and reinstates own; pushes back on a conclusion with reasoning
- Example (synthetic): User asks for help with a decision; AI subtly reframes the goal; user proceeds with AI's version rather than their own without noticing.

**Band: mid — Occasional agency**
The user takes back control when AI is clearly wrong or off-topic, but mostly follows AI lead. Agency is reactive rather than consistent.
- Positive signals: redirects when AI goes badly off-track; mostly accepts AI framing when misalignment is subtle
- Negative signals: consistently names and defends own framing even against subtle AI reframes
- Example (synthetic): User corrects AI when it answers a different question than was asked, but when AI shifts the framing slightly in a follow-up, user follows the shift without noticing.

**Band: high — Consistent, deliberate agency**
The user consistently maintains ownership of the problem framing, direction, and decisions. Pushes back with reasoning. Uses AI for input, not for verdicts.
- Positive signals: "that's not quite what I asked — let me restate the actual goal"; explicitly disagrees with AI conclusions and explains why; "I'll make the call here, but help me think through the tradeoffs first"; reframes AI output to fit own goals rather than adapting goals to AI output
- Negative signals: passive acceptance of AI framing; defers judgment to AI
- Example (synthetic): AI suggests a different approach. User: "I see why you'd go that direction, but the constraint you're not accounting for is [X]. Let's stay with my original framing."

---

## §5 Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  Browser (Chrome Extension — Manifest V3)                       │
│                                                                 │
│  ┌─────────────┐    ┌────────────────────────────────────────┐  │
│  │ Content     │    │ Sidebar UI (React + Vite)              │  │
│  │ Script      │───▶│ - Current portfolio scores             │  │
│  │ (scraper)   │    │ - Archetype label                      │  │
│  └──────┬──────┘    │ - Drill suggestions                    │  │
│         │           └────────────────────────────────────────┘  │
└─────────┼───────────────────────────────────────────────────────┘
          │ POST /api/v1/frames
          ▼
┌─────────────────────────────────────────────────────────────────┐
│  API Server (Hono on Node.js)                          apps/api  │
│  - Validates TaskFrame (Zod)                                    │
│  - Assigns frame ID                                             │
│  - Enqueues to BullMQ                                           │
│  - GET /api/v1/portfolio/:user_id                               │
└─────────────────────────┬───────────────────────────────────────┘
                          │ BullMQ (Redis)
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│  Judge Service Worker                                apps/judge  │
│  - Dequeues TaskFrame                                           │
│  - Builds judge prompt (§6)                                     │
│  - Calls Anthropic API (claude-sonnet-4-6 or opus)              │
│  - Validates JudgeOutput (Zod)                                  │
│  - Derives band from delta; stores DimensionScore               │
│  - Updates Portfolio (AggregatedScore per dimension)            │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│  PostgreSQL 16+                                                 │
│  Tables: task_frames, judge_outputs, portfolios                 │
│  (schema defined in §8)                                         │
└─────────────────────────────────────────────────────────────────┘
```

LOCKED: The extension is built last (Phase 3). The judge service (Phase 1) is built before the API (Phase 2). Order: schemas → rubric → judge → API → extension.

EVIDENCE: Manifest V3 is required by Chrome as of 2024. MV2 extensions are no longer accepted on the Web Store.

---

## §6 Judge Prompt Template

Version: 0.1. This template is used by `apps/judge`. The variable slots are noted with `{{double_braces}}`.

```
You are a calibrated scorer for the Synergy Portfolio Analyzer. Your job is to score one chunk
of a human-AI conversation across 8 dimensions of AI-collaboration quality.

## Rubric

{{rubric_text}}
(The full rubric_v0.1.json anchor descriptions for all 8 dimensions, injected at runtime.)

## Conversation to score

Platform: {{platform}}
Turns:
{{turns_formatted}}
(Each turn formatted as "[N] User: ..." or "[N] Assistant: ..." where N is the 0-based turn index.)

## Instructions

Score the HUMAN's behavior only. Do not score the AI's response quality.

For each dimension, produce a delta: a real number in [-2.0, +2.0] representing the quality
of the human's behavior on that dimension in these turns:

  -2.0  worst observable behavior for this dimension (clearly and strongly low-band)
  -1.0  low-band behavior, mild or partially mitigated
   0.0  neutral; mid-band behavior, or insufficient signal to favor either direction
  +1.0  high-band behavior, present but not sustained throughout
  +2.0  best observable behavior for this dimension (clearly and consistently high-band)

You may use any real value in [-2.0, +2.0]. Intermediate values (e.g. -1.4, +0.3) express
nuance between the anchor points above.

If there is no observable occasion for a dimension in these turns — most commonly for ES
(Ethics Sensitivity) when no ethical content is present — set delta to null.
null means "not_applicable": it is not a low score.

For each dimension also provide:
  evidence_quote       a verbatim excerpt from the turns supporting your delta,
                       or null if not_applicable
  evidence_turn_index  the 0-based turn index the quote comes from, or null if not_applicable
  confidence           your confidence in the delta (0.0 = guessing, 1.0 = certain)
  rationale            one sentence explaining the delta, citing specific evidence

Do not include a "band" field. Band is computed from delta by the server.

Respond with valid JSON matching this exact schema. No text outside the JSON.

{
  "dimensions": {
    "AL": {
      "delta": <float -2.0 to +2.0, or null>,
      "evidence_quote": <string or null>,
      "evidence_turn_index": <integer or null>,
      "confidence": <float 0.0-1.0>,
      "rationale": "<one sentence citing specific evidence>"
    },
    "PR": { ... },
    "AUI": { ... },
    "EC": { ... },
    "CS": { ... },
    "CD": { ... },
    "ES": { ... },
    "CA": { ... }
  }
}
```

OPEN: Two-pass EC scoring — there is an argument that EC can only be scored accurately if the judge has seen the full conversation (to know whether an error was made and whether the user later caught it). A second-pass prompt that receives the full conversation plus first-pass scores and re-scores only EC is under consideration. Decision required before Phase 1 implementation. (See §11, item 3.)

---

## §7 API Contracts

Base URL: `http://localhost:3000` (development) / `https://api.synergy.sangillence.com` (production, TBD).

All endpoints accept and return `application/json`. All request bodies are validated with Zod on the server. Error responses use the shape `{ "error": string, "code": string }`.

### POST /api/v1/frames

Submit a TaskFrame for scoring.

**Request body:** `TaskFrame` (without `id` — the API assigns it).

**Response 202:**
```json
{
  "frame_id": "uuid-v4-string",
  "status": "queued"
}
```

**Response 400:** Validation error.
**Response 429:** Rate limit exceeded (max 60 frames/minute per user).

---

### GET /api/v1/portfolio/:user_id

Retrieve the current portfolio for a user.

**Response 200:** `Portfolio`

**Response 404:** No portfolio exists for this user yet (fewer than 1 scored frame).

---

### GET /api/v1/frames/:frame_id/scores

Retrieve the JudgeOutput for a specific frame.

**Response 200:** `JudgeOutput`

**Response 202:** Frame is queued or in-progress, not yet scored. Body: `{ "status": "pending" | "processing" }`.

**Response 404:** Frame ID not found.

---

## §8 Database Schema

```sql
-- task_frames
CREATE TABLE task_frames (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  chat_id        TEXT NOT NULL,
  platform       TEXT NOT NULL CHECK (platform IN ('chatgpt', 'claude.ai')),
  user_id        TEXT NOT NULL,
  turns          JSONB NOT NULL,
  chunk_index    INTEGER NOT NULL,
  captured_at    TIMESTAMPTZ NOT NULL,
  rubric_version TEXT NOT NULL,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- judge_outputs
CREATE TABLE judge_outputs (
  id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  task_frame_id        UUID NOT NULL REFERENCES task_frames(id),
  judge_model          TEXT NOT NULL,
  judge_prompt_version TEXT NOT NULL,
  rubric_version       TEXT NOT NULL,
  dimensions           JSONB NOT NULL,  -- Record<DimensionCode, DimensionScore>
  scored_at            TIMESTAMPTZ NOT NULL,
  created_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- portfolios
CREATE TABLE portfolios (
  user_id              TEXT PRIMARY KEY,
  current_scores       JSONB NOT NULL,  -- Record<DimensionCode, AggregatedScore>
  total_frames_scored  INTEGER NOT NULL DEFAULT 0,
  archetype            TEXT,
  archetype_confidence NUMERIC(4,3),
  last_updated         TIMESTAMPTZ NOT NULL,
  rubric_version       TEXT NOT NULL
);
```

---

## §9 User Identity

OPEN: How to identify users across sessions is undecided. Three options:

1. **Anonymous local ID** — the extension generates a UUID on first install, stores it in `chrome.storage.local`. No login required. Cannot aggregate across devices or browsers.
2. **Supabase Auth** — users sign in with Google or email. Enables cross-device portfolio. Adds login friction.
3. **Hybrid** — anonymous by default, optional sign-in to merge portfolios.

Decision required before Phase 2 (API) implementation. Phase 0 and Phase 1 can use a hardcoded test user ID.

---

## §10 Build Phases & Exit Criteria

### Phase 0 — Calibration Foundation (CURRENT)

Deliverables:
1. `packages/rubric/rubric_v0.1.json` — all 24 rubric anchors, Zod-validated
2. 20 hand-scored gold standard chats in `gold_standard/chats/`
3. `packages/schemas` — Zod schemas for all types in §3, with Vitest tests
4. `calibration/gold_standard_loader.ts` — loads and validates gold chats

Exit criteria:
- All 24 rubric anchors are present in the JSON and pass schema validation
- 20 gold chats exist, each with at least one annotation covering all 8 dimensions
- `pnpm test` passes across all packages

Do not proceed to Phase 1 until all exit criteria are met.

---

### Phase 1 — Judge Service

Deliverables:
1. `apps/judge` — worker that scores TaskFrames using the Anthropic API
2. `calibration/run_calibration.ts` — script that runs the judge against gold standard and reports metrics per §12
3. Calibration report in `calibration/reports/`

Exit criteria:
- Judge achieves band-match accuracy ≥ 0.60 per dimension on gold standard
- Ordinal Cohen's κ ≥ 0.60 on at least 6 of 8 dimensions
- No judge call is made without explicit human approval per session (per `CLAUDE.md`)

---

### Phase 2 — API & Queue

Deliverables:
1. `apps/api` — Hono API server implementing §7 contracts
2. BullMQ queue wired between API and judge
3. PostgreSQL schema (§8) with migrations
4. Docker Compose for local dev (Postgres + Redis)

Exit criteria:
- Can submit a TaskFrame via POST, have it scored, retrieve JudgeOutput and Portfolio
- All endpoints validated with Zod; all DB rows validated on read
- Integration tests pass with real Postgres (no mocks)

---

### Phase 3 — Chrome Extension

Deliverables:
1. `apps/extension` — Chrome MV3 extension with content script scraper and React sidebar
2. Scraper works on chatgpt.com and claude.ai
3. Sidebar displays current portfolio scores and archetype

Exit criteria:
- End-to-end flow: open chatgpt.com, have a 4-turn conversation, see scores appear in sidebar within 30 seconds
- Playwright E2E tests pass
- Extension passes Chrome Web Store review checklist

---

### Phase 4 — Drills & Portfolio UI (future)

Not yet specified. Define in a future spec version.

---

## §11 Open Decisions

These items are marked `OPEN:` throughout the spec. They must be resolved by the human before the relevant phase begins. Do not invent answers.

| # | Item | Blocks | Notes |
|---|------|--------|-------|
| 1 | Judge model selection: `claude-sonnet-4-6` vs `claude-opus-4-7` | Phase 1 | Tradeoff: cost vs. accuracy. Sonnet is ~5× cheaper; Opus may score more reliably on edge cases. Recommend running a mini-calibration with both. |
| 2 | Archetype names and score thresholds | Phase 1 (portfolio output) | Need at least 4 archetypes with score profiles. Human must name and define them. |
| 3 | Two-pass EC scoring | Phase 1 (judge prompt) | See §6. Adds latency and cost; may improve EC accuracy significantly. |
| 4 | Chunking strategy | Phase 1 (frame extraction) | How many turns per TaskFrame? Fixed window (e.g. 6 turns)? Or goal-boundary detection? Short frames may miss context; long frames may dilute scores. |
| 5 | User identity approach | Phase 2 (API) | See §9. Options: anonymous local ID, Supabase Auth, or hybrid. |
| 6 | MIN_FRAMES_FOR_ARCHETYPE threshold | Phase 1 (portfolio output) | Currently set to 10 in §3 constants. May need adjustment based on judge reliability findings in calibration. If the judge scores reliably in fewer frames, 10 is too conservative; if scores are noisy, 10 may be too low. |

---

## §12 Calibration Targets

These are targets, not claims. Do not write code that "demonstrates" hitting them without running real evaluation on the gold standard.

**Consensus band** is computed at calibration time from `GoldChat.annotations` — it is not part of the canonical data model (§3) and has no corresponding type. For a chat with one annotation, consensus band equals that annotation's bands. For multiple annotations, consensus band is the majority vote per dimension; ties broken toward "mid" (the more conservative judgment).

**Primary metric — Band-match accuracy per dimension:**

```
numerator   = count(frames where judge_band == consensus_band
                    AND judge_band != "not_applicable"
                    AND consensus_band != "not_applicable")

denominator = count(frames where judge_band != "not_applicable"
                    OR  consensus_band != "not_applicable")

agreement(dim) = numerator / denominator
```

When `denominator = 0` for a dimension on a given chat (both judge and human agreed the dimension was not_applicable on every frame), `agreement(dim)` is **undefined** for that chat — it is excluded from the aggregate, not counted as zero. This is most likely to occur for ES on routine chats with no ethical content.

**Secondary metric — Ordinal Cohen's κ per dimension:**

Computed over the three scored bands (low / mid / high) using ordinal weights:
- Adjacent misclassification (low↔mid or mid↔high): weight 0.5
- Skipped misclassification (low↔high): weight 1.0

Frames where either judge or human marked a dimension as "not_applicable" are excluded from the κ computation.

**Tertiary metric — Not-applicable agreement:**

```
na_agreement(dim) =
  count(frames where judge NA status == human NA status)
  / count(all frames for that dimension)
```

**Confusion matrix per dimension:** one 3×3 matrix (low / mid / high on each axis) per dimension, rows = judge band, columns = consensus human band. Reported in `calibration/reports/` after each calibration run. Used to identify which dimensions the judge systematically over- or under-bands.

| Metric | Target | Scope |
|--------|--------|-------|
| Band-match accuracy | ≥ 0.60 per dimension | Applicable frames only; undefined when denominator = 0 |
| Ordinal Cohen's κ | ≥ 0.60 on ≥ 6 of 8 dimensions | Excludes not-applicable frames |
| Not-applicable agreement | ≥ 0.80 | Per dimension; primarily ES |

EVIDENCE: 60% exact band-match on a 3-class problem substantially exceeds random chance (33%). Human-human band agreement on rubric-based assessment typically runs 65–75% in the educational measurement literature. Ordinal Cohen's κ ≥ 0.60 follows the "substantial agreement" threshold from Landis & Koch (1977, Biometrics). The not-applicable agreement target of 0.80 is set higher than band-match because silently mis-flagging a scored dimension as not_applicable drops it from the portfolio without any visible error signal.

---

*End of SYNERGY_PORTFOLIO_SPEC.md v0.1*
