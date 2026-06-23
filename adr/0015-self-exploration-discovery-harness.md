# ADR-0015 — Self-exploration protocol: PROPOSALS register + discovery harness

- **Status:** Accepted
- **Date:** 2026-06-23
- **Decider:** Chief Engineer (governance artifact; non-blocking by construction).
- **Implements:** SAF/ARI v3.21 Part 5 — let coding agents discover and propose
  good engineering by themselves, safely, inside existing governance.
- **Artifacts:** `PROPOSALS.md`, `scripts/discovery/*.py`, `.github/workflows/discovery.yml`.
- **Commits:** `36a3942` (PROPOSALS register + P-001/P-002) → `3597e72` (harness + workflow).

## Context

The framework needs a way for agents to surface engineering findings without
self-adopting anything in a red-line class (ontology, score multipliers, the Wall,
contract edits, pilot fitting). The audit trail and the gate must be explicit.

## Decision

Two parts:

1. **`PROPOSALS.md`** — a self-exploration register. Each finding is `P-NNN [STATUS]`
   (PROPOSED → APPROVED / REJECTED / LANDED / MOOT / AUTO-PROPOSED). A red-line-class
   change is written, classified, and surfaced to the project lead — never self-adopted.
2. **Discovery harness** — `scripts/discovery/*.py` mirror the §3 probes and run
   nightly + on every PR via `discovery.yml`. **Non-blocking by construction:** each
   probe exits 0 and surfaces findings as `::warning::` lines, printing a paste-ready
   `P-NNN [AUTO-PROPOSED]` stub for CE triage. Probes are offline (deterministic fake
   judge, no DB/keys) so they run on a clean CI checkout.

Probes: D1 unwired-evidence, D2 dropped-signals, D3 determinism, D4 coverage,
D6 forbidden-words, D7 R2-audit.

## Consequences

- Two brief-sketch corrections were folded in while implementing: D1 keys on the
  contract field `id` (not a phantom `neuron_id`); D4 checks test *references*
  because leaf tests are grouped (not a per-module `test_<name>.py`). Both sketch
  errors would have flooded false hits.
- The harness can only *raise* proposals; it can never gate a release or adopt a
  change. Governance (CLAUDE.md non-negotiables + STOP gates) is unchanged.
- First register entries: P-001 (D-015 manifest activation) → MOOT (already landed);
  P-002 (grounding/vigilance leaves) → SCHEMA LANDED (see ADR-0013).
