# Chat Classifier v2 — Implementation Brief

*Engineering handoff for an AI coding agent. This document specifies the concrete changes to build v2 of the Chat Classifier — the engine that converts one raw human–AI chat into an 8-dimensional synergy profile. The scientific rationale lives in `ARI_Synergy_Framework_v2.md`; this document is the **engineering delta**. Build in phase order. Each phase has acceptance criteria. Do not skip the gates.*

---

## 0. How to read this document

- Phases are **dependency-ordered**. Do not start a phase until its predecessors pass acceptance.
- Code blocks are **contracts**, not suggestions. Match the field names exactly so downstream stages stay compatible.
- Anything marked **STUB ONLY** is an extension point for a future layer — define the interface, do not implement the logic.
- Anything marked **GATE** blocks progress until satisfied.

---

## 1. Scope

**In scope:** pure raw chat (text transcript, both roles) → 8-dimensional synergy scores with uncertainty and coverage.

**Out of scope (extension points only — stub the interfaces, do NOT implement):**
- Browser-layer inputs: user self-rating, DOM behavioral telemetry (dwell, copy/paste, scroll-back, edit rate).
- Integrated-platform inputs: target question, follow-up probes, ground-truth outcomes, quality labels.

The kernel must be built so these are **strictly additive** later — new inputs become new items or new constructs, never a re-architecture.

## 2. Governing principles (do not violate)

1. **Two hard gates.** (a) *Contract gate*: nothing scores until the neuron contract table exists and validates. (b) *Calibration gate*: a dimension does not ship until it passes ICC certification (inter-rater ≥ 0.70, judge-vs-human ≥ 0.60).
2. **Absent ≠ zero.** A neuron whose applicability condition never arose contributes **no item** to the likelihood (silence). A neuron whose condition arose but the user performed poorly is scored **0** (evidence). These are different code paths. Never coerce a non-applicable neuron to 0.
3. **Dimension count is configurable.** Do not hardcode 8. The system must accept 8–11 dimensions from config, because EFA may revise the count later.
4. **Honest uncertainty.** Every score ships with a credible interval and a coverage flag. No point estimate without an interval.
5. **Equal-weight now, learned-weight later.** Do NOT attempt to fit a Bayesian GRM on the 23 gold chats — that overfits. Ship v2 with transparent equal-weight aggregation behind a pluggable interface; swap in the GRM only when calibration data volume supports it.

## 3. The 8 dimensions (configurable set)

`AL` (AI Literacy), `PR` (Prompt Reasoning), `EC` (Error Correction), `ES` (Ethics Sensitivity), `CS` (Contextual Synthesis), `CD` (Creative Divergence), `AUI` (Augmentation Instinct), `CA` (Collaborative Agency).

Context scope per dimension (drives the dual extraction pass, Phase 3):
- **chunk-scope** (local, per 3-turn window): `EC`, `PR`, `AL`, `ES`
- **chat-scope** (global, once per conversation): `CS`, `CA`, `CD`, `AUI`

## 4. Proposed repository structure

