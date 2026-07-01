# CE Execution Brief — SAF/ARI Efficiency & Accuracy Implementation

**To:** Claude Code (Chief Engineer)
**From:** Build coordinator
**Date:** June 27, 2026
**Baseline:** v3.21 unified master + v3.22 SpecDelta, repo `main@f328a0f`
**Mode:** Gate-locked delivery. Every phase is additive, ratchet-gated, and crosses no Wall.

---

## 0. How to use this brief

You are the Chief Engineer. This brief sequences the efficiency + accuracy work into **9 phases**. For each phase you get **WHY** (the engineering rationale — do not skip it; it tells you what failure you are preventing), **WHEN** (dependencies and the gate that must be green before you start), **WHAT** (the exact files and the load-bearing change), **VERIFY** (the acceptance test and the artifact that proves it), and **DELEGATION** (what to hand Codex vs. own yourself).

Three rules govern everything below:

1. **The MAE ratchet (≤ 0.2994) on the 26-chat gold set gates every merge.** No exceptions. If a change regresses the ratchet, it is REWORK regardless of how good it looks.
2. **Accuracy-affecting changes ship behind a feature flag.** With the flag **OFF**, scores must be **byte-identical** to baseline (prove it with a regression test). With the flag **ON**, the ratchet must still pass. This is how we add accuracy without instrument drift.
3. **Delivery is three commits per step** — (1) implementation, (2) tests, (3) ADR/docs — and you return an explicit **LGTM** or **REWORK with file:line references** before the next step proceeds. You never let a phase advance past a failing gate.

---

## 1. TREAT AS SETTLED — do not re-litigate

These are decided. Implement them; do not redesign them.

