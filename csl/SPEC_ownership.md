# CSL Ownership Specification

Phase: v3.2 Phase 1.3  
Status: specification only, not runtime code  
Claim rung: MEASURABLE for displayed ownership after per-level ICC certification; genuine ownership remains DESIGNED until the retention probe validates it.

## Purpose

CSL ownership reports who visibly drove each ACF level during the session. It is a seven-level vector, never a session-level scalar.

The human side is a projection of the existing ARI `NeuronMatrix`. It must not re-run transcript extraction for human evidence. One human extraction feeds two aggregations:

1. ARI dimension scores.
2. CSL ACF-level foundation evidence.

The AI side is a separate displayed-contribution read over AI turns. It measures what the AI visibly retrieved, generated, structured, evaluated, or orchestrated at each ACF level.

## Inputs

Ownership is computed per ACF level `C1` through `C7`.

Required inputs:

- `human[level]`: `LevelEvidence` from `project_to_acf(matrix, crosswalk)`.
- `ai[level]`: AI displayed contribution strength from `extract_ai_contribution(chat, crosswalk)`.
- `cspc`: CSPC proxy state from the existing state channel.
- `status_enum`: the shared four-state reporting enum: `OK`, `NOT_APPLICABLE`, `INSUFFICIENT_SAMPLE`, `MEASUREMENT_SATURATED`.

`LevelEvidence` must carry:

- `control_strength`: weighted foundation-backed human evidence on `[0, 1]`.
- `n_eff`: effective contributing opportunities after non-applicable firings are removed.
- `firings`: the contributing neuron/opportunity records needed for bootstrap.
- `applicable_count`: count of opportunities where the ACF level actually arose.
- `ci`: optional precomputed interval; if absent, ownership derives it by bootstrap.

`CSPCState` must expose a precision factor `pi_s` on `(0, 1]` or enough fields to derive it from the existing precision-merge definition. The implementation must import the existing precision definition rather than redefine degraded state locally.

## Formula

For each level:

```text
human_weighted(level) = pi_s(level) * control_human(level)

human_ownership(level) =
    human_weighted(level)
    / (human_weighted(level) + AI_displayed(level))
```

When the denominator is zero, no ownership percentage is emitted. The result status is `NOT_APPLICABLE` if the level never arose, or `INSUFFICIENT_SAMPLE` if it arose but lacks enough evidence.

The AI complement for the same level is:

```text
ai_ownership(level) =
    AI_displayed(level)
    / (human_weighted(level) + AI_displayed(level))
```

These values are level-local contrasts. They are not normalized across the seven ACF levels and must never be averaged into a session ownership number.

## CSPC Precision Hook

CSPC changes evidential precision, not ARI capability scores.

For CSL ownership, `pi_s` has two effects:

1. It attenuates how much a control signal moves the displayed-ownership estimate when the session state is degraded.
2. It widens the credible interval by increasing uncertainty for the same observed signal.

The implementation must not use CSPC to modify any ARI score. CSL remains a parallel descriptive layer.

If per-turn precision is available, `pi_s(level)` is the opportunity-weighted mean precision over the turns that contributed to the level evidence. If only session precision is available, use the session precision factor and mark the interval derivation as session-level.

## Credible Intervals

Every emitted ownership value must carry a credible interval. Never emit a bare percentage.

Default interval procedure:

1. Gather the contributing human opportunity/firing records for the level.
2. Exclude structurally non-applicable records before resampling.
3. Resample contributing opportunities with replacement for `B` bootstrap replicates, where `B` is configurable and defaults to 1000 in implementation.
4. Recompute `control_human_b`, `pi_s_b`, `human_ownership_b`, and `ai_ownership_b` for each replicate.
5. Use the 2.5th and 97.5th percentiles as the 95 percent interval.

AI contribution is treated as fixed only for deterministic AI-side levels. If the AI-side extractor uses a judge or replicated semantic decision, its uncertainty must be included in the bootstrap by sampling from that extractor's reported distribution.

For saturated levels:

- If all applicable human evidence is at the top observable bound, status is `MEASUREMENT_SATURATED` with a high censored bound.
- If all applicable human evidence is at the bottom observable bound, status is `MEASUREMENT_SATURATED` with a low censored bound.
- A saturated result reports a censored bound, not a point estimate.

## Status Rules

Status is assigned per level:

- `NOT_APPLICABLE`: the ACF level did not arise in the session; no denominator exists.
- `INSUFFICIENT_SAMPLE`: the level arose, but `n_eff` is below the configured threshold.
- `MEASUREMENT_SATURATED`: the instrument cannot resolve above or below the observed bound.
- `OK`: the level has enough evidence, no saturation, and a computable denominator.

The four states must render as distinct labels downstream.

## Output Contract

`compute_ownership(...)` returns exactly seven entries:

```text
{
  "C1": OwnershipResult,
  "C2": OwnershipResult,
  "C3": OwnershipResult,
  "C4": OwnershipResult,
  "C5": OwnershipResult,
  "C6": OwnershipResult,
  "C7": OwnershipResult
}
```

`OwnershipResult` must carry:

- `human_pct`
- `ai_pct`
- `ci`
- `n_eff`
- `status`
- `rung`
- `method_version`

The output must not contain:

- a single session-level ownership percentage;
- a "what the human could do without AI" column;
- any ARI score averaged into a CSL bar;
- a hidden modification of ARI scores.

## Acceptance Criteria

- Output is a seven-entry vector.
- Each level either has a CI or a non-OK status explaining why no percentage is emitted.
- Non-applicable neurons do not contribute.
- Low `n_eff` produces `INSUFFICIENT_SAMPLE`.
- Levels that never arose produce `NOT_APPLICABLE`.
- Saturated levels use `MEASUREMENT_SATURATED` with censored bounds.
- The implementation imports the existing precision definition rather than redefining CSPC degradation.
- No result is collapsed to a session scalar.

