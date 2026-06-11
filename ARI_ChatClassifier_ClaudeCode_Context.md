# ARI Framework — Complete Context for Claude Code
## Chat Classifier v2 Implementation Reference
**Version:** 6.0 FINAL | **Status:** Active Development | **Date:** June 2026

---

## PART 0 — HOW TO USE THIS DOCUMENT

This file is the **single source of truth** for Claude Code when implementing any part of the Chat Classifier v2. It consolidates everything that was previously split across three project files:

| File | What it contained | Status in this doc |
|---|---|---|
| `Ritesh_s_Notes_1` | All 107 neuron definitions (v6.0 FINAL) | ✅ Fully included — Part 3 |
| `Ritesh_Notes2.pdf` | Framework architecture, layer rationale, weighting approach, OECD alignment, implementation decisions | ✅ Fully included — Part 1 & 2 |
| `The_seed_is_planted_1.pdf` | Research justification, NLP feature operationalizations, scoring signals per dimension | ✅ Fully included — Part 4 |

**Critical note on neuron count:** The master summary table states 106 neurons. The actual v6.0 taxonomy contains **107 neurons** — CA-17 (Vigilance Sustainment) was added as a v6 addition but the summary header was not updated. CA-17 is canonical and must be included. All 107 are listed in Part 3.

---

## PART 1 — WHAT WE ARE BUILDING

### The Problem
Traditional AI literacy assessments ask people what they think they can do (surveys, self-report). These are systematically unreliable because users suffer from metacognitive inflation — they rate themselves higher than their actual behavior demonstrates. The core pathology we are detecting is **"fluent incompetence"**: users who produce high-quality-sounding AI interactions but are cognitively outsourcing rather than augmenting. You cannot detect this from a survey. You can only detect it from behavioral trace analysis of a live transcript.

### What the Chat Classifier v2 Does
It takes a raw human-AI chat transcript as input and outputs:
1. A score on each of 8 ARI dimensions (0–100)
2. A score on each of 107 behavioral neurons (the fine-grained inputs)
3. A composite **Synergy Portfolio Score (κ)**
4. Risk flags: Fluent Incompetence, Cognitive Debt Accumulation, or True Synergy

No self-report. No survey. Purely behavioral trace analysis.

### Why This Matters Scientifically
Steyvers et al. (2022) mathematically proved that human-AI hybrid teams outperform either agent alone — but only when humans maintain independent judgment. Our classifier detects whether that independence is real or illusory. The complementarity bound (κ) is a falsifiable criterion: if κ exceeds the bound, genuine synergy exists; if it doesn't, we have substitution disguised as collaboration.

---

## PART 2 — ARCHITECTURE

### The 4-Layer Hierarchy (Top-Down)

```
RAW TRANSCRIPT
     ↓  [NLP Intent Scanner + LLM Judge]
LAYER 0 — 4 Latent Constructs (the true independent factors)
     ↓  [branches into]
LAYER 1 — 8 ARI Dimensions (mid-level traits)
     ↓  [computed from]
LAYER 2 — 107 Behavioral Neurons (fine-grained observables)
     ↓  [aggregated via Bayesian IRT]
SYNERGY PORTFOLIO SCORE (κ)
```

### The 4 Latent Constructs

These are the genuinely independent foundational factors. The 8 ARI dimensions are their branches, not independent entities.

| Construct | Maps to OECD/PISA | Maps to AILit | ARI Dimensions |
|---|---|---|---|
| **Foundational Interaction** | Engage | Engaging with AI | AL + PR |
| **Critical Evaluation** | Manage | Managing AI | EC + ES |
| **Integrative Synthesis** | Create | Creating with AI | CS + CD |
| **Executive Control** | Design | Designing AI | AUI + CA |

**OECD alignment is not cosmetic.** This mapping means the framework is pre-validated against two existing international frameworks (OECD/PISA and AILit) before collecting a single data point. This is the external validation anchor.

### The 8 ARI Dimensions and Their Neuron Counts

| Code | Dimension | Layer | Neurons | Primary Risk Signal |
|---|---|---|---|---|
| AL | AI Literacy | Engage | 13 | Fluent incompetence baseline |
| PR | Prompt Reasoning | Engage | 15 | Surface-level chatting vs. engineering |
| EC | Error Correction | Manage | 14 | **Highest weight** — blind trust detection |
| ES | Ethics Sensitivity | Manage | 14 | Accountability diffusion |
| CS | Contextual Synthesis | Create | 11 | **Highest weight** — cognitive offloading |
| CD | Creative Divergence | Create | 11 | Statistical homogenization |
| AUI | Augmentation Instinct | Design | 12 | Skill atrophy / dependency risk |
| CA | Collaborative Agency | Design | 17 | Psychological sovereignty |
| **TOTAL** | | | **107** | |

**Weighting rule:** EC and CS are the highest-risk dimensions. If a user scores low on both EC and CS simultaneously, the classifier MUST trigger a **Fluent Incompetence** flag regardless of how high their PR score is. A sophisticated prompter who never verifies is the core pathology.

### Bayesian IRT Scoring Engine

The scoring is not a simple weighted average. It uses Bayesian Item Response Theory:

