# CSL Emergence Scanner Specification

Phase: v3.2 Phase 1.4  
Status: specification only, not runtime code  
Claim rung: MEASURABLE as an emergence indicator after judge ICC certification; never proof of above-baseline synergy without the retention/transfer probe.

## Purpose

The emergence scanner detects discrete exchange windows where the dyad produces a formulation neither party was independently approaching. It is a sequence scanner, not a per-turn score.

An event exists only when all three conditions hold:

1. Bilateral novelty.
2. Fused dependency.
3. Reframing trace.

Candidates that clear all three tests are then passed to a judge for confirmation.

## Scope

Emergence is only valid at ACF levels `C4` and `C6`.

Do not score emergence at `C1` or `C2`. Those levels are structurally human-checks-AI acts and cannot establish fusion.

Adoption-only windows produce zero events. Persistence-only windows produce zero events.

## Window Definition

Anchor each scan window on an AI turn `A_t`.

The candidate response span is:

- the immediately following human turn `H_t+1`; plus
- up to the next two human turns if they remain in the same local topic and occur before a clear topic pivot.

Maximum window size:

- one anchor AI turn;
- one to three human turns;
- intervening AI turns may be included as context but are not counted as human injection.

Stop the window early when:

- the user changes task/topic;
- a new explicit request starts a separate thread;
- three human turns have been inspected;
- the session ends.

This keeps the scan local enough to preserve causal adjacency while allowing short actualization loops to close.

## Centroid Computation

Embeddings are computed over content-bearing turn text after the same minimization and redaction rules used elsewhere in the pipeline.

For a candidate window:

- `human_new`: embedding centroid of the human turns inside the response span.
- `human_prior_centroid`: centroid of the previous human content turns before the window, using up to the last 5 human turns in the same session.
- `ai_prior_centroid`: centroid of AI content before the response span, using the anchor `A_t` plus up to the previous 4 AI turns.

Centroids are arithmetic means of L2-normalized turn embeddings, normalized again after averaging.

If either prior centroid cannot be formed because there is no prior content, the bilateral novelty test is `INSUFFICIENT_SAMPLE` for that window and no candidate is emitted.

Semantic distance uses cosine distance:

```text
semantic_distance(x, y) = 1 - cosine_similarity(x, y)
```

The threshold for HIGH distance must come from a frozen configuration artifact. The scanner must fail loudly if the threshold artifact is missing. It must not compute or refit cut points at runtime.

## Condition 1: Bilateral Novelty

The human-new formulation must be far from both prior sources:

```text
semantic_distance(human_new, human_prior_centroid) >= novelty_high
and
semantic_distance(human_new, ai_prior_centroid) >= novelty_high
```

Interpretation:

- close to AI prior: adoption, not emergence;
- close to human prior: persistence, not emergence;
- far from both: possible emergence.

## Condition 2: Fused Dependency

The same window must show both:

- uptake: the human response materially uses the immediately preceding AI output;
- injection: the human adds content, constraints, or framing not derivable from the prior AI turns.

Operational signals:

- uptake can use low attribution gap to the anchor AI turn, explicit reference, or dependency on an AI-provided structure;
- injection can use CD/CS exogenous-content signatures, constraint injection, external context, or human-supplied criteria;
- both signals must occur in the same window.

Uptake only is adoption. Injection only is the human's own idea. Both fused is a candidate.

## Condition 3: Reframing Trace

The actualization loop must close on a reframing, not a refinement.

Valid traces include:

- the human connects the AI material to a new frame and states a new implication;
- the human supplies a constraint that causes the AI to generate the missing structure, then confirms or uses that structure;
- the exchange changes the problem representation, not merely wording, formatting, or detail level.

Invalid traces include:

- polishing the AI output;
- accepting or summarizing the AI output;
- restating the human's earlier idea;
- adding volume without changing the frame.

## Candidate To Judge Handoff

Only windows satisfying all three conditions become judge candidates.

The judge receives a minimized packet:

- window id;
- turn range;
- anchor AI turn summary;
- human response span summary;
- human prior centroid summary terms;
- AI prior centroid summary terms;
- quantitative signal values for novelty, uptake, injection, and reframing;
- proposed ACF level: `C4` or `C6`;
- proposed trigger type: `HI`, `AR`, or `BI`.

The judge returns structured output only:

```text
{
  "judge_confirmed": true | false,
  "acf_level": "C4" | "C6",
  "trigger_type": "HI" | "AR" | "BI",
  "confirmation": "explicit" | "behavioral" | "none",
  "direction_change": true | false,
  "output_delta": true | false
}
```

No free-text rationale is persisted in the event log.

## Event Schema

Confirmed events are emitted as:

```text
{
  "ev_id": string,
  "turn_range": [int, int],
  "acf_level": "C4" | "C6",
  "trigger_type": "HI" | "AR" | "BI",
  "confirmation": "explicit" | "behavioral" | "none",
  "direction_change": bool,
  "output_delta": bool,
  "judge_confirmed": bool
}
```

`judge_confirmed` must be true for reportable emergence events. Unconfirmed candidates may be retained only in an audit/debug artifact, not in the user-facing emergence count.

## Reporting Language

Reports must include the caveat:

```text
This session contained N emergence events: moments where the exchange produced formulations neither party was approaching independently. These indicate genuine complementarity. They are not proof of performance gain above what you could achieve alone, which requires the unaided follow-up task to establish.
```

## Acceptance Criteria

- The scanner uses local AI-anchored windows with at most three following human turns.
- Bilateral novelty uses both human-prior and AI-prior centroids.
- Uptake and injection must appear in the same window.
- Reframing is required; refinement is insufficient.
- Adoption-only fixtures emit zero events.
- Persistence-only fixtures emit zero events.
- Genuine bilateral-fusion fixtures emit one `BI` event at `C4` or `C6`.
- No event is emitted at `C1` or `C2`.
- Candidate windows are judge-confirmed before becoming reportable events.

