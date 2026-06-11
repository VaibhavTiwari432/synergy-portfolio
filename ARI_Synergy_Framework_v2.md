# The ARI Human–AI Synergy Capture Framework
## Version 2.0 — Unified Architecture

*The canonical, end-to-end specification for measuring human–AI synergy from real conversational data. This document supersedes the v1.0 specification (`Conversational_HumanAI_Synergy_Architecture.md`) and consolidates every confirmed decision across the project's design history into a single reference. Nothing load-bearing is left in chat-only form; it is all documented here.*

---

## 0. Orientation

### 0.1 What this framework is

A hierarchical, sector-agnostic measurement system that ingests raw human–AI dialogue and emits validated, interpretable, multidimensional **synergy** scores — with uncertainty, longitudinal trajectories, cognitive-debt markers, and user-facing reports. It is built bottom-up from **106 atomic behavioral neurons**, aggregated through **8 ARI dimensions** into **4 pillars** (and, in parallel, a psychometric **bifactor structure**), scored by **Bayesian IRT**, and conditioned on **task context** and **cognitive state**.

The unit of analysis is the **chat** (a complete human–AI conversation), not the isolated prompt.

### 0.2 Version history

| Version | Origin | What it added |
|---|---|---|
| **v0** | Original ARI proposal | Conceptual taxonomy: 8 dimensions, 4 pillars. No measurement spec. |
| **v1 (Ritesh review)** | "Ritesh's work and ARI framework" | Dimensional-redundancy critique (validated); 106-neuron bottom-up design; independent convergence on Bayesian IRT; 4-layer alternative (Engage/Manage/Create/Design); sector-universality finding. |
| **v1.0 spec** | Architecture document | Full measurement instrument: θ/κ decoupling, bifactor SEM, GRM/IRT, HMM, change-point, EWMA debt curve, complementarity bound, phased validation. |
| **v1.1** | "Synergy-based framework design" | 3-extractor pipeline (deterministic / LLM-judge / dynamic); length-residualized normalization; equal-weight v1 aggregation; 23-chat gold calibration; ICC gates; minimum-across-pillars rule. |
| **v1.2** | "Human learning coefficient…" | Human Learning Coefficient (λ); S_human token-efficiency metric; 2×2 regime surface. |
| **v1.3** | "Neural flagging and psychological validity" | LLM-judge feasibility established; 3-layer sensing stack; cross-session retention probe; multi-modal roadmap. |
| **v2.0** | This synthesis | All of the above unified. Plus: 106-neuron contract schema formalized; N/A scorability gate; embedded cognitive-load flag + ToM slope; flexible *N*-dimension structure; user-facing translation layer; explicit data-storage philosophy. Cognitive State Pre-Classifier (full version) deferred — only its two zero-infrastructure pieces ship now. |

### 0.3 What changed from v1.0 (explicit diff)

**Added in v2.0:**
- The **106-neuron content layer** with a formal per-neuron contract schema (§4) — v1.0 had only ~16 signal families.
- **Normalization and aggregation** mechanics (§6, §21) — length-residualization, rate-per-1000-tokens, equal-weight v1 → EFA-learned v2.
- The **Human Learning Coefficient λ** and **S_human** efficiency metric with their 2×2 regime surface (§15–17).
- **N/A handling** via a formal scorability gate (§18) — v1.0 only assumed sufficient length.
- **Embedded cognitive-state flags** (§19) — the two pieces of the deferred cognitive-state classifier that require no new infrastructure.
- The **user-facing translation layer** (§25).
- The **3-layer sensing stack** and longitudinal observatory (§28).
- An explicit **data-storage philosophy** (§29) — store at the neuron level so the hierarchy stays a testable hypothesis.

**Changed:**
- Dimension count is no longer frozen at 8. The architecture accepts **8–11 dimensions, determined by EFA** (§2.3, §10).
- The **4-pillar developmental structure** (Engage/Manage/Create/Design) and the **3-super-factor psychometric structure** are both retained as competing hypotheses to be tested empirically, not assumed (§2).

**Deferred (intentionally):**
- The full **Cognitive State Pre-Classifier (CSPC)** with its hierarchical-Bayesian conditioning mechanism. Held until the core pipeline is calibrated and stable; only the load flag and ToM slope ship in v2.0.

### 0.4 The seven design commitments

The first five are inherited from v1.0; each is forced by a specific empirical finding. Two are added in v2.0.

1. **Measure behavior, not self-report.** Self-efficacy is a poor proxy for competence (Chiu et al., 2025; SAIL4ALL, 2025); people are miscalibrated about their own offloading (Risko & Gilbert, 2016). Score what users *do* in the transcript.
2. **Decouple solo ability from collaborative ability.** Collaborative ability (κ) is a distinct construct from solo ability (θ) (Riedl & Weidmann). The headline metric isolates the *boost*, not the *level*.
3. **Synergy has a stringent, asymmetric baseline.** Synergy = dyad vs. max(human, AI) (Vaccaro, Almaatouq & Malone, 2024); augmentation = dyad vs. human. Most dyads achieve augmentation, not synergy. Do not use the flattering baseline.
4. **Synergy is conditional on learning and verification.** Explanations without a verification loop produce *negative* synergy (g ≈ −0.31); with verification, positive (g ≈ +0.30) (Berger et al., 2025). Reward verification, penalize unverified acceptance.
5. **Offloading is sometimes optimal — scoring must be task-conditioned.** High reliance on a superior AI for a low-stakes task is efficient delegation; identical behavior on a high-stakes task is dangerous over-trust. There is no context-free "good prompt."
6. **(v2.0) The hierarchy is a hypothesis, not an axiom.** Store data at the neuron level; let EFA decide the dimension count and the super-factor grouping. The framework must survive its structure being wrong.
7. **(v2.0) A score that cannot be explained to the user is incomplete.** Every output ships with a plain-language band, behavioral attribution, and an interpretation anchor. The translation layer is part of the instrument, not an afterthought.

---

## Part A — Theoretical Foundation

## 1. Research foundation

### 1.1 The evidence base