- Each user gets a personalized prior **θᵢ** initialized from their demographic baseline before any interaction
- θᵢ controls for variance from educational background, domain expertise, and prior AI exposure
- This ensures we are isolating genuine collaborative synergy rather than measuring underlying ability
- The final κ score is compared against the Steyvers et al. complementarity bound as a falsifiable criterion
- Start: do not hardcode weights. Train weights from behavioral data. Pre-seeding weights introduces bias before the model has seen domain variance.

### Three Output States

| Output | Condition | Meaning |
|---|---|---|
| **Fluent Incompetence** | High PR + Low EC + Low CS | User appears sophisticated, actually offloading |
| **Cognitive Debt Accumulation** | Verification Ratio below threshold across session | Critical thinking degrading over time |
| **True Synergy** | κ exceeds Steyvers complementarity bound | Human-AI hybrid outperforming either alone |

---

## PART 3 — ALL 107 NEURONS (v6.0 FINAL, COMPLETE)

This is the authoritative taxonomy. Every neuron has a code, name, definition, and version number.

---

### LAYER 1 — Foundational Interaction (ENGAGE)

---

#### ARI 1: AI Literacy (AL) — 13 Neurons

| Code | Neuron | Version |
|---|---|---|
| AL-01 | **Probabilistic Reasoning Calibration** — The mental ability to distinguish a model's linguistic confidence from factual accuracy, preventing fluency from being mistaken for correctness. | v1 |
| AL-02 | **Algorithmic Mechanism Grasp** — The foundational understanding that AI derives answers via statistical pattern completion, not logical deduction or true world-modeling. | v1 |
| AL-03 | **Context Window Awareness** — The mental tracking and anticipation of memory degradation over extended interactions, enabling proactive re-anchoring of critical context. | v1 |
| AL-04 | **Structural Brittleness Anticipation** — The foresight to predict exactly where an AI will break nested data, complex formatting, deep conditionality, or recursive logic. | v1 |
| AL-05 | **Domain-Grounding Aptitude** — The instinct to establish a specific knowledge environment and custom parameters before directing AI to execute on specialized or sensitive tasks. | v1 |
| AL-06 | **Stochastic Output Variance Awareness** — Understanding that identical prompts can produce meaningfully different outputs across invocations, requiring probabilistic rather than deterministic expectations of AI behavior. | v3 |
| AL-07 | **Capability Boundary Mapping** — The active mental cartography of what a specific AI model can reliably execute versus where its performance characteristically degrades across task types and domains. | v3 |
| AL-08 | **Training Data Recency Sensitivity** — The awareness of a model's knowledge cutoff and the instinct to automatically flag temporally sensitive claims and time-indexed data for independent verification. | v3 |
| AL-09 | **Model-Task Fit Assessment** — The meta-judgment to evaluate whether a given AI model's architecture, training modality, and capability profile is genuinely appropriate for the specific task. | v3 |
| AL-10 | **AI Epistemic State Modeling** — The capacity to mentally simulate what information the AI does and does not have access to within its current context window, enabling accurate prediction of its likely failure modes before output is generated. | v3/v5 |
| AL-11 | **Multi-modal Situational Literacy** — The calibrated understanding that AI processes images, code, audio, structured data, and natural language with fundamentally different reliability profiles and failure modes, enabling proportionally adjusted verification depth per modality. | v4 |
| AL-12 | **System Constraint Awareness** — The awareness that AI operates under invisible instruction layers — system prompts, safety filters, alignment fine-tuning — that create predictable behavioral boundaries, enabling the user to distinguish constraint-imposed refusal from genuine capability failure. | v4 |
| AL-13 | **Prompt Injection Vulnerability Awareness** — The security-oriented cognitive awareness that when AI systems process externally sourced content — web pages, emails, uploaded documents, API responses — malicious instructions embedded in that content can silently hijack the AI's subsequent behavior, enabling the user to implement appropriate sandboxing and source verification protocols. | v5 |

---

#### ARI 2: Prompt Reasoning (PR) — 15 Neurons

