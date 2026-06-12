# INTERFACES.md — Frozen leaf-module signatures (Stage 0)

**Authored by the Chief Engineer. Contract version 1.0.0 (matches `contracts/schemas.py` `SCHEMA_VERSION`).**
Every leaf module implements EXACTLY its signature below. Ambiguity → `DISCREPANCY.md`
BEFORE coding. A contract change bumps the version note at the top of this file and
requires both juniors to re-read it.

## Import rules (binding for every leaf)

- Import ONLY from `contracts.schemas`, `contracts.event_taxonomy`, `contracts.intent_tags`,
  and the standard library. (`numpy` is permitted for arithmetic if already a transitive dep;
  nothing else without a DISCREPANCY entry.)
- Read events ONLY via `src.eventlog.queries` (CE-owned; available from Stage-1 day one as
  typed read functions over `list[Event]`).
- NEVER: import another leaf, call the judge, write to the event log, read raw source
  formats, or read files from `data/`.
- Determinism: same inputs → same outputs. No network, no randomness without a fixed seed.
- Absent evidence is `None` / `ScoreStatus.NOT_APPLICABLE` / `INSUFFICIENT_SAMPLE` — never 0.0.

Types referenced below are all in `contracts/schemas.py`.

---

## 1. Codex — trait-side leaves

### 1.1 `src/trait/tagger.py`
```python
def tag_turns(session: CanonicalSession) -> list[TurnTags]:
    """One TurnTags per HUMAN turn, in turn order.
    tags ⊆ the 10 IntentTag values; a turn may carry several tags, or none
    (empty list — never invent a tag). ACCEPT_FLAT applies to a human turn that
    accepts the previous AI output with no substantive addition (heuristics:
    bare acknowledgement, 'ok/continue/next', verbatim adoption).
    Reads session.turns only."""
```

### 1.2 `src/trait/phase_classifier.py`
```python
def classify_phases(session: CanonicalSession, tags: list[TurnTags]) -> list[Phase]:
    """One Phase per HUMAN turn, in turn order (same length/order as tags).
    Phase ∈ {EXPLORE, REFINE, EXTRACT, EVALUATE}. Deterministic rules over
    turn text + intent tags."""
```

### 1.3 `src/trait/extractors/per_dimension/{al,pr,ec,es,cs,cd,aui,ca}.py` — 8 files
Each file exposes a module constant and one function:
```python
DIM: Dimension  # the module's dimension constant

def extract(
    session: CanonicalSession,
    tags: list[TurnTags],
    phases: list[Phase],
    events: list[Event],
) -> dict[str, object]:
    """Deterministic-signal extraction for this dimension's neurons ONLY
    (neuron ids from contracts/contract_table.yaml where
    extractor_type == 'deterministic' and dimension == DIM).
    Returns {
      "neuron_firings": dict[str, float],   # neuron_id -> strength 0.0–1.0; ABSENT key = no evidence (never 0.0 for absence)
      "applicable_opportunities": dict[str, int],  # neuron_id -> opportunity count (denominator)
      "evidence_turns": dict[str, list[int]],      # neuron_id -> supporting human-turn indices
    }
    Unambiguous signals only (accept-run → AUI; VERIFY rate → EC; SELF_AUDIT
    presence → CA, etc.). When in doubt, do NOT fire — the judge covers
    inferential neurons. ES (es.py): fire only when an ethics-relevant trigger
    event exists in `events`; else return empty dicts (brief §3.6.6)."""
```

### 1.4 `src/aggregate/normalize.py`
```python
def normalize_counts(
    firings: dict[Dimension, dict[str, float]],
    opportunities: dict[Dimension, dict[str, int]],
) -> NormalizedScores:
    """fired ÷ applicable opportunities per neuron, aggregated per dimension,
    standardized by neuron count (DIMENSION_NEURON_COUNTS) so CA-17 gets no
    structural edge over AUI-12. A dimension with zero opportunities →
    DimensionNormalization(status=NOT_APPLICABLE, normalized=None).
    Pure function; no I/O."""
```

---

## 2. Antigravity — state-side + dynamics leaves

### 2.1 `src/state/load_classifier.py`
```python
def classify_load(session: CanonicalSession) -> list[LoadLabel]:
    """One LoadLabel per HUMAN turn, in turn order.
    Signals: prompt-length trajectory, vocab-complexity delta, fragmentation
    (brief §3.5). Relative to the session's own baseline — never absolute
    thresholds (non-negotiable #11). Reads session.turns only."""
```

### 2.2 `src/state/epistemic_classifier.py`
```python
def classify_epistemic(session: CanonicalSession, tags: list[TurnTags]) -> list[float]:
    """One E_t ∈ [-1.0, +1.0] per HUMAN turn (extractive −1 ↔ +1 generative),
    from intent tags (GENERATIVE_TAGS / EXTRACTIVE_TAGS in contracts.intent_tags)
    + turn text. Session mean and half-to-half slope are computed downstream
    (CE estimator) — return the per-turn series only."""
```

### 2.3 `src/state/metacog_classifier.py`
```python
def classify_metacog(session: CanonicalSession, tags: list[TurnTags]) -> MetacogResult:
    """One MetacogLabel per HUMAN turn in `labels` (turn order).
    SURRENDER: accept-run ≥ 3 consecutive ACCEPT_FLAT human turns; from the
    onset turn of that run onward until a non-ACCEPT_FLAT turn. Set
    surrender_detected + surrender_onset_turn (first turn of the run).
    NOTE: SURRENDER is a CSPC label — it exists ONLY in this module's output
    and never in overlay/report text."""
```

