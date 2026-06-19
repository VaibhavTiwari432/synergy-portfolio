# SAF/ARI v3.2 — Spec-Delta over v3.1
## "The Cognitive Work Layer"

**Status:** DESIGNED revision. Adds one new descriptive layer (CSL), one ARI calibration upgrade, and three infrastructure fixes. Introduces **no new latent variables, dimensions, pillars, or neurons.** The ontology freeze (§14) holds.

**Supersedes:** nothing. Extends v3.1. The v2.2 master compilation remains the spine; v3, v3.1, and now v3.2 are stacked spec-deltas.

**Governing sentence of this revision:**
> CSL is not a new measurement system. It is the second consumer of signals ARI already extracts, re-projected onto a cognitive-work axis, plus one genuinely orthogonal extractor (the AI side) and one genuinely new detector (emergence). Everything else CSL reports is a re-aggregation of existing evidence.

**The four governing principles carried from prior versions, unchanged:**
1. Evidence before elegance. Reliability before complexity. Sustainability before synergy.
2. Every claim carries a rung tag: **DESIGNED → MEASURABLE → VALIDATED → ASPIRATIONAL.**
3. Stakes must never outrun validity (commitment 8). Relevance is not scope (v3.1).
4. Manufacture the counterfactual (commitment 9, v2.2). A claim without its counterfactual waits for the instrument that manufactures one.

---

## 0. Why v3.2 Exists

v3 was the validation-and-standards revision. v3.1 was the scope-discipline revision. **v3.2 is the revision that answers a question the prior versions could not: not "how capable is this person?" (ARI) but "who drove what in this session, and did the collaboration produce something neither party held alone?"**

The whole instrument up to v3.1 measured the human. Every one of the 107 neurons fires on a human behavior; the AI's turns are the *context* that makes the human's behavior interpretable (e.g. EC-01 requires "AI produced a checkable claim" to fire), but the AI's contribution is never itself an object of measurement. This is correct for a *competency* instrument. It is insufficient for answering *who did what* — because that question is dyadic, and it requires measuring both parties.

v3.2 closes this gap with a new **descriptive** layer that runs in parallel to ARI, never modifying ARI scores, and is honest about the single ceiling it inherits: transcript-derived contribution is *displayed* contribution, not *validated* contribution, and only the retention probe (Layer 4) crosses that wall.

### 0.1 The realization that makes CSL cheap

The central architectural finding of this revision:

- **The human side of "who did what" is already in ARI.** When the human exhibits CD-02 (Lateral Concept Injection), that *is* a human-origination signal at the Frame-and-Integrate level. The foundation evidence CSL needs is, in large part, already extracted by ARI's neurons. CSL's human side is therefore a **re-aggregation** of existing neuron firings onto a different axis — **not a re-measurement.** Re-aggregating the same evidence along a new axis is not double-counting; it is a second view of one measurement.
- **The AI side of "who did what" is genuinely orthogonal to ARI — but trivial.** No ARI neuron measures the AI's contribution. But the AI's output is *fully displayed* in the transcript; there is no hidden cognitive state to infer. Measuring "did the AI retrieve this fact, generate this structure, produce this code" is a near-deterministic read of the AI turns. New code, not new science.
- **Emergence is the one thing genuinely not derivable from ARI.** Every ARI neuron fires on one party's behavior. Emergence is a property of the *transition between turns* — it lives in the seam between an AI turn and the human turn that follows. This is the only part of CSL that requires a genuinely new detector.

**The formula:**
```
CSL = ARI-neurons-re-projected-onto-ACF-levels   (human side, free)
    + displayed-AI-contribution-extractor          (AI side, orthogonal, cheap)
    + emergence-sequence-scanner                    (the one genuinely new detector)
```

---

## 1. The v3.2 Architecture — The Four-Layer Stack

