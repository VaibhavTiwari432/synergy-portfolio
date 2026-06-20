# saf-brain — SAF/ARI v2.2 Chat Analyser

Python API that ingests a human↔AI chat transcript (Claude / ChatGPT export, or
plaintext) and computes the full SAF/ARI v2.2 measurement framework: universal event
log → parallel STATE (CSPC proxies) + TRAIT (ARI 8-dim) channels → precision merge →
aggregation → interaction dynamics → sustainability layer → claims-gated response.
Part of the **Sangillence Insight System (SIS)**.

**Scope A deliverable:** `POST /v1/sessions` → `GET /v1/sessions/{id}/score` returning
the full rung-tagged `ScoreResponse`, calibrated on the gold corpus
(MAE ratchet ≤ 0.2994). No UI, no extension.

## Read first (in order)

1. [AGENT_REBUILD_BRIEF_v3.md](AGENT_REBUILD_BRIEF_v3.md) — the mission file (scope, architecture, build plan)
2. [SAF_ARI_Final_Master_Compilation_v2.2.md](SAF_ARI_Final_Master_Compilation_v2.2.md) — the authoritative spec
3. [CLAUDE.md](CLAUDE.md) — the 21 non-negotiables (all agents bound)
4. [TEAM.md](TEAM.md) — multi-agent build order + file ownership map
5. [DISCREPANCY.md](DISCREPANCY.md) — conflict log (check OPEN items)
6. `INTERFACES.md` — frozen leaf-module signatures (authored in Stage 0)

## Layout

```
contracts/        frozen schemas, taxonomies, ontology (107 neurons), claims table
data/gold/        gold-standard corpus: 26 chats + rationales (regression suite — ADR-0003)
legacy/           v1 baselines: judge prompt v1.3, calibration 0.2994, ADRs 0001–0012
src/              the pipeline (ingestion → eventlog → state ∥ trait → merge → … → api)
calibration/      gold loader + MAE ratchet runner (CI gate)
adr/              new ADR series (0001 = reset, 0002 = gc-003 caveat, 0003 = n=26)
tests/            regression / unit / property / contract / integration
```

The v1 build (TypeScript monorepo + two Python prototypes) is preserved in full at
git tag **`v1-final`** — retrieve anything via `git show v1-final:<path>`.

## Team

| Agent | Role |
|---|---|
| Claude Code | Chief Engineer — contracts, spine, merge, judge, claims, API, integration |
| Codex | Junior Dev A — trait-side leaf modules |
| Antigravity | Junior Dev B — state-side + dynamics leaf modules |

Never edit a file you don't own (TEAM.md §3). Blocked → file in DISCREPANCY.md.