| Code | Neuron | Version |
|---|---|---|
| PR-01 | **Negative Constraint Application** — The ability to explicitly define exclusion parameters — what the AI must not produce, assume, or include — to surgically eliminate unwanted output space. | v1 |
| PR-02 | **Cognitive Scaffolding** — Structuring a directive to force the AI into sequential, multi-step reasoning rather than collapsing to a single-shot probabilistic guess. | v1 |
| PR-03 | **Contextual Density Optimization** — Calibrating the precise ratio of background context against the core directive to maximize signal-to-noise without overwhelming AI generative focus. | v1 |
| PR-04 | **Strategic Query Pivoting** — The cognitive flexibility to entirely abandon a failed linguistic framing and reconstruct the query from a structurally different angle rather than repeating the same failed approach. | v1 |
| PR-05 | **Output Topology Definition** — The ability to mentally visualize and explicitly command the desired structural architecture of the final output before generation begins. | v1 |
| PR-06 | **Persona Anchoring** — The strategy of defining a specific expert role, knowledge frame, or epistemic posture for the AI to inhabit to modulate the character of its reasoning. | v1 |
| PR-07 | **Inductive Example Provisioning** — The foresight to supply "few-shot" pattern templates that establish desired output behavior through concrete demonstration rather than abstract instruction. | v1 |
| PR-08 | **Decomposition Precision** — The ability to atomize complex, multi-faceted goals into minimal, non-overlapping sub-tasks before delegation, ensuring each AI invocation has a single unambiguous objective. | v3 |
| PR-09 | **Constraint Hierarchy Definition** — When operating under multiple competing directives, the ability to explicitly rank constraint priority so the AI resolves conflicts in a predictable, intended manner. | v3 |
| PR-10 | **Ambiguity Pre-emption** — The foresight to identify semantic misinterpretation points in a directive before submission and proactively resolve lexical or referential ambiguity that could derail output quality. | v3 |
| PR-11 | **Verification Checkpoint Embedding** — The discipline of building explicit self-audit instructions into the directive itself, directing AI to test its own output against specified criteria before concluding. | v3 |
| PR-12 | **Iterative Refinement Patience** — The cognitive disposition to treat prompt construction as a progressive, multi-cycle optimization process, tolerating refinement loops without premature closure. | v3 |
| PR-13 | **Semantic Precision Sensitivity** — The fine-grained awareness that minor lexical choices — synonyms, verb tense, quantifiers, presuppositions — can produce dramatically divergent AI outputs, driving deliberate word-level optimization beyond mere clarity. | v4 |
| PR-14 | **Recursive Self-Critique Elicitation** — The meta-prompting strategy of directing the AI to adversarially evaluate its own prior output, engineering an endogenous quality-control loop before human review. | v4 |
| PR-15 | **Parallel Task Architecture** — The cognitive ability to identify, within a decomposed task set, which sub-tasks are logically independent and can be dispatched to AI simultaneously rather than sequentially, multiplying workflow throughput by explicitly exploiting parallelism. | v5 |

---

### LAYER 2 — Critical Evaluation (MANAGE)

---

#### ARI 3: Error Correction (EC) — 14 Neurons ⚠️ HIGHEST WEIGHT

| Code | Neuron | Version |
|---|---|---|
| EC-01 | **Factual Hallucination Detection** — The active cognitive vigilance to identify fabricated, confabulated, or misattributed information presented by AI with the surface texture of established fact. | v1 |
| EC-02 | **Syntactical & Structural Debugging** — The analytical capability to identify logic gaps, missing steps, broken dependencies, or code misalignments in AI-generated procedural or technical output. | v1 |
| EC-03 | **Internal Contradiction Recognition** — Catching conflicting logic, changing premises, mutually exclusive claims, or self-negating arguments within a single AI response. | v1 |
| EC-04 | **Algorithmic Traceability** — The mental capacity to step backward through AI-generated logic to identify the precise origin of an error within a single output. | v1 |
| EC-05 | **Physical & Spatial Logic Verification** — Validating AI textual descriptions of physical laws, spatial relationships, systems logic, or geometric properties against actual real-world constraints. | v1 |
| EC-06 | **Isolated Verification Rigor** — The disciplined habit of testing AI-generated claims, code, or logic in a conceptually isolated sandbox before integrating into live production. | v1 |
| EC-07 | **Omission Detection** — The active vigilance to identify content the AI silently left out of its reasoning within a single response — missing qualifications, absent steps, truncated logic. *(Scope: single-output reasoning completeness only. Distinct from EC-13 and EC-14.)* | v3/v6 |
| EC-08 | **Statistical Plausibility Assessment** — The rapid mental heuristic to evaluate whether numerical claims, statistics, and quantitative outputs pass an order-of-magnitude sanity check before acceptance. | v3 |
| EC-09 | **Temporal Coherence Validation** — Verifying that AI-generated sequences, timelines, causal chains, and chronological narratives maintain logically consistent temporal ordering and directional causality. | v3 |
| EC-10 | **Scope Boundary Enforcement** — The vigilance to detect when AI output has silently expanded beyond explicitly defined task parameters, adding unrequested scope that introduces unreviewed risk. | v3 |
| EC-11 | **Confidence-Accuracy Decoupling** — The disciplined resistance to treating assertive, fluent AI output as implicitly more accurate — maintaining uniform critical scrutiny regardless of surface-level linguistic confidence. | v3 |
| EC-12 | **Error Propagation Tracing** — The ability to recognize that an error seeded in an early AI-generated step has cascaded through downstream outputs that appear locally consistent but are systemically compromised. | v4 |
| EC-13 | **Edge Case Coverage Audit** — The systematic enumeration of boundary conditions, exceptional inputs, and minority scenarios that AI's statistically-anchored defaults may have silently excluded from its solution space. | v4 |
| EC-14 | **Hidden Assumption Excavation** — The disciplined cognitive habit of actively surfacing and challenging the invisible load-bearing premises that an AI's reasoning chain depends on but never explicitly states — recognizing that AI outputs routinely inherit unstated axioms from training data as if they were self-evident, when they may be domain-specific, culturally contingent, or simply incorrect. | v5 |

---

#### ARI 4: Ethics Sensitivity (ES) — 14 Neurons

