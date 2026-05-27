/**
 * gen_v0.2.ts — one-shot script to produce rubric_v0.2_highband_fix.json
 * Copies rubric_v0.1.json verbatim for 21 anchors; replaces AL/PR/CS high-band
 * anchors (indices 2, 5, 14) with B.1 audited versions.
 * Run: npx tsx packages/rubric/gen_v0.2.ts
 */
import { readFileSync, writeFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const raw = readFileSync(join(__dirname, "rubric_v0.1.json"), "utf8");
const anchors: unknown[] = JSON.parse(raw);

if (anchors.length !== 24) throw new Error(`Expected 24 anchors, got ${anchors.length}`);

// ── AL high (index 2) ─────────────────────────────────────────────────────────
anchors[2] = {
  dimension: "AL",
  band: "high",
  label: "Accurate, task-calibrated model of AI capability",
  description:
    "The user demonstrates an accurate mental model of what AI can and cannot do in the specific task context, and acts on that model deliberately. The form this takes depends on task type: factual tasks show trust differentiation and uncertainty elicitation; strategic or craft tasks show deliberate role-scoping with bounded delegation; philosophical or dialectical tasks show accurate calibration of AI as a reasoning partner rather than a fact oracle. What is common across all forms is that the user knows what this AI can usefully contribute in this context and structures their engagement accordingly — whether by eliciting calibrated uncertainty, assigning a precise operational role, or designing an interaction that plays to AI strengths without expecting it to resolve questions requiring ground-truth knowledge.",
  positive_signals: [
    "elicits calibrated uncertainty before using output in consequential work: asks AI to flag low-confidence claims, differentiates trust by domain (e.g. 'flag anything you are not confident about'), or explicitly routes factual lookups outside AI",
    "assigns AI a bounded role or operational scope that accurately reflects what AI can do in this task — specifying AI as a domain consultant or reviewer for a defined audience, then evaluates output against that scoped capability rather than treating it as authoritative; orchestrating multiple AI tools for different sub-tasks is also a high-band signal",
    "in philosophical, Socratic, or open-ended inquiry tasks, treats AI accurately as a reasoning partner — asks for dialectical reasoning, structured debate, hypothesis stress-testing, or argument critique — without expecting AI to provide verified facts or serve as moral authority; the questions themselves demonstrate the user knows what type of cognitive work AI can and cannot do",
  ],
  negative_signals: [
    "treats all AI output as equally reliable regardless of claim type, domain risk, or task context",
  ],
  example_chat_snippet:
    "'ACT AS: A Senior Hiring Consultant for CERN. Review this CV for the Administrative Student Programme. Flag any section where the framing might weaken the application.' (deliberate bounded role assignment) — OR — 'Let's play a game: ask me 5 questions one by one and we will identify ethical ways of interacting with an AI.' (accurate calibration of AI as a dialectical reasoning partner, not a factual authority, for a philosophical task)",
  synthetic: true,
};

// ── PR high (index 5) ─────────────────────────────────────────────────────────
anchors[5] = {
  dimension: "PR",
  band: "high",
  label: "Systematically constructed or iteratively precise prompts",
  description:
    "High-band prompt reasoning is evident when the user reliably narrows the gap between AI output and their intended target. Three distinct behavioral patterns each constitute high-band PR: (A) upfront specification — explicit goal, format, constraints, audience, and optionally a role assignment or worked example so the AI's first response lands on-target; (B) iterative diagnostic precision — each refinement specifically names what is wrong or missing in the current output rather than expressing generic dissatisfaction, demonstrating the user has a clear internal target they are converging toward; or (C) structural conversation design — the user defines the interaction format itself to elicit a specific type of reasoning or output sequence from the AI. Any single one of these patterns sustained across the conversation constitutes high-band PR.",
  positive_signals: [
    "upfront construction: provides explicit role, worked example, rejection criteria, or chain-of-thought instruction before the AI's first response; AI's first substantive output requires minimal redirection",
    "iterative diagnostic precision: each correction or refinement identifies a specific gap — naming the constraint, context, or quality dimension that is wrong or missing — rather than generic displeasure; user demonstrably has a target and is closing toward it",
    "structural conversation design: user defines the interaction format to constrain how the AI should reason or respond — e.g. requesting questions one by one, specifying that strongest counterarguments come before recommendations, or framing the exchange as a structured game or evaluation exercise",
  ],
  negative_signals: [
    "vague or under-constrained requests with no attempt to narrow the gap",
    "generic dissatisfaction ('make it better', 'this is wrong') with no identification of what specifically needs to change",
  ],
  example_chat_snippet:
    "'You're reviewing a data model for a product manager with no SQL background. Explain this schema in plain English. Max 4 sentences. Avoid jargon. If you use a technical term, define it inline.' (upfront construction) — OR — 'Let's play a game: ask me 5 questions one by one and we will identify ethical ways of interacting with an AI.' (structural conversation design specifying format, sequence, and intellectual scope)",
  synthetic: true,
};

// ── CS high (index 14) ────────────────────────────────────────────────────────
anchors[14] = {
  dimension: "CS",
  band: "high",
  label: "Deliberate integration — explicit or visible in conversation arc",
  description:
    "The user treats AI output as raw material and synthesizes it with their own context, constraints, and prior reasoning. High-band CS does not require explicit narration of the synthesis process. Synthesis is also evident when the user's questions progressively build their own analytical framework beyond what AI suggested; when the user introduces new constraints or context that reshape AI's proposed direction; or when specific follow-up demonstrates that AI output has been processed through the user's own domain understanding rather than merely collected. The key signal is that the user's own knowledge is visibly shaping how AI output is used — not that they verbally describe the integration.",
  positive_signals: [
    "explicit synthesis narration: user names what they are keeping, adapting, or discarding from AI output and why — linked to a constraint, context, or preference the AI did not have (e.g. 'your structure is right but our team is async, so I am rewriting the cadence sections')",
    "progressive framework development: the user's analytical position or framing evolves across the conversation in a direction not suggested by the AI; later questions or conclusions integrate earlier AI output into a more refined position — the final framing is the user's own, built with AI as raw material, not borrowed from AI",
    "domain-knowledge engagement: specific follow-up, correction, or constraint injection that could only come from someone who integrated AI output with their own knowledge — demonstrating synthesis through the quality and specificity of what comes next, not only through explicit narration",
  ],
  negative_signals: [
    "AI output goes directly to use without visible modification, adaptation, or follow-up that builds on it in a new direction",
  ],
  example_chat_snippet:
    "'That structure works, but our team uses async updates not standups, so I am keeping your section headers but rewriting the cadence assumptions throughout.' (explicit synthesis) — OR — 'I am not understanding what you did in Test: buy free... It kills everything because of zero probability.' (domain-knowledge engagement: student catches the zero-probability failure by processing AI output through own ML knowledge — high-synthesis signal visible from the specificity of what the student says next, not from explicit keep/discard language)",
  synthetic: true,
};

// ── Verify other anchors unchanged ────────────────────────────────────────────
const v01 = JSON.parse(raw) as Record<string, unknown>[];
const changed = anchors.filter((_, i) =>
  JSON.stringify(anchors[i]) !== JSON.stringify(v01[i])
);
console.log(`Changed anchors (should be 3): ${changed.length}`);
changed.forEach((a) => {
  const anchor = a as Record<string, unknown>;
  console.log(`  ${anchor.dimension} ${anchor.band}`);
});

const out = JSON.stringify(anchors, null, 2);
writeFileSync(join(__dirname, "rubric_v0.2_highband_fix.json"), out, "utf8");
console.log("Written: packages/rubric/rubric_v0.2_highband_fix.json");
