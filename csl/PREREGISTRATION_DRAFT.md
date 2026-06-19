# CSL v3.2 OSF Pre-Registration Draft

Status: draft for human review  
Scope: Cognitive Work Layer v3.2  
Claim discipline: null results are publishable; no threshold may be tuned on pilot/gold outcomes after registration.

## Registered Artifacts

The following artifacts are registered before CSL runtime scoring:

1. `csl/acf_crosswalk.yaml`
   - The neuron-to-ACF projection for the human side.
   - Every contract neuron is mapped to at least one ACF level or explicitly excluded.
   - This is a data artifact, not a new extractor.

2. `csl/prompts/csl_foundation_prompt.txt`
   - The CSL foundation-evidence prompt family.
   - Review-only until human sign-off confirms it is partitioned from ARI competency scoring.

3. `csl/SPEC_ownership.md`
   - The per-level ownership formula.
   - Ownership is a seven-vector with credible intervals, never a session scalar.
   - CSPC modifies evidential precision and interval width, never ARI score values.

4. `csl/SPEC_emergence.md`
   - The emergence scanner definition.
   - All candidates must satisfy bilateral novelty, fused dependency, and reframing trace before judge confirmation.

5. `csl/validation/independence.py`
   - The empirical partition check.
   - ARI scores and CSL ownership shares must not correlate near 1.0.

## Primary Hypotheses

H1: CSL displayed ownership can be estimated at the ACF-level session aggregate without re-extracting the human side.

H2: CSL ownership shares are empirically distinguishable from ARI capability scores. Near-perfect correlation indicates partition failure.

H3: Emergence events, as defined by bilateral novelty plus fused dependency plus reframing trace, occur rarely and are concentrated at `C4` and `C6`.

H4: CSL displayed ownership and emergence rate are only leading indicators of genuine synergy. They do not prove solo-retention or transfer without the Layer 4 probe.

## Independence Test

Inputs:

- `ari_scores`: matrix of sessions by ARI dimension scores.
- `csl_shares`: matrix of sessions by ACF-level human ownership shares.

Procedure:

1. Compute Pearson correlation for each registered ARI-dimension / ACF-level pair when at least `min_n` paired observations are available.
2. Flag any pair with absolute correlation greater than or equal to `near_one_threshold`.
3. Default `near_one_threshold = 0.95`.
4. Default `min_n = 8`.
5. Missing, non-applicable, insufficient, or saturated values are excluded pairwise, never coerced to zero.

Decision rule:

- Any flagged pair is evidence that the CSL partition may be re-measuring ARI and must be reviewed before claims are upgraded.
- No flagged pair does not validate CSL by itself; it only passes the partition sanity check.

## Emergence Registration

Registered event levels:

- `C4`
- `C6`

Forbidden event levels:

- `C1`
- `C2`
- `C3`
- `C5`
- `C7`

Candidate conditions:

1. Bilateral novelty: human-new content is far from both human-prior and AI-prior centroids.
2. Fused dependency: uptake of AI material and human exogenous injection occur in the same local window.
3. Reframing trace: the actualization loop closes on a reframing, not a refinement.

Reportable event condition:

- A judge must confirm the candidate using structured output.

## Claim Boundaries

Allowed after implementation and reliability certification:

- displayed per-level ownership;
- emergence count/rate as a measurable indicator;
- partition-check results;
- per-level uncertified/certified status.

Forbidden without retention/transfer probe:

- true synergy proof;
- "what the human can do without AI";
- solo capability inference from chat data;
- session-level ownership percentage;
- CSL as validation of ARI.

## Human Review Gate

Before any prompt is wired to a judge:

- A human reviewer must confirm that the ARI competency prompt and CSL foundation prompt attend to different constructs.
- ARI prompt target: human capability evidence.
- CSL prompt target: foundation evidence relative to the preceding AI output.
- If the prompts are not partitioned, CSL runtime wiring must stop.