| Code | Neuron | Version |
|---|---|---|
| ES-01 | **Privacy & Anonymization Foresight** — The instinctual habit of mentally filtering and stripping PII and confidential organizational information before it enters an AI interaction. | v1 |
| ES-02 | **Demographic & Cultural Bias Detection** — Identifying skewed assumptions, statistical stereotyping, or cultural blindness embedded in AI reasoning or generated content. | v1 |
| ES-03 | **Regulatory Compliance Adherence** — Evaluating AI outputs strictly against external legal, safety, professional, or enterprise governance frameworks. | v1 |
| ES-04 | **Epistemic Vigilance** — The principled refusal to accept AI as a primary authority, coupled with the reflexive habit of cross-referencing AI claims against true primary sources. | v1 |
| ES-05 | **Intellectual Property Sensitivity** — Recognizing when AI output is likely reproducing, paraphrasing, or structurally deriving copyrighted material or proprietary intellectual work without appropriate transformation. | v1 |
| ES-06 | **Dual-Use Risk Assessment** — Evaluating whether a legitimate AI output could be readily weaponized or cause unintended harm when deployed in a different context or by a different actor. | v3 |
| ES-07 | **Psychological Manipulation Detection** — Identifying when AI-generated persuasive content has crossed from legitimate influence into rhetorical manipulation exploiting cognitive biases or emotional vulnerabilities. | v3 |
| ES-08 | **AI Disclosure Judgment** — The professional instinct to know when transparency about AI's role in producing a work is legally required, organizationally mandated, or morally necessary — and to act accordingly without external prompting. | v3 |
| ES-09 | **Value-Outcome Alignment Verification** — Confirming that AI recommendations are congruent with the human's and organization's actual values and long-term goals, not merely compliant with stated task constraints. | v3 |
| ES-10 | **Autonomy-Preservation Vigilance** — The active awareness that habitual deference to AI judgment erodes independent human decision-making capacity, and the counter-reflex to exercise independent judgment on consequential decisions. | v3 |
| ES-11 | **Accountability Attribution Clarity** — The ethical discipline of explicitly assigning professional, legal, and moral responsibility for an AI-assisted output to a specific human agent before deployment — preventing accountability diffusion. | v4 |
| ES-12 | **Systemic Scale Impact Reasoning** — The capacity to reason beyond the single-use context and evaluate second and third-order societal consequences when the same AI-generated output pattern is deployed at population scale. | v4 |
| ES-13 | **Data Provenance Interrogation** — Critically examining the likely character, composition, and embedded biases of the training data that generated a given AI output, particularly in minority-represented or non-Western domains. | v4 |
| ES-14 | **Consent & Agency Stewardship** — The ethical discipline of verifying that AI-generated outputs representing, characterizing, or directly affecting other human beings genuinely preserve those individuals' consent, autonomy, dignity, and material interests — including in automated contexts where affected parties will never review the output before it acts on them. | v5 |

---

### LAYER 3 — Integrative Synthesis (CREATE)

---

#### ARI 5: Contextual Synthesis (CS) — 11 Neurons ⚠️ HIGHEST WEIGHT

| Code | Neuron | Version |
|---|---|---|
| CS-01 | **Semantic Blending** — Smoothing transitions between human-authored and AI-generated blocks, eliminating tonal discontinuity and disjointedness in the final artifact. | v1 |
| CS-02 | **Dependency Preservation** — Integrating AI output without breaking existing logical dependencies, narrative threads, data pipelines, or structural hierarchies. | v1 |
| CS-03 | **Information Density Pruning** — Stripping verbose, repetitive AI filler to extract only high-signal insights and discard low-value elaboration. | v1 |
| CS-04 | **Authorial Tone Alignment** — Editing AI vocabulary, syntax, cadence, and rhetorical patterns to match a specific, pre-established human or organizational voice. | v1 |
| CS-05 | **Cross-Domain Translation** — Taking highly technical AI output and accurately restructuring it for a non-specialist audience without loss of accuracy. | v1 |
| CS-06 | **Inferential Gap Bridging** — Identifying and explicitly completing logical or contextual gaps that the AI left implicit but which a human reader requires made explicit for coherent comprehension. | v3 |
| CS-07 | **Salience Hierarchy Reconstruction** — Re-ranking AI-generated information by actual domain relevance and impact rather than accepting AI's default statistical co-occurrence ordering. | v3 |
| CS-08 | **Multi-Source Coherence Integration** — Maintaining logical consistency and narrative coherence when synthesizing outputs from multiple AI calls, sessions, or tool modalities. | v3 |
| CS-09 | **Attribution Tracking** — Bookkeeping which specific conceptual contributions, claims, and structural decisions originated from human reasoning versus AI generation within a synthesized artifact. | v3 |
| CS-10 | **Register Modulation** — Calibrating the formality, technicality, cultural register, and assumed shared knowledge of AI-generated content for the specific deployment audience and relational context. | v3 |
| CS-11 | **Uncertainty Transparency Calibration** — Restoring appropriate epistemic hedges and conditionality to AI-generated claims in the final synthesized artifact, counteracting AI's characteristically over-assertive language that strips probabilistic hedging from genuinely provisional information. | v4 |

---

#### ARI 6: Creative Divergence (CD) — 11 Neurons

