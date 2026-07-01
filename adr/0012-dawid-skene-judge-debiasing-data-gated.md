# ADR-0012 — Dawid–Skene judge de-biasing interface (data-gated)

- **Status:** Accepted
- **Date:** 2026-06-23
- **Decider:** Chief Engineer (engineering decision; data-gated, no human-review gate)
- **Implements:** SAF/ARI v3.21 — judge-bias correction as a *calibration* number.
- **Artifacts:** `calibration/dawid_skene.py`; tests in `tests/unit/test_calibration.py`.
- **Commit:** `9580dbf` (Phase D).

## Context

The judge exhibits a documented elaborated-over-terse shift: equivalent behaviour
scored higher when the transcript is verbose. Dawid–Skene EM can estimate a
per-dimension bias from multi-annotated gold so MAE can be reported *corrected*
alongside raw.

## Decision

Build the de-biasing interface now, but as a **calibration-only** output that is
never wired into a `DimensionScore`:

- Non-negotiable **#10** — annotations are never used raw to move a behavioural
  score. The module imports only stdlib, so it *structurally* cannot touch a
  score path.
- Non-negotiable **#3 / addendum #3 (data-gated)** — full EM needs ≥2 annotators
  per chat per dimension; the n=26 gold set is single-annotation. `run_dawid_skene()`
  raises `DataGatedError` until ≥2 annotators on ≥3 chats exist for at least one
  dimension. Fabricating a bias from single annotations would mislead calibration.
- Non-negotiable **#12 (absent ≠ zero)** — an under-threshold dimension returns a
  `None` bias (DATA_GATED), not 0, and does not raise when another dimension qualifies.

## Consequences

- The placeholder spread estimate activates only past the gate and is replaced by
  real EM when dual-annotation data lands. No pilot fitting on the 26 chats (addendum #2).
- Building the interface + raising the gate is the correct posture: the seam is
  ready the moment the corpus exists, and nothing fabricated reaches calibration today.
