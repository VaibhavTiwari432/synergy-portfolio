# CHANGELOG — major upgrades and edits

Narrative history of the project, newest first. This is not a commit log (232
commits and counting — see `git log` for that); it's the milestone-level story
of what the system is today and how it got here. Each entry links to the ADR,
`DISCREPANCY.md` id, or spec doc that has the full detail.

For the live, line-item build tracker of the current effort, see `STATUS.md`.
For rejected/reversed decisions, see `PROPOSALS.md` and `adr/`.

---

## v3.22 remediation — wiring the dead modules live (2026-06-27 → present)

The v3.22 "twelve upgrades" (below) shipped as modules but were never called
from the live scoring path — every emitted score was still v3.21
(`STATUS.md` META-1). This wave rewires the real pipeline:

- **Neuron-grain judge** (A1–A5): replaced the single joint 8-dimension judge
  call with 107 per-neuron typed rubric calls (`judge/rubric_bank.py`,
  `judge/per_criterion.py`), aggregated via `aggregate/normalize.py`. Fixes
  dimension clustering (0.85–0.98 for every dim, regardless of signal).
- **FIX-0 / FIX-0.5**: grain router (`classifier/grain_router.py`) + evidence
  provenance classifier (`classifier/provenance_classifier.py`) — lets the
  pipeline choose neuron-grain vs. legacy grain per session and stamp where
  each evidence value came from.
- **ADR-0019 — pre-filter eligibility gate**: `contracts/neuron_task_eligibility.yaml`
  restricts which neurons are even eligible to fire for a given intent tag,
  cutting pass-through/hallucinated evidence. Landed flag-off, then tightened
  to `v1.1.0-critic-refined` (98 cells) and wired live (2026-06-30).
- **ADR-0017 — reject external integrations**: closed `PROPOSALS.md` P-007/008/009;
  no third-party integration surface added to the scoring path.
- **CSPC-weighted aggregation** (Phase 2 / ADR-0015): long-chat accuracy fix —
  aggregation now weights by CSPC state precision instead of a flat mean.
- **Async dimension-batching + disagreement cascade** (Phase 1b / ADR-0016):
  parallel per-dimension judge calls with cascade re-judge on disagreement.
- **Judge client cost optimizations** (Phase 1a / ADR-0014): Flash-Lite
  default model, prompt caching, OpenRouter fallback.
- **Storage gate split** (Phase 0 / ADR-0013): sparse-but-valid sessions no
  longer collapse into the same bucket as malformed ones.
- Fix train FIX-1 through FIX-8: replication-median wiring, EC Tobit onto the
  live path, D2 fluent-incompetence gate correction (attribution_gap +
  majority vote), live judge pipeline restore (Gemini 400 handling, asyncio
  guard, interceptor BFS), CSPC enum fix.
- **Gate A** (the release gate for this wave): criteria (ii) dimension
  spread and (iii) CSL density pass; criterion (i) CD cross-run range is
  still outside tolerance — see `gate_a_runs.json` and D-033 in
  `DISCREPANCY.md`. **Not yet clear to ship.**
- Still blocked: **C1** (AI-ownership discount, D-029) and **B1** (tagger
  rebalance, D-028) — both need Chief-Engineer contract approval before a
  junior dev can pick them up.

## v3.22 "twelve upgrades" — built but unwired (2026-06-26)

A large single-day push implemented all 12 planned upgrade modules (Tobit
censored-EC estimator, cascaded selective evaluation, per-criterion judge +
107-neuron rubric bank, two-table event-log split, IRT/GRM diagnostics, SSSR
validation, pm4py conformance checking, κ-efficiency substrate, LPA archetype
discovery, CRO overlay, baseline capability specs, active-learning sampling)
plus a long-chat capture fix in the extension (chunked accumulation +
reassembly for chats too large for one DOM read). A follow-up audit
(`specs/v3.22/AUDIT_FINDINGS_AND_REMEDIATION.md`) found the modules were
correct in isolation but never called from `api/pipeline.py` — this is what
the remediation wave above exists to fix.

## Scope C — Projects, portfolio, and extension UI (2026-06-20 → 06-24)

Ten build stages (S1–S10b) delivered the full extension panel: modal shell,
FAB, sidebar navigation, chat list, score detail drawer, remarks/feedback,
portfolio radar, a projects workspace with CRUD + conflict retry, project
detail radar, and user settings (including a one-click "dev key" sentinel for
local testing). Backend: migration 012 froze the projects/sessions/
portfolio-ack contract (D-012); `acknowledgePortfolio` and session-intent
persistence landed alongside it. Two features were explicitly deferred rather
than half-built: feedback pre-population (D-023) and a windowed past/present
portfolio radar (D-024).

