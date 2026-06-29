# ADR-0017 — Reject external integrations (IANVS, ChatGPMe, prompt-evaluator)

**Date:** 2026-06-30  
**Status:** PROPOSED (awaiting LGTM — Vaibhav / Ritesh / CE)  
**Context:** v3.23 Strategic Implementation Specification §4 + Appendix R.5 (gating)  
**Impact:** No code. Closes three integration proposals; records vetting precedent.

---

## Decision

Three GitHub repositories proposed for integration into SAF/ARI are **rejected**:

- **IANVS** — `kubeedge/ianvs` (edge-AI benchmarking framework)
- **ChatGPMe** — `keyboardP/ChatGPMe` (persistent vector DB over sessions)
- **chatgpt-prompt-evaluator** — `alignedai/chatgpt-prompt-evaluator` (jailbreak filter prompt)

Each is rejected for a **structural** reason — an architectural mismatch or a
direct conflict with a standing non-negotiable — not a quality judgement. Three
other repos reviewed in the same pass (`vibe-log-cli`, `gpt-chat-analysis`,
`chatgpt-usage-analyzer`) are **partially accepted as pattern reads only** (§6):
their schemas/UX may be read, but no code is imported.

The rejections are filed in `PROPOSALS.md` as **P-007 / P-008 / P-009**.

---

## Context

The v3.23 review identified three real needs — reproducible benchmarking, a way
to carry information across sessions, and an evaluator-before-judge scoring
pattern — and surveyed six external repos against them. The question this ADR
settles is not "are these good projects" but "does adopting them serve SAF/ARI's
*psychometric measurement* problem without crossing a non-negotiable."

SAF/ARI's validation stack is psychometric: a G-study with ≥30 subjects, an MAE
ratchet on the gold corpus (≤0.2994), DIF testing, EFA, retention probes, OSF
pre-registration. The instrument is frozen (107 neurons / 8 dims / 4 pillars),
gated by The Wall (MEASURED never claims VALIDATED), and bound by DPDP
data-dignity commitments. Any integration is measured against those three
constraints first. All three rejected repos fail at least one.

The trade-off of rejection is small: each rejected capability is already served
by an existing component, or by a cited reference pattern that we implement
ourselves. The trade-off of acceptance is large: each would import an
abstraction that has to be continuously defended against the freeze, the Wall,
or DPDP. Rejecting now is cheaper than un-wiring later.

---

## §3. Rejection: IANVS (`kubeedge/ianvs`)

**What it is.** An edge-AI ML benchmarking framework from KubeEdge. Its
primitives — test environments, paradigms, story managers — assume the task is
benchmarking *model performance* on *labeled tasks* (federated learning,
distributed model evaluation).

**Why it was proposed.** "Benchmarking infrastructure, reproducible evaluation,
CI regression testing."

**Rejection rationale (structural mismatch).** SAF/ARI does not benchmark a
model; it *measures a human-AI interaction* with a psychometric instrument.
Reliability here means inter-rater agreement, generalizability coefficients, and
MAE against a gold corpus — not throughput or accuracy on a labeled benchmark.
IANVS's abstractions have no place to put a G-study, an MAE ratchet, DIF, or a
retention probe; adopting it would force a psychometric problem into an
ML-benchmark shape and obscure the validation that actually matters.

**Alternative (already built).** The 26-chat gold corpus plus the MAE ratchet
enforced in CI already provide reproducible regression testing for the
instrument. This is the correct shape for psychometric regression.

**Decision.** REJECTED — recorded as P-007. Re-proposal requires showing IANVS
expresses a psychometric (not ML-benchmark) validation, which it does not.

---

## §4. Rejection: ChatGPMe (`keyboardP/ChatGPMe`)

**What it is.** A persistent vector database over sessions: embeds session
events and indexes them for semantic similarity search / retrieval.

**Why it was proposed.** "Semantic memory, persistent vector indexing, retrieval
across sessions."

**Rejection rationale — three standing violations:**

1. **The Wall (non-negotiable; spec §2.1).** Indexing scored, MEASURED-tier
   sessions and retrieving "similar" ones reconstructs validated-looking
   patterns from data that has only earned the MEASURED rung. The Wall is
   enforced structurally (response schema), precisely to stop a retrieval layer
   from laundering MEASURED evidence into VALIDATED-looking claims.

