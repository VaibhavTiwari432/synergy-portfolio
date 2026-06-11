# ADR-0001 — Repository reset to SAF/ARI v2.2 rebuild (Phase 0)

- **Status:** Accepted
- **Date:** 2026-06-12
- **Decider:** Human lead via `AGENT_REBUILD_BRIEF_v3.md` §2; executed by Chief Engineer
- **Predecessor state:** tag `v1-final` (commit `f3a0830` + housekeeping)

## Context

The v1 build accumulated three parallel implementations (TypeScript monorepo, Python
`saf_chat_analyser`, Python `chat_classifier`) plus superseded framework documents.
`AGENT_REBUILD_BRIEF_v3.md` mandates a clean rebuild: one Python 3.12 / FastAPI
implementation of the full SAF/ARI v2.2 framework, built by three agents against
frozen contracts.

## Decision

Everything is recoverable at tag **`v1-final`**. On top of that, the following was
**preserved live** (per brief §2.1):

| Asset | New location | Notes |
|---|---|---|
| Gold chats (26 JSON + 28 rationales + metadata) | `data/gold/{chats,rationales,metadata.json}` | n=26 regression suite — see ADR-0003 |
| Anonymized gold copies | `data/gold/chats_anonymized/` | 26 files |
| Source PDFs (28 chats) | `data/gold/source_pdfs/` | **NOT in git** (never were — gitignored; contain real names; 73 MB). Disk-only. Recovery source for gc-014/gc-015. Never delete from disk. |
| `contract_table.yaml` (107 neurons) | `contracts/contract_table.yaml` | moved with history |
| `neurons_v6.json` | `contracts/neurons_v6.json` | moved with history |
| Judge prompt v1.3 | `legacy/judge_prompt_v1.3.md` | neuron-grain baseline to beat |
| Calibration v1.3 MAE table | `legacy/calibration_baseline_v1.3.md` | ratchet numbers |
| Raw v1.3 calibration report | `legacy/calibration_v1.3_report.json` | was gitignored (`calibration/reports/*.json`) — now tracked here; includes per-chat detail |
| ADRs 0001–0012 (v1) | `legacy/adr_v1/` | rejected ideas stay visibly rejected (non-negotiable #17) |

**Deleted** (per brief §2.2; all tracked content recoverable from `v1-final`):
`chat_classifier/`, `saf_chat_analyser/`, `apps/`, `packages/`, `calibration/` (TS),
root `tests/`, `docs/`, `gold_standard/` (after moves), superseded framework docs
(AEGIS, ARI_Synergy_Framework_v2, v1/v2/v2.1 master compilations, SYNERGY_PORTFOLIO_SPEC,
implementation briefs), TS toolchain configs (package.json, pnpm-*, tsconfig.json),
v1 `requirements.txt`, tmp files.

**Kept at root:** `AGENT_REBUILD_BRIEF_v3.md` (mission), `SAF_ARI_Final_Master_Compilation_v2.2.md`
(authoritative spec), `CLAUDE.md` (§8 non-negotiables verbatim), `TEAM.md`,
`DISCREPANCY.md`, `AGENT_KICKOFF.md`, `README.md` (rewritten), `adr/` (new series from 0001).

## Consequences

- The only ground truth for calibration is `data/gold/`; the only ontology is
  `contracts/contract_table.yaml` + `contracts/neurons_v6.json`.
- New ADR numbering starts at 0001 in `adr/`; v1 ADR references are written
  `legacy/adr_v1/00NN`.
- Anything an agent misses from v1 is retrieved via `git show v1-final:<path>`,
  never by resurrecting deleted directories wholesale.
- The source PDFs exist only on this machine. Back them up outside git before any
  machine migration (human action item).
