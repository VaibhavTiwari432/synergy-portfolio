# CLAUDE.md - Current v3/v3.1 Addendum Pointer

**Read this first:** the current v3/v3.1 addendum is appended at the end of this
file. It supersedes historical rules only where it is more specific about the
current update, data-gating, disclosure gates, and no-pilot-fitting constraints.

---

# CLAUDE.md — Non-negotiables (AGENT_REBUILD_BRIEF_v3.md §8, verbatim; all agents bound)

1. **Ontology freeze:** exactly 107 neurons, 8 dims, 4 pillars. Fields may be added to the contract table; items may not.
2. **No score multipliers for state.** State → evidence precision (CI width) only. (R2)
3. **Never claim "true synergy" from transcripts** (Tier 1–2). (R3)
4. **"synergy" never appears in Tier-1 user-facing output.**
5. **"surrender" never appears in regime-overlay output** (CSPC construct only).
6. **No leaderboards / population ranking / bare composite without CI + rung.**
7. **No raw "Cognitive Debt Score"** — measured quantities + inference language only.
8. **CSPC is sole owner of latent state.** Overlay is rules only; no second latent model.
9. **Full HGF deferred.** ProxyEstimator behind the StateEstimator interface.
10. **Self-ratings never used raw** — Dawid–Skene corrected only. (Scope B concern; rule stands.)
11. **Latency thresholds personal + relative** (~1.5 SD vs rolling baseline). Never absolute.
12. **Absent ≠ zero.** N/A or INSUFFICIENT_SAMPLE.
13. **Ecology and laboratory data pools never merge.**
14. **Every emitted claim carries exactly one rung;** nothing presented above it.
15. **Minor protection:** no bare composite / peer rank / debt score to `is_minor: true`.
16. **Data dignity:** minimization; deletion propagates to derived features.
17. **Rejected ideas stay rejected:** Cognitive Primitive Layer, two-pass EC, multipliers, transcript true-synergy, second latent model → read `legacy/adr_v1/` + spec §14, write an ADR, stop for approval.
18. **MAE ratchet ≤ 0.2994** is a release gate.
19. **EC is a data problem.** Do not prompt-tune past v1.3's lesson; the fix is 40+ high-band gold chats.
20. **Judge family ≠ partner family.** Gemini judge for Claude/ChatGPT partners; if a Gemini-partner chat is scored, flag it (see ADR-0002 / gc-003 caveat). Never an Anthropic model as judge.
21. **(Team) Never edit a file you don't own; never silently work around a blocker** — `DISCREPANCY.md` or nothing.
# CLAUDE.md - v3/v3.1 Addendum For Current Framework

These rules are current as of 2026-06-18 and supersede the historical
non-negotiables above where they are more specific.

1. **v3/v3.1 is an update, not a rebuild.** Preserve the working API, DB,
   worker, extension, calibration gates, and file ownership unless a current
   task explicitly changes them.
2. **No pilot fitting.** Do not fit models, recompute cuts, run causal
   discovery, or make validation claims from the 26 gold chats; they are a
   pilot/regression set.
3. **Data-gated means stubbed.** CDM, G-DINA, causal estimation, KT
   sustainability, disclosure-effects analysis, drift/invariance analysis, and
   longitudinal stability claims raise clear data-gated errors until the
   required corpus exists.
4. **Predictive-validity gate is load-bearing.** No config may disable it or
   down-weight its margin. Attempts must raise:
   `the predictive-validity gate is load-bearing and not configurable (spec 14.1)`.
5. **Brier calibration is a field, not a replacement.** It feeds
   CA-08/calibration gap alongside slope and returns N/A/None when no realized
   in-session outcome exists.
6. **Relational-AI signatures are evidence fields only.** They may map to
   existing CA neurons after review; task-irrelevant disclosure remains an
   unscored observation unless a human approves a clean mapping.
7. **Negative sustainability disclosure is gated.** Minors and low-validation
   tiers are formative-only; distress routes to support; bare negative verdicts
   are unreachable.
8. **Relevance is not scope.** Adjacent sciences can ground or consume SAF
   outputs, but they do not add SAF neurons, dimensions, pillars, latent
   variables, or live claims.

---
