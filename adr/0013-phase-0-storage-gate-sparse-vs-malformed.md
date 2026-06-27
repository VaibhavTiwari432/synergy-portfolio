# ADR-0013 — Phase 0: Storage gate splits malformed from sparse-but-valid

**Date:** 2026-06-28  
**Status:** ACCEPTED  
**Context:** v3.21→v3.22 CE Execution Brief, Phase 0 (spine + hygiene)  
**Supersedes:** Implicit rejection of sparse transcripts in Phase 0 baseline

---

## Problem

The completeness gate in `src/db/queries.py` and the ingest router was rejecting
sparse or incomplete chats with HTTP 422, treating sparsity as a storage failure:

```python
incomplete_reason = capture_completeness_error(...)
if incomplete_reason is not None:
    raise ValueError(...)  # → HTTP 422
```

This violated the non-negotiable principle **"absent ≠ zero"** (#12): a chat with
incomplete metadata or few evidence turns was rejected entirely, rather than stored
with flags so the scoring layer could emit explicit missingness labels.

Root cause: the storage boundary was conflating two distinct issues:
- **Malformed:** structurally broken (no turns, role imbalance) → genuinely unsafe
- **Sparse:** incomplete capture metadata or short sessions → valid data, requires flagging

---

## Decision

**Split the storage gate into two layers:**

1. **Structural validation** (reject malformed): `capture_validation_error()`
   - No turns, no user turns, no assistant turns, imbalanced roles, unknown roles
   - Raises `ValueError` → HTTP 422
   - Unchanged behavior: malformed transcripts cannot be stored

2. **Completeness gate** (informational only, do NOT reject): `capture_completeness_error()`
   - Detected incomplete captures: `capture_complete=False`, `captured < expected`
   - Stored alongside the chat; does NOT prevent ingest
   - Scoring layer emits `INSUFFICIENT_SAMPLE` or other flags as appropriate
   - Enables "absent ≠ zero" compliance: sparse is not invalid, just flagged

---

## Changes

### `src/db/queries.py`
- `upsert_chat()` now ignores completeness errors (stores them for reference)
- Structural validation (`capture_validation_error()`) still raises on malformed

### `src/api/routers/ingest.py`
- Removed HTTP 422 on completeness errors
- Ingest now accepts sparse/incomplete chats (status='pending')
- Completeness info persisted on the chat row for scoring layer visibility

### `.gitignore`
- Added `saf_brain.db` (development SQLite, never commit)

### `README.md`
- Version bump: v2.2 → v3.21
- Spec reference updated to current location

---

## Acceptance Criteria

✅ Sparse chat (few turns, incomplete metadata) → 200, persists  
✅ Malformed chat (no turns) → 422 MALFORMED, rejected  
✅ Incomplete capture (proven truncated) → 200, persists  
✅ All existing tests pass (structural validation unchanged)

---

## Consequences

- **Scoring layer now responsible for flagging:** must emit `INSUFFICIENT_SAMPLE`,
  `INSUFFICIENT_HISTORY`, etc. on chats with incomplete metadata or sparse content
- **Caller visibility improved:** sparse/incomplete chats reach pending queue;
  if scoring fails, the failure reason is discoverable, not masked by early rejection
- **Database state more transparent:** completeness info persists, enabling
  post-hoc analysis of which chats were problematic and why

---

## Related

- Non-negotiable #12: "Absent ≠ zero. N/A or INSUFFICIENT_SAMPLE."
- Brief Phase 0 (spine + hygiene): storage gate refactor is blocking unlock
  for Phase 1 (efficiency) and Phase 2 (accuracy)