2. **Ontology freeze (non-negotiable #1; spec §14.3).** Semantic retrieval over
   neuron firings invites *discovered* constructs — latent clusters, archetypes,
   "emergent" dimensions — exactly the new latent variables the freeze forbids
   until a diverse corpus and EFA justify them. A vector index is a construct-
   discovery engine pointed at frozen ontology.

3. **DPDP / data-dignity (non-negotiable #16; Δ9).** Persistent embeddings of
   student transcripts are derived from sensitive data and are difficult to
   delete-propagate. A retained, retrievable vector store conflicts with data
   minimization and the deletion-propagates-to-derived-features commitment.

**Alternative (already built).** Cross-session need is met by the 26-chat gold
corpus plus deterministic event-log replay — idempotent re-entry, not semantic
search over behavioral history. Determinism, not similarity, is what the
instrument requires.

**Decision.** REJECTED — recorded as P-008. Re-proposal requires resolving all
three structural violations, not merely scoping the index.

---

## §5. Rejection: chatgpt-prompt-evaluator (`alignedai/chatgpt-prompt-evaluator`)

**What it is.** A single system prompt for jailbreak filtering. It is a prompt
template, not an evaluator framework.

**Why it was proposed.** "Evidence gating, evaluator-before-judge architecture."

**Rejection rationale (misidentification).** The repo does not implement the
desired pattern. The architecture actually wanted — evidence extraction →
validation → scoring — already exists in the v3.22 spec as Item #2 (per-criterion
judge calls + anchored rubric), now live on the neuron-grain path. Importing a
jailbreak prompt would add nothing and confuse the evaluator design.

**Better references (cite, do not import).** For evaluator-before-judge:
- **G-Eval** (Liu et al., 2023) — chain-of-thought scoring with explicit
  criteria decomposition.
- **Prometheus 2** (Kim et al., 2024) — fine-grained, rubric-based LLM
  evaluators.

These are pattern references for the existing per-criterion design, not
dependencies.

**Decision.** REJECTED as proposed — recorded as P-009. G-Eval and Prometheus 2
are adopted as reference patterns (see ADR-0018, task-oriented scoring).

---

## §6. Partial acceptance (pattern reads only — no code import)

Carried verbatim from v3.23 §4.4–4.6:

- **vibe-log-cli (event sourcing patterns).** Read patterns, do not import code.
  The Universal Event Log (Δ3, §5.9a) is already in build deltas. CE reads its
  event-log schema and sync protocol and writes a one-page mapping ADR.
- **gpt-chat-analysis (incremental processing).** One engineer-hour reading the
  incremental-processing checkpoint logic — directly relevant to the pipeline
  idempotent re-entry pattern. No code import.
- **chatgpt-usage-analyzer (UI inspiration).** Use for the Settings/Profile/
  operational dashboard (S8–S10 surfaces only). Do **not** mix with the
  Portfolio radar (D-024), which follows the cognitive-analytics design
  language.

These are reads, not integrations, and carry no architectural risk.

---

## §7. New references adopted (patterns, not imports)

Carried verbatim from v3.23 §4.7:

| Need | Reference | Purpose |
|------|-----------|---------|
| Item #1 cascaded selective evaluation | `confident-ai/deepeval` or `microsoft/promptflow` | Variance-based escalation natively |
| Item #3 IRT diagnostics (GRM fitting) | `eribean/girth` or `philchalmers/mirt` via rpy2 | GRM, partial credit, IRT for ordinal responses |
| Item #8 two-table event log | `crate-py/eventsourcing` | Battle-tested Python event sourcing |
| P4 Snorkel orchestrator | `snorkel-team/snorkel` + `HazyResearch/metal` | Multi-task weak supervision |
| P5 Hierarchical Bayesian GRM | `pymc-devs/pymc` + `bambinos/bambi` | Partial pooling for sparse sessions |
| Cost cascade (Item #1) | `stanford-futuredata/FrugalGPT` | Reference implementation |
| Task-oriented evaluation patterns | TD-EVAL (Acikgoz et al., 2025) | Turn-level evaluation architecture |
| Task-specific rubric generation | RUBICON (Microsoft Research, 2024) | Domain-sensitized rubric generation |

---

## §8. Consequences

For future integration proposals, this ADR sets four precedents:

1. **Psychometric ≠ ML-benchmark.** A benchmarking framework is not a validation
   framework. Integrations must serve the psychometric stack (G-study, MAE, DIF,
   EFA, retention) to be considered.
2. **Wall violations are structural, not stylistic.** Any component that can
   surface MEASURED evidence as VALIDATED-looking output is rejected at the
   schema boundary, regardless of intent.
3. **The freeze gates construct discovery.** Retrieval / clustering / embedding
   layers that can surface new constructs are blocked until corpus + EFA justify
   them.
4. **DPDP is non-negotiable for student data.** Persistence of derived features
   (embeddings included) must honour minimization and deletion-propagation.

A proposal that does not address the relevant precedent is rejected at the
proposal stage rather than entering review.

---

## §9. Approval

| Role | Name | Decision | Date |
|------|------|----------|------|
| Decision authority (architecture, Appendix R alignment) | Vaibhav | ⏳ pending | |
| Compliance (DPDP / data-dignity rationale) | Ritesh | ⏳ pending | |
| Technical review (Wall / freeze interpretation) | CE | ⏳ pending | |

---

## Notes

- **Filename / numbering:** the v3.23 kickoff named this `ADR-0017-...`; the repo
  ADR convention is `NNNN-kebab.md`, and 0015/0016 are already taken (twice
  each). Filed as `adr/0017-reject-external-integrations.md` per Appendix R.3.
  Companion ADRs renumber to **0018** (task-oriented scoring) and **0019**
  (pre-filter eligibility gate).
- **No code, no tests** — pure documentation, ungated per Appendix R.5.