| Code | Neuron | Version |
|---|---|---|
| CD-01 | **Statistical Homogenization Resistance** — Consciously rejecting the AI's most statistically probable, averaged, and safe response — the active preference for the genuinely interesting over the statistically expected. | v1 |
| CD-02 | **Lateral Concept Injection** — Introducing metaphors, cultural frameworks, emotional nuances, and references that exist outside the AI's training distribution, forcing genuine creative novelty. | v1 |
| CD-03 | **Counter-Factual Probing** — Using hypothetical inversions and "what if" scenarios to actively challenge, stress-test, and expand the AI's initial creative hypothesis. | v1 |
| CD-04 | **Stylistic Idiosyncrasy Retention** — Defending unique human formatting choices, unconventional pacing, personal humor, and edge-case perspectives against AI's normalizing tendency. | v1 |
| CD-05 | **Aesthetic Discernment** — Evaluating AI creative output against an internalized human standard of taste, quality, resonance, and intended emotional impact on the target audience. | v3 |
| CD-06 | **Constraint-Transcendence Instinct** — Recognizing when deliberately violating a stated constraint — breaking a rule by intent — would yield a qualitatively superior creative outcome than strict compliance. | v3 |
| CD-07 | **Narrative Tension Injection** — Deliberately introducing productive conflict, ambiguity, stakes, or irresolution that AI tends to prematurely smooth into safe, harmonious, consensus-seeking resolutions. | v3 |
| CD-08 | **Analogical Novelty Generation** — Producing genuinely novel analogical mappings and cross-domain metaphors that fall outside the statistical co-occurrence patterns of AI training data. | v3 |
| CD-09 | **Surprise Preservation** — Protecting counterintuitive, unexpected, or structurally unconventional creative elements from AI's normalizing tendency to sand them into statistically expected forms. | v3 |
| CD-10 | **Embodied Experience Injection** — Infusing creative or analytical work with authentic sensory, physical, kinesthetic, and visceral experience constitutionally unavailable to AI due to its lack of embodied reality — producing outputs with a quality of felt truth that cannot be statistically generated. | v4 |
| CD-11 | **Audience Empathy Modeling** — Constructing and maintaining a rich, specific mental model of the target audience's emotional state, cognitive load, prior knowledge, and unstated needs, producing work genuinely calibrated to a real human rather than a statistical average. | v4 |

---

### LAYER 4 — Executive Control (DESIGN)

---

#### ARI 7: Augmentation Instinct (AUI) — 12 Neurons

| Code | Neuron | Version |
|---|---|---|
| AUI-01 | **Cognitive Friction Recognition** — Identifying the precise moment a task's complexity, volume, or cognitive demand exceeds the threshold of optimal manual effort, triggering AI delegation. | v1 |
| AUI-02 | **Task-Type Delegation Judgment** — Strategically routing rote, high-volume, or pattern-based work to AI while intentionally reserving high-nuance, high-stakes, or ethically consequential work for human cognition. | v1 |
| AUI-03 | **Modality Appropriateness** — Matching the correct type of AI system — generative, analytical, visual, logical, retrieval-based — to the specific structural requirements of the problem. | v1 |
| AUI-04 | **Interaction ROI Intuition** — Recognizing the tipping point where executing a task through direct human effort becomes more efficient than the compounding cognitive cost of debugging a failing prompt chain. | v1 |
| AUI-05 | **Working Memory Offloading** — The intentional use of AI as an external cognitive scratchpad to externalize intermediate states, freeing human executive function for higher-order strategic reasoning. | v1 |
| AUI-06 | **Cognitive Load Self-Monitoring** — Real-time metacognitive awareness of one's own mental saturation level, enabling strategic offloading to AI at the precise moment of productive overload before performance degrades. | v3 |
| AUI-07 | **Prompt Investment Calibration** — The precise real-time judgment of how much cognitive effort to invest in prompt crafting and refinement versus the expected return in output quality improvement. | v3 |
| AUI-08 | **Dependency Risk Awareness** — The forward-looking recognition that sustained AI delegation for specific task types creates progressive skill atrophy and cognitive fragility in one's own capability profile. | v3 |
| AUI-09 | **Handoff Timing Precision** — The executive judgment of exactly when to reclaim agentic control from an AI mid-task — before unchecked autonomous completion introduces irreversible errors or goal drift. | v3 |
| AUI-10 | **Skill-Gap Self-Awareness** — The metacognitive inventory of one's own knowledge gaps and competency limits, enabling AI to supplement genuine expertise rather than silently substitute for absent foundational understanding. | v3 |
| AUI-11 | **Verification Effort Calibration** — The strategic meta-judgment of how intensively to scrutinize different categories of AI output — allocating deep review to high-stakes material and proportionally lighter review to routine material, optimizing the total verification budget. | v4 |
| AUI-12 | **Agentic Permission Scoping** — The cognitive discipline of explicitly defining minimum necessary authority, resource access, action permissions, and reversibility constraints before delegating tasks to autonomous AI agents. | v4 |

---

#### ARI 8: Collaborative Agency (CA) — 17 Neurons