## v3.2 — Cognitive Synergy Layer (CSL) (2026-06-19 → 06-20)

New top-level `csl/` package: human-side re-projection, AI-side
displayed-contribution extraction, ownership normalization with CSPC
precision, an emergence scanner (judge-confirmed, dormant), Tier-1 flow/
bottleneck/orchestration analytics, and a three-panel CSL report. Persisted
as JSON blobs via migration 011. Independence-check wiring and drift/
invariance analysis exist as **data-gated stubs** per the v3/v3.1 addendum —
they raise clear errors rather than fabricate a result until the corpus
exists.

## v3 / v3.1 — measurement hardening (2026-06-19 → 06-23)

- Four-state "never-collapse" model for measurement saturation (a judge
  score pinned at the scale ceiling is flagged, not trusted as a real 1.0).
- Instrument-saturation detection (tau ceiling + conjunctive guard), verified
  live against a real gold chat.
- Judge non-determinism protocol: stratified N-replication instead of a
  single noisy call.
- EIG question-quality extractor and appropriate-reliance proxies, wired as
  evidence only after explicit approval (D-020, D-021) — per the "relational
  signatures are evidence fields only" rule.
- Frozen-anchor judge-drift detection; a nightly/PR discovery harness with 6
  offline probes.
- Migration 009 (INT4→BIGINT) fixed a silent overflow crash on long chats;
  migration 010 added a scoring-lease watchdog for stuck sessions.
- `v3.21` unified master spec published as the spec-of-record for this era.

## Scope B — Capture-interception spine (2026-06-17 → 06-21)

Chrome extension MV3 capture pipeline (network-intercept primary, DOM
fallback) plus a 4-track post-build audit: security (secret-guard
fixtures), error handling (generic 500/503 + request IDs + recovery),
operational readiness (deploy scripts, health checks, structured logs), and
code quality (dead-import removal, ruff in CI). Merged as PR #1.

## v1-final → v3 rebuild (2026-06-12)

The v1 build (TypeScript monorepo + two Python prototypes) was frozen and
tagged `v1-final`, then the repo was reset per `AGENT_REBUILD_BRIEF_v3.md`
§2. Stage 0 froze the contracts (`INTERFACES.md`, 107-neuron ontology).
Stages 1–2 then built the full pipeline spine in one continuous push:
event log → ingestion (4 adapters) → intent tagging → phase classification →
deterministic extractors → judge (dimension-grain v2.0) → state estimator
(`ProxyEstimator` behind a `StateEstimator` interface, per the "full HGF
deferred" rule) → precision merge → gates + softmin aggregation →
sustainability layer (Ŝ_human, debt EWMA) → claims. First live calibration
run: shadow MAE 0.2368 vs. the 0.2994 ratchet (pass), 100% coverage.

## v1 — Python rebuild of the initial prototype (2026-06-06)

7-stage Chat Classifier v2 pipeline, gold-loader + MAE-ratchet calibration
runner, judge prompt tuned to v1.3. First calibration result: MAE 0.2994
(pass) on the composite, but EC MAE 0.41 (miss) — the origin of the
standing rule "EC is a data problem, not a prompt-tuning problem" (needs 40+
high-band gold chats, not more prompt iteration).

## v0 — TypeScript monorepo prototype (2026-05-20 → 05-27)

Original scaffold: pnpm workspace, Zod schema validators, a 24-anchor rubric,
and the first 4 hand-scored gold chats (gc-001–gc-004). Completed Phase 0+1
scoring and exposed the first `POST /score` API. Superseded by the Python
rebuild above but preserved in full at `git tag v1-final`.

---

## Rejected / reversed (kept here so they don't get re-proposed)

- **Cognitive Primitive Layer, two-pass EC, score multipliers for state,
  transcript "true synergy" claims, a second latent-state model** — all
  rejected outright; re-proposing requires reading `legacy/adr_v1/` + spec
  §14 and writing a new ADR (`CLAUDE.md` non-negotiable #17).
- **Two-pass EC** — tried during Phase 1/2, reverted (ADR-0011): 15.8
  percentage-point regression vs. single-pass.
- **Dev-local header-bypass auth** — rejected (`PROPOSALS.md` P-003): would
  have broken localhost auth semantics for a marginal convenience gain.
- **External integrations** (ADR-0017, 2026-06-30) — rejected as out of
  scope for the scoring path; see `PROPOSALS.md` P-007/008/009.
