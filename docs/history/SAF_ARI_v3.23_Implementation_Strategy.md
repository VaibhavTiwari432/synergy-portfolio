# SAF/ARI v3.23 — Strategic Implementation Specification

**Document class:** Implementation directive for Claude Code (CE) and Codex
**Date:** June 30, 2026
**Baseline:** v3.22 (twelve upgrades branch: `feat/v3.22-twelve-upgrades`)
**Status:** Ready for gate-locked implementation
**Owner:** Vaibhav (architecture decisions) + Ritesh (implementation oversight)
**Supersedes scope:** External integration proposals (IANVS, ChatGPMe, vibe-log-cli, prompt-evaluator)

---

## 0. Executive Summary

This document compiles four strategic conclusions reached during architectural review:

1. **External integration proposals are mostly net-negative.** Original proposal ranking is reversed; three of six rejected outright; two re-targeted to task-oriented dialogue (TOD) frameworks (TD-EVAL, RUBICON).
2. **Task-oriented neuron scoring is the missing measurement layer.** Holistic 107-neuron scoring loses precision because the same neuron measured across different intents (VERIFY vs. EXTRACT vs. OVERRIDE) means different things.
3. **The human-AI loop has a measurement gap at Stage 5→6.** Cognitive state and learning happen between user reception and next-turn action; this is where the pipeline currently breaks.
4. **The eligibility gate is the missing pre-filter.** Before scoring, the pipeline must determine which of 107 neurons are structurally elicitable from this task. Currently it scores all 107 indiscriminately.

**Three new ADRs are proposed:**

- **ADR-0015:** Task-oriented neuron scoring (TD-EVAL + RUBICON patterns)
- **ADR-0016:** Pre-filter eligibility gate (Behavioral Capability Specification)
- **ADR-0017:** Reject external integrations (IANVS, ChatGPMe, prompt-evaluator)

**Zero items cross The Wall. Zero items modify existing scores. Zero items add neurons. Zero items violate the v2 ontology freeze.**

---

## 1. Architectural Diagnosis

### 1.1 The actual human-AI loop (what we are measuring)

The interaction is **not** the sanitized "user types → AI responds" narrative. It is a 7-stage cognitive loop:

| Stage | What happens | Visible to instrument? | SAF/ARI measurement |
|-------|--------------|------------------------|---------------------|
| 1. User's mind | Prior knowledge, cognitive load, stakes, confidence | ❌ Invisible | Inferred from prompt linguistics (AL surface signals) |
| 2. Prompt formulation | Underspecified text encoding implicit assumptions | ✅ Text + telemetry | PR (Prompt Reasoning), intent tags |
| 3. AI processing | Pattern-match against training data, no state model | ❌ Black box | Response artifacts only |
| 4. AI output | Tokens generated, hallucination risk context-dependent | ✅ Text | Judge evaluates response quality |
| 5. User reception & interpretation | Pattern-match against prior beliefs, fill gaps | ❌ Mostly invisible | EC, CA, ES neurons |
| 6. User cognitive processing | Learn vs. accept vs. critically synthesize | ❌ Invisible | CSPC state inference (load, affect, meta) |
| 7. User's next action | Prompt reveals what they understood | ✅ Text + telemetry | Next-turn neurons + Friction Transition Matrix |

**Three blindspots no measurement captures:**
1. **The inference gap** — AI does not know if user understood; user does not know AI's uncertainty
2. **The delegation paradox** — efficient offloading looks identical to learning in a single turn; only longitudinal data reveals which is happening
3. **The stakes blindness** — neither party fully sees consequences until much later

**Why the framework has three axes:**
- **MEASURED** — single-session observables (ARI, CSPC, EC signals)
- **VALIDATED** — only after Layer-4 probes (retention, far-transfer, independence)
- **DESIGNED** — sustainability layer (λ, debt curves) hypothetical until corpus + retention data

### 1.2 Where the current pipeline breaks

The pipeline stalls at **Stage 5 → Stage 6**:

- ✅ Ingestion works (extension captures chats via network interception)
- ✅ Scoring runs (7-stage pipeline executes judge calls)
- ❓ Storage layer is the suspected break (`src/db/queries.py` completeness gates)
- ❓ Aggregation never runs (λ, debt curves require cross-session data flow)
- ❓ CSPC precision weights do not condition the next session's neuron scores
- ❓ Wall enforcement at API schema level is not yet verified end-to-end