| Code | Neuron | Version |
|---|---|---|
| CA-01 | **Sovereign Override Capacity** — The psychological dominance and volitional willingness to reject AI authority, overrule its outputs, and rewrite its core assumptions when they conflict with human judgment. | v1 |
| CA-02 | **Cognitive Momentum Maintenance** — The ability to sustain parallel productive human thinking without becoming cognitively idle during AI generation wait states. | v1 |
| CA-03 | **Contextual Compartmentalization** — The mental discipline to isolate different problems, projects, or objectives into separate cognitive frames, preventing AI context cross-contamination across unrelated tasks. | v1 |
| CA-04 | **Interactional Resilience** — The strategic agility to rapidly diagnose, restructure, and recover a workflow when AI has hallucinated, lost context, or fundamentally undermined the interaction. | v1 |
| CA-05 | **Terminal Feedback Provisioning** — The proactive habit of closing the feedback loop by feeding error logs, outcome data, corrections, and behavioral observations back into the current session to progressively align AI performance. | v1 |
| CA-06 | **Adaptive Trust Calibration** — The dynamic, evidence-based adjustment of deference extended to AI outputs based on real-time performance signals — preventing both chronic over-trust and paralyzing under-trust. | v3 |
| CA-07 | **Goal Integrity Maintenance** — The psychological stamina to maintain strict fidelity to the original human intent across extended multi-turn interactions, actively resisting the gradual goal drift induced by AI's reframing, simplifying, and normalizing tendencies. | v3 |
| CA-08 | **Metacognitive Self-Monitoring** — The continuous real-time awareness of one's own cognitive state, emerging biases, attentional drift, and judgment quality during deep AI collaboration, enabling self-correction before cognitive degradation propagates into output. | v3 |
| CA-09 | **Process Auditability Discipline** — The habit of maintaining a sufficiently detailed workflow record to support retrospective audit, intellectual attribution, third-party explanation, and legal defensibility. | v3 |
| CA-10 | **Selective Attention Governance** — The inhibitory cognitive capacity to actively resist AI-generated scope expansions, tangential elaborations, and irrelevant content, maintaining deliberate anchor on the core objective throughout the interaction. | v3 |
| CA-11 | **Affective Regulation Under Failure** — The emotional management skill to prevent frustration, helplessness, or impatience from degrading strategic decision quality and prompt rationality when AI repeatedly fails, misinterprets, or hallucinates. | v3 |
| CA-12 | **Cross-Session Transfer Learning** — The human capacity to extract generalizable strategic insights, workflow heuristics, and failure patterns from past AI interactions and apply them as durable principles to novel future tasks and tools. | v3 |
| CA-13 | **Identity Authorship Preservation** — The psychological stability to maintain a clear, continuous, and defensible sense of one's intellectual contribution, creative voice, professional identity, and epistemic ownership throughout deep AI collaboration — resisting the gradual authorial diffusion of uncritical high-volume AI integration. | v4 |
| CA-14 | **Intra-Session Pattern Recognition** — The real-time metacognitive skill of detecting recurring failure patterns, systematic biases, and capability limitations in the AI's current-session responses, enabling proactive strategy adjustment before errors compound. | v4 |
| CA-15 | **AI Sycophancy Resistance** — The active epistemic discipline of recognizing that AI systems are structurally trained to affirm, validate, and agree with the user's stated views and decisions — making AI agreement categorically unreliable as independent confirmation — and therefore proactively soliciting adversarial challenge and disconfirming evidence even when the AI has already validated one's position. | v5 |
| CA-16 | **Pre-Generation Epistemic Independence** — The cognitive discipline of deliberately forming one's own hypothesis, judgment, or prediction *before* reading AI output — preserving an independent cognitive baseline that prevents AI-generated content from anchoring and displacing human independent thought before it has a chance to form. | v5 |
| CA-17 | **Vigilance Sustainment** — The disciplined maintenance of consistently rigorous critical scrutiny across extended AI collaboration sessions — actively counteracting the natural temporal degradation of evaluation quality caused by habituation, fatigue, and performance-based complacency — ensuring that outputs produced late in a long session receive the same depth of scrutiny as those produced at the beginning. | **v6 NEW** |

> **Why CA-17 exists:** Vigilance decrement is one of the most replicated findings in human factors psychology (Mackworth, 1948; Warm, Parasuraman & Matthews, 2008). In automation research, complacency — performance-based reduction in monitoring following reliable system behavior — is a primary cause of catastrophic human-automation failures. CA-17 is distinct from CA-06 (which correctly adjusts trust upward after reliable performance) and CA-08 (which is *awareness* of cognitive state). CA-17 is the *active effort* to maintain scrutiny intensity against temporal decay. Measurable via scrutiny consistency metrics across session duration.

---

## PART 4 — NLP OPERATIONALIZATION: HOW TO DETECT EACH CONSTRUCT IN A TRANSCRIPT

These are the behavioral signals the LLM Judge should scan for. These come directly from the research justification in `The_seed_is_planted_1.pdf`.

### Core Composite Metrics (must compute for every transcript)

**1. Attribution Gap**
Compute lexical overlap between AI-generated output and user's final submission/synthesis. High overlap = low human contribution = cognitive offloading signal. This is the primary metric for detecting fluent incompetence. Bypasses self-reported efficacy entirely.

**2. Verification Ratio**
Count "verification turns" — prompts where the user challenges, cross-references, or tests an AI claim against an external constraint or their own knowledge. Formula: `verification_turns / total_AI_response_turns`. If ratio drops below the active cognitive engagement threshold, flag for cognitive debt.

