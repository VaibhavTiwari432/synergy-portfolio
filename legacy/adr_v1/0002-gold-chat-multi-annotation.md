# ADR 0002 — GoldChat Multi-Annotation Structure

**Status:** Accepted
**Date:** 2026-05-20
**Deciders:** Sangillence (owner), Claude Code (implementation)

---

## Context

Phase 0 requires 20 hand-scored gold-standard chat transcripts. The calibration harness compares judge output against human scores to compute band-match accuracy and Cohen's κ (§12).

The initial schema had `GoldChat` as a single-scorer object:

```typescript
// original (replaced)
export interface GoldChat {
  human_scores: Record<DimensionCode, number>;  // integer 1–5
  scorer_id: string;
  scorer_notes: Record<DimensionCode, string>;
  scored_at: string;
  ...
}
```

Two problems:

1. **Single scorer blocks IRR analysis.** Inter-rater reliability (Cohen's κ across human scorers) requires at least two independent annotations per chat. The original schema had no place to put a second annotation without a migration.
2. **Integer scores misalign with the delta-band schema.** With ADR 0001, judge output is now band-level (low/mid/high/not_applicable). Comparing integer human scores against band-derived judge output requires a conversion step that loses information and adds a potential source of calibration error.

## Decision

Restructure `GoldChat` to hold a list of annotations:

```typescript
export interface GoldChatAnnotation {
  scorer_id: string;
  bands: Record<DimensionCode, "low" | "mid" | "high" | "not_applicable">;
  notes: Record<DimensionCode, string>;
  scored_at: string;
}

export interface GoldChat {
  id: string;
  platform: "chatgpt" | "claude.ai";
  turns: Turn[];
  annotations: GoldChatAnnotation[];  // length >= 1
  rubric_version: string;
}
```

Human scorers assign band labels directly (not integers). This aligns the gold standard format with judge output format, making calibration comparison a direct equality check (`judge_band == annotation_band`) rather than a conversion.

The `annotations` array supports single-scorer Phase 0 work (length = 1) and multi-scorer IRR analysis without any schema migration.

## Consequences

- Phase 0 scoring workflow: scorer fills in one `GoldChatAnnotation` per chat. The array always has exactly one entry during Phase 0.
- When a second human scorer is added, their annotation is appended to the same array. No schema change, no migration.
- Calibration computes consensus band as majority vote across `annotations[*].bands[dim]`, ties broken toward "mid". With one annotation, consensus equals that annotation's bands.
- Cohen's κ between human scorers is computed across `annotations` where `annotations.length >= 2`. With one scorer, IRR is not computable and the calibration report must say so explicitly.
- Integer scores are not stored. If future analysis requires numeric human scores, they should go into annotation `notes` as free text — they are not a structured field.

## Alternatives considered

**Keep single scorer, add second scorer as a separate parallel field.** Creates a fixed maximum of 2 scorers and requires code changes for a third. Rejected.

**Separate table/file per scorer.** Disconnects annotations from their source chat, complicates loading logic. Rejected.

**Keep integer scores alongside band labels.** Adds complexity; the information gain is small given that rubric anchors are written at band granularity and human scorers calibrate to bands, not integers. Rejected.