**Symptom-level confirmation:**
- `score_all_neurons` runs 107 **sequential** LLM calls despite being described as parallel — a 500-600× throughput claim that does not hold
- Three named commits at branch tip `32fe186` are local-only, never pushed
- Chats are not storing/scoring end-to-end

---

## 2. ADR-0015 — Task-Oriented Neuron Scoring

**Integration Point:** §6 (judge prompt design) + §6.2a (session-intent classification)
**Files:** `src/trait/judge/prompt.py`, `src/trait/judge/client.py`, `src/trait/judge/rubric_bank_v2.py` (new), `src/scorer/intent_aggregator.py` (new)
**Source patterns:** TD-EVAL (Acikgoz et al., 2025), RUBICON (Microsoft Research, 2024)

### 2.1 Problem

The current judge scores each of 107 neurons with a single rubric, regardless of which intent (VERIFY, EXTRACT, OVERRIDE, etc.) the user's turn expresses. This causes:

- **Halo contamination** — neurons measured in different task contexts get aggregated as if equivalent
- **Precision loss** — EC measured on a VERIFY turn means something fundamentally different from EC measured on an EXTRACT turn; averaging them dilutes signal
- **Rubric brittleness** — a single rubric cannot capture intent-specific behavioral expectations

### 2.2 Decision

Adopt task-oriented dialogue evaluation patterns from TD-EVAL and RUBICON. Score each neuron **conditioned on the intent of the turn(s) it is observed in**.

### 2.3 Implementation

```python
# src/trait/judge/rubric_bank_v2.py
RUBRIC_BANK = {
    "EC-5": {  # Calibration Accuracy
        "VERIFY": RubricAnchor(
            unmet="Does not acknowledge the claim being checked",
            emerging="Acknowledges but does not validate against evidence",
            met="Validates against independent evidence",
            exceeded="Pre-validates alternatives to prevent future errors"
        ),
        "EXTRACT": RubricAnchor(
            unmet="Accepts hallucinated content as fact",
            emerging="Surface check only (rephrases without testing)",
            met="Cross-references against source",
            exceeded="Identifies extraction gaps and queries them"
        ),
        "OVERRIDE": RubricAnchor(
            unmet="Pushes back without evidence",
            emerging="Pushes back with weak evidence",
            met="Pushes back with specific evidence and reasoning",
            exceeded="Corrects with verifiable references and proposes alternative"
        )
    }
    # ... 106 more
}
```

```python
# Judge call signature changes
for neuron in scorable_neurons:  # Note: scorable, not all 107 — see ADR-0016
    intent_tags = intent_tagger.tag_turns(chat.turns)
    
    for intent in set(intent_tags):
        turns_with_intent = filter_by_intent(chat.turns, intent)
        if not turns_with_intent:
            continue
        
        response = judge.score(
            neuron_id=neuron.id,
            turns=turns_with_intent,
            intent_context=intent,
            rubric=RUBRIC_BANK[neuron.id][intent]
        )
        
        neuron_scores[neuron.id].append({
            "score": response.score,
            "intent": intent,
            "n_turns": len(turns_with_intent),
            "precision": response.confidence
        })
```

### 2.4 Aggregation

Intent-specific scores aggregate to the neuron level via **CSPC-weighted precision pooling**:

```python
def aggregate_intent_specific_scores(scores: List[IntentSpecificScore]) -> NeuronScore:
    total_precision = sum(s.precision * s.n_turns for s in scores)
    weighted_value = sum(s.score * s.precision * s.n_turns for s in scores) / total_precision
    return NeuronScore(
        value=weighted_value,
        precision=total_precision,
        intent_breakdown={s.intent: s.score for s in scores}
    )
```

### 2.5 Acceptance gate

- Human IRR study on 30 chats: Cohen's κ ≥ 0.70 across intents (per Item #5 in v3.22)
- MAE ratchet holds per-intent (currently 0.2994 overall on 26-chat gold corpus)
- Ablation: holistic vs. intent-aware on 28 gold chats → expect MAE improvement on EC (current 0.41)
- No regression on dimensions where intent-conditioning is uniform (e.g., AL)

### 2.6 Rung

**MEASURABLE** (once G-study clears with ≥30 subjects)

