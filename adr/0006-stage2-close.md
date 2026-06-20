# ADR-0006 — Stage 2 close: all four gates green

- **Status:** Accepted
- **Date:** 2026-06-12
- **Decider:** Chief Engineer; close-at-n=23 confirmed by project lead
- **Evidence:** `calibration/results/stage2_final.json` (prompt v2.1, Gemini 2.5
  Flash); v2.0 baseline preserved at `calibration/results/stage2_prompt_v2.0.json`

## The ratchet landed at

| | Shadow (n=26) | Headline (n=23) | Target |
|---|---|---|---|
| **Overall MAE** | **0.2368** | **0.2502** | ≤ 0.2994 ✅ |
| Coverage | 100% (26/26) | 100% (23/23) | ≥ 80% ✅ (D-002 gate) |
| Per-dim max | AL 0.3096 | AL 0.3348 | ≤ 0.375 ✅ all dims |

Per-dim (shadow / headline): AL .310/.335 · PR .267/.285 · EC .205/.215 ·
ES .280/.280 · CS .165/.185 · CD .269/.274 · AUI .202/.211 · CA .231/.241.
The v1 baseline this ratchets against was 0.2994 (judge prompt v1.3,
neuron-grain, same 26 chats) — the rebuild beats it by ~0.06 absolute.

## What it took

- **ES fix (v2.0 → v2.1, ADR-0005):** the dimension-grain judge initially
  saturated ES at 1.0 on ethical *topic salience* (ES MAE 0.460). Behavioral
  anchors at 0.80/0.25 (pinned to gold band centers) + a ">0.9 reserved" rule
  took ES to 0.280, and incidentally improved every other dimension
  (overall 0.2771 → 0.2368). Same disease and same cure as v1.3's EC anchors.
- **EC vindication:** EC MAE 0.407 (v1.3, neuron-grain) → 0.205 (v2.1,
  dimension-grain). The "EC is a data problem" pressure (non-negotiable #19)
  has substantially eased; the 40+ high-band gold-chat target remains as
  corpus growth, no longer as the gating concern.
- **Coverage gate (D-002, Codex's catch):** Gate A now requires ≥80% headline
  coverage — a near-empty run can never pass on a lucky MAE. Both runs scored
  26/26 with zero judge failures.

## Gates

| Gate | Result | Evidence |
|---|---|---|
| **A** — MAE ≤ 0.2994 + coverage ≥ 80% | ✅ | `stage2_final.json`, `ratchet_passed: true` |
| **B** — contract/forbidden-word/tier tests | ✅ | explicit run at `cf87a08`: 49 passed + 7 stem-derivative tests (synergize/synergies/synergized/synergistic covered; no-overmatch verified) |
| **C** — synthetic fixtures | ✅ | explicit run at `cf87a08`: 60 passed (precision moves CIs not scores; state caveat never multiplier; 4 EWMA modes; FTM sparse-event gating; no-latent-variable audits) |
| **D** — live POST → GET ScoreResponse | ✅ | `calibration/gate_d_smoke.py`: fresh non-gold 14-turn chat, real judge, 19/19 checks (8 dims present, rungs everywhere, nothing above MEASURABLE, no forbidden words, full response shape) |

## Deferred (visible, not forgotten)

- **gc-003/016/018 re-judge** (Gemini partners; D-001/ADR-0002): code path
  built and tested (`openai_family_judge()`, `--rejudge-conflicts`), blocked
  solely on OPENROUTER_API_KEY — tracked as **D-005**, first action when the
  key lands. Stage 2 closes on the n=23 headline by project-lead decision.
- **gc-014/gc-015 transcripts** (ADR-0003): rationale-only; recovery from
  source PDFs restores the corpus to n=28.

## Addendum (same day, post-close) — D-005 resolved

The OpenRouter key landed hours after close (zero credits → used the free
OpenAI-family `openai/gpt-oss-120b:free`). gc-003/016/018 re-judged cleanly:
`judge_family_conflict=false` on all three; headline pool restored to **n=26**.
Full-corpus conflict-free report: **MAE 0.2505, coverage 100%,
ratchet_passed=true** (`calibration/results/stage2_rejudged.json`; per-dim max
AL 0.3154, all ≤ 0.375). The n=23 close record above stands unchanged as the
close-time evidence. Upgrade path if credits arrive: re-run the three with
`SAF_REJUDGE_MODEL=openai/gpt-4o-mini`.

## What is next (project lead decides)

Per brief §6, the Scope-A definition of done is met: the pipeline computes the
full framework on the gold corpus and the API is the deliverable. The fork:
**Scope B debate** (browser extension, §9 locked decisions) versus **corpus
growth** (the 40+ high-band chats, gc-014/015 recovery, re-judge on key
arrival) to harden calibration before any new surface is built.