```
chat_classifier/
  __init__.py
  config.py                  # dimension list, tau thresholds, model names, scale anchors
  schemas.py                 # Pydantic models for ALL contracts (Section 5)
  pipeline.py                # end-to-end orchestration: RawChat -> SynergyReport

  ingestion/
    parsers.py               # platform export -> RawChat (one adapter per source)
    chunker.py               # 3-turn sliding windows

  neurons/
    contract_table.yaml      # THE neuron contract table (DATA, not code) — Phase 2
    loader.py                # load + validate contracts against NeuronContract schema

  extraction/
    tier_a_deterministic.py  # mechanical features (local)
    tier_b_embedding.py      # embedding features (local + chat-level)
    tier_c_judge.py          # LLM-judge, graded ordinal per neuron
    chat_level.py            # whole-conversation pass (chat-scope neurons)
    orchestrator.py          # runs chunk pass + chat pass -> NeuronMatrix

  inference/
    task_classifier.py       # task-type + goal-completion (LLM-judge sub-module)

  scoring/
    scorability.py           # S_id gate, structural vs insufficient N/A
    scorer.py                # ScorerBackend interface: EqualWeightScorer | GRMScorer
    aggregation.py           # neurons -> dimensions -> pillars
    gated_index.py           # g_synergy x gates x minimum-across-pillars

  output/
    report.py                # SynergyReport assembly: scores + CI + coverage + flags
    translation.py           # plain-language bands + attribution (minimal v2 ok)

  calibration/
    gold_set.py              # load double-coded gold chats
    icc.py                   # ICC computation + per-dimension certification (GATE)
    active_learning.py       # uncertainty/disagreement sampling (hooks for the flywheel)

  extensions/                # STUB ONLY — interfaces for future layers
    browser_inputs.py        # SelfRating + DomSignal interfaces (no logic)

tests/
  fixtures/                  # sample RawChat JSON, a few hand-scored chats
  test_<each_module>.py
```

## 5. Core data contracts (schemas.py)

These are the spine. Implement as Pydantic models. Field names are fixed.

### 5.1 RawChat (the input contract)

```python
class Turn(BaseModel):
    index: int                      # 0-based turn order
    role: Literal["human", "ai"]
    text: str
    timestamp: datetime | None = None

class RawChat(BaseModel):
    chat_id: str
    source_model: str               # "chatgpt" | "claude" | "gemini" | ... (sets kappa_AI)
    turns: list[Turn]
    metadata: dict = {}             # free-form; never required by the scorer
```

### 5.2 NeuronContract (the item bank — Phase 2 fills the table)

```python
class NeuronContract(BaseModel):
    id: str                                  # e.g. "EC-04"
    dimension: str                           # one of the configured dimensions
    type: Literal["behavioral", "metacognitive", "structural"]
    context_scope: Literal["chunk", "chat"]  # routes to the correct extraction pass
    extractor_type: Literal["deterministic", "embedding", "llm_judge"]
    micro_rubric: dict[str, str] | None      # {"0": anchor, ..., "4": anchor} for llm_judge
    detector: str | None                     # expression/function ref for deterministic/embedding
    valence: Literal[1, -1]                  # +1 healthy synergy, -1 cognitive debt
    applicability_rule: str                  # expression deciding whether the neuron fires
    sector_universal: bool
```

### 5.3 ItemResponse (one neuron firing)

```python
class ItemResponse(BaseModel):
    neuron_id: str
    dimension: str
    scope: Literal["chunk", "chat"]
    chunk_index: int | None          # None for chat-scope items
    applicable: bool                 # did the applicability_rule fire?
    ordinal_score: int | None        # 0-4 if applicable, else None  (NEVER 0 for non-applicable)
    raw_value: float | None          # continuous value before discretization (Tier A/B)
    extractor: str
```

`NeuronMatrix = list[ItemResponse]` for a chat.

### 5.4 DimensionScore and SynergyReport (the output contract)

```python
class NeuronContribution(BaseModel):
    neuron_id: str
    signed_contribution: float       # how much this item moved the posterior (for attribution)

class DimensionScore(BaseModel):
    dimension: str
    scorable: bool                            # S_id
    na_reason: Literal["structural", "insufficient_length"] | None
    posterior_mean: float | None              # internal logit-ish scale
    score_0_100: float | None                 # criterion-anchored reporting scale
    credible_interval: tuple[float, float] | None
    n_items: int
    top_contributors: list[NeuronContribution]

class SynergyReport(BaseModel):
    chat_id: str
    dimensions: list[DimensionScore]
    pillar_scores: dict[str, float | None]    # Engage/Manage/Create/Design (configurable)
    g_synergy: float | None
    synergy_index: float | None               # 0-100, after gates + min-pillar cap
    min_pillar_cap_applied: bool
    coverage: dict[str, int]                  # {"scored": k, "total": n_dims}
    task_context: dict                        # task_type, goal_completion_estimate, confidence
    within_chat_trajectory: dict              # verification trend, attribution-gap trend, etc.
    flags: list[str]                          # cognitive-state flags: load_level, tom_slope, ...
    confidence_note: str                      # plain-language coverage/uncertainty summary
```