### 2.7 Estimated work

2–3 engineer-weeks for CE, gate-locked at three commits per step.

---

## 3. ADR-0016 — Pre-Filter Eligibility Gate

**Integration Point:** New stage between Stage 2 (intent tagging) and Stage 5 (judge scoring)
**Files:** `src/classifier/eligibility_gate.py` (new), `neurons/neuron_task_eligibility.yaml` (new), `src/aggregator/dimension_aggregator.py` (modified)
**Source patterns:** Item #12 v3.22 (Behavioral Capability Specification), §7.1a (structural NA discipline)

### 3.1 Problem

The pipeline scores **all 107 neurons on every chat**, regardless of whether the task structure can elicit those behaviors.

**Concrete example:** CA-16 (Override Capability) measures whether the user pushes back on the AI. In an EXTRACT task ("summarize this for me"), there is nothing to push back on. Scoring CA-16 yields meaningless output — either an inflated score (judge defaults positive) or noise.

**Cost-side consequences:**
- 107 sequential judge calls (currently) instead of ~40 elicitable ones
- ~3× unnecessary API spend
- 60% of NA values are structural (cannot fire) but indistinguishable from behavioral NA (could fire, did not)

**Measurement-side consequences:**
- Structural NAs dilute reliability (CI widens needlessly)
- Aggregation cannot weight "this neuron is N/A because the task did not call for it" differently from "this neuron is N/A because the user failed to engage"
- The EC MAE = 0.41 issue (above per-dim target) likely stems partly from EC being scored on tasks where it is structurally NA

### 3.2 Decision

Introduce a pre-filter eligibility gate between intent tagging and judge scoring. The gate consults a `neuron_task_eligibility.yaml` matrix that specifies which neurons can fire under which intent tags.

### 3.3 The eligibility matrix

```yaml
# neurons/neuron_task_eligibility.yaml
eligibility_matrix:
  EC-5:
    name: "Verifies claims independently"
    triggers_on:
      - VERIFY
      - OVERRIDE
      - SELF_AUDIT
    absent_in:
      - EXTRACT
      - CLARIFY
      - INJECT_CONTEXT
  
  CA-16:
    name: "Pushes back on AI"
    triggers_on:
      - OVERRIDE
      - PIVOT
      - SELF_AUDIT
    absent_in:
      - EXTRACT
      - INJECT_CONTEXT
      - DECOMPOSE
      - CLARIFY
  
  CS-8:
    name: "Integrates across sources"
    triggers_on:
      - VERIFY
      - EXTRACT
      - INJECT_CONTEXT
      - DECOMPOSE
    absent_in:
      - CLARIFY
  
  CD-11:
    name: "Generates orthogonal ideas"
    triggers_on:
      - DECOMPOSE
      - ABSTRACT
      - PIVOT
    absent_in:
      - VERIFY
      - EXTRACT
      - CLARIFY
  
  # ... 103 more entries, one per neuron
```

The matrix is built by reviewing each of 107 neurons against the 10 intent tags. Estimated work: 4-6 hours for systematic review by domain owner.

### 3.4 Gate implementation

```python
# src/classifier/eligibility_gate.py
from typing import List, Set
import yaml

class EligibilityGate:
    def __init__(self, matrix_path: str):
        with open(matrix_path) as f:
            self.matrix = yaml.safe_load(f)['eligibility_matrix']
    
    def determine_scorable_neurons(
        self, 
        task_intents: List[str],
        phase: str = None
    ) -> Set[str]:
        """
        Returns the subset of 107 neurons that can fire given the task's intents.
        """
        scorable = set()
        
        for neuron_id, spec in self.matrix.items():
            can_fire = any(
                intent in spec['triggers_on'] 
                for intent in task_intents
            )
            if can_fire:
                scorable.add(neuron_id)
        
        return scorable
    
    def classify_na_reason(
        self, 
        neuron_id: str, 
        task_intents: List[str]
    ) -> str:
        """
        Distinguishes STRUCTURAL_NA from BEHAVIORAL_NA.
        """
        spec = self.matrix[neuron_id]
        if any(i in spec['triggers_on'] for i in task_intents):
            return "BEHAVIORAL_NA"  # Could fire, did not
        else:
            return "STRUCTURAL_NA"  # Cannot fire in this task
```