```
═══════════════════════════════════════════════════════════════════
              SAF/ARI MEASUREMENT STACK (v3.2)
═══════════════════════════════════════════════════════════════════

LAYER 1 — ARI  [RUNNING: 108 tests green, MAE 0.299]
  Object:   The human's collaborative-process competency
  Question: "How capable is this person at working with AI?"
  Reads:    The full dyadic transcript (human turns scored against
            AI-turn context — ARI is and always was DYADIC)
  Output:   107 neurons → 8 dimensions → 4 pillars → g_synergy
  Trait:    Relatively stable across sessions
  Rung:     MEASURABLE per dimension (once ICC-certified)

LAYER 2 — CSPC  [STUB + 2 PROXIES]
  Object:   The cognitive conditions under which behavior occurred
  Question: "In what state was the person while doing it?"
  Reads:    State-diagnostic features (latency, load, task-switching)
            — DISJOINT from competency-diagnostic features (§2.1)
  Output:   π(S_t) — a precision modulator on Layers 1 AND 3
  Now:      Two proxies ship (load_level, tom_slope)
  Rung:     DESIGNED (full 4D HGF); the two proxies are MEASURABLE

LAYER 3 — CSL  [NEW in v3.2 — SPEC]
  Object:   How cognitive work was distributed across the dyad
  Question: "Who drove what, and did the dyad produce emergence?"
  Reads:    Track 1: ARI neurons re-projected + AI-side extractor
            Track 2: turn-sequence seams (the one new channel)
  Output:   Per-ACF-level ownership map + Emergence Event Log
  Rung:     MEASURABLE as process indicators (NOT synergy proof)

────────────────────── THE WALL ───────────────────────────────────
  Everything above is CHAT-DERIVED → describes the PROCESS.
  Everything below needs the MANUFACTURED COUNTERFACTUAL → OUTCOME.
────────────────────────────────────────────────────────────────────

LAYER 4 — θ + the deferred no-AI retention probe  [NOT DEPLOYED]
  Object:   What the human can actually do alone, on a real task
  Question: "Without AI, 24-48h later, can they perform?"
  Output:   The single external criterion everything is validated against
  Derived:  λ (sustainability), true synergy, validated ownership,
            validated S_human — ALL gated on this probe
  Rung:     DESIGNED → VALIDATED only when probe data arrives
═══════════════════════════════════════════════════════════════════
```

**The wall is the load-bearing concept of the entire framework.** Layers 1-3 describe *how the collaboration unfolded*. Layer 4 measures *what it did to the human*. No claim from below the wall may be made using only data from above it. This is the operational form of commitment 9. CSL does not move any claim across the wall; it makes the process layer richer, and it provides *leading indicators* for what Layer 4 will eventually confirm or falsify.

---

## 2. The CSL Specification

### 2.1 What CSL Is and Is Not

