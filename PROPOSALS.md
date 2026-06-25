# PROPOSALS.md — self-exploration register

Discovery-pass findings and design proposals. Each entry is `P-NNN [STATUS]`.
A proposal is the audit trail for a non-trivial change; nothing in a red-line
class (ontology, score multipliers, the Wall, contract edits, pilot fitting) is
self-adopted — it is written here, classified, and surfaced to the project lead.

Status values: `PROPOSED` → `APPROVED` / `REJECTED` / `LANDED` / `MOOT` /
`AUTO-PROPOSED` (raised by the discovery harness, awaiting CE triage).

**Discovery harness (Phase G):** `.github/workflows/discovery.yml` runs the
`scripts/discovery/*.py` probes nightly + on every PR (non-blocking — findings are
`::warning::` lines, never a gate). A real hit prints a paste-ready
`P-NNN [AUTO-PROPOSED]` stub; CE triages it into a numbered entry here. The probes
are offline (deterministic fake judge, no DB/keys) and mirror the §3 discovery
pass: D1 unwired evidence, D2 dropped signals, D3 determinism, D4 coverage,
D6 forbidden words, D7 R2 audit.

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

Status: SCHEMA LANDED (project lead approved STOP C, 2026-06-23 — D-027). The
contract types (`GroundingFunction`, `VigilanceResult`) and the INTERFACES.md
§1.4/§1.5 signatures are frozen at SCHEMA_VERSION 1.2.0. **Codex implementation of
`src/trait/grounding.py` + `src/trait/vigilance.py` is now READY** (TEAM.md task
C-001). The merge-side precision wiring remains a separate CE follow-up.

---

## P-003 [REJECTED] — Omit X-API-Key header for the dev-local sentinel on localhost

Found by: CE (S10 follow-up to the Settings "Use dev key" sentinel, `993a958`+`ab13ec5`).
Domain: extension egress / local-dev auth.

Finding considered: after the Settings sentinel writes `dev-local` to storage,
should `api_client._request()` *omit* the `X-API-Key` header when
`key === 'dev-local' && endpoint` is localhost — on the theory that the key
"never leaves the extension on localhost"?

Why rejected — **it would break localhost auth.** The backend does NOT skip auth
on localhost. `start_saf.ps1` (default, no `-Prod`) sets `SAF_API_KEY = "dev-local"`,
and `src/api/middleware/auth.py::require_api_key` still enforces the header on every
guarded router (`ingest.py:33`, `users.py:44`, `projects.py:48`):

```python
if x_api_key is None or not hmac.compare_digest(x_api_key, expected):
    raise HTTPException(status_code=401, detail="invalid or missing X-API-Key")
```

A missing header → 401 on every ingest/users/projects call — the exact failure the
S10 sentinel was built to remove. Note the precise mechanism: the localhost server
is **pre-configured** to accept the literal `dev-local`, NOT running auth-skipped.
(Correcting a tempting misread — there is no localhost exemption anywhere in the
auth path; do not add code or docs that assume one.)

Also: `dev-local` is a public, well-known constant committed in `start_saf.ps1`,
sent only to a localhost server the developer controls — transmitting it is not an
exposure, so there is nothing to protect against.

Decision (project lead, 2026-06-23): **the sentinel IS the contract.** The
extension sends `dev-local` as a real key; the server accepts it because it is
pre-configured to. The two localhost guards on the extension side (localhost-only
rendering + click-time re-check, S10) already prevent accidental remote
transmission. No api_client bypass logic; no backend auth weakening. Done.
Status: REJECTED (unnecessary; would break localhost auth).

---

## P-004 [LANDED] — Read-only CSL route + descriptive contribution panel

Found by: CE (panel design iteration 3, project-lead request to integrate the CSL
layer into the per-chat results).
Domain: API surface (new read-only endpoint) + panel UI.

Finding/decision: the CSL (Cognitive Work Layer) ownership artifact is stored in
`scores.csl` (migration 011) but no route served it — by design, CSL is never in
the frozen `ScoreResponse`. Project lead approved surfacing it as a **separate
read-only route** feeding a **descriptive** panel (2026-06-24).