### 3.5 Pipeline integration (Stage 5 modification)

```python
# src/scorer/scorer.py — modified
def score_chat(chat: Chat) -> ChatScore:
    # Stage 2: intent tagging (existing)
    intents = intent_tagger.tag_turns(chat.turns)
    
    # NEW Stage 2.5: eligibility gate
    gate = EligibilityGate("neurons/neuron_task_eligibility.yaml")
    scorable_neurons = gate.determine_scorable_neurons(intents)
    
    # Stage 5: score only elicitable neurons
    scores = {}
    for neuron_id in scorable_neurons:
        scores[neuron_id] = judge.score(
            neuron_id=neuron_id,
            transcript=chat.transcript,
            rubric=RUBRIC_BANK[neuron_id][primary_intent_for(neuron_id, intents)]
        )
    
    # Mark non-scorable as STRUCTURAL_NA
    for neuron_id in ALL_107_NEURONS - scorable_neurons:
        scores[neuron_id] = NeuronScore(
            value=None,
            status="STRUCTURAL_NA",
            reason=f"Task intents {intents} do not elicit {neuron_id}"
        )
    
    return ChatScore(neuron_scores=scores, intents=intents)
```

### 3.6 Aggregator changes

```python
# src/aggregator/dimension_aggregator.py — modified
def aggregate_dimension(
    neuron_scores: Dict[str, NeuronScore], 
    dimension: str
) -> DimensionScore:
    trait_scores = []
    structural_nas = []
    behavioral_nas = []
    
    for neuron_id, score in neuron_scores.items():
        if neuron_id not in DIMENSION_MAP[dimension]:
            continue
        
        if score.status == "SCORED":
            trait_scores.append(score.value)
        elif score.status == "STRUCTURAL_NA":
            structural_nas.append(neuron_id)
        elif score.status == "BEHAVIORAL_NA":
            behavioral_nas.append(neuron_id)
    
    return DimensionScore(
        value=np.mean(trait_scores) if trait_scores else None,
        n_scored=len(trait_scores),
        n_structural_na=len(structural_nas),
        n_behavioral_na=len(behavioral_nas),
        validity_note=(
            f"Dimension {dimension}: "
            f"{len(trait_scores)} measured, "
            f"{len(structural_nas)} structurally ineligible, "
            f"{len(behavioral_nas)} behaviorally absent"
        )
    )
```

### 3.7 Acceptance gate

- Cost reduction: 107 → ~40 judge calls per chat (60%+ reduction expected)
- EC MAE improvement on gold corpus (currently 0.41; target ≤0.30 on VERIFY-dominant chats after gating)
- No regression on overall MAE ratchet (≤0.2994)
- Structural vs. behavioral NA distribution per task type documented
- Migration script: backfill structural/behavioral NA classification on existing 26-chat gold scores

### 3.8 Migration 017

Add columns:
- `neuron_score.na_status` (ENUM: SCORED, STRUCTURAL_NA, BEHAVIORAL_NA)
- `neuron_score.na_reason` (TEXT)
- `chat_score.scorable_neuron_count` (INT)

### 3.9 Rung

**MEASURABLE** (matrix is a behavioral capability specification; conformance-based, not norm-referenced)

### 3.10 Estimated work

1 engineer-week for CE:
- 4-6h: build matrix (107 neurons × 10 intents)
- 2h: implement gate
- 1h: modify Stage 5
- 1h: modify aggregator
- 2h: write migration 017
- 1d: validate on gold corpus

---

## 4. ADR-0017 — Reject External Integrations

This ADR documents the rejection of three external integration proposals and the partial acceptance of three others.

### 4.1 Rejected: IANVS (KubeEdge benchmarking framework)

**Original claim:** Benchmarking infrastructure, reproducible evaluation, CI regression testing.

**Rejection reason:** IANVS is designed for edge-AI ML benchmarking (federated learning, distributed model evaluation). Its primitives (test envs, paradigms, story managers) assume benchmarking *model performance* on *labeled tasks*. SAF/ARI's validation problem is psychometric (G-study with ≥30 subjects, MAE ratchet on gold corpus, OSF pre-registration, DIF testing, EFA, retention probes), not ML-benchmark. Adopting IANVS would shoehorn psychometric validation into the wrong abstraction.

