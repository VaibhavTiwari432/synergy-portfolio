# Sustainable Augmentation Framework (SAF) / ARI — v3 Spec Delta over v2.2
### The Validation-and-Standards Revision — *"inherit before invent; benchmark before claim; honest limits before reach."*

**Document class:** Spec delta + integration plan (extends, does not replace, the v2.2 master compilation).
**Version:** v3 — **the validation-and-standards revision.** Where v2 fixed the measurement engine, v2.1 added population/humanity, and v2.2 integrated interaction dynamics, **v3 re-grounds every previously-bespoke mechanism in its established formal home** and makes the instrument honest about what it can and cannot claim. The unifying realization driving this revision: *several of SAF/ARI's hardest "open problems" are not novel — they are well-solved problems in adjacent fields (psychometrics, educational data mining, cognitive science of inquiry, human–AI reliance), and the disciplined move is to adopt validated machinery and standard metrics rather than defend invented constructs.*
**Supersedes for reference purposes:** nothing — this is a delta. The authoritative end-to-end reference remains `SAF_ARI_Final_Master_Compilation_v2.2.md`; this document layers onto it and will be folded into a v3 master compilation only after the changes below clear gold validation.
**Ontology status:** **FROZEN, unchanged.** 107 neurons · 8 dimensions · 4 pillars · 4D CSPC state. **v3 adds zero neurons, zero dimensions, zero pillars, zero latent-state variables.** Every change below is a measurement-engine method, an instrument, a validation procedure, a reporting fix, or governance — i.e. inside the freeze's permitted list (§14.3). Freeze-compliance audit: §V-Audit.
**How changes are marked:** the **v3 Change Set** (§0.0c) states every change (what + why + section + type + rung); inline **`[v3]`** callouts mark each edit at its point of application. Every claim carries a four-rung tag per §0.2 (DESIGNED / MEASURABLE / VALIDATED / ASPIRATIONAL). **No v3 claim is tagged VALIDATED** — validation is gated on a benchmark that does not yet exist (§F2).

---

## 0.0c — v3 Change Set (what changed and why)

Each row is a confirmed change. **Type** ∈ {Engine, Instrument, Validation, Reporting, Governance}. **Rung** is the highest rung the change can currently occupy. **Origin** records who surfaced it (PL = project lead; prior-art = the June 2026 literature sweep).