---

## 6. Implementation phases

Each phase: **Goal · Files · Interface · Acceptance**. Build in order.

### Phase 1 — Ingestion & chunking
- **Goal:** normalize any chat export into `RawChat`; produce 3-turn sliding windows.
- **Files:** `ingestion/parsers.py`, `ingestion/chunker.py`, `schemas.py`.
- **Interface:** `parse(source: str, raw: Any) -> RawChat`; `chunk(chat: RawChat, window: int = 3, stride: int = 1) -> list[Chunk]` where `Chunk` carries its turn span and `chunk_index`.
- **Acceptance:** round-trips at least two real export formats (e.g. ChatGPT JSON, a Claude transcript) into identical `RawChat`; a 20-turn chat yields ~18 chunks; unit tests on edge cases (single-turn chat, empty turns).

### Phase 2 — Neuron contract table (GATE: contract gate)
- **Goal:** author `contract_table.yaml` for the **text-detectable subset** of the 106 neurons; validate on load.
- **Files:** `neurons/contract_table.yaml`, `neurons/loader.py`.
- **Interface:** `load_contracts(path) -> list[NeuronContract]`, raising on schema violation, duplicate ids, or a `dimension` not in config.
- **Process:** start with `EC` and `PR` (highest-signal, cleanest to detect), then `AL`, `ES`, then the chat-scope dimensions `CS`, `CA`, `CD`, `AUI`. Every row needs all fields from §5.2. Mark `extractor_type` honestly — only mechanically-observable neurons are `deterministic`; inference goes to `llm_judge`. Tag `context_scope` correctly (drives Phase 3).
- **Acceptance:** the table validates; every dimension has ≥ 1 neuron; `loader` rejects a deliberately malformed row in tests. **Nothing downstream runs until this passes.**

### Phase 3 — Dual-granularity extraction
- **Goal:** produce the `NeuronMatrix` by running two passes — chunk-level and chat-level — and routing each neuron to its pass by `context_scope`.
- **Files:** `extraction/tier_a_deterministic.py`, `tier_b_embedding.py`, `tier_c_judge.py`, `chat_level.py`, `orchestrator.py`.
- **Interfaces:**
  - `extract_tier_a(chunk) -> list[ItemResponse]` — mechanical features: turn lengths, question density, hedging markers, readability (Flesch-Kincaid/SMOG), imperative:interrogative ratio, constraint/example/success-criteria presence.
  - `extract_tier_b(chunk_or_chat) -> list[ItemResponse]` — embedding features: **Attribution Gap** `= 1 - cos_sim(ai_output, user_next_contribution)`, latent reasoning correlation `rho_HM`, novelty, text-derived element-interactivity. Runs at BOTH scopes (chunk for local, chat for the **Attribution-Gap trajectory**).
  - `extract_tier_c(chunk_or_chat, contracts) -> list[ItemResponse]` — calls the LLM judge with the `micro_rubric` per applicable neuron; returns graded ordinal 0–4. Output MUST be structured (JSON), fixed temperature, versioned prompt. Never free text.
  - `chat_level_features(chat) -> list[ItemResponse]` — goal-thread integrity, context-accumulation depth, generative:extractive slope, reliance drift.
  - `orchestrate(chat, chunks, contracts) -> NeuronMatrix` — runs chunk pass over chunk-scope neurons + chat pass over chat-scope neurons; merges. **Continuous Tier A/B values must be discretized to ordinal bins** (data-driven quantile cuts from the gold set; for cold start use fixed quintiles) before they become `ordinal_score`.
- **Acceptance:** for a fixture chat, the matrix contains chunk items (with `chunk_index`) and chat items (`chunk_index = None`); non-applicable neurons have `applicable=False, ordinal_score=None`; judge output parses deterministically; same input → same output (temperature fixed).

