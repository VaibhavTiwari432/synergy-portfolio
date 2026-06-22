# PROPOSALS.md — self-exploration register

Discovery-pass findings and design proposals. Each entry is `P-NNN [STATUS]`.
A proposal is the audit trail for a non-trivial change; nothing in a red-line
class (ontology, score multipliers, the Wall, contract edits, pilot fitting) is
self-adopted — it is written here, classified, and surfaced to the project lead.

Status values: `PROPOSED` → `APPROVED` / `REJECTED` / `LANDED` / `MOOT`.

---

## P-001 [MOOT] — Manifest activation of the D-015 network interceptor

Found by: CE (Phase A, v3.21 synthesis brief).
Finding: the brief's Phase A planned to keep `extension/interceptor.js` out of the
manifest (dormant) until the Codex `content.js` bridge landed, then activate it
with a two-line MAIN-world stanza gated on "bridge merged first".

Resolution: **already landed on this branch.** `content.js` carries the full
bridge (`activePathFromMapping`, the `saf-capture` consumer, the D-016 ready-ping
/ cache-replay race fix) AND `interceptor.js` is already wired into the manifest
(`world: MAIN`, `run_at: document_start`). STOP A is therefore moot — bridge +
activation shipped together exactly as the activation plan intended. The only
outstanding D-015 item is the human VERIFY of the ChatGPT JSON field names
against a live network tab (D-015 §3) — a project-lead action, not CE code.
Status: MOOT (superseded by the landed activation).

---

## P-002 [PROPOSED] — Grounding and vigilance precision-conditioner leaves

Found by: CE (v3.21 synthesis brief, Part 3.1, C2/C3).
Domain: Unwired evidence (AI-psychology precision conditioners).
Finding: two of the five AI-psychology precision conditioners specified in v3.21
§3.1 are absent from the repo — conversational grounding (Clark & Brennan) and
epistemic vigilance (Sperber & Mercier). Their evidence would RAISE EC/CA
evidence precision (narrow the CI) for well-grounded or vigilant users; it never
moves a score value (#2). They are **leaf modules** (Codex's domain); CE specifies
them precisely and does the schema work first.

Proposed minimal change (two new Codex-authored leaf modules):

### src/trait/grounding.py  — OWNER: Codex
```python
def classify_grounding(
    session: CanonicalSession,
    tags: list[TurnTags],
) -> list[GroundingFunction]:
    """One GroundingFunction per HUMAN turn, in turn order (length == n_human_turns).
    GroundingFunction ∈ {INITIATION, GROUNDING, REPAIR, NONE}.
      REPAIR     : the human turn corrects or requests clarification on AI content.
      GROUNDING  : the human turn confirms/acknowledges without adding content.
      INITIATION : the human turn introduces a new topic/constraint.
      NONE       : none of the above.
    REPAIR turns are richer evidence for EC and CA — the precision merge uses the
    REPAIR fraction as an UPWARD precision adjustment (never a score change, #2).
    Reads session.turns + tags only. Deterministic; no judge, no event-log writes."""
```

### src/trait/vigilance.py  — OWNER: Codex
```python
def score_vigilance(
    session: CanonicalSession,
    tags: list[TurnTags],
) -> VigilanceResult:
    """Session-level vigilance pattern. Signals: justification requests, source
    probing, expressing a prior before accepting AI output, challenge-then-accept
    sequences. Returns VigilanceResult{score ∈ [0,1], n_signals, pattern_detected}.
    A DISTRIBUTED pattern — hard to fake across a whole session. The score
    CONDITIONS EC/CA evidence precision; the score value never changes (#2).
    Reads session.turns + tags only. Deterministic."""
```

Freeze check:
  - [x] adds NO neuron / dimension / pillar / latent variable (#1) — these are
        evidence fields that map onto EXISTING EC/CA precision, not new ontology.
  - [x] introduces NO score multiplier — precision (CI width) only (#2).
  - [x] crosses NO Wall (no λ, no true-synergy claim, no second latent model).
  - [ ] does NOT edit contracts/schemas.py — **FALSE**: `GroundingFunction` +
        `VigilanceResult` must be added to the contract first (CE schema work),
        which bumps `SCHEMA_VERSION` and obliges Codex to re-read.

Self-classification: **needs-CE-review** (a contract/schema edit is required
before Codex can implement). The schema change is surfaced for signoff via the
STOP C DISCREPANCY entry; the merge-side precision wiring (the REPAIR-fraction /
vigilance-score → EC/CA CI-widening) is a SEPARATE follow-up after the leaves
land, and is itself precision-only (no value change, R2-audited).

Status: PROPOSED — pending project-lead approval of the schema bump (STOP C).