| # | Change | Why (failure fixed) | Section | Type | Rung | Origin |
|---|---|---|---|---|---|---|
| **V1** | **Reliability as a Generalizability-Theory study.** The K-replication plan becomes a formal crossed G-study (subject × judge-replication × occasion); σ_judge, σ_subject, σ_occasion are variance components; report the **absolute Φ coefficient**; a D-study sets K. | "Measure σ_judge" was ad-hoc. G-theory is the established framework for partitioning multi-facet measurement error and projecting how many replications buy a target dependability. | §A1, §7.7a | Validation | MEASURABLE | prior-art |
| **V2** | **Judge non-determinism protocol.** N-replication with mean ± SD; **stratified re-judging** (cheap heuristics → selective judge sampling → panel for quadrant-boundary chats); version-pinning + provenance stamps; semantic-equivalence aggregation. | Temperature-0 non-determinism flips quadrant assignments. Field-standard mitigation is N-replication + variance reporting + ensembles for high-impact decisions, not pretending determinism. | §A2, §5.8 | Engine | MEASURABLE | Grok G7 / PL / prior-art |
| **V3** | **`MEASUREMENT_SATURATED`** — the censored-reporting state. Third categorical sibling to `STRUCTURAL_NA` and `INSUFFICIENT_SAMPLE`. Right-censored (Tobit) treatment: report "≥ X, instrument saturated" not "= max". | The PL's "human potential has no cap" challenge. Conflates *unbounded construct* with *bounded display*. Real problem = ceiling/floor effects + information collapse at extremes. Censoring is the honest fix; uncapping would license judge hallucination. | §A3, §3.6, §9 | Reporting | DESIGNED | PL |
| **V4** | **The 107→8 neuron→dimension map is a Q-matrix.** Adopt **Cognitive Diagnosis Models** (DINA / DINO / G-DINA) as the **classification** backend, complementary to GRM (the **estimation** backend). **G-DINA empirically validates the Q-matrix** (tests neuron→dimension loadings). | CDM was already on the maturation roadmap (§7.7a, D1) but un-formalized. Recognizing the map as a Q-matrix unlocks (a) DINA's conjunctive logic as the formal twin of min-across-pillars, and (b) empirical validation of an assignment currently taken on faith. | §B1, §7.7a, §3.6 | Engine + Validation | DESIGNED | PL #3 / prior-art |
| **V5** | **Archetype discovery via LCA/LPA** — the categorical analog of the deferred EFA gate. Confirmatory (CDM, Q-matrix specified) paired with exploratory (latent-class). | The 10 archetypes are currently decreed. Latent-class analysis lets them be discovered-and-validated, the same discipline EFA imposes on the dimensions (commitment 6). | §B2, §7.7a | Validation | DESIGNED | PL #3 / prior-art |
| **V6** | **CDM identifiability folded into §8.1.** Q-matrix-based CDMs have documented non-identifiability / equivalence classes; this is the existing structural-identifiability gate restated in CDM terms. | Prevents adopting CDM without inheriting its known identifiability hazard. | §B3, §8.1 | Validation | DESIGNED | prior-art |
| **V7** | **Knowledge-tracing backend for the sustainability axis.** An **interpretable** BKT/IKT-style tracer (not deep DKT) with an **active forgetting parameter**, per dimension; uncertainty-preserving (state-space; the HGF is the natural host). | The sustainability axis ("is independent capacity growing or eroding?") *is* the knowledge-tracing problem, run with forgetting on. Mature, validated, interpretable. Deep DKT rejected for interpretability + the existing embedding deferral. | §C1, §7.7a | Engine | DESIGNED (data-gated) | prior-art |
| **V8** | **Retention probe → fitted decay curve.** Replace the binary 48-h gate with a fitted **stability** parameter (FSRS Difficulty–Stability–Retrievability, or half-life regression), from ≥2 staggered unaided probes (≥24 h apart; power-law form). | A single binary at 48 h discards the shape of forgetting. Stability is a continuous, per-subject, per-skill quantity; rising stability = capacity growth, falling = cognitive debt made measurable. It is the observable feeding V7. | §C2, §7.5a, §8.3 | Instrument | DESIGNED (data-gated) | Grok G3/G6 / prior-art |
| **V9** | **Question-asking science as an evidence instrument.** EIG / Optimal-Experiment-Design scoring of prompts + Graesser/Bloom question taxonomy, feeding **existing** PR / AL / EC neurons. Question-complexity/originality trajectory = candidate sustainability observable. | The PL's psychological input #1. Prompt quality is a primary, under-exploited behavioral signal. Freeze-safe (new fields/instruments on existing neurons). Externally grounded (see §C3). | §C3, §2.2, §5.9 | Instrument | DESIGNED | PL #1 / prior-art |
| **V10** | **Drift = longitudinal measurement (non-)invariance / Response Shift.** Re-score the frozen anchor set on schedule; test **scalar invariance over time via ΔCFI**; failure = drift alarm distinguishing judge drift from subject change. Anchor-item design; **Reg-DIF** for small-sample anchor selection. | "Hosted judge drift is a validity threat" had no formal test. Response Shift is the exact psychometric name; scalar invariance is the precise condition under which a change score is interpretable. | §D1, §8.x | Validation | MEASURABLE (test) / data-gated (run) | PL / prior-art |
| **V11** | **Fairness three-level discipline (AERA/APA/NCME).** Distinguish mean differences (≠ bias) · item bias / DIF · predictive bias (Cleary). DIF gate restated; group differences never treated as bias. | The existing DIF gate lacked the surrounding fairness taxonomy. Prevents the common error of reading a group mean gap as bias. | §D2, §7.7a | Validation | DESIGNED | prior-art |
| **V12** | **Re-anchor synergy/reliance metrics on the appropriate-reliance literature.** Weight of Advice (continuous), switch fraction, appropriate reliance (over/under), judge-advisor framework for transfer tasklets, TIAS for self-rating construction. | The synergy/reliance signals were partly bespoke. A live field has validated constructs; importing them inherits their validation and stops re-derivation. | §E1, §5.8 | Instrument | VALIDATED in source field / DESIGNED here | PL #2 / prior-art |
| **V13** | **Scope-honesty / claims-ladder correction.** Explicit: on the **within-chat synergy** axis, the full apparatus is a reliability-and-calibration **wrapper** around an LLM judge. The framework's **irreplaceable** value is (a) the **sustainability axis** and (b) the **validation apparatus**. | The PL's existential challenge #3. Honest scoping strengthens, not weakens, the framework: it stops over-claiming on single-chat synergy and stakes existence where the claim is defensible. | §E2, §0.3 | Governance | n/a (epistemic correction) | PL #3 |
| **V14** | **Operate under the AERA/APA/NCME Standards.** Validity = evidence supporting a **specific** score interpretation/use; structure the OSF pre-registration around validity/reliability/fairness; cite AI-scored-constructed-response validity (Williamson; McCaffrey); add **QWK** alongside MAE as the judge-vs-human agreement metric. | The instrument is a psychometric test; the Standards are the governing reference and were unstated. QWK is the field-standard agreement metric for AI-scored constructed responses. | §F1, §0.2, §8.x | Governance | DESIGNED | prior-art |
| **V15** | **Benchmark vs pilot — formalized.** The 26 gold chats are a **PILOT/SEED, not a benchmark.** **Split the 8-dimension and 107-neuron data timelines** (annotation grain caps downstream). Minimum-viable-benchmark spec defined. | The PL's challenge #2. 26 single-archetype, 8-dim-grain chats cannot fit 107-neuron psychometrics, cannot hold out a test split, and double-duty as calibration+test. Naming them a benchmark would be rung-inflation. | §F2, §7.2a | Governance | n/a (definition) | PL #2 |
| **V16** | **Freeze status update + structural-transition triggers.** Freeze on new latent variables **holds**; v3 specifies the trigger conditions for the *permitted* structural transitions (GRM activation, EFA-learned loadings, CDM Q-matrix validation, freeze lift). | v2.2 froze the ontology but left the un-freeze conditions implicit. v3 makes the ladder explicit so transitions are gated, not opportunistic. | §F3, §14.3 | Governance | DESIGNED | PL / prior-art |