### 2.4 `src/state/tomer_slope.py`
```python
def tom_slope(session: CanonicalSession) -> tuple[list[float], float | None]:
    """(per-human-turn ToM-signature strengths 0.0–1.0, fitted slope).
    ToM signatures: prompts that model the AI's perspective/capabilities
    ('you might not know…', 'given your training…', anticipating failure modes).
    Slope None if < 4 human turns (insufficient sample — never 0.0)."""
```

### 2.5 `src/dynamics/transitions.py`
```python
def compute_transitions(events: list[Event], tags: list[TurnTags]) -> TransitionMetrics:
    """The five frozen metrics (brief §3.8) over the event log ONLY.
    Each rate is a CellGatedProb: n_events = the denominator count; value=None
    when n_events < MIN_EVENTS_PER_CELL (contracts.event_taxonomy).
    accept_run_max/mean from consecutive ACCEPT_FLAT human turns; None when
    there are no substantive acceptance opportunities."""
```

### 2.6 `src/dynamics/overlay.py`
```python
def regime_overlay(events: list[Event], tags: list[TurnTags]) -> RegimeOverlay:
    """RULES ONLY. Deterministic segmentation into RegimeLabel runs:
    occupancy shares (sum ≈ 1.0 over labeled turns), strip (one label per
    human turn), run_lengths per label. No probabilities, no latent variables,
    no smoothing across runs. The word 'surrender' must not appear anywhere
    in this module — including comments and test names (CI greps for it)."""
```

---

## 3. Chief Engineer — spine (juniors: read-only awareness)

| Module | Role |
|---|---|
| `src/ingestion/adapters/{claude_export,chatgpt_export,plaintext}.py` | `parse(payload: str \| dict, *, partner_model: PartnerModel \| None) -> CanonicalSession` |
| `src/ingestion/canonical.py` | source detection + adapter dispatch |
| `src/eventlog/schema.py` / `writer.py` / `queries.py` | append-only log; **`queries.py` is the ONLY read surface for leaves** |
| `src/trait/judge/{client,prompt,parser}.py` | Gemini 2.5 Flash, temp 0.1, 3 retries, dimension-grain `JudgeOutput`; OpenRouter fallback |
| `src/trait/evidence.py` | provenance tagging + theater check (`theater_counter`) |
| `src/state/estimator.py` | `StateEstimator` interface + `ProxyEstimator` assembling §2.1–2.4 outputs into `list[StateVector]` + `StateValidity` |
| `src/merge/precision.py` | **THE meeting point** — see input contract below |
| `src/aggregate/{softmin,gates}.py` | soft non-compensatory composite; scorability (≥4/8 dims valid) + state validity gates |
| `src/dynamics/reactions.py` | E→R signatures, Dirichlet partial pooling, per-cell gating → `ReactionSignatures` |
| `src/dynamics/reliability_map.py` | era-keyed partner-reliability scaffold |
| `src/sustainability/{debt_tracker,ewma,lambda_proxy,probe_schema}.py` | Ŝ_human, EWMA, λ stub |
| `src/claims/{rungs,tier_engine,report}.py` | rung tagging, tier gating, forbidden-word enforcement |
| `src/api/*` | FastAPI app, routes, API-key auth |
| `calibration/{gold_loader,runner}.py` | the MAE ratchet (n=26 — ADR-0003) |

### 3.1 The precision-merge input contract (`src/merge/precision.py`, CE only)

```python
def merge(
    trait_scores: dict[Dimension, DimensionScore],   # CIs BEFORE state conditioning
    state_validity: StateValidity,
    state_strip: list[StateVector],
) -> dict[Dimension, DimensionScore]:
    """State conditions trait evidence PRECISION (CI width) only:
    - output value == input value for every dimension, ALWAYS (R2 — audit-tested)
    - state_compromised → widen all CIs; per-dimension widening may use the
      strip's load/metacog series
    - statuses pass through unchanged (absent stays absent)
    """
```
A synthetic-fixture CI test asserts: same scores in, same scores out, only `ci` changes
(Stage-2 Gate C). **No score multipliers for state, ever.**

---

## 4. Orchestration order (who consumes whom — for understanding, not for importing)

```
adapters → CanonicalSession → eventlog.writer → events
tagger → tags ─┬→ phase_classifier → phases ─┬→ extractors (×8) ─┐
               ├→ epistemic/metacog/load/tom ─→ estimator ────────┤
               └→ transitions / overlay / reactions               │
judge ────────────────────────────────────────────────────────────┤
                  estimator → StateValidity ──→ merge.precision ←─┘ (trait scores)
merge → normalize/softmin/gates → composite → sustainability → claims → ScoreResponse
```

The pipeline (CE) passes leaves their inputs; leaves never fetch.

---

## 5. Test obligations per leaf

- Unit tests beside the module under `tests/unit/` named `test_<module>.py`, owned by
  the module's owner.
- Each leaf ships with: happy path, empty-session behavior (no human turns), and the
  absent-≠-zero case for its outputs.
- Stage-0 stub tests in `tests/unit/test_stage1_stubs.py` are `xfail` markers, one per
  leaf — flip yours to a real import as you deliver (delete the stub line in the same
  commit that lands the module).

*Version log: 1.0.0 — initial freeze (Stage 0).*
