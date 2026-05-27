# Future: Cognitive Debt Detection Layer

**Status: DO NOT BUILD YET.**  
Touch this file only after Phase 3 (Chrome extension) is complete and the platform has real session data.

---

## What this is

A research layer built on top of the synergy scoring system. Phase 1–3 measure *how well a candidate collaborates with AI*. This layer measures *whether that collaboration builds or erodes the candidate's cognitive capacity*.

Defined use case: a candidate receives a problem statement inside a closed assessment environment, uses an AI chatbot to solve it, and submits a final answer. The platform captures the interaction. This layer tells you whether the candidate learned something or outsourced their thinking.

---

## The two-layer architecture

```
Layer 1 (built): Synergy score
  — 8 dimensions measuring interaction process quality
  — Behavioral fingerprint of the session
  — Already in production after Phase 3

Layer 2 (this file): Cognitive debt signal
  — Did the candidate build a mental model, or just extract outputs?
  — Requires: problem_statement + candidate_submission + session transcript
  — Becomes statistically meaningful at ~500 sessions
```

---

## Detection signals

### Signal 1 — Query type ratio (computable from existing data)

Classify each candidate turn as:
- **Generative**: building understanding — "why does this work?", "how does X relate to Y?", "what if we changed this assumption?"
- **Extractive**: getting outputs — "rewrite this", "fix this", "now do the next step"

Ratio of generative to extractive across a session is a lightweight learning proxy. No additional API calls needed — works on the conversation transcript already captured.

### Signal 2 — Verification behavior (computable from existing data)

Count turns where the candidate checks, cross-references, or questions AI output — even when the AI was technically correct. Verification independent of error presence is a metacognitive marker. Distinct from EC (Error Catching), which only fires when the AI is wrong.

### Signal 3 — Answer attribution (requires candidate_submission)

Compare the candidate's final submitted answer to the AI's last substantive response. High lexical overlap with low candidate-injected reasoning = transcribed, not synthesized. Does not require a gold answer — only the conversation and the submission.

### Signal 4 — Follow-up probe (requires assessment platform design)

After session closes, before results are shown: ask the candidate 3 short comprehension questions about concepts that appeared in the AI's explanations during their session. If they absorbed the AI's output, they answer correctly. If they passed it through, they cannot. Low-noise, resistant to gaming (candidate does not know which concepts will be probed).

---

## Strongest early cognitive debt flag

Low CS + Low CA + Low CD together in a session is the prototype flag, detectable from Layer 1 data alone. This cluster means:
- Not integrating AI output into own understanding (CS)
- Being steered by AI rather than steering (CA)
- Not questioning AI's framing of the problem (CD)

This is actionable before Layer 2 is built.

---

## Archetype 2×2 (research framing)

|  | High Synergy | Low Synergy |
|--|-------------|-------------|
| **Learning** | Cognitive Amplifier — uses AI to think better | Independent Thinker — learns despite poor AI use |
| **Not Learning** | Skilled Outsourcer — efficient but not growing | Passive Consumer — high cognitive debt, high risk |

The **Passive Consumer** quadrant is the primary research target. The **Skilled Outsourcer** is the counterintuitive risk — good synergy scores masking dependency. Both require longitudinal data to identify reliably.

---

## What makes this a trajectory problem, not a snapshot problem

A single session score is ambiguous. A low-synergy candidate could be a beginner. A high-synergy candidate could be a skilled outsourcer. Cognitive debt is only visible in the *slope* of synergy scores across multiple sessions on the same candidate:
- Improving slope: building capability
- Flat or declining slope: accumulating dependency

Minimum viable dataset for trajectory analysis: 3+ sessions per candidate, same problem complexity tier.

---

## Schema additions needed (flag for Phase 2 API design)

Before Phase 2 locks the DB schema, add these fields even if unpopulated:

```typescript
// On session/chat record
problem_statement_id: string | null
candidate_submission: string | null   // final answer text
session_number: number                // nth session for this candidate
```

Adding these costs nothing now. Not adding them requires a migration when Layer 2 begins.

---

## Important constraints

**Do not show synergy scores to candidates during the session.** Silent scoring only. If candidates can see their score in real time, the measurement changes the behavior being measured.

**Normalize by problem complexity.** Tag each problem statement with a complexity level before computing benchmarks. Low PR on a trivial task and low PR on an expert-level task are not the same signal. Without this, benchmark distributions are uninterpretable.

**The closed environment is load-bearing.** The learning signal only works if the problem statement is known, the AI tool is controlled, and the final submission is captured. Open-ended scraping of public chat sessions cannot support Layer 2 — too many confounds.

---

## Research hypothesis (to validate with data)

> Candidates whose sessions show a high generative/extractive query ratio, sustained verification behavior, and improving synergy trajectory across sessions will demonstrate significantly higher post-session comprehension (follow-up probe scores) than candidates with low generative ratio and flat/declining synergy trajectory — independent of final answer correctness.

This is testable once the platform has ~500 sessions with follow-up probes collected.
