"""
calibration/human_irr_runner.py — Human IRR ceiling measurement (v3.22 Item #5).
OWNER: Chief Engineer.

Purpose: Compute Cohen's κ per neuron across two human raters for ≥30 annotated
gold chats. The resulting κ_per_neuron values set the empirical Φ target for the
cascaded replication threshold in cascade_eval.py:DEFAULT_DISAGREEMENT_THRESHOLD.

STATUS: NOT RUNNABLE — requires:
  1. Second human rater with access to the gold chat set
  2. Rater-2 annotations for ≥30 chats in the same format as data/gold/rationales/
  3. CE co-ordination to resolve disagreements before computing κ

When runnable:
  python -m calibration.human_irr_runner \
      --rater1 data/gold/rationales/ \
      --rater2 <rater2_dir>/ \
      --output calibration/results/irr_kappa.json

Output format:
  {
    "per_neuron_kappa": {"EC-01": 0.72, "EC-02": 0.68, ...},  # Cohen's κ per neuron
    "mean_kappa": 0.71,
    "phi_target": 0.70,  # = mean_kappa (or CE-adjusted value)
    "n_chats": 30,
    "rater1_id": "...",
    "rater2_id": "...",
    "computed_at": "..."
  }

After running: update cascade_eval.py:DEFAULT_PHI_TARGET and
DEFAULT_DISAGREEMENT_THRESHOLD from the output. File a new ADR.
"""

from __future__ import annotations
# Implementation pending rater-2 annotation set.
# Stub present to define the interface and prevent ambiguity about ownership.
raise NotImplementedError(
    "human_irr_runner not yet runnable — see module docstring for prerequisites."
)