- **The cost driver is `score_all_neurons` issuing 107 sequential per-criterion calls + 1 joint = 108 round-trips per chat.** This is the bottleneck. (v3.22 Item #2 acknowledges the cost; we are now reducing it.)
- **LLM-judge reliability degrades with transcript length** (stable under ~8K tokens; pairwise judges fall below random past ~32K). Longer chats carry more noise, not more signal.
- **Wide CIs (±46/±95) are three stacked phenomena:** small effective-n, off-screen-censored signals (EC/ES), and equal-weight aggregation inflating noisy neurons. Each has a distinct fix.
- **CSPC is a sibling state axis to ARI trait, and it doubles as evidence-quality metadata for trait scoring.** This is the basis of the accuracy fix in Phase 2.
- **Method choices are final:** scorer-type cascade, dimension-batching, CSPC-weighted aggregation, hierarchical partial pooling, SetFit, Snorkel weak supervision, distillation. The *only* open design artifact is the per-neuron triage table (see Phase 3).

---

## 2. DO NOT TOUCH — frozen

Changing any of these breaks comparability or crosses the Wall. If a task seems to require touching one, **stop and escalate** — it does not.

- `src/merge/precision.py` — the precision-not-multiplier invariant. CSPC weighting goes **upstream** of this, in aggregation.
- `csl/ownership.py` — the ownership formula.
- `contracts/` — 107 neurons, 8 dimensions, 4 pillars, the claims table.
- The **four missingness labels** (`absent ≠ zero`) and **The Wall** (no VALIDATED claim without Layer-4 evidence).
- Any change that alters a stored score's *value* without an ADR **and** a ratchet pass.

---

## 3. Phase plan (overview)

| Phase | Goal | Axis | Depends on | Can parallelize with |
|---|---|---|---|---|
| 0 | Fix the spine + hygiene | unblock | — | nothing (must be first) |
| 1 | Judge call path → ~6 calls/chat | Efficiency | P0 | P2 |
| 2 | CSPC-weighted aggregation | Accuracy | P0 | P1 |
| 3 | Cascade router + SetFit | Both | P0, triage table | — |
| 4 | Snorkel data engine | Both | P3 | — |
| 5 | Hierarchical GRM | Accuracy | corpus growth + PyMC | P6 |
| 6 | `memory/` layer (Layer 3) | Architecture | stable kernel | P5 |
| 7 | Distillation | Efficiency | corpus ≥ ~few hundred | — |
| 8 | SynergyAPI contract | Architecture | stable kernel interface | all |

**Critical path:** P0 → P1/P2 (parallel) → P3 → P4. Corpus growth (P4) gates P5 and P7, matching your v3.22 critical path (Item #4 gates everything downstream).

---

## PHASE 0 — Fix the spine + hygiene

**WHY.** A broken spine optimizes to nothing — every efficiency and accuracy gain downstream is wasted if chats don't store and score. The completeness gate in `src/db/queries.py` is the prime suspect for the 422 rejections, and critically, **it currently fights the `absent ≠ zero` invariant**: a chat is being rejected merely because ES is N/A or EC is sparse, when the correct behavior is to store it and let the scoring layer emit a missingness label. The hygiene items (unpushed commits, stale README, committed DB, billing) are prerequisites: you cannot reason about behavior when running code ≠ committed code, and the free tier trains on student transcripts, which is a privacy violation before it is a quota problem.

**WHEN.** First. Blocks every other phase. No gate precedes it.

**WHAT.**
- `src/db/queries.py` — split "malformed" from "sparse-but-valid." Reject only genuinely broken structure; store sparse chats with flags.

```python
def gate_for_storage(session):
    if not has_required_structure(session):       # no turns, no events, broken schema
        return Reject(reason="MALFORMED")
    flags = []
    if effective_n(session) < MIN_N:
        flags.append("INSUFFICIENT_SAMPLE")        # store + flag — NEVER reject for sparsity
    return Store(session, flags=flags)
```

- Push the three `feat/v3.22-twelve-upgrades` commits. Add `saf_brain.db` to `.gitignore` and remove it from tracking. Reconcile the README version label (v2.2 → v3.21). Enable paid Gemini billing (Tier 1).

**VERIFY.** Acceptance test: post a known-sparse chat (ES absent, EC sparse, short) and assert it returns **200 with `INSUFFICIENT_SAMPLE` flags**, then scores, then persists — not a 422. Post a malformed chat (no turns) and assert it returns a clean `MALFORMED` reject. Artifact: `tests/integration/test_storage_gate.py` green; `git log origin/main` shows the three commits; `saf_brain.db` untracked.

**DELEGATION.** You own `queries.py` (backend). Hygiene is yours.

---

## PHASE 1 — Judge call path (the cost collapse)

**WHY.** 108 sequential round-trips against a 1,500/day free ceiling is ~15 chats/day — the wall you hit. Per-neuron calls were chosen to kill halo contamination, which is correct in principle but **premature precision**: you cannot run the GRM/EFA that per-neuron resolution feeds until the corpus is in the hundreds, so today you are paying a ~12× call premium for resolution you cannot consume. Dimension-batching keeps the property that actually matters — between-dimension independence, where halo lives — at a fraction of the cost. Caching exploits the fact that the rubric is static across every chat; batching exploits that scoring is async.

**WHEN.** After P0. Parallelizable with P2 (different files). High priority — it is what makes the corpus growth in later phases affordable.

**WHAT.**
- `src/trait/judge/per_criterion.py` — route non-inferential neurons off the LLM, dimension-batch the rest, run concurrently:

```python
async def score_all_neurons(transcript, neurons):
    det, nlp, inferential = partition_by_scorer_type(neurons)   # from triage table (P3)
    scores = run_deterministic(transcript, det) | run_nlp(transcript, nlp)  # 0 LLM
    by_dim = group_by_dimension(inferential)
    results = await asyncio.gather(*[
        judge.score_dimension(transcript, dim, ns) for dim, ns in by_dim.items()
    ])  # 8 batched, cached, concurrent calls — not 90 sequential
    return scores | merge(results)
```

- `src/trait/judge/client.py` — (a) prompt-cache the static rubric prefix (rubric first, transcript last); (b) add a Batch API path for the async worker; (c) default model = Flash-Lite; (d) fix the OpenRouter third-attempt waste so all three retries hit Gemini when no OR key exists.
- `src/trait/judge/replication.py` — replace fixed-N with the disagreement cascade (3 passes → escalate K only if variance > threshold). This is v3.22 Item #1; wire it now.

**VERIFY.** Two gates, both required. (1) **Call-count gate:** instrument the dispatch and assert LLM calls per chat drop from ~98 to ~6–8 on a representative chat. (2) **Quality gate:** the MAE ratchet must still pass with Flash-Lite + batching in the loop — **validate Flash-Lite against gold before making it the default**; the research says small models often match or beat large ones on rubric scoring, but prove it on *your* gold, do not assume it. Artifact: a call-count log per chat + a ratchet run showing MAE ≤ 0.2994 with the new path.

**DELEGATION.** You own `client.py` and the dispatch in `per_criterion.py` (backend/orchestration). You may hand Codex the per-dimension prompt templates and `rubric_bank.py` entries as leaf work, reviewed against the anchored-rubric spec (Item #2).

---

## PHASE 2 — CSPC-weighted aggregation (the long-chat accuracy fix)

**WHY.** This is the highest leverage-per-effort change you have and the one genuinely novel insight: CSPC, built as a sibling axis, is *evidence-quality metadata* for trait scoring. A neuron firing during a high-quality CSPC state (active, high-epistemic, low-load) is high-signal; the same firing during a degraded state is the user reacting to stress, not expressing trait. So the judge-fatigue problem on a 294-turn chat **dissolves** — you are not asking the judge to discriminate quality across 20K tokens, because CSPC already discriminated it per turn. You weight firings by CSPC quality (inverse-variance), and noisy late-turn evidence is automatically down-weighted. **No new LLM calls.** It is a post-processing step downstream of the judge.

**WHEN.** After P0; parallel with P1 (touches aggregation, not the judge). Do this early — it is cheap and it directly attacks the wide-CI symptom.

**WHAT.** `src/trait/aggregation/neuron_to_dimension.py` — replace equal-weight mean with CSPC-weighted aggregation, **behind a feature flag**:

```python
def cspc_weight(turn_state):
    z = A*turn_state.epistemic - B*turn_state.load + C*turn_state.metacognition
    return sigmoid(z)                       # A, B, C tuned on gold

def aggregate_neuron(firings, cspc_by_turn, use_cspc_weighting):
    if not use_cspc_weighting:
        return mean([f.value for f in firings])          # baseline path, unchanged
    w = [cspc_weight(cspc_by_turn[f.turn]) for f in firings]
    return weighted_mean([f.value for f in firings], w)  # inverse-variance
```

**Placement is critical:** this goes in **aggregation, upstream of `src/merge/precision.py`**, which is frozen. Do not put weighting in the merge layer.

**VERIFY.** (1) **Flag-off regression:** with `use_cspc_weighting=False`, scores byte-identical to baseline across the full gold set. (2) **Flag-on quality:** ratchet passes, AND on the long-chat fixtures the late-turn (degraded-CSPC) evidence demonstrably receives lower weight — assert that a 294-turn chat's effective late-turn contribution drops while early-turn contribution holds. Artifact: `test_cspc_weighting.py` (flag-off byte-identical + flag-on weight behavior) and a before/after CI-width comparison on the long chats. File an ADR — this changes how scores aggregate, so it needs deliberation and the ratchet.

**DELEGATION.** You own this — it touches the scoring core. Codex may own the `A, B, C` tuning harness against gold as a leaf task.

---

## PHASE 3 — Cascade router + SetFit classifiers

**WHY.** The router is what makes Phase 1's "route non-inferential neurons off the LLM" real — it removes ~half the calls before batching even runs. SetFit replaces the LLM for *classification-shaped* neurons at zero API cost, trained on your existing gold labels (~8 labels/class is enough). But not every neuron is SetFit-able: the genuinely latent ones stay on the LLM, so this phase **requires the per-neuron triage table first** — the decision of which of the 107 neurons go deterministic / SetFit / LLM-only. That table is the open artifact; build it before the router.

**WHEN.** After P0. Hard dependency: the triage table (`contract_table.yaml` extended with a `scorer_type` per neuron). Do not write the router against guesses.

**WHAT.**
- New `src/extraction/cascade.py` — the scorer-type router, driven by the neuron→type map.
- New `src/extraction/setfit/` — one classifier per neuron assigned to SetFit; local, no API.

**VERIFY.** (1) Routing: every neuron dispatches to its assigned tier; assert no neuron silently falls through to the LLM that the table marked deterministic. (2) **SetFit gating:** a neuron is only allowed on the SetFit tier if its classifier **matches the LLM judge on held-out gold within tolerance** — do not route a neuron to SetFit on faith. Artifact: the routing table + a per-neuron SetFit-vs-LLM agreement report; neurons below tolerance get bumped back to the LLM tier.

**DELEGATION.** You own `cascade.py` (architecture). Individual SetFit classifiers are ideal Codex leaf tasks — one per neuron, each with its own agreement-vs-gold acceptance criterion.

---

## PHASE 4 — Snorkel weak-supervision data engine

**WHY.** The corpus is the binding constraint (26–82 chats), and this breaks it. Your 107 micro-rubrics are *already labeling functions*; the LLM judge becomes one strong-but-expensive labeling function among many cheap deterministic ones; Snorkel's label model denoises them without ground truth and labels your entire unlabeled backlog. This is the concrete mechanism behind v3.22 Item #4 (Active Learning). It decouples labeling effort from training-set size — you stop hand-labeling and start generating labels, and those labels feed SetFit (P3) and the distilled student (P7).

**WHEN.** After P3 — the labeling functions reuse the same rubric logic the cascade routes on. Gold stays validation-only throughout; it never enters the weak-label training set.

**WHAT.** New `calibration/weak_supervision.py` — define LFs from the micro-rubrics + the judge-as-LF, fit the label model, emit probabilistic labels over the unlabeled pool.

**VERIFY.** The label model produces probabilistic labels with reasonable coverage; a model trained on the weak labels beats a majority-class/random baseline on held-out gold; the gold corpus is provably excluded from training. Artifact: a label-model coverage + accuracy report, and a training-set manifest proving gold exclusion.

**DELEGATION.** You own the label-model pipeline. Individual labeling functions are clean Codex leaf tasks.

---

## PHASE 5 — Hierarchical GRM (narrow the wide CIs)

**WHY.** The ±46/±95 intervals on short sessions are partly correct Bayesian behavior on tiny n — but they can be *principledly narrowed*, not just abstained on. Hierarchical partial pooling draws each session/user parameter from a shared population distribution, so a sparse session borrows strength from the corpus and shrinkage is automatically stronger the sparser the session. This is the IRT-native upgrade over the equal-weight aggregator, and it needs **no new dependency — you already plan PyMC for the GRM**; reformulate it hierarchically rather than flat per-session.

**WHEN.** Needs corpus breadth (multiple sessions across users) — gates on P4's corpus growth. Parallel with P6.

**WHAT.** `src/trait/irt/*` — reformulate the planned GRM with session/user random effects from a population prior.

**VERIFY.** Short-session CI widths shrink versus the unpooled baseline **without** the population-level estimates degrading; ratchet passes. Artifact: a CI-width before/after distribution across the gold set, showing the largest narrowing on the sparsest sessions.

**DELEGATION.** You own this (statistical core).

---

## PHASE 6 — `memory/` layer (unlock Layer 3)

**WHY.** The pipeline is per-session, but λ, cognitive debt, and personal rolling baselines are cross-session quantities — you cannot compute "is this user getting more capable over time" from one session. This layer is the missing piece for the entire sustainability axis. It is **additive**: the kernel feeds it, it never modifies a kernel score. (Borrow the Context-State-Object pattern — compress long transcripts into a structured per-subject state object — for token efficiency, but keep no autonomous agent in the scoring path.)

**WHEN.** Once the kernel interface is stable (post P1–P3). Parallel with P5. Additive, so low risk to the core.

**WHAT.** New `memory/` — a per-subject model store: rolling baselines, λ EWMA, debt, trajectories, keyed by subject, with read/write seams to the kernel that do not alter scoring.

**VERIFY.** (1) **Core untouched:** kernel scores byte-identical before and after the layer exists. (2) **Accumulation correct:** a multi-session fixture produces the expected λ trajectory and debt EWMA. Artifact: a byte-identical regression on the kernel + a multi-session trajectory test.

**DELEGATION.** You own the schema and seams. Codex may own the EWMA/baseline math as leaf functions.

---

## PHASE 7 — Distillation (the ~0-cost endgame)

**WHY.** The permanent cost fix. Once the corpus is deep enough, a fine-tuned small student scores all 107 neurons in one local forward pass at near-zero marginal cost, and the frontier teacher retreats to gold-candidate scoring and drift detection. Your scored corpus *is* the training set — the expensive phase funds its own replacement. **Selective distillation:** only high-CSPC-quality evidence (from P2) enters the teacher set, so the student learns from reliable rather than noisy labels.

**WHEN.** **Only after corpus ≥ ~few hundred chats** (gates on P4). Do not reach for this early — it is the "make it fast" phase, not the "make it work" phase.

**WHAT.** New `distill/` — teacher-trajectory generation (high-CSPC filtered), student fine-tune, and a production swap so the student serves scoring while the teacher samples for calibration.

**VERIFY.** The student matches the teacher on held-out gold within tolerance, and the ratchet passes with the student in the production loop. Artifact: a student-vs-teacher agreement report on held-out gold.

**DELEGATION.** You own the pipeline and the swap.

---

## PHASE 8 — SynergyAPI contract (the platform)

**WHY.** Multiple products (Tracer, Integrated Platform, Audits, Enterprise Governance) must call the *same* frozen kernel — the moment two products score differently, cross-product comparability dies. The universal event log is already the narrow waist; this phase formalizes the adapters above it and the claims middleware below it. Claims must be enforced **structurally** (the response schema for a tier physically lacks the fields it isn't entitled to), and **the Wall becomes a runtime boundary**: VALIDATED claims require Layer-4 data for that subject.

**WHEN.** Parallel/refactor as the kernel interface stabilizes. Not greenfield — you are refactoring a validated monolith into kernel-plus-adapters.

**WHAT.** New `src/ingest/adapters/*` (per-product normalization to the event log) and `src/claims/middleware.py` (per-caller tier shaping; forbidden-field stripping; version stamping; Wall enforcement).

**VERIFY.** (1) A Tracer-tier response **structurally lacks** a λ/synergy field (not nulled — absent from the schema). (2) Every score carries an instrument-version stamp and cross-version comparison is refused. (3) A VALIDATED claim request without Layer-4 data for the subject returns the MEASURED version. Artifact: per-tier schema tests + a Wall-enforcement test.

**DELEGATION.** You own middleware and the contract. Adapters are delegable per product once the event-log schema is fixed.

---

## Appendix — CE review checklist (run before every LGTM)

Before you sign off on any step, confirm:

- [ ] **Ratchet:** MAE ≤ 0.2994 on the 26-chat gold with the change in place.
- [ ] **Frozen files untouched:** `src/merge/precision.py`, `csl/ownership.py`, `contracts/` unchanged (diff them).
- [ ] **Flag-off byte-identical** (accuracy phases only): scores identical to baseline with the feature flag off.
- [ ] **Call-count target met** (cost phases only): measured LLM calls/chat at or below the phase target.
- [ ] **Agreement-vs-gold within tolerance** (SetFit/distillation): no neuron routed to a cheaper tier that fails its gold-agreement bar.
- [ ] **Three commits present:** implementation, tests, ADR/docs.
- [ ] **Tests green** and the verifying artifact attached.
- [ ] **No Wall crossing, no ontology change, no neuron added.**

If any box is unchecked, the verdict is **REWORK** with the specific file:line. Otherwise, **LGTM** and the next phase may begin.

---

*Additive to v3.21/v3.22. Crosses no Wall, changes no ontology, modifies no frozen score. Every phase gated on the MAE ratchet (≤ 0.2994). Open artifact required before Phase 3: the per-neuron triage table (`contract_table.yaml` + `scorer_type`).*