| Source | What it establishes | What we operationalize |
|---|---|---|
| **Vaccaro, Almaatouq & Malone (2024)** | 370 effects / 106 studies; synergy is rare; baseline = max(H, AI); Hedges' g | Formal synergy vs. augmentation definitions; effect-size standardization |
| **Berger et al. (2025)** | Explanation-without-feedback → negative synergy; learning is the missing moderator | The "explanation trap" flag; verification-loop reward; λ |
| **Riedl & Weidmann** | Two-stage Bayesian IRT; θ vs κ; ToM as causal engine (trait + state); LMRA scores ToM from prompts | The scoring spine; ToM-signature extraction; the trait/state split behind the cognitive-state flags |
| **Steyvers et al. (2022)** | Complementarity bounded by latent correlation ρ_HM; confidence asymmetry; weaker AI still helps if errors decorrelate | Creative Divergence = driving ρ_HM down; the accuracy–correlation bound; confidence-asymmetry features |
| **Bao, Gong & Yang (2023)** | Synergy as iterative affordance-actualization loop; four affordances; patterns shift with task uncertainty | Interaction-chain (not single-prompt) scoring; the Task-Uncertainty Matrix |
| **Kosmyna et al. (2025, MIT)** | Neural connectivity scales down with AI support; LLM group weakest coupling, poor recall; Brain-to-LLM > LLM-to-Brain on later transfer | Mechanistic grounding for cognitive debt; the falsifiable transfer prediction; the cross-session retention probe |
| **Risko & Gilbert (2016)** | Offloading is metacognitively triggered, a self-reinforcing drift; offloading can be optimal | The dependency-marker model; the normative caveat (commitment 5); λ's self-reinforcing-loop logic |
| **Gerlich (2025)** | r = −0.68 AI-use ↔ critical thinking, mediated by offloading; non-linear decay past a threshold | Empirical thresholds for the accelerated-decay penalty; demographic priors |
| **Ayodele et al. (Augmented Cognition Framework)** | Dual-mode cognition; asymmetric dependency; Orchestration as a 7th meta-level; fluent incompetence as the central risk | The Orchestration dimension; mode-switching / trust-calibration / degradation-detection capacities |
| **Chiu et al. (2025, SAICS)** | 8 validated competency dimensions; self-report is the wrong instrument; CFA CFI .95, RMSEA .056 | The literacy-vs-competency shift; the Attribution Gap; invariance testing |
| **SAIL4ALL (2025)** | Multi-phase scale development; CFA fit thresholds; reliability often below bar with binary items | The validation-methodology template; fit-index targets |
| **Precision Proactivity (Lepine et al.)** | Conversation-derived load features: element interactivity, phase spread, dependency debt; unsolicited task-switching is the strongest negative predictor | The cognitive-load instrumentation; the load flag; dependency-debt signal |
| **Human–AI team decision-making (Table 1)** | Eight complementarity dimensions; over/under-trust failure modes | Role-partitioning and trust-calibration behavioral targets |

### 1.2 Classical scaffolding

The framework inherits: **Cognitive Load Theory** (Sweller — intrinsic/germane/extraneous); **metacognition** (Flavell; Nelson & Narens; Zimmerman); **distributed/extended cognition** (Hutchins; Clark & Chalmers); **intelligence augmentation** (Engelbart); the **ZPD and scaffolding** (Vygotsky); **desirable difficulties** (Bjork); **trust in automation** (Lee & See, 2004; Hoff & Bashir, 2015); the **Google effect / transactive memory** (Sparrow et al., 2011); and the **complementarity** program (Bansal et al.).

---

## 2. The unified hierarchical structure

### 2.1 Three levels, bottom-up

```
106 atomic neurons   ← the trainable, observable content layer (what we score)
        │  aggregate
        ▼
   8 ARI dimensions   ← AL · PR · EC · ES · CS · CD · AUI · CA (latent competencies)
        │  aggregate
        ▼
    4 pillars         ← Engage · Manage · Create · Design (developmental, OECD/PISA-aligned)
```

The eight dimensions are: **AL** (AI Literacy), **PR** (Prompt Reasoning), **EC** (Error Correction), **ES** (Ethics Sensitivity), **CS** (Contextual Synthesis), **CD** (Creative Divergence), **AUI** (Augmentation Instinct), **CA** (Collaborative Agency). This is the team's working set and the set Ritesh's 106 neurons were authored against.

### 2.2 Two competing organizing structures — both retained as hypotheses

There are two defensible ways to group the eight dimensions above the dimension level, and v2.0 deliberately does **not** pick one a priori:

**(a) The developmental 4-pillar structure (Ritesh / ARI / OECD-PISA):**
- Engage = {AL, PR}
- Manage = {EC, ES}
- Create = {CS, CD}
- Design = {AUI, CA}

**(b) The psychometric 3-super-factor structure (v1.0 architecture):**
- Orchestration & Governance = {CA, OR, ES}
- Epistemic Integrity = {EC, AUT, AL}
- Generative Complementarity = {CS, CD}

> Note on AUI: the v1.0 architecture splits **AUI** into **OR** (Adaptive Orchestration / trust calibration) and **AUT** (Cognitive Autonomy / anti-debt). The team's working taxonomy keeps AUI unified and adds **PR** as a distinct dimension. v2.0 keeps both labelings live: the neuron contracts are authored against the 8-dimension working set (with AUI and PR), and the OR/AUT split is treated as a candidate refinement that the EFA may or may not justify.

These are not reconciled by argument. They are reconciled by **EFA on the 106-neuron response matrix** (§10). Whichever grouping the loadings support is the one that ships. If the developmental pillars fit the data better than the psychometric super-factors, that is the finding.

### 2.3 The dimension count is not frozen

v2.0 is built to accept **8 to 11 dimensions**. Three structural revisions are anticipated and explicitly allowed:

1. **PR may be confirmed as a standalone 9th construct** (the working taxonomy already treats it as distinct; the v1.0 architecture had folded prompt-reasoning across CA/AL).
2. **The super-factor grouping may change** — the 4-pillar developmental arc may out-fit the 3-super-factor psychometric grouping.
3. **CA may bifurcate** — its ~17 neurons span both session-level executive control and metacognitive self-governance, which may load on separate sub-factors.