### Phase 4 — Task-type & goal-completion inference
- **Goal:** label task context from text alone to drive conditioning.
- **Files:** `inference/task_classifier.py`.
- **Interface:** `infer_task(chat) -> {task_type: Literal["decide","create","learn","produce"], stakes: float, goal_completion: float, confidence: float}`.
- **Acceptance:** returns a calibrated estimate with confidence on fixtures; low-confidence cases flagged rather than forced. This is a known-noisy module (no target question yet) — surface the uncertainty, do not hide it.

### Phase 5 — Scorability gate
- **Goal:** decide per dimension whether there is enough evidence to score; classify N/A type.
- **Files:** `scoring/scorability.py`.
- **Interface:** `scorability(matrix, dim, tau=3) -> {scorable: bool, na_reason: str|None, n_items: int}`. `scorable = (count applicable items for dim) >= tau`. If not scorable: `na_reason = "structural"` when the applicability conditions were never present in the chat, else `"insufficient_length"`.
- **Acceptance:** a dimension with 2 applicable items and tau=3 returns `scorable=False`; the two N/A reasons are distinguished correctly on crafted fixtures; non-applicable neurons are never counted.

### Phase 6 — Scoring core (pluggable backend)
- **Goal:** estimate the latent dimension trait from its applicable items, with a credible interval.
- **Files:** `scoring/scorer.py`, `scoring/aggregation.py`.
- **Interface:** define `ScorerBackend` ABC with `score(items_for_dim) -> {posterior_mean, ci, contributions}`. Provide two implementations:
  - `EqualWeightScorer` (**ship this in v2**): normalize ordinals by valence, equal-weight aggregate, map to the latent/0–100 scale, derive CI by **bootstrap over items**. Within-chat temporal features (verification trend, attribution-gap slope) computed here.
  - `GRMScorer` (**interface only / future**): Samejima GRM via NumPyro/PyMC; activated only once calibration data volume supports stable item-parameter estimation. Same return contract.
- **Acceptance:** `EqualWeightScorer` produces `score_0_100` + CI for scorable dimensions and `None` for N/A; swapping backends does not change the calling code; CIs widen as `n_items` falls.

### Phase 7 — Aggregation, gates, and the index
- **Goal:** combine dimension scores into pillars, a general factor, and the gated synergy index.
- **Files:** `scoring/gated_index.py`.
- **Interface:** `assemble_index(dimension_scores, task_context) -> {g_synergy, synergy_index, pillar_scores, min_pillar_cap_applied}`.
  - v2 `g_synergy` ≈ coverage-weighted mean of scorable dimensions (replace with bifactor SEM loadings once fitted).
  - **Non-compensatory gates:** `synergy_index = g_synergy * product(gate_caps)`. Implement at least the over-trust gate (fires on high-stakes segments with unverified acceptance) and the ethics gate (fires when value-laden high-stakes content proceeds with no boundary-setting). Each cap ∈ (0, 1].
  - **Minimum-across-pillars:** headline `synergy_index` is additionally capped by the weakest scorable pillar; set `min_pillar_cap_applied` when this binds.
  - Index computed over **scorable dimensions only**; never let N/A dimensions enter as zeros.
- **Acceptance:** a profile strong on Create but weak on Design cannot post a high index (min-pillar cap binds); an unverified-high-stakes fixture triggers the over-trust gate; removing a dimension to N/A changes coverage, not the remaining scores.

### Phase 8 — Output, coverage, and translation
- **Goal:** assemble `SynergyReport` with honest coverage and a plain-language summary.
- **Files:** `output/report.py`, `output/translation.py`.
- **Interface:** `build_report(...) -> SynergyReport`; `translate(report) -> report` populating per-dimension band + `top_contributors` (signed item contributions from the scorer) + `confidence_note`.
- **Embedded cognitive-state flags (ship in v2):** populate `flags` with `load_level` (from Tier B element-interactivity/dependency-debt — Overloaded/Optimal/Underloaded) and `tom_slope` (within-chat ToM-signature trend — rising/flat/declining). These are derived from existing signals; no new extractor.
- **Acceptance:** report always carries CI + coverage; a 5/8-coverage report is visibly distinguished from 8/8; `confidence_note` reads in plain language; anchors present ("50 = corpus median").

