# saf-brain — SAF/ARI v3.21 Chat Analyser

Python API that ingests a human↔AI chat transcript (Claude / ChatGPT export, or
plaintext) and computes the full SAF/ARI v3 measurement framework: universal event
log → parallel STATE (CSPC proxies) + TRAIT (ARI 8-dim) channels → precision merge →
aggregation → interaction dynamics → sustainability layer → claims-gated response.
Part of the **Sangillence Insight System (SIS)**.

**Scope A deliverable:** `POST /v1/sessions` → `GET /v1/sessions/{id}/score` returning
the full rung-tagged `ScoreResponse`, calibrated on the gold corpus
(MAE ratchet ≤ 0.2994). Scope B added a Postgres-backed worker + Chrome
extension capture spine; Scope C added projects/portfolio. See
[CHANGELOG.md](CHANGELOG.md) for the full build history.

## Read first (in order)

1. [specs/v3/AGENT_REBUILD_BRIEF_v3.md](specs/v3/AGENT_REBUILD_BRIEF_v3.md) — the mission file (scope, architecture, build plan)
2. [specs/v3/SAF_ARI_Master_Spec.md](specs/v3/SAF_ARI_Master_Spec.md) — the authoritative spec
3. [CLAUDE.md](CLAUDE.md) — the non-negotiables (all agents bound) + current v3/v3.1 addendum
4. [TEAM.md](TEAM.md) — multi-agent build order + file ownership map
5. [DISCREPANCY.md](DISCREPANCY.md) — conflict log (check OPEN items)
6. [STATUS.md](STATUS.md) — the live line-item tracker for the current build wave
7. [CHANGELOG.md](CHANGELOG.md) — milestone-level history of every major upgrade so far
8. `INTERFACES.md` — frozen leaf-module signatures (authored in Stage 0)

## Architecture

One scoring request flows through the pipeline in this order
(`src/api/pipeline.py` is the orchestrator):

```
ingestion (adapters: claude / chatgpt / plaintext / gold_json)
  -> canonical event log (append-only, ordered)
  -> intent tagging (10 frozen tags) + phase classification (explore/refine/extract/evaluate)
  -> STATE channel (CSPC proxy estimator)   ||   TRAIT channel (judge + deterministic extractors, 107 neurons / 8 dims)
  -> precision merge (state -> CI width only, never a score multiplier)
  -> per-dimension gates + softmin aggregation (non-compensating composite, 4 pillars)
  -> CSL (Cognitive Synergy Layer): ownership, emergence, flow analytics
  -> sustainability layer (S_human, debt EWMA)
  -> claims (rung-tagged) -> ScoreResponse
```

The **TRAIT** side currently runs neuron-grain: each of the 107 contract
neurons gets its own typed judge call (`judge/per_criterion.py`) gated by
`contracts/neuron_task_eligibility.yaml` (which intents a neuron is even
eligible to fire on), rather than one joint 8-dimension call. The **STATE**
side is a `ProxyEstimator` behind a `StateEstimator` interface — full HGF is
explicitly deferred (`CLAUDE.md` #9). CSPC is the sole owner of latent state;
the regime overlay is rules-only and never claims "synergy" in Tier-1 output.

**Current status:** this pipeline is mid-remediation on branch
`feat/v3.22-twelve-upgrades` — see `STATUS.md` for exactly which waves are
live vs. blocked, and `gate_a_runs.json` for the latest release-gate numbers.

## Running locally

```powershell
.\start_saf.ps1            # API + worker, dev key = "dev-local" (matches the extension's "Use dev key" button)
.\start_saf.ps1 -Prod      # rotates a random key persisted to .saf_api_key
```

Requires Postgres reachable via the connection settings in `alembic.ini` /
`src/db/connection.py`; run outstanding migrations with `alembic upgrade head`
first. `/v1/health` reports both API and worker liveness.

## Testing

```bash
python -m ruff check src/ --select F      # lint (pyflakes rules; CI-enforced)
python -m pytest tests/ -q                # full suite: unit / property / contract / integration / regression
PYTHONHASHSEED=0 python -m pytest         # required for the determinism tests (E1) to be meaningful
```

Calibration (the release gate — MAE ratchet ≤ 0.2994) runs via
`calibration/`; never fit it to `data/gold/` — that corpus is a pilot/
regression set, not a training set (`CLAUDE.md` v3 addendum #2).

## Layout

```
src/              the pipeline (ingestion → eventlog → state ∥ trait → merge → … → api)
extension/        Chrome extension (capture spine + panel UI)
contracts/        frozen schemas, taxonomies, ontology (107 neurons), claims table
specs/            versioned specs (v2.2, v3, v3.1, v3.2, v3.21, v3.22)
adr/              new ADR series (0001 = reset, 0002 = gc-003 caveat, 0003 = n=26)
legacy/           v1 baselines: judge prompt v1.3, calibration 0.2994, ADRs 0001–0012
data/gold/        gold-standard corpus: 26 chats + rationales (regression suite — ADR-0003)
calibration/      gold loader + MAE ratchet runner (CI gate)
tests/            regression / unit / property / contract / integration
benchmarks/       perf/quality benchmark harnesses
audit/            audit tooling and reports
csl/              CSL-specific pipeline code/config
alembic/          DB migrations
infra/            deployment/infra config
scripts/          one-off dev tooling (e.g. Vertex AI credential smoke test)
measurements/     committed diagnostic/regression run outputs
docs/             deployment guides, FAQ, runbooks; docs/history/ = superseded briefs & audits
visuals/          standalone HTML demos
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