> **v3 thesis (adopted as this revision's summary sentence):** *SAF understands cognition; AEGIS understands interaction dynamics; v2.2 converged them; v3 grounds the convergence in established measurement standards and tells the truth about what is measured versus what is merely scored.*

---

## 0.0d — Disposition of the Grok V2.2 Refinements (G1–G9)

Every Grok proposal is dispositioned here so none silently resurfaces (the §14 discipline). Triage buckets: **ADOPT** (folded into a V-change), **HOLD-and-TEST** (kept but conditional on evidence), **DEFER** (correct target, wrong moment).

| Grok # | Proposal | Disposition | Folds into / condition |
|---|---|---|---|
| G1 | Regime-weighted n_eff | **HOLD-and-TEST** | Weights must be **derived from predictive-validity data**, not asserted; else it is construct-by-declaration. Gated on §F2 corpus. |
| G2 | Intent × Stakes × Regime precision modifiers | **DEFER** | Three-way interactions overfit catastrophically at n = 26. Post-benchmark only. |
| G3 | Hybrid probe + transfer tasklets | **ADOPT** | → V8 (retention as fitted stability) + V12 (transfer tasklets via judge-advisor framework). Tasklets need isomorphic deep-structure design, not surface reuse. |
| G4 | HGF volatility coupling + partner-map continuous update | **DEFER** | The full 4D HGF is still stubbed; coupling sophistication to a stub is premature. Natural host is V7 when it activates. |
| G5 | Tiered telemetry provenance + consent flag | **ADOPT (with caveat)** | Implement; `telemetry_consent` is a DPDP precondition. **But validate the telemetry signals before treating them as evidence-precision upgraders** (caching/pre-fetch/background-tab noise). |
| G6 | External criteria + AI-side symmetry | **SPLIT** | External criteria → **ADOPT** as predictive-validity target (retention/transfer, §8.3). AI-side symmetry → **HOLD-and-TEST**: "symmetrically" is undefined; operationalize before pre-registering. |
| G7 | Simulation harness for archetypes/edge cases | **ADOPT (governed)** | → V2 robustness testing. **For pipeline robustness only, never for calibration** — calibration waits for held-out gold (over-fitting-to-simulation risk, per Grok's own caveat). |
| G8 | Enhanced profile + actionable trajectory + theater monitoring | **ADOPT** | → V3 (saturated state) + reporting layer (three views, never-collapse) + theater-rate (TR) dashboard. "Features-over-text retention" needs a concrete feature spec. |
| G9 | Updated pre-registration + shared-gold protocol | **ADOPT** | → V14 (Standards-structured pre-reg) + V15 (benchmark spec). Shared-gold with AEGIS resolves bets B1–B6. |

---

## 0.1 — Governing-principle reinforcement (v3 addendum)

The v2/v2.1/v2.2 principle stands verbatim:

> *Evidence before elegance. Reliability before complexity. Sustainability before synergy.* North Star: **AI should amplify human cognition without silently consuming it.**

v3 appends three operational clauses, each answering one of the PL's challenges:

1. **Borrowed-and-validated before invented.** Where an established, validated method exists for a problem (G-theory for reliability, CDM for classification, forgetting curves for retention, measurement invariance for drift, appropriate-reliance metrics for synergy), adopt it and inherit its validation. Reserve invention for what is genuinely novel — which, for SAF, is the *joint* synergy–sustainability instrument, not its component machinery.
2. **Benchmark before claims.** No claim about predictive validity or population behavior is admitted until it rests on a benchmark meeting §F2. Until then the binding constraint is **data coverage**, exactly as the freeze already states.
3. **Honest limits before reach.** The instrument declares where it saturates (V3), where its scores are a wrapper rather than a discovery (V13), and where a number is a pilot artifact rather than a validated measurement (V15).

**Restatement of §0.3 as the answer to "why not just ask the model" (the PL's challenge #3).** §0.3 already draws the load-bearing boundary: *the deep-learning components (LLM Judge, encoders) live entirely in the measurement layer; they are the microscope; "the model said so" must never substitute for "the cognitive structure predicts so."* v3 makes the corollary explicit. A bare LLM rating of a chat is *exactly* "the model said so" with no cognitive structure, no error surface, no defined construct, and — critically — **no access to the one thing SAF most wants to measure: what the human can do unaided, 48 hours later, on a transfer task.** That evidence is *structurally absent* from any single transcript. The dataset exists precisely so the instrument does **not** have to take the judge's word for it: it is the ground truth against which the judge's MAE, DIF, drift, and predictive validity are measured. See §E2 for the full scoping.

---

# PART A — RELIABILITY & MEASUREMENT ENGINE

## A1 · [V1] Reliability as a Generalizability-Theory study `[v3]`

**[MEASURABLE]** The recommended K-replication study to quantify judge non-determinism is formalized as a **Generalizability (G) study** — the established framework for partitioning measurement error across multiple facets, where Classical Test Theory models only a single undifferentiated error.

- **Design:** a crossed `subject × judge-replication × occasion` G-study. The judge-replication facet captures σ_judge (the non-determinism the PL flagged); the occasion facet captures session-level variation; the subject facet is the object of measurement.
- **Variance components estimated (G-study):** σ²(subject), σ²(judge-rep), σ²(occasion), and their interactions. **Diagnostic reading:** if σ²(subject) dominates (>50%), the instrument discriminates among people; if the residual / judge-rep component dominates, measurement is imprecise and more replications/items are needed.
- **Coefficient:** report the **absolute (Φ) coefficient**, *not* the relative G-coefficient — SAF makes criterion-referenced statements about an individual, and **population ranking is prohibited** (commitment 12). The relative coefficient is for norm-referenced ranking; using it would contradict the no-leaderboard rule.
- **D-study:** project how the Φ coefficient changes with K judge-replications, the multi-facet generalization of the Spearman–Brown formula. This sets **K** empirically: the smallest number of replications that achieves the target dependability for a stable quadrant assignment.
- **Quadrant flip rate** is reported alongside Φ as the decision-relevant reliability number (how often the synergy–sustainability quadrant assignment changes across replications).

**Data gate.** Stable variance-component estimation typically requires **≥30 subjects** crossed with the facets. At n = 26 (single archetype) the G-study is under-powered on the subject facet; run it as the corpus crosses 30+ diverse subjects (§F2). Until then, the *design* is fixed and pre-registered; the *estimates* are pending.

## A2 · [V2] Judge non-determinism protocol `[v3]`

**[MEASURABLE]** Adopt the field-standard discipline: **do not pretend the judge is deterministic; bound and report its variance.**

- **N-replication at scoring time** for chats whose initial score lands in a **quadrant-boundary band**: re-judge N times, report posterior mean ± SD. Interior (unambiguous) chats are scored once. This is **stratified re-judging** (cheap heuristics → selective sampling → ensemble), reserving cost for high-impact decisions.
- **Panel-of-judges (PoLL)** for the highest-impact boundary cases: aggregate independent judges to reduce idiosyncratic single-model variance. (Cost-gated; not default.)
- **Version pinning + provenance stamps:** every judge call already stores model ID/version (per the data-governance spec); v3 makes pinning mandatory and logs the judge config in the experiment record so drift (V10) is attributable.
- **Semantic-equivalence aggregation:** score on rubric-satisfaction / structural correctness, never byte-exact match.
- **Tier-A determinism hardening (engineering):** the mechanical-feature layer must be made bit-reproducible (fix Python hash seeding, async ordering); quantile cuts must be **frozen, never recomputed**. These are bugs, not noise, and are fixed before the G-study so σ_judge is not contaminated by σ_code.

**Caveat (carried from Grok G7).** A simulation harness may stress-test this protocol against synthetic archetypes, **but never calibrate on simulation** — held-out gold only.

## A3 · [V3] `MEASUREMENT_SATURATED` — the censored-reporting state `[v3]`

**[DESIGNED]** This resolves the PL's "human potential has no cap" challenge by separating two things the original framing conflated: the **construct** (unbounded) and the **score scale** (bounded by the instrument's resolution).

**The clarification.**
- In the **EqualWeightScorer** (shipping), the cap is real and unavoidable: an average of valence-normalized ordinals in [0,1] is in [0,1]. Surplus is impossible by construction.
- In the **GRM/HGF backend** (stubbed), the cap mostly dissolves on its own: Samejima's GRM places the latent trait θ on (−∞, +∞), and the HGF's belief means are Gaussian — also unbounded. The 0–100 display is a squashing transform. **"Surplus and deficit" already exist in the native latent scale; they are hidden only by the display.** Part of this challenge therefore resolves the moment GRM activates (§F3 trigger).

**What does *not* dissolve — and what V3 fixes.** Ceiling/floor effects and **information collapse at the extremes**: if the most demanding evidence pattern tops out, a genuinely exceptional collaborator saturates the instrument and discrimination among the exceptional is lost. IRT makes this measurable — the test information function `I(θ)` shows where precision exists, and `SE(θ) = 1/√I(θ)` blows up where no item carries information.

**The treatment — censored reporting (Tobit / right-censoring), the formal sibling of survival-analysis censoring.** When a subject saturates the instrument's range on a dimension, **report `≥ X, MEASUREMENT_SATURATED` — never `= max`.** This:
- is statistically honest (it states the true value is unknown above the saturation point, rather than fabricating a ceiling value);
- fits the architecture exactly as a **third categorical sibling** to `STRUCTURAL_NA` (applicability condition never arose) and `INSUFFICIENT_SAMPLE` (too few items), and obeys the **never-collapse rule** (§9 reporting): the three N/A-class states and genuine low/high scores are never merged into one label;
- is strictly preferable to uncapping, which would license the LLM judge to emit unbounded scores it has no evidence to support — the opposite of the framework's intent.

**Engineering response.** Author **high-difficulty evidence patterns** (new *micro-rubric levels on existing neurons*, not new neurons) to push the discriminating ceiling higher where it matters — particularly on EC and CS (the highest-weight, ceiling-prone dimensions). This is freeze-compliant (new fields on existing neurons).

---

# PART B — CONSTRUCT STRUCTURE & CLASSIFICATION (over the frozen ontology)

## B1 · [V4] The neuron→dimension map is a Q-matrix; CDM as the classification backend `[v3]`

**[DESIGNED]** CDM was already on the maturation roadmap (§7.7a, item 5; deferred as D1 "until the GRM is fit and validated"). v3 *formalizes* it and extracts immediate, data-free value from the recognition that **the 107→8 neuron→dimension map is a Q-matrix** — the I×K binary item-attribute matrix at the center of every Cognitive Diagnosis Model.

**The model family.**
- **DINA** (Deterministic-Input Noisy-And): conjunctive, **non-compensatory** — a respondent must possess *all* attributes a item requires; extra attributes do not compensate for missing ones; slip/guess parameters carry item-level error.
- **DINO** (Noisy-Or): disjunctive, for "any-of" cases.
- **G-DINA** (de la Torre): the general framework nesting saturated and reduced models, with item- and test-level fit and — decisively for SAF — **empirical validation of the postulated item–attribute associations.**

**Why this is the right tool, and what it buys with zero new data:**
1. **DINA's conjunctive logic is the formal twin of `minimum-across-pillars` (§3.6).** The penalized power-mean and Skilled-Outsourcer / Fluent-Incompetence gates were reasoned to; CDM is the established model class that already formalizes non-compensatory aggregation. v3 re-expresses §3.6 as a CDM-style conjunctive condition (DINA where mastery is all-or-none on a dimension; DINO for disjunctive sub-cases).
2. **G-DINA validates the Q-matrix — i.e. tests whether each neuron actually loads on its assigned dimension.** This directly attacks the PL's challenge #2 ("26 chats are assumptions, not a benchmark") from a new angle: it converts the hand-authored neuron→dimension assignment from a *design artifact* into a *testable hypothesis*. The Q-matrix can be written and the G-DINA validation plan drafted **now**, before any new data.
3. **It is interpretable** (named, discrete attribute mastery + slip/guess), unlike sequence-embedding clustering — keeping faith with the epistemic discipline and the existing embedding deferral.

**Division of labour (resolving the discrete-vs-continuous tension).** CDM and GRM are **not competitors** — they answer different questions over the *same* frozen 8 dimensions:
- **GRM → continuous dimension scores** (θ per dimension): "how capable, on a continuum." The home of the score and the trajectory.
- **CDM → discrete attribute-mastery profile** (α per dimension): "which profile / which archetype." The formal home of **archetype classification** (§B2).

Both sit over the 107→8 Q-matrix; neither adds a construct. **CDM attribute α_d is a discrete readout of the existing dimension d, exactly as GRM θ_d is its continuous readout — engine parameters for frozen constructs, not new constructs** (see §V-Audit).

**Data gate.** CDM is more data-efficient for *classification* than full continuous estimation, but **not viable at n = 26**, and Q-matrix misspecification degrades it badly. Build the backend as an interface + write the Q-matrix now; fit when the corpus supports it.

## B2 · [V5] Archetype discovery via LCA/LPA `[v3]`

**[DESIGNED]** The 10 archetypes (§7.2a sampling frame) are currently **decreed**. v3 adds the exploratory cousin of the EFA gate:

- **Latent Class / Latent Profile Analysis** discovers response *types* from data — the categorical analog of EFA's factor discovery for the dimensions. Where CDM is **confirmatory** (Q-matrix specified), LCA is **exploratory** (types emerge).
- Paired use: LCA discovers candidate archetypes → compare against the 10 decreed archetypes → the discrepancy is the finding (commitment 6: *structure is discovered, not decreed*). Dimensionality methods from the factor-analysis literature (parallel analysis, etc.) determine the number of latent classes, the same way EFA fixes the number of factors.

**Data gate.** Same as B1; LCA needs the diverse corpus. The *plan* is fixed now; the *fit* waits.

## B3 · [V6] CDM identifiability folded into §8.1 `[v3]`

**[DESIGNED]** Q-matrix-based CDMs have documented **non-identifiability and equivalence classes** (attribute profiles indistinguishable from data under certain Q-matrix structures). This is **the existing structural-identifiability gate (§8.1, rank(Λ)=4) restated in CDM terms** — so adopting CDM imports a hazard SAF has already committed to test, not a new one. The §8.1 posterior-correlation check extends to: *after fitting, verify the attribute profiles are separately recoverable; if two profiles are empirically indistinguishable, the Q-matrix is under-determined and must be revised (add identity-submatrix items per the CDM identifiability conditions).*

---

# PART C — THE SUSTAINABILITY AXIS (the irreplaceable core)

## C1 · [V7] Knowledge-tracing backend for the longitudinal trajectory `[v3]`

**[DESIGNED — data-gated]** The sustainability axis — *is the human's independent capacity growing or eroding over time?* — **is the knowledge-tracing (KT) problem, run with forgetting enabled.** KT is four decades mature in educational data mining.

- **Backend:** an **interpretable** tracer — Bayesian Knowledge Tracing or Interpretable KT (per-skill mastery + ability + difficulty features), **with an active forgetting parameter** (most KT deployments suppress it; SAF needs it). **Deep DKT is rejected** for its known interpretability loss and inconsistent predictions across similar states, and consistent with the existing embedding deferral.
- **Uncertainty:** the tracer must be **uncertainty-preserving** (a state-space / variational form that integrates evidence over time *and* carries epistemic uncertainty). **The existing 4D HGF is the natural host** — it is already a recursive Bayesian filter over latent state; v3 extends it to carry the *across-session* trait trajectory for the longitudinal-sink dimensions (AUI, CA), not just within-session state.
- **Per dimension:** the tracer runs on the existing 8 dimensions; the mastery/erosion trajectory is the temporal readout of an existing dimension — **not a new construct.**
- **Note (prior-art):** specialized KT models are reported faster, cheaper, and more accurate than LLMs at this task — a further argument *against* leaning on the Gemini judge for the longitudinal trajectory and *for* a dedicated tracer.

**Data gate.** KT requires **multi-session sequences per subject.** Build the interface now; fit when longitudinal data exists. This is the v3 longitudinal backend, replacing the under-specified "AUT is the longitudinal sink" note with a concrete, validated model class.

## C2 · [V8] Retention probe → fitted decay curve `[v3]`

**[DESIGNED — data-gated]** Upgrade the **decisive predictive-validity gate (§8.3)** from a binary threshold to a fitted curve.

- **Model:** FSRS **Difficulty–Stability–Retrievability (DSR)** — Stability = the time for recall probability to fall from 100% to 90%, on a **power-law** forgetting curve; or **half-life regression** (Settles & Meeder) as the lighter form. Both are trainable by gradient descent on historical probe data.
- **Procedure:** fit a per-subject, per-skill **stability** parameter from **≥2 staggered unaided probes** (≥24 h apart). **Caveat:** FSRS has no short-term-memory model and cannot capture sub-hour decay — keep probes ≥24 h where the power-law form holds.
- **Interpretation:** *rising* stability across sessions = capacity growing; *falling* stability under continued AI assistance = **cognitive debt made continuous** — the synergy/sustainability tension, operationalized as a fitted quantity rather than a binary pass/fail.
- **Integration:** stability is the natural observable feeding the V7 tracer; and it sharpens §8.3 — the CSPC-states model must now beat the quality-only baseline at predicting the *stability parameter* (a richer target than binary retention), by the pre-specified ΔAUC / Δ-fit margin.

## C3 · [V9] Question-asking science as an evidence instrument `[v3]`

**[DESIGNED]** The PL's psychological input #1, instantiated rigorously and **freeze-safe** (new instruments/fields on existing neurons; **no new dimension**).

- **Normative model:** **Expected Information Gain (EIG) / Optimal Experiment Design (OED)** (Coenen, Nelson & Gureckis; Gureckis & Markant; Nelson) — people ask questions to maximize expected information gain; EIG scores a question by how much is expected to be learned from each possible answer. Pair with the **Graesser & Person question taxonomy** and **Bloom tiers** (already held in project files) for categorical question typing.
- **Where it feeds:** the EIG/taxonomy scores of the human's prompts feed **existing** neurons — primarily PR (Prompt Reasoning), AL (AI Literacy), and EC (Error Correction). No new latent variable.
- **Cognitive-load link:** good questions are *effortful* — formulating higher-quality inquiries is associated with reported fatigue / high computational cost (Gottlieb). This maps question quality onto **germane load** in the CSPC's L_t channel, connecting to the Lepine load taxonomy already cited.
- **Sustainability observable (the external grounding):** a 2026 longitudinal study (npj Science of Learning, N = 68 undergraduates) found that **domain-specific question-asking improved over a semester** while general question-asking stayed flat/declined, and that question-asking ability was **negatively related to closed-ended test performance but positively related to open-ended project performance.** This is near-direct external corroboration: question sophistication tracks genuine knowledge, is longitudinal, is measured in *SAF's exact population (students)*, and **dissociates the two kinds of performance the synergy/sustainability split predicts.** The **question-complexity/originality trajectory across sessions is therefore admitted as a candidate observable for the sustainability axis** (feeding V7), alongside retention stability (V8).
- **Honest limit (prior-art):** OED rests on assumptions about the asker's priors and does not capture the full richness of real question-asking; treat EIG as one question-quality feature among several, not the whole signal.

---

# PART D — DRIFT, INVARIANCE & FAIRNESS (validation apparatus)

## D1 · [V10] Drift = longitudinal measurement (non-)invariance / Response Shift `[v3]`

**[MEASURABLE test / data-gated run]** "Hosted judge drift is a validity threat" now has a formal test and a formal name.

- **The principle:** **longitudinal measurement invariance** is the prerequisite for interpreting a change score — an apparent gain could otherwise reflect *the instrument shifting meaning rather than the person changing.* When invariance fails over time specifically, it is called **Response Shift.** This is *exactly* the judge-drift-vs-subject-change problem.
- **The hierarchy & test:** configural → metric → **scalar** → strict invariance, tested by constraining parameters and judging **ΔCFI** (not the sample-size-sensitive χ²). **Scalar invariance is the minimum condition for a change score to be interpretable.**
- **The drift alarm:** re-score the **frozen anchor set** of gold chats on a fixed schedule; test scalar invariance of the instrument across re-scoring occasions. **A scalar-invariance failure on the anchor set = judge drift** (the instrument moved); invariance holding while a subject's scores change = genuine subject change. This is the formal counterpart of the existing frozen-anchor strategy.
- **Anchor / DIF method:** anchor-item design; **Reg-DIF** (lasso regularization for anchor selection and DIF identification) — chosen specifically because it has better Type-I-error control and performs well at **smaller sample sizes** than conventional IRT-LR-DIF, which matters under SAF's data constraints. Also handled in the continuous-time longitudinal IRT framework (DIF/Response-Shift covariate terms) when the longitudinal corpus exists.

## D2 · [V11] Fairness three-level discipline `[v3]`

**[DESIGNED]** Wrap the existing DIF gate in the AERA/APA/NCME fairness taxonomy so it is not misapplied:

- **Three distinct levels:** (1) **mean score differences** between groups — **not, by itself, evidence of bias**; (2) **item bias / DIF** — an item functions differently for equally-able members of different groups (construct meaning); (3) **predictive bias** (Cleary regression model) — scores over/under-predict an external criterion for a group (score *use*).
- **The discipline:** *construct/method/item bias concern what a score means; predictive bias concerns what a score does.* Keep these distinct in the pre-registration. **A group mean gap is never reported as bias.** For minors in India this fairness analysis is an ethical/legal precondition (carried from §7.7a / DPDP), not a refinement.

---

# PART E — THE SYNERGY AXIS, RE-GROUNDED + SCOPE HONESTY

## E1 · [V12] Re-anchor synergy/reliance metrics on the appropriate-reliance literature `[v3]`

**[VALIDATED in source field / DESIGNED here]** A live field already has validated constructs for the synergy/reliance side; SAF imports them and inherits their validation rather than carrying bespoke definitions.

- **Weight of Advice (WoA)** — continuous measure of how far a person shifts toward AI advice; the only common reliance measure that extends to non-discrete contexts. The continuous reliance signal for the behavioral layer.
- **Switch fraction** — how often a person changes their initial answer to adopt AI advice.
- **Appropriate reliance** — accept AI when correct, reject when wrong; measured as a two-dimensional (over-/under-reliance) construct. Maps onto the EC dimension and the metacognitive calibration gap.
- **Judge-advisor framework** — the canonical paradigm; the clean experimental design for the **transfer tasklets** (Grok G3): an isomorphic task where the human receives (or is denied) AI advice and the reliance/transfer is measured.
- **TIAS** (Trust in Automation Scale, validated short form) — informs the construction of the **self-rating widget**, which (per existing design) feeds **only** the metacognitive calibration gap, never the behavioral scores.

## E2 · [V13] Scope-honesty / claims-ladder correction `[v3]`

This is the PL's existential challenge #3, answered as an epistemic correction rather than a feature. **It strengthens the framework by stopping it from over-claiming.**

**The concession, stated plainly.** On the **within-chat synergy** axis — the part of the construct that genuinely *is* present in a single transcript — the full IRT/CDM/HGF apparatus probably adds **modest value over a well-calibrated frontier judge** (which SAF already uses: Gemini). On single-chat synergy scoring, SAF is best described as a **reliability-and-calibration wrapper** around an LLM judge, not a replacement for one. **Do not claim to out-judge the judge on single chats.**

**Where the framework's value is irreplaceable, and where it therefore stakes its existence:**
1. **The sustainability axis.** Cognitive sustainability is *not a property of a chat* — it is a property of a person's trajectory across sessions and their unaided performance, 48 h later, on a transfer task. **That evidence is structurally absent from any single transcript.** No amount of judge intelligence recovers it, because the decisive data (what the human can do *without* the AI) was never in the transcript. This is the one claim no prompting defeats — and it is why V7 (KT trajectory) and V8 (retention stability) are the core.
2. **The validation apparatus.** Calibrating the judge against human gold (QWK/MAE), detecting drift (V10), partitioning reliability (V1), and running the pre-registered falsification gates (§8) are what convert "the model said 73" into "73, with error ±Y, corresponding to human-rated X, predicting stability Z." That conversion **is** psychometrics, and a bare rating skips it entirely.

**Convergent external evidence for the thesis.** The appropriate-reliance literature repeatedly finds that **calibrated reliance fails to improve task performance** ("calibration without improvement"), and a 2025 line argues that *measuring and mitigating overreliance is necessary for human-compatible AI.* This is an independent, published instance of SAF's central claim — *short-term synergy can mask long-term cognitive debt* — and is cited as convergent support for the tension axis, upgrading it from purely DESIGNED toward externally-corroborated. The intervention template is also pre-built: **cognitive forcing functions** reduce overreliance, a ready scaffold for the intervention-design layer.

**The uncomfortable, non-hallucinative reading (for internal honesty).** Right now, on the synergy axis alone, the skeptic in challenge #3 is essentially correct. **The framework becomes more than a wrapper at exactly the moment the dataset is large and clean enough to (a) calibrate the judge against human gold and (b) demonstrate that scores predict unaided retention.** Until then, the part that justifies the whole edifice is the part that does not yet exist. This is not a reason to stop; it is the reason the priority is unambiguous (§F2).

---

# PART F — GOVERNANCE & STANDARDS

## F1 · [V14] Operate under the AERA/APA/NCME Standards `[v3]`

**[DESIGNED]** SAF/ARI is a psychometric instrument; the **Standards for Educational and Psychological Testing** (AERA/APA/NCME, 7th ed., open access) are the governing reference and were previously unstated.

- **Validity is a property of an interpretation/use, not of the instrument:** *the degree to which evidence and theory support the interpretations of test scores for proposed uses.* This maps cleanly onto the four-rung ladder (§0.2) and the Tier-1/2/3 charter — a *different use* (formative-for-minors vs. summative) requires a *different validity argument*.
- **Pre-registration structure (OSF):** organize the falsification gates (§8) under the Standards' tripartite — **validity** (§8.3 predictive-validity gate; content validity of the Q-matrix via V4), **reliability** (§A1 G-study; V10 invariance), **fairness** (§D2 DIF; Cleary predictive bias).
- **AI-scored constructed-response validity:** cite the dedicated literature (Williamson et al. 2012; McCaffrey et al. 2022) as the validity-evidence backbone for the **Q-star rubric / Gemini judge**. Add **Quadratic-Weighted Kappa (QWK)** — the field-standard agreement metric for AI-scored constructed responses — **alongside MAE** as the judge-vs-human gold agreement statistic. (The EC-dimension MAE weak spot is, in QWK terms, a category-agreement weakness; report both.)

## F2 · [V15] Benchmark vs pilot — formalized `[v3]`

This is the PL's challenge #2, made operational. **The 26 gold chats are a PILOT/SEED, not a benchmark**, and anything resting on them is at most **MEASURABLE — never VALIDATED.**

**Two structural problems beyond size:**
1. **Annotation grain caps everything downstream.** 8-dimension-grain annotation **cannot** fit 107-neuron item parameters or run EFA on the 107-neuron matrix, regardless of chat count — the resolution of conclusions is bounded by the resolution of labels. **Therefore: split the 8-dimension and 107-neuron data timelines.** They are different programs on different schedules.
2. **Double-duty leakage.** If the same 26 set the quantile cuts *and* validate MAE *and* anchor the aggregator, calibration and test roles have merged. A benchmark separates them — and the inability to hold out a test split at n = 26 *is* the diagnosis that they are not yet a benchmark.

**Minimum-viable-benchmark spec (the five conditions):**
- sufficient **n** for stable parameter estimation — rough arithmetic: EFA wants ~5–10 respondents/item (8-dim: low hundreds; 107-neuron: four figures); GRM item calibration wants hundreds; the G-study (§A1) wants ≥30 persons;
- **established inter-rater reliability** — ≥2 annotators, Dawid–Skene aggregation (already in the stack) and **QWK** reported;
- **coverage across the 10 archetypes** (not a single passive-extraction archetype);
- a **held-out train/validation/test split**;
- **external-validity anchoring** to the retention/transfer outcomes (V8).

**Sequencing implication:** get the **8-dimension instrument** to benchmark quality first (achievable in the low hundreds of chats); keep the **107 neurons as the evidence-extraction layer**; defer neuron-level psychometrics (EFA on 107, GRM item params, CDM fit) until a much larger **neuron-grain** corpus exists. Validating the 107-neuron structure first is the harder problem with the worse data and is *not* the binding constraint on shipping a credible 8-dim score.

## F3 · [V16] Freeze status update + structural-transition triggers `[v3]`

**[DESIGNED]** The freeze on **new latent variables holds** (§14.3, unchanged). v3 makes the *permitted* structural transitions explicit and gated:

| Transition | Trigger condition |
|---|---|
| **GRM activation** (replace EqualWeightScorer's continuous role) | Data volume supports stable Bayesian item-parameter estimation (hundreds of neuron-grain responses). |
| **EFA-learned loadings** (replace equal-weight aggregator) | Diverse corpus collected **and** EFA run on the appropriate-grain matrix. Fitting GRM/loadings on 26 gold chats would overfit; the calibration set is a *validation anchor, not training data.* |
| **CDM Q-matrix fit + validation** (V4/V5) | Corpus crosses the classification-data threshold; G-DINA item/test fit run. |
| **Freeze LIFT for new dimensions/latent variables** | **Unchanged from v2.2:** diverse corpus collected + EFA run + §8.3 predictive-validity gate addressed. Not before. |

---

## §14 append — Rejection & Deferral Log additions `[v3]`

| Idea | Status | Reason / Re-entry condition |
|---|---|---|
| **Uncapping dimension scores to allow unbounded "surplus"** | **Rejected → superseded** | Conflates unbounded construct with unbounded display; would license judge hallucination. Superseded by GRM's native unbounded θ (display-transform issue) **+** `MEASUREMENT_SATURATED` censored reporting (V3). |
| **Intent × Stakes × Regime three-way precision modifiers** (Grok G2) | **Deferred** | Overfits at n = 26. Re-entry: post-benchmark with sufficient power. |
| **HGF volatility coupling / partner-map continuous update** (Grok G4) | **Deferred** | Couples sophistication to a still-stubbed 4D HGF. Re-entry: when V7/HGF activates. |
| **AI-side symmetry as a pre-registered bet** (Grok G6) | **Hold-and-test** | "Symmetrically" undefined; operationalize (variance-explained? predictive direction?) before pre-registering. |
| **Deep DKT / sequence embeddings for the sustainability trajectory** | **Deferred (reaffirmed)** | Interpretability loss; reaffirms the existing v2.2 embedding deferral. Re-entry: post-validation freeze lift + a bet showing sequence signal interpretable models miss. |
| **Calibrating the pipeline on the simulation harness** (Grok G7 misuse) | **Rejected** | Over-fitting to simulation. Harness is for robustness testing only; calibration on held-out gold only. |
| **Treating the 26 gold chats as a benchmark** | **Rejected** | Pilot/seed only (V15). Re-entry: the five minimum-viable-benchmark conditions met. |

## §14.4 append — Freeze-compliance audit, v3 `[v3]` — **§V-Audit**

Every v3 change audited against §14.3 before adoption.

**Totals: neurons added 0 · dimensions added 0 · pillars added 0 · latent-state variables added 0.**

Specific reconciliations (the non-obvious cases):
- **CDM attribute α_d (V4)** is *not* a new construct — it is the **discrete readout of the existing dimension d** over the existing 107→8 Q-matrix, exactly as **GRM θ_d** (already accepted/stubbed) is its continuous readout. Both are engine parameters for frozen constructs.
- **KT mastery/erosion trajectory (V7)** is the **temporal readout of an existing dimension** (the longitudinal-sink dimensions AUI/CA), hosted in the existing HGF; it adds no new latent variable.
- **Latent classes / archetypes (V5)** are **patterns over the existing dimension profile**, discovered to validate the already-decreed archetypes — not new constructs.
- **EIG question-quality (V9)** is a **new instrument/field feeding existing neurons** (PR/AL/EC) — explicitly inside the freeze's permitted "new fields on existing neurons."
- **`MEASUREMENT_SATURATED` (V3)** is a **reporting/scorability state**, not a construct.
- Everything else (G-study, judge protocol, invariance testing, fairness taxonomy, appropriate-reliance metrics, Standards alignment, benchmark spec) is **validation, engine, reporting, or governance** — all permitted.

Conclusion: **v3 lands entirely inside the freeze.** It is a methods-and-honesty revision, not a structural one.

---

## v3 Rung Summary

| Rung | v3 items |
|---|---|
| **VALIDATED** | **None** — by design. Validation is gated on the §F2 benchmark, which does not yet exist. (Appropriate-reliance metrics in V12 are validated *in their source field*; their validity *for SAF* is not yet established.) |
| **MEASURABLE (now)** | G-study design (V1), judge non-determinism protocol (V2), scalar-invariance *test* (V10), QWK reporting (V14). |
| **DESIGNED (specified, not yet validated)** | `MEASUREMENT_SATURATED` (V3), Q-matrix + G-DINA validation plan (V4), LCA plan (V5), CDM identifiability check (V6), KT backend interface (V7), retention-stability fitter (V8), EIG instrument (V9), fairness taxonomy (V11), reliance-metric import (V12), Standards alignment (V14), freeze triggers (V16). |
| **DATA-GATED (DESIGNED but cannot run until corpus grows)** | G-study *estimates* (V1), CDM/LCA *fits* (V4/V5), KT *fit* (V7), retention *fit* (V8), invariance *run* (V10), GRM/EFA activation (V16). |
| **ASPIRATIONAL** | Intervention design via cognitive forcing functions (E2); population norming (post-benchmark, §7.7a). |

---

## The throughline

The PL's three challenges and the Grok refinements collapse onto one fact: **the framework earns its right to exist only through validated measurement, and validated measurement requires (a) honest treatment of the instrument's limits — its ceilings (V3) and its wrapper-vs-discovery scope (V13) — resting on (b) a real benchmark anchored to external outcomes (V15), which is (c) the entire answer to "why not just ask the model" (E2/§0.3).**

v3 does not add capability. It adds **discipline and inheritance**: it takes the framework's hardest problems out of the "novel, must-invent" column and puts them in the "solved elsewhere, must-adopt-and-validate" column, and it states clearly where the instrument is a calibrated wrapper versus where it measures something a transcript cannot contain. The binding constraint is unchanged and unhidden: **the dataset is the load-bearing element, and it is currently the weakest point.** Every data-gated item above is a promissory note the corpus must redeem.

*End of v3 spec delta. To be folded into a v3 master compilation only after these changes clear gold validation.*