**3. Generative vs. Extractive Query Ratio**
- **Extractive:** "Write this essay for me," "Finish this code," "Summarize this text"
- **Generative:** "Explain this concept," "What are the alternatives?", "Why did you choose this approach?"
High extractive ratio → penalize Augmentation Instinct (AUI). High generative ratio → reward Augmentation Instinct.

**4. Actualization Depth**
Track whether users complete full actualization loops: trigger AI → receive output → refine AI based on human-centric feedback. Partial loops (extract without refining) = Actualization Deficit. Penalizes CS and CD scores.

**5. Semantic Distance Δ**
Measure semantic distance between first prompt and final output. Low distance = user accepted AI's first framing. High distance = user actively redirected, restructured, or challenged. Maps to Creative Divergence (CD).

**6. Iteration Depth**
Count number of substantive refinement cycles per task. Low iteration = passive acceptance. High iteration = active cognitive engagement. Maps to PR-12.

### Phase Classification (AILit 4-Domain Framework)
Classify each conversational chunk into one of:
- **Engage:** user evaluating AI output accuracy and relevance
- **Create:** user iteratively guiding and refining AI output
- **Manage:** user delegating structured tasks while retaining judgment
- **Design:** user reasoning about data, systems, or AI limitations

This phase label becomes input context for the IRT scorer.

### Intent Tags for NLP Scanner
Every user prompt should be tagged with:

| Tag | Detection Signal | Dimension Impact |
|---|---|---|
| `VERIFY` | User challenges or cross-checks AI claim | EC ↑ |
| `EXTRACT` | Simple task delegation, no evaluation | CS ↓, AUI ↓ |
| `INJECT_CONTEXT` | User adds domain-specific constraint AI didn't have | CS ↑ |
| `PIVOT` | User entirely reframes after AI failure | PR-04 ↑, CA-04 ↑ |
| `ANTHROPOMORPHIZE` | User treats AI as having intent/emotion | AL ↓ |
| `ETHICS_GATE` | User adds ethical constraint or privacy filter | ES ↑ |
| `OVERRIDE` | User explicitly rejects AI output | CA-01 ↑ |
| `DECOMPOSE` | User breaks task into sub-tasks before delegating | PR-08 ↑ |
| `SCAFFOLD` | User's structure progressively takes over from AI | CD ↑, CS ↑ |
| `SELF_AUDIT` | User asks AI to evaluate their own human-generated logic | CA ↑ highest tier |

### Fluent Incompetence Detection Pattern
```
IF prompt_quality_score HIGH (PR ↑)
AND verification_ratio < threshold
AND attribution_gap > threshold
AND generative_query_ratio < 0.3
THEN → FLAG: FLUENT INCOMPETENCE
```
This is the core classifier pathology pattern. Must be hardcoded as a priority override.

### Cognitive Debt Detection Pattern
```
IF verification_ratio(session_first_half) > verification_ratio(session_second_half)
AND session_duration > [threshold]
AND high_stakes_task = TRUE
THEN → FLAG: COGNITIVE DEBT ACCUMULATION
```
Temporal degradation of scrutiny. CA-17 is the neuron this maps to.

---

## PART 5 — IMPLEMENTATION DECISIONS (from Ritesh's architecture notes)

### What NOT to do

1. **Do not hardcode sector-specific neuron weights.** 97–98 of 107 neurons are sector-agnostic. Segregating by sector reduces training data and introduces artificial variance. All 107 neurons are treated in the same tier with no pre-assigned importance weighting.

2. **Do not start with 8 input features.** Training a model on only 8 ARI dimension scores produces overfitting with increasing data and cannot accommodate occupational variance. The 107 neurons are the actual input feature space.

3. **Do not use survey/self-report data as ground truth.** Self-efficacy scales measure perceived confidence, not actual ability. The Attribution Gap and behavioral trace metrics are the ground truth.

4. **Do not pre-seed Bayesian IRT weights from our own judgment.** We are biased toward 17–24 year old tech students. Let the model learn weights from behavioral data. Initial values: zero (if fine-tuning) or random (if training from scratch).

### Training Approach (Ritesh's current recommendation)
- **Bayesian IRT** is the principled fit: handles question difficulty, sparse data, and structured assessment input with relatively little data
- The 107 neurons are the "items" in the IRT model
- Each user session is a "respondent"
- θᵢ (person ability parameter) is what we ultimately want to score and track over time
- Avoid putting Bayesian IRT directly in the main pipeline initially — use it as the measurement model for validation

### Open Validation Gate (consult Sathwik bhaiya)
- EFA (Exploratory Factor Analysis) on real behavioral data to confirm the 4-factor structure is empirically justified, not just theoretically asserted
- This is the empirical gate that must be cleared before treating the 4 constructs as truly independent
- Do not bypass this by running EFA on synthetic or generated data

---

## PART 6 — DISCRIMINANT VALIDITY REGISTER (KEY NEAR-PAIRS)

These are the neuron pairs that look similar but are distinct. Useful for building the LLM Judge's scoring rubric to avoid double-counting.

