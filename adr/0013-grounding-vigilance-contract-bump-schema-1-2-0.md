# ADR-0013 — Grounding + vigilance precision-conditioner contract (SCHEMA 1.2.0)

- **Status:** Accepted
- **Date:** 2026-06-23
- **Decider:** Project lead (STOP C human-review gate); change prepared by Chief Engineer.
- **Implements:** SAF/ARI v3.21 §3.1 (C2/C3) — two of the five AI-psychology
  precision conditioners: conversational grounding (Clark & Brennan) and
  epistemic vigilance (Sperber & Mercier).
- **Artifacts:** `contracts/schemas.py` (`GroundingFunction`, `VigilanceResult`),
  `INTERFACES.md` §1.4/§1.5, `PROPOSALS.md` P-002, `DISCREPANCY.md` D-027, `TEAM.md` C-001.
- **Commits:** `36a3942` (P-002 spec, pre-STOP-C) → `0e8701a` (STOP C contract bump).

## The gate

A contract/schema edit is a red-line class (addendum, CLAUDE.md): not self-adopted.
The grounding/vigilance leaves require two new contract types before Codex can
implement them, which bumps `SCHEMA_VERSION` and obliges a re-read. P-002 was
written to PROPOSED, classified `needs-CE-review`, and held for STOP C signoff.

## Decision — additive contract, approved at STOP C (D-027)

Project lead approved the additive edit on 2026-06-23:

- `GroundingFunction` ∈ {INITIATION, GROUNDING, REPAIR, NONE} and
  `VigilanceResult` {score ∈ [0,1], n_signals, pattern_detected} added to
  `contracts/schemas.py`; `SCHEMA_VERSION` 1.1.0 → 1.2.0; both in `__all__`.
- `INTERFACES.md` §1.4 `classify_grounding` + §1.5 `score_vigilance` — Codex-owned
  leaf signatures, frozen at 1.2.0.

Freeze checks held:

- **#1 ontology freeze** — these are *evidence fields* that map onto existing
  EC/CA precision. No neuron / dimension / pillar / latent variable added.
- **#2 no score multiplier** — the REPAIR-fraction / vigilance-score CONDITION
  EC/CA evidence precision (CI width) only; they never move a score value.
- No Wall crossing (no λ, no true-synergy claim, no second latent model).

## Consequences

- The new types have **no consumer yet** — the producing leaves are Codex's
  (`TEAM.md` C-001, READY). Codex must re-read before implementing (D-027).
- The merge-side precision wiring (REPAIR-fraction / vigilance-score → EC/CA
  CI-widening) is a **separate CE follow-up**, itself precision-only and R2-audited.
- Calibration is unaffected: with no producer, scoring output for the 26 gold
  chats is byte-identical; the post-bump re-run holds at MAE 0.2505 (≤ 0.2994).
