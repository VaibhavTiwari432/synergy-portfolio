# Calibration Baseline v1.3 — the ratchet numbers

Source: `calibration/reports/calibration_20260606_190551.json` at tag `v1-final`
(raw report preserved as `legacy/calibration_v1.3_report.json`, including per-chat detail).
Run date: 2026-06-06. Judge: Gemini, prompt v1.3 (`legacy/judge_prompt_v1.3.md`),
neuron-grain. Corpus: **26 gold chats** (gc-014/gc-015 are rationale-only — see
`adr/0003-gold-corpus-n26.md`).

## The ratchet (release gate — brief §2.3, non-negotiable #18)

The rebuilt pipeline must reach **overall MAE ≤ 0.2994** on the same 26 chats.
Per-dimension target ≤ 0.375. EC is tracked separately (data problem, not prompt
problem — non-negotiable #19).

## v1.3 results

| Metric | Value | vs. target 0.375 |
|---|---|---|
| **Overall MAE** | **0.2994** | PASS |
| AL | 0.3381 | PASS |
| PR | 0.2990 | PASS |
| EC | 0.4073 | **MISS** (tracked separately) |
| ES | 0.1309 | PASS |
| CS | 0.2849 | PASS |
| CD | 0.2761 | PASS |
| AUI | 0.3030 | PASS |
| CA | 0.3562 | PASS |

## Lessons encoded in the non-negotiables

- **EC 0.41 is a data problem** — the corpus lacks high-band EC examples. The fix is
  40+ high-band gold chats, not prompt tuning (#19). Until then the rebuild emits
  `low_calibration_confidence: true` on EC (brief §3.6.4).
- **Two-pass EC was rejected** — 15.8pp regression (legacy/adr_v1/0011). Stays rejected (#17).
- **Boundary chunker verdict** — see legacy/adr_v1/0012.
- A rewrite that scores worse than v1.3 is a regression, not progress.