**Already built (correct alternative):** Gold corpus (26 chats) + MAE ratchet in CI.

**Status:** Rejected. Document in `PROPOSALS.md`.

### 4.2 Rejected: ChatGPMe (persistent vector DB over sessions)

**Original claim:** Semantic memory, persistent vector indexing, retrieval.

**Rejection reason:** Three violations:

1. **The Wall.** Indexing scored sessions for retrieval builds a system that retrospectively constructs validated-looking patterns from MEASURED-tier data. Schema-level claims-gating exists to prevent exactly this.
2. **Ontology freeze (§14.3).** Semantic retrieval over neuron firings invites "discovered" constructs, which the freeze forbids until diverse corpus + EFA.
3. **DPDP / data-dignity (Δ9).** Persistent embeddings of student transcripts are a compliance landmine.
4. **Solves a problem not present.** Retrieval need is the 26-chat gold corpus + per-session event log replay, not semantic search over behavioral history.

**Status:** Rejected. Document in `PROPOSALS.md` as "rejected: violates Wall semantics and DPDP posture."

### 4.3 Rejected: chatgpt-prompt-evaluator

**Original claim:** Evidence gating, evaluator-before-judge architecture.

**Rejection reason:** This repo is a single system prompt for jailbreak filtering, not an evaluator framework. The architectural pattern desired (evidence extraction → validation → scoring) is already in v3.22 spec as Item #2 (per-criterion calls + anchored rubric).

**Better references for evaluator-before-judge architecture:**
- G-Eval (Liu et al., 2023) — chain-of-thought scoring with explicit criteria decomposition
- Prometheus 2 (Kim et al., 2024) — fine-grained rubric-based LLM evaluators

**Status:** Rejected as proposed; reference replacement in ADR-0015.

### 4.4 Partially accepted: vibe-log-cli (event sourcing patterns)

**Status:** Read patterns, do not import code. Universal Event Log (Δ3, §5.9a) is already in build deltas. CE reads its event log schema and sync protocol, writes one-page mapping ADR.

### 4.5 Partially accepted: gpt-chat-analysis (incremental processing)

**Status:** One engineer-hour reading incremental-processing checkpoint logic. Directly relevant to current pipeline-break audit (idempotent re-entry pattern). No code import.

### 4.6 Partially accepted: chatgpt-usage-analyzer (UI inspiration)

**Status:** Use for Settings/Profile/operational dashboard (S8–S10 surfaces only). Do not mix with Portfolio radar (D-024) which follows your cognitive analytics design language.

### 4.7 New references adopted