The aggregation layer (§21) and the SEM (§10) both take dimension count as a parameter, not a constant.

## 3. Formal definition of synergy

Synergy is defined at two levels; both are reported.

**(a) Performance-level (outcome view).** For task *t* by dyad *d = (H, AI)*:

$$\text{Syn}_t = \frac{\mu_d - \max(\mu_H, \mu_{AI})}{\sigma_{\text{pooled}}} \quad (\text{Hedges'-}g,\ \text{bias-corrected})$$

This is the Vaccaro/Malone bar. It needs counterfactuals for μ_H and μ_AI, which raw chat usually lacks — a central limitation (§33) the latent model circumvents.

**(b) Capacity-level (latent view).** The boost a user extracts, isolated from baseline expertise:

$$\text{Boost}_i = \kappa^{\text{total}}_{i,AI} - \theta^{\text{human}}_i, \qquad \kappa^{\text{total}}_{i,AI} = \kappa^{\text{human}}_i + \kappa^{\text{AI}}_m$$

where θ_i is solo ability, κ^human_i the user's collaborative ability, κ^AI_m the model's contribution (Riedl & Weidmann). This is estimable from behavior even without ground-truth performance.

**Working definition.** *Human–AI synergy is the degree to which a user's behavior during interaction raises the dyad's effective cognitive output above the better of the two agents acting alone, while preserving or building the user's independent capability.* The second clause is essential: output gains accrued while accumulating cognitive debt are **not** synergy — they are borrowing against future capability (Kosmyna; Gerlich).

---

## Part B — The Content Layer (the 106 neurons)

## 4. The 106-neuron item bank

The neurons are the **trainable, observable units** of the framework. Everything above them (dimensions, pillars, super-factors) is an aggregation. This is the single most important addition in v2.0: v1.0 had only ~16 signal families; the neurons give each dimension 11–17 concrete items, which is the minimum needed for stable IRT estimation and credible-interval reporting.

### 4.1 The per-neuron contract schema

Every one of the 106 neurons must be written out as a contract row with exactly these fields. This contract is the artifact that turns Ritesh's prose descriptions into something a scorer can run, and it is the highest-priority unbuilt deliverable (§34).

```
id              | stable identifier, e.g. CA-15
dimension       | parent dimension (AL/PR/EC/ES/CS/CD/AUI/CA)
type            | construct type (behavioral / metacognitive / structural)
micro_rubric    | 1–5 behavioral anchors (the LLM-judge scoring scale)
extractor_type  | deterministic / LLM-judge / dynamic
valence         | +1 (healthy synergy) or −1 (cognitive debt / over-reliance)
applicability_rule | the condition under which the neuron fires
sector_universal   | yes (97–98 neurons) / no (the ~8 exceptions, flagged explicitly)
```

Supplementary field used during integration: `flag: check_EFA` — applied to any neuron suspected of overlapping with another, so redundancy is resolved empirically rather than asserted.

### 4.2 The valence system

Directionality is explicit and load-bearing, because a neuron firing positively versus negatively moves the dimension score in opposite directions, and the aggregation logic depends on getting this right *before* the first calibration run.

- `valence = +1` for healthy synergy behaviors (e.g., AUI-08 "Dependency Risk Awareness" is protective; CA-16 "Pre-Generation Epistemic Independence" is healthy).
- `valence = −1` for cognitive-debt behaviors (over-delegation, blind trust, unverified acceptance). Several neurons embedded inside CA and AUI describe over-reliance and are negatively valenced.

The valence map is extracted from the neuron descriptions, not invented. Ritesh's write-ups already carry the signal; it must be made explicit in the contract.

### 4.3 Sector-universality → task-type (not domain) conditioning

Ritesh ran 97–98 of the 106 neurons across all 7 major sectors and found they applied universally. This is a real empirical result and it justifies a clean design decision: **condition on task type (decide / create / learn / produce), not on sector/domain.** Domain conditioning happens only at the normalization stage (post-extraction), per Vaccaro's task-type moderation finding — never at the neuron level. The ~8 non-universal neurons are flagged `sector_universal = no` and handled as exceptions. This is the stated rationale that answers a reviewer asking "why not build sector-specific weights?"

### 4.4 Worked contract rows (priority dimensions: EC and AUI)

EC (Error Correction) and AUI (Augmentation Instinct) are scored first because they are the highest-signal dimensions for Skilled-Outsourcer detection. Illustrative rows (micro-rubric abbreviated to the level-5 anchor):

| id | dimension | type | extractor | valence | applicability | sector_univ |
|---|---|---|---|---|---|---|
| EC-01 | EC | behavioral | LLM-judge | +1 | AI produced a checkable claim | yes |
| EC-04 | EC | behavioral | LLM-judge | +1 | high-stakes output present | yes |
| EC-09 | EC | behavioral | deterministic | −1 | ≥1 confident AI claim accepted with zero verification turns | yes |
| AUI-03 | AUI | metacognitive | LLM-judge | +1 | multi-turn session > 5 turns | yes |
| AUI-08 | AUI | metacognitive | LLM-judge | +1 | reliance decision visible in transcript | yes |
| AUI-11 | AUI | behavioral | dynamic | −1 | task complexity rising while human contribution falling | yes |

These rows are the template; the full table (all 106) is the first deliverable for the team.

---

## Part C — Signal Extraction

## 5. The three-extractor architecture

Signals are extracted by three extractors operating together. They correspond directly to the three tiers of the v1.0 architecture (Tier A / B / C) and the team's deployed pipeline.

### 5.1 Deterministic extractor (Tier A)

Transparent, reproducible, ~free. Mechanically observable from transcript metadata: turn counts and lengths; question density; lexical confidence/hedging markers; syntactic complexity and readability (Flesch–Kincaid, SMOG, Dale–Chall — validated load correlates in Precision Proactivity); imperative-vs-interrogative ratio; presence of constraints, examples, and success criteria in prompts; edit ratio; copy-paste events. A neuron is `extractor_type = deterministic` only if it is mechanically observable this way; everything else is LLM-judge.

### 5.2 LLM-judge multi-pass extractor (Tier C)

Inferential, highest coverage, requires calibration. A structured rubric prompt scores each chunk on the neurons that load on each dimension and on ToM linguistic signatures. Riedl & Weidmann demonstrated an LMRA recovers ToM from prompts at ICC ≈ 0.59 against aggregated human gold — so this is achievable, but only verified per-construct (§26). Outputs are **graded ordinal codes** (0–4 per neuron per chunk), never free text, so they feed the IRT directly. Multi-pass = an ensemble of distinct base models for judge-judge agreement.

### 5.3 Dynamic per-window extractor (Tier B)

Model-based but objective, computed over sliding windows:
- **Attribution Gap** = 1 − sim(AI output, user's subsequent contribution) — the core anti-replacement metric (bypasses self-report inflation).
- **Latent reasoning correlation ρ̂_HM** = semantic correlation between the AI's proposed reasoning path and the human's subsequent prompts (low = high Creative Divergence).
- **Cognitive-load dynamics** (Precision Proactivity): element interactivity, phase spread, dependency debt.
- **Novelty generation** = semantic distance of the user's injected content from prior turns and AI outputs.
- **Unsolicited task-switching** by the model (the strongest negative predictor of output quality in Lepine et al.) — tracked via a subtask focus stack.

### 5.4 Judge control and calibration (mandatory for validity)

Because Tier C uses an LLM to evaluate human–LLM interaction, **judge circularity and bias are first-order threats** (§33). Mitigations are part of the spec:
- A **human-coded anchor set** (the 23 gold chats, double-coded) calibrates and continuously audits the judge; report inter-rater reliability (ICC, Krippendorff's α) and judge–human agreement.
- **Rubric anchoring with exemplars** per ordinal level; fixed temperature; versioned prompts.
- **Tier-A/B cross-checks:** where deterministic features and the judge disagree systematically, flag and recalibrate. Judge per-code uncertainty propagates into score intervals (§14).

## 6. Normalization

Raw neuron firings are normalized before aggregation so that conversation length and verbosity do not contaminate scores:
- **Length-residualization:** regress each raw signal on conversation length (turns/tokens) and use the residual, so a longer chat does not mechanically inflate counts.
- **Rate-per-1000-tokens:** count-type signals are expressed as rates, not totals.
- **Task-type conditioning** is applied here (post-extraction), per §4.3 — domain/task moderates the normalized signal, the neuron itself stays universal.

---

## Part D — Mathematical Core

## 7. Measurement model (GRM / IRT)

Each chunk *c* yields, per dimension *D*, an ordinal code $X_{icD} \in \{0,\dots,K\}$. We use **Samejima's Graded Response Model**. For person *i*, item (chunk-dimension) *j*, the probability of responding in or above category *k*:

$$P^{*}_{ijk}(\eta_i) = \frac{1}{1+\exp(-a_j(\eta_i - b_{jk}))}, \qquad P_{ijk} = P^{*}_{ijk} - P^{*}_{ij(k+1)}$$

where η_i is the latent dimension trait, a_j the discrimination, b_{jk} the category thresholds. GRM gives **item information** for free — which neurons are most diagnostic at which ability levels — and lets us prune low-information items. This is where the bottom-up neurons earn their discrimination parameters: the data tells us which of Ritesh's 106 actually separate high- from low-synergy users.

## 8. Decoupling solo from collaborative ability (the Riedl–Weidmann spine)

The probability of a quality outcome on item *j*:

$$\text{solo:}\quad \Pr(Y_{ij}=1) = \operatorname{logit}^{-1}(\theta^{\text{human}}_i - \beta_j)$$
$$\text{with AI } m:\quad \Pr(Y_{ij}=1) = \operatorname{logit}^{-1}(\kappa^{\text{human}}_i + \kappa^{\text{AI}}_m - (\beta_j + \gamma_j))$$

with β_j the task difficulty and γ_j the collaboration-specific difficulty adjustment. The **boost** is $\kappa^{\text{total}}_{i,AI} - \theta^{\text{human}}_i$.

**Ground-truth scarcity (the central problem).** Pure chat usually lacks correctness labels, so κ is partly model-inferred rather than measured. Four mitigations: (1) behavioral quality as the observable in the GRM; (2) the 23-chat gold set as anchored ground truth; (3) outcome linkage where available (artifact quality, downstream task success); (4) honest CI widening when correctness is unobserved. This is the strongest and most contestable assumption in the framework (§33).

## 9. The complementarity bound (Steyvers et al.)

Complementarity is bounded by the latent error correlation ρ_HM between human and machine. Even a weaker AI helps if errors decorrelate; a strong AI whose errors mirror the human's adds little. **Creative Divergence (CD)** is operationally defined as driving ρ̂_HM *down* — introducing orthogonal constraints and experiential knowledge that open the statistical space where complementarity is possible. ρ̂_HM is estimated from Tier B (§5.3) and used as a falsifiable criterion variable.

## 10. Dimensionality testing and the bifactor SEM

The structure (8 dimensions, the super-factor/pillar grouping) is **tested, not assumed**, on the 106-neuron response matrix:

1. **Parallel analysis + scree + VSS + MAP** to estimate the number of factors. This is the procedure that decides whether the count is 8, 9, 10, or 11 (§2.3).
2. **EFA** to inspect the loading pattern — which neurons load where, which cross-load, which are redundant (`check_EFA`).
3. **Confirmatory bifactor / second-order SEM** to test the hypothesized structure: a general factor $g_{\text{syn}}$ plus the super-factors (or pillars).
4. **Measurement invariance** testing across demographic groups (configural → metric → scalar), per SAICS/SAIL4ALL.
5. **Bifactor indices** — Omega-hierarchical (ω_h) and Explained Common Variance (ECV). If ω_h is high and ECV > ~0.7, the data are essentially unidimensional and reporting 8 separate scores would be misleading — the honest output would then be one g-factor plus a few diagnostic residuals.

This step adjudicates between the 4-pillar and 3-super-factor hypotheses (§2.2). Whichever fits, ships.

## 11. Hierarchical Bayesian estimation

Dimension traits, super-factors, and $g_{\text{syn}}$ are estimated jointly as posterior distributions (MCMC — Stan/NumPyro/PyMC). Demographic priors are used where justified by invariance testing, with the explicit caveat that priors which *control* for baseline can, if misused, *encode* disadvantage — so group-conditioned scoring must be transparent and contestable (§33).

## 12. Temporal modeling (trajectories, regimes, debt)

A user's record is a set of trajectories, not a snapshot:
- **Per-dimension growth slope** via latent growth curve models.
- **ToM trait/state decomposition** (Riedl) — a stable trait plus moment-to-moment state variance; the state component is exposed as a flag (§19).
- **Kalman filtering** for online state estimation.
- **HMM regimes** — discrete interaction regimes (e.g., scaffolded-learning vs. passive-delegation) with timestamped transitions.
- **Change-point detection** for the non-linear decay threshold (Gerlich's finding that critical thinking decays sharply past a usage threshold).
- **Cognitive-debt EWMA** — an exponentially-weighted moving average of debt-valenced signals, with an accelerated-decay flag when the curve crosses the empirical threshold.

## 13. Network vs. latent fork

As an alternative to the reflective latent model, estimate a **Gaussian Graphical Model** (regularized partial correlations via graphical LASSO) treating neurons/dimensions as a mutually-reinforcing system. **Centrality** then identifies load-bearing behaviors (if EC is the most central node, target verification for intervention). Recommendation: report the latent index as the primary product and the network as a diagnostic/interventional companion; compare their fit empirically rather than assuming one.

## 14. Uncertainty, reliability, and validity

- Every score ships as a posterior with a **credible interval**. Judge uncertainty and ground-truth scarcity both widen intervals honestly.
- **Reliability:** marginal reliability from the IRT; ω_h and ECV from the bifactor model; inter-rater and judge-human ICC from the gold set.
- **Validity battery:** content (Delphi), structural (CFA/invariance), convergent/discriminant, criterion (against the Kosmyna-style transfer test), and consequential (fairness audit).

---

## Part E — Cognitive-Debt Instrumentation

These two metrics are the project's distinctive contribution beyond standard psychometrics. They pull in opposite directions, which is exactly why both are needed.

## 15. The Human Learning Coefficient (λ)

**The premise** — *"if learning is detected, there is less chance of cognitive debt"* — is supported by three independent strands: Berger's RoBMA result (learning-causing design flips g from −0.31 to +0.30), Risko & Gilbert's self-reinforcing offloading drift (only maintained internal capability breaks the loop), and Kosmyna's neural evidence (the learning-connectivity surge does not appear when AI carries the load, and solo performance never recovers to baseline).

λ is therefore **not a yes/no detector — it is a rate**: the AI-attributable, practice-adjusted slope of the user's *solo* capability over repeated sessions. The spine is the longitudinal slope of solo ability θ from the Bayesian-IRT backbone, estimated from periodic **no-AI probe items**, netted against ordinary practice:

$$\lambda_i = \underbrace{\frac{d\,\theta_i^{\text{AI-assisted}}}{dt}}_{\text{solo gain with AI in the loop}} - \underbrace{\frac{d\,\theta^{\text{control}}}{dt}}_{\text{practice-only baseline}}$$

The baseline comes from a matched no-AI arm or a Kosmyna-style within-subject crossover. Around this spine, fold convergent indicators into a small latent learning factor Λ_i: the slope of metacognitive-probe accuracy (the existing "Learning Signal"), the slope of query generativity (generative-to-extractive ratio climbing over time), transfer-test performance on an unassisted novel task, and — if neural data is ever available — EEG connectivity recovery on solo tasks.

**The trap (critical):** measure λ from *downstream solo performance, never from in-session confidence or fluency.* Tool use systematically inflates "cognitive self-esteem" while solo capability drops (metacognitive inflation), and a fluent AI rationale *feels* like understanding while producing none (the explanation trap). Any in-session "this felt productive" signal is exactly what to discard.

## 16. The S_human token-efficiency metric

S_human captures how much redundant model computation the human's intelligence *avoided* — the value of human specificity. It is a **counterfactual residual, not a meter reading:**

$$S_{\text{human}} = \kappa^{\text{human}}_{\text{eff}} \cdot \left[\hat{T}_{\text{redundant}}^{(0)} - \hat{T}_{\text{redundant}}^{(\text{human})}\right]$$

where $\hat{T}_{\text{redundant}}^{(0)}$ is expected redundant tokens under a no-specificity baseline, $\hat{T}_{\text{redundant}}^{(\text{human})}$ is redundant tokens with the human's actual contribution, and $\kappa^{\text{human}}_{\text{eff}}$ is the human's effective collaborative ability (from the IRT, swapping correctness for negative log-tokens).

Supporting structure:
- **Token split:** total tokens = $T_{\text{floor}}$ (irreducible, to locate via multiple runs per (task, model)) + $T_{\text{redundant}}$ (avoidable sprawl).
- **What the human actually contributes:** information (ΔH), not tokens — they reduce uncertainty about the goal (Information Bottleneck framing).
- **Caching multiplier:** early-phase specificity is worth more — early sprawl is re-paid every subsequent round (cache-read multiplier).
- **Validity gate — refuse to score when:** output quality is below a domain-expert-defined Q*, human information contribution is below threshold τ, or the (task, model) cell is uncalibrated.

## 17. The 2×2 regime surface (λ × S_human)

S_human alone is a vanity metric. It is **always reported paired with λ**:

|  | Low S_human | High S_human |
|---|---|---|
| **High λ** | Productive struggle (healthy for novices) | **True synergy** (target state) |
| **Low λ** | Friction (stalling or aversion) | **Skilled Outsourcer** — cognitive-debt flag fires |

The identical offloading signals are scored as *scaffolded delegation* in the top row and *substitutive offloading* in the bottom row. S_human is good news only when λ ≥ 0. This 2×2 is the operational heart of the Skilled-Outsourcer detection that the whole framework is built to deliver.

---

## Part F — Contextual Conditioning

## 18. N/A handling and the scorability gate

The model must never confuse "absent" with "low." A dimension that cannot be evidenced from a given chat is marked N/A and excluded from the index — not scored as zero, not imputed.

**Scorability indicator.** For person *i*, dimension *d*:

$$S_{id} = \mathbb{1}\left[n_{id}^{\text{items}} \geq \tau_d\right], \qquad \tau_d = 3\ \text{(recommended minimum scorable chunks)}$$

**Two distinct N/A cases**, same math, different meaning:
- **Structural N/A** — the task type cannot elicit the dimension (e.g., Creative Divergence in a pure factual lookup; Ethics Sensitivity with no value-laden content). The Task-Uncertainty Matrix specifies which dimensions are elicitable per task type.
- **Random N/A** — insufficient conversation length.

**Mathematical handling:**
- In the IRT, a missing dimension contributes no item responses; the posterior reverts to the (uninformative or population-calibrated) prior, and the CI widens. This is reported as "unscored," distinct from a low score.
- In the SEM, structural missingness is handled by **FIML** (full-information maximum likelihood) — all available information, no imputation.
- The gated index is computed over observed dimensions only: $\text{Index} = g_{\text{syn}}^{(S)} \times \prod_k \min(1, G_k^{(S)})$, and **every score set ships with a coverage flag** (how many of the dimensions were scorable). A 8/8-coverage score and a 5/8-coverage score are not comparably interpretable even with identical observed values.

## 19. Embedded cognitive-state flags (the CSPC pieces that ship now)

The full Cognitive State Pre-Classifier is deferred (§0.3). But two of its components require **zero new infrastructure** — they are already computed inside existing extractors — and ship in v2.0 as contextual metadata attached to every report:

- **Cognitive Load flag** (Overloaded / Optimal / Underloaded), derived from the Tier-B Precision-Proactivity signals already specified (element interactivity, dependency debt, information sprawl). A user accepting AI output under overload is *coping*, not *delegating*; the flag lets a human reader interpret a low EC/AUT score correctly. It is reported as a flag in v2.0; the *conditioning* mechanism (using load to adjust IRT thresholds) waits for the full CSPC.
- **ToM slope flag** (Engagement: rising / flat / declining), the within-session trend of ToM signatures already extracted in Tier C (Riedl's rubric). A declining slope (coordinating → bare extraction) marks accumulating extraneous load or disengagement.

Both are **named output fields**, not new measurements. This is the maximal slice of the cognitive-state idea that can ship safely before the core pipeline is calibrated.

## 20. The Task-Uncertainty Matrix

All scoring is conditioned on task context (commitment 5). The matrix classifies each chat segment by task type (decide / create / learn / produce) and uncertainty/stakes, and:
- determines which dimensions are *elicitable* (feeding the structural-N/A logic, §18);
- flips the scoring valence of reliance behaviors (efficient delegation under low stakes ↔ over-trust under high stakes);
- activates the non-compensatory gates (§22) — e.g., the Ethics gate engages only on value-laden, high-stakes segments.

---

## Part G — Scoring and Aggregation

## 21. Aggregation: equal-weight v1 → EFA-learned v2

Aggregation runs bottom-up: neurons → dimensions → pillars/super-factors → $g_{\text{syn}}$.
- **v1 (now):** equal-weight aggregation within each level. Defensible and transparent until enough response data exists to learn weights.
- **v2 (after calibration):** EFA/IRT-learned weights — neuron weights become discrimination parameters; dimension weights come from the SEM loadings.

**Why store at the neuron level (the storage philosophy, §29):** because the weights *will* change — from equal-weight v1 to EFA-learned v2 to whatever the data eventually says. If only dimension scores were stored, every weighting revision would force re-collecting data. Storing leaves means the dataset survives every change to the theory. The hierarchy stays a hypothesis the data tests, never an assumption baked into unrecoverable numbers.

## 22. The gated synergy index

A pure weighted sum (compensatory) would let a brilliant generative user mask catastrophic over-trust; a pure minimum (non-compensatory) is too brittle. v2.0 uses a **hybrid**, plus a top-level pillar rule:

$$\text{Synergy Index} = \underbrace{g_{\text{syn}}\ \text{(bifactor headline)}}_{\text{compensatory core}} \times \underbrace{\prod_k \min(1, G_k)}_{\text{non-compensatory gates}}$$

where each gate $G_k \in (0,1]$ caps the index on a critical failure — e.g., a confirmed **Over-Trust gate** on a high-stakes segment, or an **Ethics gate** when value-laden tasks proceed with no boundary-setting. This encodes commitments 3 and 5 directly into the arithmetic.

**Minimum-across-pillars rule.** At the very top, the headline reportable is gated by the *weakest* pillar, not the average. This is the explicit Skilled-Outsourcer punisher: a user who is strong on Create but hollow on Design (orchestration/autonomy) cannot post a high overall synergy score by averaging over the gap.

## 23. Derived indices

- **Orchestration Capability Index (OCI):** weighted composite of CA, OR/AUI, AL plus the ACF four capacities (mode-switching, trust calibration, degradation detection, partnership optimization), measured behaviorally.
- **Reasoning Amplification Score (RAS):** the boost (κ_total − θ) on reasoning-heavy segments combined with CD and CS; positive only when output rises *and* the human's reasoning is visibly present.
- **Dependency Risk Metric (DRM):** rising function of Attribution-Gap-toward-dependence, offloading-without-verification, debt EWMA (§12), and a negative AUT/λ slope; the early-warning analogue of the MIT skill-atrophy finding.
- **Trust Calibration Indicator (TCI):** alignment between reliance and warranted reliance, penalizing both over- and under-trust, conditioned on the Task-Uncertainty Matrix.
- **Interaction Efficiency:** quality-of-collaboration per unit of extraneous load.
- **Adaptability:** responsiveness of reliance/strategy to changing task conditions (the helpful component of dynamic-state variance).

---

## Part H — Output and Translation

## 24. The eight-dimensional profile and personas

The system emits, per user (and aggregable per cohort): the 8-dimensional profile (posterior mean ± CI per dimension) plus pillars/super-factors and the headline $g_{\text{syn}}$; cognitive-debt tagging (debt curve, accelerated-decay flag, contributing behaviors); OCI, RAS, DRM, TCI, interaction efficiency, adaptability; the λ × S_human regime cell; and the full longitudinal trajectory object.

**Personas** are assigned via latent-profile / Gaussian-mixture analysis over the dimension vectors *and* trajectory features. Theory-anchored prototypes: *Orchestrator* (high OCI, high autonomy), *Sparring-Partner* (high EC/CD, builds with the AI), *Scaffolded-Learner* (rising autonomy, healthy delegation, high λ), *Skilled-Outsourcer* (high output, falling autonomy — the dangerous one the θ/κ decoupling and the 2×2 surface are built to expose), *Passive-Delegator / Over-Truster* (low EC, high debt), *Algorithm-Averse Expert* (high θ, low κ — under-trust). Personas are descriptive clusters with uncertainty, never deterministic labels.

## 25. The translation layer (user-facing reports)

Commitment 7: a score that cannot be explained is incomplete. The translation layer converts IRT posteriors into three user-actionable outputs per dimension:

1. **Performance band + behavioral sentence** — "Strong / Developing / Needs attention," with a one-line behavioral explanation: *"You verified AI outputs on 42% of high-stakes turns — above average, with room on ethical boundary-setting."*
2. **Top-3 signal attribution** — the specific behaviors that moved the score, with direction: *"↑ verification ratio, ↑ self-correction, ↓ boundary-setting on value-laden tasks."* This is recoverable from the IRT item-information function (each item's signed contribution to the posterior shift).
3. **One actionable recommendation** per flagged dimension.

Framing devices: the **persona** is the narrative frame; the **trajectory** is shown in plain language (improving / stable / declining); the **λ × S_human regime cell** is named ("you're in productive-struggle"). 

**Interpretation anchors are mandatory.** The 0–100 scale communicates nothing without them: every report shows "50 = median of the calibration corpus" and a behavioral exemplar at the 10th/50th/90th percentile, so the user knows what 60 means relative to real behavior. Internal computation stays on the IRT logit scale (≈ −4 to +4); the 0–100 criterion-anchored scale is for reporting; risk indices report on 0–1.

---

## Part I — Calibration, Validation, and Sensing

## 26. The 23-chat gold calibration set and ICC gates

The 23 chats are the **validation anchor, not the training set.** They exist to answer one question: can the cheap automated scorer reproduce careful human judgment? Scoring happens at the **neuron level** on these chats, double-coded by expert raters.

**The calibration gate is binary and unforgiving — and that is the point.** A dimension ships only if it clears:
- inter-rater **ICC ≥ 0.70** (humans agree on what the neuron means), and
- judge-vs-human **ICC ≥ 0.60** (the LLM judge reproduces human coding).

Some of the eight dimensions will fail this — the ones requiring inference about the user's internal state rather than pointing at something in the transcript. **That failure is a finding, not a defeat:** it tells you which constructs are honestly transcript-scorable and which need the platform's external probes. The Riedl precedent (ICC ≈ 0.59 on ToM) shows it is achievable, but only verified per-construct, never assumed across the board.

If the 23 ever became training data, the project would be fitting to 23 points and calling it generalization — exactly the overclaim the framework exists to avoid. The generalizable model is trained separately, at scale (hundreds of chats, user-feedback labels, dual-annotator reconciliation).

## 27. Phased falsifiable validation

1. **Content (Delphi):** expert panel rates each neuron/dimension for representativeness, relevance, clarity (as SAICS did across three rounds); prune redundant neurons.
2. **Pilot + neuron scoring** on the gold set; compute ICC gates.
3. **Structural:** parallel analysis → EFA → bifactor CFA → invariance (§10).
4. **Convergent/discriminant/criterion:** against external measures.
5. **The Kosmyna-style transfer study:** the single most important test of whether cognitive debt is real or a scoring artifact — pair AI-assisted phases with periodic unaided phases and measure solo-capability transfer.
6. **Longitudinal field study:** track real users over months; validate the growth/regime/debt models against observed capability change.
7. **Fairness audit:** consequential validity across demographic groups.

## 28. The three-layer sensing stack and the longitudinal observatory

The chat classifier is the cheap, scalable **middle** layer — not the whole instrument. Design the data collection from day one to support all three layers:

1. **Psychometric baseline** (predict-then-verify logs, no-AI probes) — the IRT ground truth and the λ baseline.
2. **Behavioral telemetry** (keystroke dynamics, dwell time on AI suggestions, copy-paste events, scroll-back, artifact diff history, retention of AI framing weeks later) — captures the "accept without reading" pattern and the longitudinal dimension that chat alone misses.
3. **Chat transcripts** — the current surface; cheapest, most scalable, weakest signal.

**The biggest under-explored opportunity: cross-session retention testing.** Kosmyna found LLM-group participants could not quote essays they had written minutes earlier. A randomized retention probe 48 hours after a session ("what was the core argument you made?") yields a longitudinal cognitive-debt signal no in-session metric can. The field's largest gap is the absence of a **longitudinal observatory** — every paper in the corpus is hours-to-days. Building that, even at small N, would be a contribution exceeding anything chat-only analysis delivers. Anything measured now that cannot be revisited in 6 months on the same users is, by Vaccaro's and Kosmyna's lights, a snapshot of a moving system.

---

## Part J — Engineering and Operations

## 29. Data-storage philosophy

Store at the **neuron level**, always. Persist every neuron firing (with chunk index, extractor, raw value, normalized value) rather than only dimension scores. Rationale in §21: weights change; only neuron-level storage lets the dataset survive every revision to the hierarchy. Store the gold-set human codes separately and immutably (they are the validation anchor, never training data).

## 30. Implementation stack

- **LMRA judge:** an ensemble of distinct base models, versioned rubric prompts, fixed temperature, graded-ordinal output.
- **Embeddings:** for Attribution Gap, ρ̂_HM, novelty, element interactivity.
- **Bayesian estimation:** Stan / NumPyro / PyMC for the GRM + hierarchical SEM.
- **Temporal:** hmmlearn (or custom) for regimes; standard change-point libraries; EWMA in-house.
- **Network:** graphical-LASSO for the GGM companion.
- **Storage:** neuron-level event store; separate immutable gold-code store.

---

## Part K — Honest Accounting

## 31. Assumptions

1. Behavioral signals in transcripts are valid proxies for the latent competencies (tested via the ICC gates).
2. The LMRA judge is reliable and reasonably unbiased after calibration (quantified, not assumed — §26).
3. Conversation chunking preserves the interaction structure that carries synergy signal.
4. A reflective latent structure exists for the default model (if the network ontology fits better, the index interpretation changes — §13).
5. Counterfactual baselines (μ_H, μ_AI) are estimable via the latent model even when unobserved — the strongest and most contestable assumption (§8).
6. Task type is recoverable from the transcript well enough to drive the Task-Uncertainty Matrix.

## 32. Tradeoffs

- **Compensatory vs. non-compensatory** scoring — resolved by the hybrid + minimum-across-pillars (§22).
- **Latent index vs. network** — reported together, fit compared (§13).
- **Breadth (106 neurons) vs. parsimony** — resolved by EFA pruning, not by assertion.
- **Research-grade vs. prototype** — the same architecture serves both; the prototype skips the experimental-validation and longitudinal steps and uses convergent validity only. Realistic timelines: ~9–12 months research-grade, ~4–6 months prototype.

## 33. Limitations

- **Ground-truth scarcity.** Pure chat often lacks correctness labels; the boost is then partly model-inferred. Outcome linkage is the only full remedy (§8).
- **Judge circularity.** Using an LLM to score human–LLM interaction risks rewarding interaction styles a model merely finds legible. Mitigated, not eliminated, by human anchoring and ensembles (§5.4).
- **Goal-completion detection (the recurring blocker).** Task-success outcomes for the IRT, the S_human token metric, and the productive-vs-wasted decomposition all need to know when a chat actually *reached its goal* — and a large fraction of real conversations have no crisp finish line. This is the top open problem (§34).
- **The normative problem.** "Good synergy" is partly a value judgment; the framework makes its value commitments explicit (commitments 1–7) rather than hiding them.
- **Fairness.** Demographic priors that control for baseline can encode disadvantage if misused; invariance testing and fairness audits are mandatory (§27).
- **Gaming / Goodhart.** Once scored, users may perform the signals; the behavioral-not-self-report stance and the verification-requiring gates raise the cost of gaming but do not eliminate it.

## 34. Open problems and build sequence

**Open problems, in order of how much they block:**
1. **Goal-completion detection** — blocks the IRT outcome, S_human, and the productive/wasted split.
2. **The per-neuron contract table** — all 106 rows in the §4.1 schema. Nothing can be scored without it.
3. **Sign-conflicted neurons** — behaviors that raise short-term tokens (exploratory questioning) but reduce long-term redundancy; the S_human estimator must handle these.
4. **Aggregation level for κ** — session vs. trajectory; when does $\kappa^{\text{human}}_{\text{eff}}$ stabilize?
5. **Q\* for open-ended tasks** — defining the quality gate where there is no objective correctness label.

**Build sequence (priority order):**

| # | Deliverable | Status |
|---|---|---|
| 1 | Per-neuron contract table (106 × schema), starting with EC and AUI | Not built — top priority |
| 2 | 23-chat gold calibration execution (neuron-level, double-coded) | Not run |
| 3 | ICC validation per dimension (≥ 0.70 / ≥ 0.60) | Not run |
| 4 | Goal-completion detection model | Not built |
| 5 | N/A scorability gate implementation (§18) | Spec'd |
| 6 | EFA on the 106-neuron matrix → fix the dimension count (§10) | Planned |
| 7 | λ + S_human integration into the live pipeline (§15–17) | Math complete |
| 8 | Embedded load flag + ToM slope output fields (§19) | Ready to ship |
| 9 | Translation layer (§25) | Spec'd |
| 10 | Behavioral telemetry + retention probe (§28) | Roadmapped |
| 11 | Full Cognitive State Pre-Classifier with conditioning | Deferred until 1–7 stable |

---

## Appendix A — Symbol glossary

| Symbol | Meaning |
|---|---|
| $\theta_i$ | solo (individual) ability of person *i* |
| $\kappa^{\text{human}}_i$ | person *i*'s collaborative ability |
| $\kappa^{\text{AI}}_m$ | model *m*'s contribution to collaborative solving |
| $\kappa^{\text{total}}_{i,AI}$ | total collaborative ability of the dyad |
| Boost_i | $\kappa^{\text{total}}_{i,AI} - \theta_i$ (capacity-level synergy) |
| $g_{\text{syn}}$ | general synergy factor (bifactor headline) |
| $\eta_i$ | latent trait on a given dimension |
| $a_j, b_{jk}$ | GRM discrimination and category thresholds for item *j* |
| ρ_HM | latent human–machine error correlation (complementarity bound) |
| $S_{id}$ | scorability indicator for person *i*, dimension *d* |
| λ_i | Human Learning Coefficient (difference-in-slopes of solo θ) |
| Λ_i | latent learning factor (convergent indicators around λ) |
| S_human | human token-efficiency contribution (counterfactual residual) |
| $T_{\text{floor}}, T_{\text{redundant}}$ | irreducible vs. avoidable token split |
| ΔH | information contributed by the human (uncertainty reduction) |
| Q* | domain-expert quality gate for the S_human validity check |
| $G_k$ | non-compensatory gate *k* (∈ (0,1]) |

## Appendix B — The condensed changelog

v0 (taxonomy) → v1 (Ritesh: 106 neurons + redundancy critique + IRT) → v1.0 (full measurement instrument) → v1.1 (3-extractor pipeline + normalization + 23-chat gold + ICC + minimum-across-pillars) → v1.2 (λ + S_human + 2×2 surface) → v1.3 (judge feasibility + 3-layer sensing + retention probe) → **v2.0 (this document: all unified + neuron contract schema + N/A gate + embedded cognitive-state flags + flexible N-dimensions + translation layer + storage philosophy; full CSPC deferred).**

---

*End of v2.0 specification. This document is the canonical reference; the v1.0 spec is retired. The single highest-priority next action is the per-neuron contract table (§4.1, §34).*
