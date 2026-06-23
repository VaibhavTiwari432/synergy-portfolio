# ADR-0014 — Frozen-anchor judge-drift detection

- **Status:** Accepted
- **Date:** 2026-06-23
- **Decider:** Chief Engineer (CI/offline instrument-monitoring; non-blocking).
- **Implements:** SAF/ARI v3.21 §8.6 — detect when the *instrument* moved, not the subject.
- **Artifacts:** `calibration/drift_check.py`, `alembic/versions/017_drift_runs.py`,
  `src/db/queries.insert_drift_run`; tests in `tests/unit/test_calibration.py` +
  `tests/integration/test_drift_runs.py`.
- **Commit:** `b6bbddc` (Phase F).

## Context

Non-negotiable **#18** makes the MAE ratchet a release gate, but a judge-model or
prompt change can shift MAE without any change in the subjects. The ratchet alone
cannot distinguish instrument drift from subject change.

## Decision

Re-score a **frozen 10-chat gold anchor set** and compare overall MAE to the
ratchet baseline; a rise > `DRIFT_THRESHOLD` (0.05) flags judge drift.

- `ANCHOR_CHAT_IDS` excludes the ADR-0002 judge-family-conflict chats; baseline
  read from `stage2_rejudged.json`.
- `compute_drift()` is **pure** over an injected `score_fn` — it reuses the tested
  `run_calibration` MAE logic and is therefore testable offline without a live judge.
- **CI/cron only; never on a user path.** `drift_detected=True` is a WARNING, not a
  release block — it surfaces that the instrument needs re-anchoring, not that a
  subject regressed.
- Non-negotiable **#12** — a missing baseline or unscorable anchor yields
  `drift_detected = None` (unknown), never a false "stable".

## Consequences

- `drift_runs` is append-only history (anchor_set, mae_overall, mae_per_dimension,
  baseline_mae, drift_detected, drift_note) — a durable record of instrument
  stability over time, separate from the per-release ratchet.
- Tests cover the three offline verdicts (stable / drift / indeterminate) plus
  DB-gated persistence (flagged row; NULL flag for indeterminate).