**CSL IS:**
- A **descriptive** mapping layer. It maps the distribution of cognitive work; it does not score the human.
- Two parallel tracks: a **Contribution/Ownership Map** (Track 1) and an **Emergence Event Log** (Track 2).
- Built primarily from re-aggregated ARI evidence plus one orthogonal extractor and one new detector.
- For **user-centric understanding**, not for cross-validating ARI (it shares ARI's human-side evidence and therefore *cannot* independently check it — by construction).

**CSL IS NOT:**
- A competency score. (That is ARI.)
- A cognitive-state estimate. (That is CSPC.)
- A synergy proof. (Emergence events are MEASURABLE *indicators*; proof needs Layer 4.)
- A token count, a word count, or any surface-volume metric. **Ownership is measured as cognitive control, never as surface attribution** (see §2.4.3 — this is non-negotiable and the framework's own Expert POV demands it).
- A populated "what the human can do without AI" map. (That is the Dependency Map, DESIGNED only; see §2.6.)

### 2.2 Grounding in the Augmented Cognition Framework (ACF)

CSL's cognitive-work vocabulary is the **ACF** (`Bloomy_Taxonomy_for_synergy.pdf`), already in the project literature and already the external validation anchor for ARI's four pillars. The ACF is Bloom's six levels × two modes (Individual / Distributed) plus a seventh Distributed-only level (Orchestrate).

The **Distributed-mode verbs** are CSL's seven work-types. The ACF's **dependency column** is the measurement specification — each "cannot X without Y" names the foundation evidence CSL must detect to distinguish genuine contribution from fluent incompetence.

| ACF Level | Distributed Verb | Foundation requirement (the dependency column) |
|---|---|---|
| C1 | Curate | Cannot curate without knowledge to recognise errors |
| C2 | Discriminate | Cannot discriminate without understanding to detect superficiality |
| C3 | Specify & Verify | Cannot verify without execution experience to recognise misapplication |
| C4 | Frame & Integrate | Cannot frame without analytical capacity to specify what matters |
| C5 | Critique Criteria | Cannot critique criteria without judgment to assess proper application |
| C6 | Direct Cognitive Product | Cannot direct effectively without generative experience |
| C7 | Calibrate Partnership | Human-only; no AI equivalent; governs all other levels |

**Why the dependency column is the measurement spec:** the Distributed act and its hollow imitation look *identical* at the surface (this is the definition of fluent incompetence). The only thing that distinguishes them is whether the act rested on the Individual-mode foundation. CSL therefore measures **foundation evidence**, not surface activity. (See §2.4.4.)

### 2.3 The Non-Circularity Guarantee

The double-measurement risk between ARI and CSL is real and is resolved by two mechanisms, the same discipline that already governs ARI↔CSPC:

**Mechanism 1 — Re-projection, not re-extraction (human side).** CSL's human side does not run a second extraction over the transcript. It takes the *existing* ARI `NeuronMatrix` and projects each neuron firing onto its ACF level via a frozen crosswalk (§2.4.1). One extraction, two aggregations (one into ARI's 8 dimensions, one into CSL's 7 ACF levels). There is no second measurement of the human, therefore no double-counting.

**Mechanism 2 — The feature partition (§2.1 of the master).** This is the framework's existing non-circularity guarantee, here applied to confirm independence empirically. State-diagnostic features feed CSPC; competency-diagnostic features feed ARI; the AI-side extractor reads a disjoint channel (the AI turns, which no ARI neuron scores). **Ordering without partition is the circularity, not its cure.** The empirical check: ARI dimension scores and CSL ownership shares must NOT correlate near 1.0 (the independence test, §6).

> **Correction logged (this is a v3.2 correction to a transient error):** ARI is **dyadic** and always was. An earlier framing that "ARI reads human turns in isolation" was wrong — neuron applicability rules (e.g. "AI produced a checkable claim") require AI turns. The real ARI↔CSL partition is not *isolation vs relational* (both are dyadic) but *which latent object the shared evidence is aggregated toward* — trait (ARI) vs work-distribution (CSL) — plus the orthogonal AI-side channel. This correction is recorded so the spec is not built on the wrong partition.

### 2.4 Track 1 — The Contribution / Ownership Map

#### 2.4.1 The neuron → ACF crosswalk (frozen configuration, not code)

A static mapping table projecting existing neurons onto ACF levels. Illustrative (full table to be frozen in the contract layer):

| ACF Level | User-Friendly Label | Primary ARI neurons projected here |
|---|---|---|
| C1 Curate | Knowledge Sourcing | CS external-injection neurons; AL-grounding |
| C2 Discriminate | Sense-Making | EC-02/03 (coherence/source auditing); AL-01 |
| C3 Specify & Verify | Direction & Checking | EC-01/06/09 (verification cluster); PR-structuring |
| C4 Frame & Integrate | Problem Framing | CS-05/06/08 (synthesis); CD-02 (lateral injection) |
| C5 Critique Criteria | Quality Judging | EC (criterion-level); CA-15/16 (epistemic independence) |
| C6 Direct Cognitive Product | Original Making | CD-06/08/09 (constraint/novelty); CS-01 |
| C7 Calibrate Partnership | Partnership Steering | CA-01/06/13/14/17; AUI-02/08/09 |

The framework's existing AILit 4-domain phase classifier already does a coarse version of this projection (Engage/Manage/Create/Design); the ACF crosswalk is its higher-resolution successor. **This table is frozen before any judge sees it** to prevent Goodhart drift.

#### 2.4.2 The user-friendly terminology

Reporting NEVER exposes academic terms (C4, "Frame & Integrate", "Distributed Mode"). The user sees:

| Internal (ACF) | User-facing label | Plain-English meaning |
|---|---|---|
| C7 Orchestrate | **Partnership Steering** | Who managed the collaboration — when to trust, push back, redirect |
| C6 Create | **Original Making** | Who generated genuinely new ideas/products/solutions |
| C5 Evaluate | **Quality Judging** | Who assessed whether output was actually good/correct/appropriate |
| C4 Analyse | **Problem Framing** | Who broke down the problem and integrated the pieces |
| C3 Apply | **Direction & Checking** | Who specified what was needed and verified it was right |
| C2 Understand | **Sense-Making** | Who separated genuine insight from plausible-sounding noise |
| C1 Remember | **Knowledge Sourcing** | Who brought the raw knowledge, facts, and context |

#### 2.4.3 Ownership as cognitive control, NOT surface attribution (the central constraint)

The framework's own Expert POV (`Expert's POV 19:35 PM, 23 May 2026`) is explicit and binding:
> *"Tracking the 'attribution gap' (lexical overlap between AI output and human submission) is a clever proxy, it is highly gameable and conflates linguistic originality with cognitive engagement. A genuine expert might copy an AI's phrasing simply because it is correct."*

Therefore ownership at each ACF level is measured by **control signals** — behaviors that require the underlying competence to produce — not by whose words survived. Surface attribution *inverts* the truth exactly at the Compressed-Expert / Delegating-Manager boundary the instrument exists to resolve (the §8.5 twin-pair gate):

- The **Compressed Expert** accepts correct AI phrasing verbatim → low surface attribution, but **high control** (selective rejection when the AI errs, exogenous injection when framing, criterion challenge when evaluating).
- The **Delegating Manager** rewrites everything in his own words → high surface attribution, but **low control** (uniform acceptance, no exogenous injection, no criterion challenge).

Surface attribution scores the Manager higher. Control scores the Expert higher. Control is correct.

#### 2.4.4 Foundation evidence per ACF level (the control signals)

Each level's human-ownership is the precision-weighted probability that the contribution was *foundation-backed*, evidenced by the level-specific signal below. **Negative evidence — conspicuous absence where the level was engaged — is as informative as positive evidence.**

| Level | Foundation signature (genuine) | Hollow signature | Existing metric reused |
|---|---|---|---|
| C1 Curate | Selective rejection (accepts some, rejects the wrong ones correctly) | Uniform acceptance | Accept/reject events vs AI-error presence |
| C2 Discriminate | Differential response to AI depth (probes; reacts to quality) | Accepts deep and superficial identically | Verification-selectivity |
| C3 Specify & Verify | Calibrated verification (checks the real failure points) | Verify-everything (Anxious Over-Verifier) or verify-nothing | Verification Ratio + selectivity |
| C4 Frame & Integrate | **Exogenous injection** (content the AI lacked, not derivable from prior turns) | Recombines what the AI already said | CD constraint-injection; CS external-injection; `semantic_distance_delta` (bilateral) |
| C5 Critique Criteria | Criterion substitution (challenges the *standard*, not the answer) | Accepts the AI's implicit criteria | EC criterion-level firing |
| C6 Direct Cognitive Product | Generative specification anticipating failure modes | Vague generation requests | Generative-vs-Extractive ratio; constraint precision |
| C7 Calibrate Partnership | Mode-switching, override, trust-calibration across the session arc | Passive drift | CA sovereignty + AUI delegation neurons |

**C4 (exogenous injection) is the cleanest signal** in the entire stack — exogenous knowledge cannot be hollow. **C7 is human-only** — if C7 activity is absent, the human was being orchestrated by the AI rather than orchestrating it.

#### 2.4.5 The AI-side extractor (the orthogonal piece)

A lightweight, near-deterministic read of the AI turns: at each ACF level, what did the AI contribute (retrieve, generate, structure)? No foundation inference is required because the AI's output is fully displayed and the AI has no foundation to fake. This is the only genuinely new extraction in Track 1, and it is the easy kind.

#### 2.4.6 The ownership formula

For each ACF level:
```
                          π(S_t) · control_signal_human(level)
Human_ownership(level) = ───────────────────────────────────────────────
                         π(S_t) · control_signal_human(level) + AI_displayed(level)

where:
  control_signal_human(level)  = the re-projected ARI evidence for that level (§2.4.4)
  AI_displayed(level)          = the AI-side extractor output (§2.4.5)
  π(S_t)                       = CSPC precision weight (§2.4.7)
```

Output is a **per-level distribution** (7 ownership percentages), each with a credible interval, **never collapsed to a single session number**, denominators explicit. Reported as **displayed ownership**, tagged MEASURABLE.

#### 2.4.7 CSPC precision weighting (the accuracy multiplier)

A control signal observed under collapsed metacognitive state (low M_t) is *weaker evidence* of genuine ownership than the same signal under high M_t. CSPC enters CSL exactly as it enters ARI: as a **precision modulator on the evidence, never as a score multiplier** (multipliers were rejected, §14 R2). A constraint-injection performed while cognitively disengaged moves the ownership estimate less and widens its interval. This is the third defense against fluent incompetence: not just *did the control signal fire*, but *did it fire under cognitive conditions consistent with genuine ownership.*

#### 2.4.8 Session-level aggregation and identifiability

Foundation evidence is **unidentifiable per-turn** (a silent correct acceptance by an expert emits no trace) and **identifiable in aggregate** (foundation accumulates across the session). CSL Track 1 is therefore reported only at the **session level**, never as a per-turn verdict. Per-turn accuracy is genuinely low; session-level accuracy rises substantially — this gap is structural, not an engineering deficiency.

### 2.5 Track 2 — The Emergence Event Log

#### 2.5.1 Definition (the one genuinely new measurement)

Emergence is a **discrete event** at the seam between turns, not a source column and not a percentage. It is flagged when a turn-window satisfies **all three** conditions simultaneously:

1. **Non-existence before the exchange (novelty test).** The formulation is at high *bilateral* semantic distance — far from both the human's prior turns AND the AI's prior outputs. (Close to the AI = adoption. Close to the human = persistence. Far from both = emergence.) Reuses `semantic_distance_delta`, extended to the bilateral form.
2. **Non-derivability from either party alone (dependency test).** The human turn shows BOTH uptake of AI-provided material AND injection of human-provided material, and the output depends on both. (Uptake only = adoption. Injection only = the human's own idea. Both fused = emergence.) This is the cleanest discriminator.
3. **Observable in the transcript (trace test).** The actualization loop closes on a *reframing* (not a refinement): "that connects to X, which means Y" where Y is the new thing; or the AI, given the human's constraint, generates the missing piece the human confirms. Reuses the existing actualization-depth metric, reframing variant.

#### 2.5.2 The detection mechanism

A **per-window sequence scan** (AI turn + the human turn(s) that follow), NOT a per-turn score. Each window is tested on the three conditions jointly; windows that clear all three become **candidates**; candidates are passed to the **LLM judge for confirmation** (the three quantitative signals can co-occur by coincidence; the judge verifies genuine emergence). Confirmed candidates enter the log.

#### 2.5.3 Event schema

```
EmergenceEvent:
  ev_id           : str
  turn_range      : tuple[int, int]
  acf_level       : Literal[C4, C6]      # emergence is structurally impossible at C1/C2
  trigger_type    : Literal[HI, AR, BI]  # Human-Injection | AI-Reframe | Bilateral (highest)
  confirmation    : Literal[explicit, behavioral, none]
  direction_change: bool                  # did the session pivot after this?
  output_delta    : bool                  # did subsequent output quality/novelty rise?
  judge_confirmed : bool

Session summary:
  emergence_count, emergence_rate (per 100 turns),
  c4_c6_concentration, bilateral_rate, confirmed_rate
```

#### 2.5.4 Rung tagging (non-negotiable)

- Emergence events as **synergy indicators** → **MEASURABLE** (the exchange had the structural signature of complementarity).
- Emergence events as **synergy proof** → **ASPIRATIONAL** (proven synergy = dyad outperforming max(human-alone, AI-alone), which requires Layer 4).

Reporting language (mandatory): *"This session contained N emergence events — moments where the exchange produced formulations neither party was approaching independently. These indicate genuine complementarity. They are not proof of performance gain above what you could achieve alone, which requires the unaided follow-up task to establish."*

#### 2.5.5 Why emergence earns its place

The instrument leans heavily toward detecting pathology (debt, surrender, fluent incompetence). The framework itself notes (§5.7) this is demoralizing and scientifically incomplete — the Amplification quadrant deserves positive instrumentation, not merely "absence of debt." Emergence is that positive instrumentation, and it is the one signal ARI structurally cannot produce (it lives in the seam between turns), which is what makes the contribution layer worth building as more than a re-projection.

### 2.6 The Derived CSL Analytics — The Ten Aspirational Layers, Triaged

The "Cognitive Work Analytics" vision proposes ten outputs richer than ownership %. Run through the framework's discipline (derivable? renaming? below the wall? survives fluent-incompetence and no-volume-reward?), they split cleanly:

**TIER 1 — BUILD NOW (transcript-derivable, MEASURABLE, survives the traps):**

| Layer | What it is | Notes / caveats |
|---|---|---|
| **Cognitive Flow Analysis** | How cognition *moved* (Human-idea→AI-expand→Human-verify vs AI-output→accept→AI-output→accept) | Pure sequence structure over the event log; the cleanest "bigger than ownership" output; needs no solo baseline |
| **Emergence Detection** | §2.5 above | Already specified |
| **Cognitive Bottleneck Detection** | The consistently-weak ACF function across sessions ("always stalls at verification", "never reframes") | Makes CSL *developmental*, not just descriptive; MUST be task-conditioned (a "bottleneck" may be appropriate delegation) |
| **Orchestration Efficiency** | Same output, 12 prompts vs 120 | Maps to existing OCI (§5.6) + prompt-compression anchor; MUST be paired with quality, never standalone |

**TIER 2 — ALREADY BUILT / RENAMINGS (surface as legible indices, no new measurement):**

| Layer | What it actually is | Rung |
|---|---|---|
| **Ownership** | CSL Version 0 (§2.4) | MEASURABLE |
| **Cognitive Sovereignty** | A re-projection of the existing CA+EC cluster (CA-01/15/16/17 + EC) onto a single legible index. *"Does the human remain the final cognitive authority?"* | MEASURABLE (observational version). **The injected-error version** ("AI deliberately hallucinates, observe recovery") is an *intervention*, not an observation — that version is DESIGNED and needs the probe |

**TIER 3 — DEFER TO THE PROBE (the proxy is MEASURABLE now; the real claim is DESIGNED):**

| Layer | Why it's below the wall | What to ship now |
|---|---|---|
| **Cognitive Dependency Map** ("Without AI: Curate ✓, Generate ✗") | "Without AI" = θ = the solo baseline = Layer 4 | Ship the per-function H-share *trend* as a leading indicator; populate the real "without AI" column only after the probe |
| **Cognitive Trajectory / Skill Transfer** (Week 1 AI-driven → Week 20 human-driven) | "Skill transfer" requires the solo-θ slope = λ = Layer 4 | Ship the H-share trajectory as a behavioral pattern (MEASURABLE); interpret it as transfer only after λ validates |

**TIER 4 — RESIST AS STATED (scientifically unsupportable without heavy conditioning):**

| Layer | The problem | Salvage condition |
|---|---|---|
| **Cognitive Leverage** ("12 inputs → 900 units = 75x") | A **volume ratio**. Rewards the Delegating Manager who dumps a vague prompt and gets 900 units of sophisticated garbage. S_human's vanity-metric trap in a seductive costume. | NEVER standalone. Only inside the λ × quality(Q*) gate, exactly as S_human is gated. As "75x" alone: do not ship. Rung: HYPOTHESIS |
| **Cognitive Diversity / Exploration Breadth** | **Narrowing is not inherently bad.** An expert who discards the wrong branches exhibits good judgment; this metric scores them as poor. | Only when conditioned on whether un-explored branches were viable (hard from transcript). Rung: HYPOTHESIS. Promising for innovation settings specifically; not a general output |

**The pattern across all ten:** the moment a metric claims to know what the human can do *without* the AI, or claims that *more* (output, exploration, leverage) is *better*, it has either crossed the wall or entered the fluent-incompetence trap. The survivors describe the *structure and movement* of cognition (flow, emergence, bottleneck) rather than asserting hidden capability or rewarding volume.

---

## 3. The ARI Calibration Upgrade

### 3.1 Bloom-level tagging in ARI scoring — REJECTED

Tagging neuron firings with Bloom/ACF level to *weight the score* creates strong Goodhart risk: the judge (or users) optimize for "high-Bloom" language instead of actual cognitive depth, violating reliability (V1) and honest limits (V13). **Rejected for the ARI scoring pipeline; logged in §14.1.** Bloom/ACF vocabulary is adopted only in CSL as a *descriptive classifier* (no score effect, no incentive to game).

### 3.2 Five calibration mechanisms — ADOPTED as precision conditioners (NOT multipliers)

The Gemini judge currently scores each turn in a vacuum. These five ground the judge in query-response / human-AI psychology, entering as **contextual priors on evidence precision** within the existing Bayesian framework — never as score multipliers.

| Mechanism | Grounding | Integration | Risk |
|---|---|---|---|
| **Judge-Advisor Framework (JAF) + Weight of Advice** | Yaniv & Kleinman; Sniezek & Buckley | Score each AI-response uptake as a calibrated reliance event {prior, claim-strength, shift, stakes}; conditions EC/AUI precision. Extends v3 V12 | Low |
| **Conversational Grounding** | Clark & Brennan (1991), already in the architecture doc | Classify each human turn's grounding function (initiation / grounding / repair); repair turns are richer evidence; conditions EC/CA precision | Very low |
| **Epistemic Vigilance** | Sperber & Mercier (2011, 2017) | Detect the vigilance *pattern* (justification requests, source probing, prior-expression); a distributed signal hard to game; conditions EC/CA | Low |
| **Dawid-Skene Sycophancy Correction** | Dawid & Skene (1979); already in stack | Extend to estimate the judge's bias toward elaborated-over-terse responses; calibrate it out on gold. Also calibrates CSL origin tags | None (immediate reliability win) |
| **Predictive Interaction Entropy** | Shannon | Prompt-entropy over the session as a PR/CD prior; low entropy over a long session = cognitive narrowing; conditions the *meaning* of a firing, not the score | Low (report with CIs) |

All five are Goodhart-resistant because they are *distributed patterns* across many turns, not single gameable behaviors.

---

## 4. Infrastructure Fixes (Bucket 1 — The Broken Things)

These are concrete defects, not features. They are cheap, they precede everything, and CSL built on top of them inherits their stability.

### 4.1 The security hole (P0)
An OpenAI API key sitting in `telemetry.metadata` (JSONB). This is a live vulnerability with an external-harm clock. **Rotate the key, scrub the field, add a guard that rejects any secret-shaped string from telemetry metadata at write time.** This precedes all other work.

### 4.2 Pipeline non-determinism
Scores change on re-running the same chat. Four stacked stochastic layers:
- **Tier A code-level nondeterminism** — pin `PYTHONHASHSEED`, make async ordering deterministic. (Bug, not noise.)
- **Un-frozen quantile cuts** — freeze the quantile boundaries; recomputing them per-run is a bug.
- **Embedding batch variance (Tier B)** — pin batch composition / use deterministic batching.
- **Judge nondeterminism (Tier C)** — documented even at temperature 0; the seed parameter is Vertex-AI-only. Protocol: **N-replication with mean±SD, reported only near quadrant boundaries.**
Until fixed, every downstream number — including any CSL number — is built on sand.

### 4.3 Reporting never-collapse violation
The framework forbids merging `STRUCTURAL_NA`, `INSUFFICIENT_SAMPLE`, and genuine low scores. Current reporting violates this. **Add the third sibling `MEASUREMENT_SATURATED` (from v3) and enforce four distinct labels in code.** CSL's per-level reporting reuses these same four states unchanged.

---

## 5. The CSL Reporting Layer

Three panels on one screen, all derived from the ACF stack, all in user-friendly language:

**Panel A — The Collaboration Stack.** Each ACF level shows an independent H% / AI% split (bars are NOT parts of a whole summing to 100 — both can be high or both low). Purple = human, teal = AI.

**Panel B — The Emergence Ribbon (above the stack).** Sits above because emergence is *produced by* the stack, not part of it. Event count, levels, bilateral fraction. The session's positive signal.

**Panel C — The ARI Alignment Strip (alongside Panel A).** Per level, the human's ARI capability dot. When ARI is high but H% is low, the strip flags it: "you have the capability but the AI did most of this work this session" — the Borrowed Brilliance signal, made legible without jargon. **ARI dots are NEVER averaged into the contribution bars** — the two layers stay separate.

Rules: never collapse the four reporting states; never show bare percentages without defined denominators; bars independent per level; ARI separate from contribution.

---

## 6. Validation Protocol for CSL

CSL ships as MEASURABLE process indicators and is validated like everything else — pre-registered, gated, outcome-anchored.

- **Independence test (the partition check):** correlation between ARI dimension scores and CSL ownership shares must NOT be near 1.0. Near-1.0 means the partition failed and CSL is re-measuring ARI. Pre-register the threshold.
- **Reliability:** G-study (V1, extended) on CSL ownership tags and emergence-event detection; per-ACF-level judge-human ICC (this *is* the per-level accuracy ceiling — it will not be uniform; C4 exogenous-injection is clean, C2 superficiality-detection is subtle and the judge shares the human's fluent-incompetence vulnerability).
- **Predictive validity (§8.3 gate):** does CSL ownership + emergence rate beat quality-only at predicting Layer 4 probe outcomes / retention / transfer? Pre-registered ΔAUC.
- **Judge calibration:** Dawid-Skene + the non-determinism protocol applied to CSL tags.
- **Causal home:** the CSL-ownership → stability hypothesis lives in the pre-registered DAG (v3.1-B).
- **OSF pre-registration** under AERA/APA/NCME; null results publishable.

---

## 7. The v3.2 Rung Ledger

| Item | Rung | Gate to promote |
|---|---|---|
| CSL Track 1 ownership map (displayed) | **MEASURABLE** | ICC certification per ACF level |
| CSL Track 1 ownership (validated, "genuine") | DESIGNED | Layer 4 probe |
| CSL Track 2 emergence as synergy indicator | **MEASURABLE** | Judge ICC on emergence detection |
| CSL Track 2 emergence as synergy proof | ASPIRATIONAL | Layer 4 (solo baseline) |
| Flow Analysis | **MEASURABLE** | Reliability on flow-pattern coding |
| Bottleneck Detection | **MEASURABLE** | Task-conditioning + cross-session data |
| Orchestration Efficiency | **MEASURABLE** | Paired-with-quality reporting |
| Cognitive Sovereignty (observational) | **MEASURABLE** | Inherits CA/EC certification |
| Cognitive Sovereignty (injected-error) | DESIGNED | Probe / intervention arm |
| Dependency Map (real "without AI" column) | DESIGNED | Layer 4 probe |
| Trajectory as skill transfer | DESIGNED | λ validation (Layer 4) |
| Cognitive Leverage | HYPOTHESIS | Only inside λ × Q* gate |
| Cognitive Diversity | HYPOTHESIS | Conditioning on branch-viability |
| Five ARI calibration mechanisms | DESIGNED → MEASURABLE | Gold-set ICC after integration |
| The four ARI dimensions' existing rungs | unchanged | (per v2.2/v3) |

**Nothing in v3.2 moves any claim across the wall.** CSL makes the process layer richer and provides leading indicators; Layer 4 remains the sole promoter of synergy and sustainability claims.

---

## 8. Limitations (Stated, Not Hidden)

1. **CSL measures displayed contribution, not genuine contribution.** Transcript-based control signals can still be fooled by sophisticated fluent incompetence (a Delegating Manager who has *learned* to perform constraint-injection without understanding). Only the retention probe resolves it. Same wall as λ.
2. **Per-turn ownership is unidentifiable.** Foundation evidence is identifiable only in session aggregate. The per-turn accuracy floor is structural.
3. **Per-ACF-level accuracy is non-uniform.** C4 (exogenous injection) is clean; C2 (superficiality detection) is subtle and shares the judge's own fluent-incompetence vulnerability. The per-level ICC is the per-level ceiling.
4. **Emergence detection is judge-dependent.** The three quantitative signals can co-occur by coincidence; the judge confirmation has its own ICC and its own non-determinism.
5. **CSL cannot cross-validate ARI.** It shares ARI's human-side evidence by construction. This is intentional (the use case is user-centric understanding, not cross-validation) but it means CSL is not an independent check on ARI.
6. **The binding constraint is unchanged: the gold corpus.** 26 chats, single dominant archetype. EFA, GRM, EC few-shot, CSL per-level ICC — all gate on growing the corpus to 60+ with archetype spread (§7.2a quota). No algorithm substitutes for this.
7. **The decisive instrument is unchanged: the retention probe.** Not deployed. Until it is, the entire stack is a process-description system. With it, it becomes the first validated psychometric tool for human-AI interaction.

---

## 9. Build Sequence for v3.2

```
PHASE 0 — Bucket 1 fixes (BEFORE any CSL work)
  0.1  Security: rotate key, scrub telemetry.metadata, add write-time guard
  0.2  Determinism: pin hash seed, freeze quantile cuts, deterministic
       batching, judge N-replication at boundaries
  0.3  Reporting: add MEASUREMENT_SATURATED, enforce 4 distinct states

PHASE 1 — CSL specification artifacts (writable now, zero new data)
  1.1  Freeze the neuron→ACF crosswalk table
  1.2  Write the two PARTITIONED judge-prompt families
       (ARI competency-scoring prompt vs CSL foundation-detection prompt)
       — STOP-FOR-HUMAN-REVIEW: confirm the two prompts attend to
         genuinely different things before either touches the judge
  1.3  Write the ownership formula + CSPC precision hook
  1.4  Write the emergence sequence-scanner spec (3 conditions + judge confirm)
  1.5  Pre-register all of the above on OSF, including the independence test

PHASE 2 — CSL build (over the frozen spec)
  2.1  Track 1 human side: re-projection function over existing NeuronMatrix
       (NO new extraction)
  2.2  Track 1 AI side: displayed-AI-contribution extractor (the orthogonal piece)
  2.3  Track 1: ownership normalization + CSPC weighting
  2.4  Track 2: emergence sequence-scanner + judge confirmation
  2.5  Tier-1 analytics: flow, bottleneck, orchestration-efficiency
  2.6  CSL reporting layer (3 panels, user-friendly, 4-state, never-collapse)

PHASE 3 — Validation (gated on corpus)
  3.1  Independence test (ARI scores vs CSL shares — must not be ~1.0)
  3.2  Per-ACF-level ICC certification
  3.3  Predictive-validity registration against Layer 4 (when probe exists)

CONTINUOUS — the binding constraints (cannot be shortcut)
  C.1  Grow the gold corpus to 60+ with archetype spread (§7.2a)
  C.2  Design and deploy the retention probe (the only wall-crossing instrument)
```

---

## Appendix A — Concept Glossary (v3.2 terms)

- **The Wall** — the boundary between chat-derived process measurement (Layers 1-3) and outcome measurement requiring the manufactured counterfactual (Layer 4). No claim crosses it without probe data.
- **Re-projection** — taking existing ARI neuron firings and aggregating them onto the ACF axis instead of (or in addition to) the 8-dimension axis. Not a re-measurement; a second view.
- **Foundation evidence** — observable traces that a Distributed-mode act rested on the Individual-mode competence the ACF dependency column requires. The measurement target for ownership, replacing surface activity.
- **Control signal** — the level-specific foundation evidence (selective rejection, exogenous injection, criterion substitution, etc.) that requires the underlying competence to produce, and therefore cannot be faked by surface volume.
- **Displayed ownership** — ownership measured from the transcript; MEASURABLE; distinct from *genuine* ownership, which requires Layer 4.
- **Emergence event** — a discrete turn-seam event satisfying bilateral-novelty + fused-dependency + reframing-trace, judge-confirmed; a synergy *indicator*, never synergy *proof*.
- **The twin pair** — Compressed Expert (archetype 10, calibrated mastery) and Delegating Manager (archetype 5, hollow), surface-identical and sustainability-opposite; the §8.5 gate CSL exists to help separate.
- **Fluent incompetence** — sophisticated-looking output without the comprehension to back it; looks identical to genuine competence at the surface; the central thing the control-signal approach is designed to detect.

---

*End of SAF/ARI v3.2 Spec-Delta. This document extends v3.1, which extends v3, which extends the v2.2 master compilation. The ontology freeze holds: no new neurons, dimensions, pillars, or latent variables. CSL is a parallel descriptive layer built primarily from re-aggregated existing evidence.*