### Phase 9 — Calibration & ICC certification (GATE: calibration gate)
- **Goal:** certify which dimensions are honestly transcript-scorable; wire the active-learning hooks.
- **Files:** `calibration/gold_set.py`, `calibration/icc.py`, `calibration/active_learning.py`.
- **Interface:** `compute_icc(gold_codes, model_codes) -> {per_dimension_icc, inter_rater_icc}`; `certify(icc) -> list[certified_dimensions]` applying ≥0.70 / ≥0.60. `select_for_coding(scored_chats, k) -> list[chat_id]` via uncertainty/disagreement sampling.
- **Acceptance:** runs on the double-coded gold set; emits a certification report; **only certified dimensions are exposed in `SynergyReport` by default** (others present but flagged `uncertified`). Failures are logged as findings, not errors.

### Phase 10 — Extension points (STUB ONLY)
- **Goal:** define interfaces so browser-layer inputs plug in later without re-architecture. Do NOT implement.
- **Files:** `extensions/browser_inputs.py`.
- **Interfaces to define (stubs):**
  - `SelfRating` — per-dimension user self-scores. Consumed later as a **separate construct** (metacognitive calibration = `self_rating - behavioral_score`), NEVER averaged into the behavioral posterior.
  - `DomSignal` — dwell-before-keystroke, copy/paste events, scroll-back depth, edit rate, regeneration clicks. Consumed later as **additional Tier A items** for `AUI`/`AUT`/`EC`/`CA`, and as a **relaxation of the scorability gate** for autonomy/dependency neurons that are N/A from text alone.
- **Acceptance:** interfaces compile and are documented; a stub test asserts `NotImplementedError`; the scorer signature already accepts an optional `extra_items` argument so DOM items can be appended later without changing call sites.

---

## 7. Cross-cutting guardrails (the "do NOT" list)

1. **Do not score a non-applicable neuron as 0.** Non-applicable → no item. Only applicable-but-poor → 0.
2. **Do not average self-rating into the behavioral score.** It is a separate construct (calibration gap).
3. **Do not fit the GRM on the 23 gold chats.** Ship `EqualWeightScorer`; gate `GRMScorer` on data volume.
4. **Do not run EFA to set weights until data volume supports it.** Equal-weight v1 is the launch state.
5. **Do not hardcode 8 dimensions or the pillar grouping.** Read from `config.py`.
6. **Do not let N/A dimensions enter the index as zeros.** Compute over scorable dimensions; report coverage.
7. **Do not emit a score without a credible interval.**
8. **Do not expose an uncertified dimension as a headline score.** Certification gate governs the public surface.
9. **Do not send raw chat text anywhere the config marks local-only.** (Forward-compat with the browser layer's privacy modes.)
10. **Do not use free-text judge output.** Structured ordinals only, fixed temperature, versioned prompt.

## 8. Build order (one line)

`Phase 1 (ingest) → Phase 2 (neuron table — GATE) → Phase 3 (dual extraction) → Phase 4 (task inference) → Phase 5 (scorability) → Phase 6 (equal-weight scorer) → Phase 7 (gates + index) → Phase 8 (report + flags) → Phase 9 (ICC certification — GATE) → Phase 10 (extension stubs).`

## 9. First task

Build **Phase 1 + Phase 2** together and prove the loop end-to-end on a single fixture chat: ingest → chunk → load the (initially small) neuron table → run one Tier A and one Tier C neuron → emit a single `ItemResponse`. Once that round-trips, the entire pipeline can be filled in phase by phase against a stable contract.

---

*This brief is the implementation contract for v2 of the Chat Classifier. Pair it with `ARI_Synergy_Framework_v2.md` for the scientific rationale behind every choice.*