| Near-Pair | What makes them different |
|---|---|
| AL-01 vs EC-11 | General epistemic understanding (stable trait) vs in-session resistance to fluency bias on specific output (applied reflex) |
| EC-04 vs EC-12 | Error origin within one output (intra-response) vs error cascade across a chain of outputs (inter-response) |
| EC-07 vs EC-13 | Missing reasoning in one response vs incomplete coverage of solution space across responses |
| EC-07 vs EC-14 | Absent explicit content vs invisible load-bearing premises — absence vs hidden presence |
| ES-02 vs ES-13 | Detecting bias symptoms in current output vs interrogating training data composition upstream |
| ES-08 vs ES-11 | Transparency to others about AI involvement (outward) vs internal assignment of moral ownership (inward) |
| ES-10 vs AUI-08 | Ethical concern: am I surrendering independent judgment? vs cognitive concern: will I lose the skill itself? |
| AUI-04 vs AUI-07 | Whether to use AI at all (binary) vs how much prompt effort to invest given AI will be used (gradient) |
| AUI-09 vs AUI-12 | Reactive mid-task control reclamation vs proactive pre-task permission envelope design |
| CA-01 vs CA-15 | Overriding AI when you disagree vs evaluating AI agreement that is structurally worthless as confirmation |
| CA-01 vs CA-16 | Overriding AI output after reading it vs forming independent views before reading AI output |
| CA-06 vs CA-17 | Correctly increasing trust after reliable performance vs maintaining scrutiny against complacency — these can work in opposite directions |
| CA-08 vs CA-17 | Awareness of one's full cognitive state vs active maintenance of scrutiny intensity against temporal decay |
| CA-15 vs CA-16 | Resisting AI validation of views already held (post-formation) vs forming independent views before reading AI (pre-formation) |

---

## PART 7 — THEORETICAL GROUNDING MAP

These are the psychological and computational theories each neuron cluster is built on. Useful for defending the framework against peer review and for extending it.

| Theory | Neurons |
|---|---|
| Cognitive Load Theory (Sweller) | AL-03, AL-06, PR-02, PR-08, AUI-05, AUI-06 |
| Theory of Mind (Premack & Woodruff) | AL-10, CD-11 |
| Metacognition Theory (Flavell; Nelson & Narens) | CA-08, AUI-06, AUI-10, CA-14 |
| Executive Function (Miyake et al.) | CA-07, CA-10, AUI-09 |
| Human-Automation Trust (Lee & See 2004) | CA-06, AUI-04 |
| Automation Complacency (Parasuraman & Manzey) | AUI-08, ES-10, CA-17 |
| Vigilance Decrement Research (Mackworth 1948) | CA-17 |
| Embodied Cognition (Merleau-Ponty) | CD-10 |
| Affect Regulation (Gross) | CA-11 |
| Transfer Learning (Barnett & Ceci 2002) | CA-12 |
| Calibration Research (Lichtenstein & Fischhoff) | AL-01, EC-11, CS-11 |
| Sycophancy in LLMs (Sharma et al. 2023) | CA-15 |
| Anchoring & Adjustment Heuristic (Tversky & Kahneman) | CA-16 |
| Bayesian Complementarity (Steyvers et al. 2022) | Scoring engine — κ criterion |
| Critical Rationalism (Popper) | EC-14, ES-04 |
| Narratology / Tension Theory | CD-07, CD-09 |
| Creativity Research (Weisberg; Hofstadter) | CD-06, CD-08 |
| Moral Responsibility Theory (Fischer & Ravizza) | ES-11 |
| AI Governance Frameworks (EU AI Act; OECD) | ES-11, ES-14, AUI-12 |
| Prompt Injection Security (OWASP LLM Top 10) | AL-13 |
| Fault Propagation Theory (Systems Engineering) | EC-12 |
| Boundary Value Analysis (Software Testing) | EC-13 |
| Signal Detection Theory (Green & Swets) | CA-17 |
| OECD Digital Competency Frameworks | 4-layer structure |

---

## PART 8 — QUICK REFERENCE CARD FOR CLAUDE CODE

```
TOTAL NEURONS:  107 (not 106 — CA-17 added in v6)
TOTAL ARIs:     8
TOTAL LAYERS:   4

HIGHEST RISK DIMENSIONS:   EC + CS (co-low = fluent incompetence flag)
SECTOR DEPENDENCY:         None (97–98/107 neurons are sector-agnostic)
SELF-REPORT:               Not used anywhere in pipeline
GROUND TRUTH:              Attribution Gap + Verification Ratio + behavioral trace

PRIMARY SCORING METHOD:    Bayesian IRT (θᵢ per user)
FALSIFIABLE CRITERION:     Steyvers et al. complementarity bound (κ)
EXTERNAL VALIDATION:       OECD/PISA 4 pillars + AILit Framework (pre-validated alignment)

OPEN EMPIRICAL GATES:
  1. EFA on real data (consult Sathwik bhaiya) — confirm 4-factor structure
  2. Attribution Gap calibration for expert users (genuine experts may re-use AI phrasing correctly)
  3. Longitudinal "AI-off probe" — distinguish skill substitution from skill growth

VISUALIZATIONS OF ALL 107 NEURONS (interactive):
  https://tiny-froyo-bc4ae4.netlify.app/
  https://splendid-piroshki-c8e861.netlify.app/
  https://sweet-cannoli-ef7dae.netlify.app/ (sector-wise, best visualization)
```

---

*End of document. This file supersedes all three source files for Claude Code implementation purposes. When in doubt, this document takes precedence. Last verified: June 2026.*