| Need | Reference | Purpose |
|------|-----------|---------|
| Item #1 cascaded selective evaluation | `confident-ai/deepeval` or `microsoft/promptflow` | Variance-based escalation natively |
| Item #3 IRT diagnostics (GRM fitting) | `eribean/girth` or `philchalmers/mirt` via rpy2 | GRM, partial credit, IRT for ordinal responses |
| Item #8 two-table event log | `crate-py/eventsourcing` | Battle-tested Python event sourcing |
| P4 Snorkel orchestrator | `snorkel-team/snorkel` + `HazyResearch/metal` | Multi-task weak supervision |
| P5 Hierarchical Bayesian GRM | `pymc-devs/pymc` + `bambinos/bambi` | Partial pooling for sparse sessions |
| Cost cascade (Item #1) | `stanford-futuredata/FrugalGPT` | Reference implementation |
| Task-oriented evaluation patterns | TD-EVAL paper (Acikgoz et al., 2025) | Turn-level evaluation architecture |
| Task-specific rubric generation | RUBICON paper (Microsoft Research, 2024) | Domain-sensitized rubric generation |

---

## 5. Implementation Sequence (Gate-Locked)

### 5.1 This week: resolve pipeline break (blocking everything else)

**No external integration on top of broken storage.** Audit must complete first.

1. ✅ Finish audit on `src/db/queries.py` completeness gates
2. ✅ Confirm which endpoint the extension's API client calls (network interception path)
3. ✅ Identify the storage break (chats scoring but not persisting)
4. ✅ Verify Wall enforcement at API schema level end-to-end
5. ✅ Push the three local-only commits at `32fe186`

**Gate:** Audit findings document + fixes applied + LGTM before any new work begins.

### 5.2 Sprint 1: parallelization fix + eligibility gate

**Critical performance bug first:**
1. Fix `score_all_neurons` to actually run parallel (currently 107 sequential despite description)
2. Add Item #1 cascaded selective evaluation pattern (deepeval reference)

**Then eligibility gate (ADR-0016):**
3. Build `neuron_task_eligibility.yaml` (4-6h: 107 neurons × 10 intents)
4. Implement `eligibility_gate.py` (2h)
5. Modify Stage 5 to call gate (1h)
6. Modify aggregator for STRUCTURAL_NA vs BEHAVIORAL_NA (1h)
7. Write migration 017 (2h)
8. Validate on gold corpus (1d)

**Gate per ADR-0016 §3.7:**
- 60%+ cost reduction confirmed
- EC MAE improvement on VERIFY-dominant chats
- No regression on overall MAE ratchet ≤0.2994

### 5.3 Sprint 2: task-oriented neuron scoring (ADR-0015)

1. Read TD-EVAL paper §3 and §5 (architecture + turn-level dimensions)
2. Read RUBICON paper (domain-sensitized rubric generation)
3. Build `rubric_bank_v2.py` with intent-specific rubric anchors
4. Modify judge call signature to accept `intent_context`
5. Build `intent_aggregator.py` for CSPC-weighted precision pooling
6. Ablation study: holistic vs. intent-aware on 28 gold chats

**Gate per ADR-0015 §2.5:**
- Cohen's κ ≥ 0.70 across intents (Human IRR study, 30 chats)
- MAE ratchet holds per-intent
- Documented improvement on EC MAE

### 5.4 Sprint 3: E→R taxonomy + Friction Transition Matrix (Item #8)

1. Map 10 intent tags as E (Events) in E→R taxonomy
2. For each intent × dimension, define expected reaction patterns
3. Generate Friction Transition Matrix (state changes after VERIFY failure vs. success)
4. Wire into event log (Δ3)

### 5.5 Sprint 4: corpus collection go/no-go decision

This decision cascades into P3 cascade router, P5 hierarchical GRM, P7 distillation, P8 SynergyAPI contracts. Defer all downstream work until corpus is collected or explicitly deferred.

---

## 6. Non-Negotiables (Inherited from v3.22 and Earlier)

### 6.1 The Wall

- MEASURED outcomes never claim to be VALIDATED
- VALIDATED outcomes require Layer-4 retention probe evidence
- Enforcement is structural (API response schema), not policy
- Forbidden terminology (e.g., "synergy" in Tracer outputs) raises a schema-level exception

### 6.2 The Ontology Freeze (§14.3)

- ❌ No new neurons
- ❌ No new dimensions
- ❌ No new pillars
- ❌ No new latent variables
- ✅ Permitted: new fields on existing neurons, measurement-engine fixes, calibration work, corpus collection, validation

**Freeze compliance audit:** Every ADR in this document audited against §14.3. Totals:
- ADR-0015: 0 new neurons, 0 new dimensions (adds intent-conditioning to existing rubrics; permitted)
- ADR-0016: 0 new neurons, 0 new dimensions (adds eligibility metadata to existing neurons; permitted)
- ADR-0017: rejections only

### 6.3 The CSPC/ARI Partition (§2.1)

State-channel features and trait-channel neurons must remain disjoint. Eligibility gate operates on trait-channel only; CSPC state inference runs on the disjoint state channel and feeds precision weights to the trait-channel scorer.

### 6.4 MAE Ratchet (CI Enforcement)

- Current: overall MAE ≤ 0.2994 on 26-chat gold corpus
- Per-dimension targets in v3.22 §8.5
- Any code change must hold the ratchet or be reverted

### 6.5 Gate-Locked Delivery Discipline

Every engineering step requires three commits:
1. Implementation
2. Tests
3. ADR

Followed by explicit LGTM or REWORK with file:line references before proceeding to the next step. No exceptions.

---

## 7. Open Questions Requiring Human Decision

These items are flagged for Vaibhav's decision before implementation begins:

1. **Eligibility matrix authorship.** Who builds the initial `neuron_task_eligibility.yaml`? Recommendation: Vaibhav drafts (4-6h), Ritesh reviews, CE validates against gold corpus.

2. **Per-intent rubric authorship.** For ADR-0015, who writes the intent-specific rubric anchors? Recommendation: auto-generate via RUBICON-style prompt, seeded with 3-5 hand-written examples per neuron, human-review before merge.

3. **EC dimension MAE remediation.** Does the eligibility gate alone fix the EC = 0.41 issue, or does it also require Item #2's per-criterion calls? Recommendation: implement gate first, re-measure EC MAE, then decide whether Item #2 needs to proceed independently.

4. **Cost cascade decision.** Adopt deepeval or roll a thin in-house cascade implementation? Recommendation: deepeval if it can be vendored cleanly; otherwise in-house with ≤200 LOC.

5. **TD-EVAL turn-level dimensions.** The paper defines three (cohesion, backend consistency, policy compliance). How do these map onto our 8 dimensions and 4 pillars? Recommendation: ADR-0015 §2.3 maps onto existing dimensions; no new dimension introduced.

---

## 8. Files to Create or Modify

### New files

```
neurons/neuron_task_eligibility.yaml             # ADR-0016 §3.3
src/classifier/eligibility_gate.py               # ADR-0016 §3.4
src/trait/judge/rubric_bank_v2.py                # ADR-0015 §2.3
src/scorer/intent_aggregator.py                  # ADR-0015 §2.4
tests/test_eligibility_gate.py                   # ADR-0016
tests/test_intent_scoring.py                     # ADR-0015
adr/ADR-0015-task-oriented-neuron-scoring.md
adr/ADR-0016-pre-filter-eligibility-gate.md
adr/ADR-0017-reject-external-integrations.md
migrations/017_eligibility_metadata.sql
```

### Modified files

```
src/scorer/scorer.py                             # ADR-0016 §3.5
src/aggregator/dimension_aggregator.py           # ADR-0016 §3.6
src/trait/judge/prompt.py                        # ADR-0015 §2.3
src/trait/judge/client.py                        # ADR-0015 signature change
src/db/queries.py                                # NA status persistence
PROPOSALS.md                                     # Rejection documentation
```

### Files explicitly NOT to touch

```
neurons/contract_table.yaml          # Ontology frozen
data/neurons/neurons_v6.json         # Ontology frozen
calibration/run_calibration.ts       # MAE ratchet logic
gold_standard/                       # Corpus immutable during freeze
```

---

## 9. Acceptance Criteria Summary

| ADR | Acceptance | Owner | Status |
|-----|-----------|-------|--------|
| Pipeline break audit | Findings document + fixes applied | CE | Blocking |
| `score_all_neurons` parallelization | Actually parallel; timing verified | CE | Blocking |
| ADR-0016 eligibility gate | 60% cost reduction + EC MAE improvement | CE | Sprint 1 |
| ADR-0015 task-oriented scoring | Cohen's κ ≥ 0.70 across intents | CE + Psychometrics | Sprint 2 |
| Friction Transition Matrix | E→R taxonomy wired to event log | CE | Sprint 3 |
| Corpus go/no-go | Decision + execution plan | Vaibhav | Sprint 4 |

---

## 10. References

### Project documents
- v3.22 SpecDelta (twelve upgrades)
- v3.21 Unified Master Specification
- SAF/ARI Final Master Compilation v2.2 (§2.1 partition, §14.3 freeze)
- CLAUDE.md (21 non-negotiables)
- AGENTS.md (file ownership)

### External patterns adopted (not imported)
- TD-EVAL — Acikgoz et al. (2025), https://arxiv.org/pdf/2504.19982
- RUBICON — Microsoft Research (2024), https://www.microsoft.com/en-us/research/wp-content/uploads/2024/05/RUBICON__Rubric_Based_Evaluation_of_Domain_Specific_Human_AI_Conversations-10.pdf
- G-Eval — Liu et al. (2023)
- Prometheus 2 — Kim et al. (2024)

### External proposals rejected
- IANVS (KubeEdge benchmarking) — `kubeedge/ianvs`
- ChatGPMe (persistent vector DB) — `keyboardP/ChatGPMe`
- chatgpt-prompt-evaluator — `alignedai/chatgpt-prompt-evaluator`

### External patterns partially adopted (read only)
- vibe-log-cli (event sourcing patterns)
- gpt-chat-analysis (incremental processing checkpoints)
- chatgpt-usage-analyzer (UI for operational dashboards only)

---

## 11. Closing Discipline

> **Evidence before elegance. Reliability before complexity. Sustainability before synergy.**
>
> *— SAF/ARI Governing Principle, §14.3*

Every change in this document was audited against:
1. The Wall (no MEASURED→VALIDATED crossing)
2. The ontology freeze (§14.3)
3. The CSPC/ARI partition (§2.1)
4. The MAE ratchet (≤0.2994)
5. The gate-locked delivery discipline (three commits per step)

Zero violations. Ready for CE kickoff.

**End of v3.23 implementation specification.**

---

## Appendix R — Reality Reconciliation (vs. repo @ `6c2e844`, 2026-06-30)

> The body above was written against an assumed tree. A trace of the live repo
> found five mismatches that change the plan. The body is **kept verbatim**;
> this appendix is the authoritative correction where they conflict.

### R.1 The "parallelization bug" does not exist — strike it

§1.2 and §5.2 item 1 claim `score_all_neurons` "runs 107 **sequential** LLM
calls." It does not. `_score_all_neurons_async` already fans out with
`asyncio.gather(*tasks)` (`src/trait/judge/per_criterion.py:368`), and the
FIX-1 replication path uses `gather` too (`:437`, `:460`). **Remove "fix
parallelization" from Sprint 1.** The remaining Sprint-1 perf lever is the
cost *cascade* (FrugalGPT-style escalation), which is a different thing and
stays as proposed.

### R.2 Every file path in the spec is invented — use the real ones

| Spec path (does not exist) | Real path |
|---|---|
| `src/scorer/scorer.py` | `src/api/pipeline.py` (`score_session_with_artifacts`) |
| `src/aggregator/dimension_aggregator.py` | `src/aggregate/normalize.py` |
| `src/classifier/eligibility_gate.py` | `src/aggregate/eligibility_gate.py` (new, real package) |
| `src/scorer/intent_aggregator.py` | `src/trait/judge/intent_aggregator.py` (new) |
| `src/trait/judge/rubric_bank_v2.py` | OK — `src/trait/judge/` exists |

`neurons/` is also not the live neuron home — confirm against
`contracts/contract_table.yaml` / `data/neurons/` before adding a matrix file.

### R.3 ADR numbers collide — renumber 0015/0016/0017 → 0017/0018/0019

`adr/` already contains **two** 0015s and **two** 0016s (e.g.
`0015-phase-2-cspc-weighted-aggregation.md`,
`0016-phase-1b-async-dimension-batching-cascade.md`). Next free is **0017**:

- ADR-0017 → **Reject external integrations** (was "0017")
- ADR-0018 → **Task-oriented neuron scoring** (was "0015")
- ADR-0019 → **Pre-filter eligibility gate** (was "0016")

### R.4 Example intent tags are partly invalid — the frozen set is fixed

Frozen `IntentTag` (10): `VERIFY, EXTRACT, INJECT_CONTEXT, OVERRIDE,
SELF_AUDIT, DELEGATE, SCAFFOLD, PIVOT, DECOMPOSE, ACCEPT_FLAT`.

- `CLARIFY` and `ABSTRACT` in §3.3 examples **do not exist** — drop or remap.
- `PIVOT` is valid (keep).
- The spec **never uses `DELEGATE` or `ACCEPT_FLAT`** — the two tags most
  directly tied to cognitive offloading. Any eligibility matrix that omits
  them is incomplete; every neuron's `triggers_on`/`absent_in` must be
  authored against all 10 real tags.

### R.5 Gating status — what is buildable now vs. blocked

| ADR (renumbered) | Buildable now? | Blocker |
|---|---|---|
| 0017 Reject integrations | ✅ Yes — pure docs | none |
| 0019 Eligibility gate (code) | ⚠️ Gate code yes; **matrix content no** | matrix = domain authoring (§7 Q1, yours); acceptance is gold-corpus gated |
| 0018 Task-oriented scoring | 🔒 Stub only | rung MEASURABLE needs G-study n≥30; corpus n=26 → `data-gated means stubbed` |
| Migration 017 | ⚠️ Schema only | renumber to next free migration; backfill is corpus work |

**Sequencing implied by R.5:** ADR-0017 docs → eligibility-gate code against
real paths (matrix stubbed, raises until authored) → everything else gated.
The §7 human decisions remain prerequisites for the gated items.

**End of Appendix R.**
