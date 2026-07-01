# ADR-0021 - FIX-0.5 provenance classifier

**Date:** 2026-06-30  
**Status:** ACCEPTED  
**Context:** SAF/ARI v3.23 FIX-0.5, after ADR-0020.

## Decision

Add `src/classifier/provenance_classifier.py` as a deterministic evidence
classifier:

- `HUMAN_ORIGINAL`
- `AI_ASSISTED`
- `COPY`
- `VERBATIM`
- `UNKNOWN`

`COPY` and `VERBATIM` receive weight `0.0`. The scorer preserves their
opportunity and sets the neuron firing to `0.0`, so copied evidence is observed
as non-contributory rather than erased as missing. This keeps absent-vs-zero
semantics intact.

## Consequences

- Exact copied/verbatim human turns can no longer inflate neuron-grain evidence.
- Judge results without evidence turns remain conservative (`UNKNOWN`, weight
  `1.0`) rather than guessing attribution.
- Existing score contract is unchanged; per-dimension audit counts use
  `raw_counts["provenance_zeroed_neurons"]` and flag
  `copy_verbatim_weighted_out`.

## Verification

- `python -m pytest tests/test_provenance_classifier.py`
- Included in full unit pass: `589 passed`.

