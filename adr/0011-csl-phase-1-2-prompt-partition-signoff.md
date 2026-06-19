# ADR-0011 — CSL Phase 1.2 prompt-partition sign-off (ARI vs CSL foundation)

- **Status:** Accepted
- **Date:** 2026-06-19
- **Decider:** Project lead (human-review gate); review prepared by Chief Engineer
- **Implements:** SAF/ARI v3.2 §1.2 — the mandatory STOP-FOR-HUMAN-REVIEW that
  gates CSL Phase 2. No CSL prompt may be wired to a judge until a human confirms
  the ARI competency prompt and the CSL foundation prompt attend to genuinely
  different constructs.
- **Artifacts reviewed:** `src/trait/judge/prompt.py` (ARI competency, `v2.1`) and
  `csl/prompts/csl_foundation_prompt.txt` (CSL foundation, `v0.1`).

## The gate

The double-measurement risk: if the judge collapses ARI scoring and CSL
foundation-detection into one measurement, CSL re-measures ARI and the partition
is fictional. §1.2 requires the partition be enforced at the PROMPT level and
confirmed by a human before either prompt is wired.

## Finding — partitioned; both acceptance-diff conditions met

| | ARI competency prompt | CSL foundation prompt |
|---|---|---|
| Scored construct | human collaboration competence (8 dims, "what they demonstrably did") | foundation-backed control **relative to the immediately preceding AI output** |
| Reference point | the human's behavior | the AI/human **seam** |
| Origination | explicitly avoided ("Score only observed behavior. Never infer ability.") | central ("not derivable from the AI output alone") |

- **CSL references the AI-turn baseline** ✅ — `ai_prior` input; "relative to the
  immediately preceding AI output"; control signals defined as not producible by
  "merely accepting or remixing the AI output."
- **ARI does not reference origination** ✅ — no "who originated" language; it
  forbids inferring ability and scores observed behavior only.
- CSL carries explicit anti-collapse instructions: "scoring CSL foundation
  evidence, not ARI capability"; "Do not modify or reinterpret any ARI score"; and
  a final self-check against accidentally scoring general ARI competence.

## Accepted caveat (on the record)

The two share *surface evidence* by construction — one verification turn informs
both ARI **EC** and CSL **C3**; likewise CD↔C6, CS↔C4, CA↔C7. This is expected:
CSL shares ARI's evidence by design (Do-NOT #11 — never claim CSL cross-validates
ARI). The prompts differ in what they SCORE from that evidence (trait magnitude vs
seam-relative foundation control). The residual is backstopped empirically by the
independence test (`csl/validation/independence.py`, Phase 3.1), which flags any
ARI-vs-CSL correlation ≈ 1.0 as a partition failure.

## Decision & consequences

- **Partition APPROVED.** The CSL foundation prompt status flips
  `REVIEW_ONLY_DO_NOT_WIRE → PARTITION_APPROVED_2026-06-19`; it is wirable in CSL
  Phase 2.
- Standing conditions carried into Phase 2: (1) CSL never modifies an ARI score
  (#2); (2) CSL adds no neuron/dimension/latent variable (#1, ontology freeze);
  (3) the independence test remains the empirical guard and CSL is never claimed to
  cross-validate ARI; (4) any material change to either prompt re-opens this gate.
- Unblocks Phase 2 build order: 2.1 human-side re-projection (no new extraction) →
  2.2 AI-side displayed-contribution extractor → 2.3 ownership + CSPC precision →
  2.4 emergence scanner → 2.5 Tier-1 analytics → 2.6 CSL reporting.
