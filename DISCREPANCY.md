# DISCREPANCY.md — Conflict & Resolution Log
**The single place where build conflicts get raised and resolved.**

- Any agent raises a discrepancy here when blocked.
- ONLY the Chief Engineer (Claude Code) writes the `Decision:` line and marks `RESOLVED`.
- Juniors never silently work around a problem — a silent workaround is the one thing that breaks the team.
- Chief Engineer reviews every OPEN item at the start of each session before writing new code.

---

## Entry format (copy this block, append below, increment NNN)

```
## D-NNN  [OPEN]  — <one-line title>
- Raised by: <Codex | Antigravity | Chief Engineer>
- Date: <when>
- File(s): <paths involved>
- Problem: <what is blocking, concretely — be specific>
- Proposed fix: <your suggestion, optional>
- Decision: <CHIEF ENGINEER ONLY — the resolution>
- Status: OPEN
```

When resolved, change `[OPEN]` → `[RESOLVED]` in the heading and set `Status: RESOLVED`.
If the fix changed a contract, add: `Contract bumped: <file> — re-read required by: <agents>`.

---

## Active log

<!-- New discrepancies go below this line, newest at the bottom -->

## D-001  [RESOLVED]  — Three Gemini-partner gold chats conflict with the Gemini judge family
- Raised by: Chief Engineer
- Date: 2026-06-12
- File(s): data/gold/chats/gc-003.json, gc-016.json, gc-018.json; data/gold/metadata.json; adr/0002
- Problem: Non-negotiable #20 (judge family ≠ partner family). The pipeline judge is
  Gemini 2.5 Flash. The partner-family census run after the adapters landed (Stage 1,
  tests/integration/test_gold_roundtrip.py::test_gold_corpus_partner_family_census)
  found THREE Gemini-partner chats, not just the one (gc-003) known at ADR-0002 time:
  gc-003 (Ritesh_Gemini), gc-016 (Puransh_Gemini), gc-018 (Shreyas_Gemini).
  All three were judged same-family in v1.3 — and v1.3's MAE 0.2994 baseline INCLUDES them.
- Proposed fix: flag all three; exclude from calibration until re-judged.
- Decision: (1) All three flagged `judge_family_conflict: true` in data/gold/metadata.json.
  (2) Excluded from the headline calibration MAE until re-judged with a non-Gemini,
  non-Anthropic judge (OpenAI family via OpenRouter — the only family satisfying #20
  for Gemini partners). (3) For ratchet like-for-like comparability with v1.3,
  calibration/runner.py reports BOTH: the headline MAE on the non-conflicted set and a
  shadow MAE on all 26 with per-chat conflict flags visible. (4) ADR-0002's consequence
  section stands; the re-judge path is Stage-2 work.
- Status: RESOLVED

## D-000  [RESOLVED]  — Template / smoke-test entry
- Raised by: Chief Engineer
- Date: setup
- File(s): none
- Problem: Verify the discrepancy flow works end to end.
- Proposed fix: This entry is the example.
- Decision: Flow confirmed. Agents: when you hit a blocker, copy the format block above, fill it in, and keep working on another unblocked task while you wait. Do not block on a single stuck item.
- Status: RESOLVED

## D-002  [OPEN]  — Stage-2 ratchet passes with almost all predictions missing
- Raised by: Codex
- Date: 2026-06-12
- File(s): calibration/runner.py, calibration/run_stage2.py,
  calibration/results/stage2_initial.json, tests/unit/test_calibration.py
- Problem: `stage2_initial.json` reports `ratchet_passed: true` and overall MAE
  0.15, but only four applicable predictions from gc-025 contributed errors.
  Nearly every applicable dimension on the other chats is listed as missing.
  `run_calibration()` excludes absent predictions from MAE but does not require
  complete applicable-prediction coverage before passing the release gate. The
  current shell also has no GEMINI_API_KEY, GOOGLE_API_KEY, or OPENROUTER_API_KEY,
  so the required real-judge rerun cannot currently fill that coverage.
- Proposed fix: Add a coverage gate over every non-null gold target; report
  required, present, missing, and coverage ratio; require zero missing applicable
  predictions for `ratchet_passed`. Add a regression test proving a patchy
  predictor can report MAE without passing. Then rerun all 26 chats with valid
  judge credentials, using the OpenAI-family rejudge path for gc-003, gc-016,
  and gc-018, and replace the invalid Stage-2 report.
- Decision:
- Status: OPEN

## D-003  [OPEN]  — Delivered Stage-1 leaves are not fully wired into Stage 2
- Raised by: Codex
- Date: 2026-06-12
- File(s): src/api/pipeline.py, calibration/run_stage2.py,
  src/trait/judge/client.py
- Problem: `src/api/pipeline.py` still uses optional imports for delivered
  Stage-1 leaves. It invokes the tagger and state/dynamics leaves, but does not
  invoke `classify_phases`, the eight deterministic extractors, or
  `normalize_counts`; the trait profile is built directly from judge output.
  The new `openai_family_judge()` factory also has test callers only, so
  `run_stage2.py` still sends gc-003, gc-016, and gc-018 through the default
  Google-family judge instead of the required OpenAI-family rejudge path. Its
  current model validation rejects Anthropic IDs but does not require an
  OpenAI-family ID; for example, a Google model could be accepted and then
  incorrectly recorded as `judge_family="openai"`.
- Proposed fix: Replace optional leaf loading with hard Stage-2 imports, wire
  tagger -> phase classifier -> deterministic extractors -> normalization into
  the trait evidence path defined by INTERFACES.md, and route Google-partner
  calibration chats through `openai_family_judge()`. Add integration tests that
  fail when a delivered leaf is skipped and assert the three rejudged chats have
  no judge-family conflict. Validate the selected rejudge model as genuinely
  OpenAI-family before assigning OpenAI provenance.
- Codex update (2026-06-12): Audited the deterministic trait leaves against
  `contract_table.yaml` before integration. Corrected PR-02 to detect
  constraint/example/success-criteria markers, PR-05 to compute the
  generative-vs-extractive prompt ratio with its two-prompt applicability gate,
  EC-07 to compute the interrogative sentence ratio, and EC-09 to emit only
  supporting human-turn indices and require a following human opportunity.
  Added regression and evidence-index tests. Trait-focused suite: 78 passed;
  all 26 gold sessions execute through tag -> phase -> extract -> normalize;
  full suite: 333 passed.
- Codex update (2026-06-12, state/dynamics transfer): Audited all six newly
  transferred leaves against INTERFACES.md and brief sections 3.5/3.8. Corrected
  `load_classifier.Z_THRESHOLD` from 1.0 to the required personal-relative
  1.5 standard deviations and added a contract pin. All 26 gold sessions execute
  through state classifiers + transition metrics + regime overlay; state,
  estimator, and dynamics tests: 33 passed; full suite: 334 passed.
- Decision:
- Status: OPEN

---

## Quick reference — when to file here vs just build

| Situation | Action |
|---|---|
| Interface signature is clear, I know what to build | Just build it |
| Interface is ambiguous | File here, ask, build something else meanwhile |
| My test fails because of MY bug | Fix it, don't file |
| My test fails because another module's output is wrong/missing | File here against that module |
| I need a field the schema doesn't have | File here — only CE changes schemas |
| A non-negotiable seems to block me | File here — never quietly violate one |
| I think a contract is wrong | File here — never edit contracts if you're a junior |