Implementation (all CE-owned files):
  - `GET /v1/users/{ref}/chats/{id}/work` (`src/api/routers/users.py`) — reads the
    stored `csl.ownership` via the existing `get_scored_score_row` (no new query),
    returns the 7 ACF levels (C1–C7) in order, each with `status / human_pct /
    ai_pct / ci / flags`, plus top-level `rung: DESIGNED`, `uncertified: true`,
    `note`, `contract_version`. No new DB write; no schema/contract edit.
  - `api_client.getChatWork` + `detail.js renderCSL` — 7 per-level human/AI bars;
    thin-evidence levels show a status, never a fabricated 50/50.

Freeze check:
  - [x] adds NO neuron / dimension / pillar / latent variable (#1).
  - [x] introduces NO score multiplier; CSL never modifies an ARI score (#2).
  - [x] NOT in `ScoreResponse`; the frozen contract is untouched.
  - [x] NEVER averaged into a whole-session scalar (`csl/ownership.py` Do-NOT #5) —
        the route and panel are strictly per-level.
  - [x] every value carries the DESIGNED rung + `uncertified_pending_icc` (#14);
        displayed (not genuine) contribution — genuine ownership needs the probe.

Verified: handler called against the live DB returns OK with per-level splits
(e.g. C2 54%/46%, C3 100%/0%, C4 14%/86%, plus N/A + saturated rows). Live route
needs a server restart to register (the running server predates it).
Status: LANDED (pending project-lead screenshot review).

---

## P-005 [PROPOSED — gated on MAE] — Judge score-resolution instruction (v2.1 → v2.2)

Found by: CE (panel iteration 3 follow-up). Project lead asked for finer-grained
dimension values so scores stop clustering on round tenths (0.8/0.9/0.6).
Domain: calibrated judge prompt (`src/trait/judge/prompt.py`, CE-owned).

Context the request resolved to: literal display decimals like `87.34` require the
judge to emit `0.8734` — sub-0.01 precision, below the LLM judge's noise floor and
in tension with the per-row CI (`±9.5`); that is false precision (#14) and was
declined. The project lead instead chose **more resolution at 0.01 granularity**:
the judge uses the full two-decimal range so scores spread (0.83, 0.87, 0.91)
instead of snapping to tenths. Values still read as whole numbers on the ×100
display, but they vary meaningfully.

Change (v2.2): added a SCORE RESOLUTION paragraph instructing two-decimal use and
"do NOT default to round tenths", with an explicit "never an invented decimal"
guard. **Anchor meanings are unchanged** — this is output resolution only, not a
recalibration. Version bumped v2.1 → v2.2 (the prompt file's own traceability
contract); `tests/unit/test_judge.py` pin updated + a v2.2 regression assertion.

Freeze check:
  - [x] adds NO neuron / dimension / pillar / latent variable (#1).
  - [x] introduces NO score multiplier (#2).
  - [x] does NOT change anchor values or scoring semantics — resolution only; not
        prompt-tuned to fit the gold set (#19 / addendum #2 "no pilot fitting").
  - [ ] **MAE ratchet (#18) — NOT YET VERIFIED.** This is the load-bearing gate.
        A judge-prompt change is not release-eligible until the shadow-corpus MAE
        stays ≤ 0.2994 over the 26 gold chats. Pending until run.

How to clear the gate (needs `ANTHROPIC_API_KEY`; re-judges all 26 chats — billable):
  1. Invalidate the stale cache (it keys on chat_id only, NOT prompt version, so a
     plain re-run would silently reuse v2.1 predictions):
     `rm calibration/results/stage2_predictions_cache.json`
  2. `python -m calibration.run_stage2`  (re-judges all 26 under v2.2)
  3. Read `shadow.overall_mae` in `calibration/results/stage2_initial.json`.
     - ≤ 0.2994 → gate PASS, promote P-005 to LANDED.
     - > 0.2994 → gate FAIL. Per #19/addendum #2 the prompt is NOT re-tuned to
       recover MAE; the change is reverted (v2.2 → v2.1) and parked. Run ONCE.

Observation (separate, minor): `run_stage2` cache has no prompt-version key — a
latent stale-cache risk on any future prompt edit. Worth a follow-up to stamp the
cache with `JUDGE_PROMPT_VERSION`; not blocking this change.
Status: PROPOSED — code landed behind the MAE gate; awaiting the gold-set re-judge.
