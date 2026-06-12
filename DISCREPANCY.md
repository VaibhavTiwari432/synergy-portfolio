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

## D-002  [RESOLVED]  — Stage-2 ratchet passes with almost all predictions missing
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
- Decision: ACCEPTED with one calibration of the threshold. The runner must treat
  a missing prediction as an error, not a skip: any chat with judge_unavailable
  = true OR fewer than 4 dimensions returning valid scores is EXCLUDED from the
  MAE and counted in a separate coverage metric printed alongside MAE
  (n_scored, n_excluded, coverage_pct). Gate A is now: MAE ≤ 0.2994 AND
  coverage_pct ≥ 80% of the headline pool — a run with low coverage cannot pass
  regardless of its MAE number (zero-missing stays the goal; 80% is the hard
  floor so one flaky judge call cannot block a release while a near-empty run
  can never pass). Implemented in calibration/runner.py with the regression
  test Codex proposed; Gate A definition updated in TEAM.md Stage 2. The
  invalid stage2_initial.json is superseded by the full re-run.
- Status: RESOLVED

## D-003  [RESOLVED]  — Delivered Stage-1 leaves are not fully wired into Stage 2
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
- Decision: NO SCOPE CHANGE — both halves are already on the Stage-2 board.
  (1) Hard-wiring the leaves (phases, extractors, normalize into the trait
  evidence path) is Stage-2 item 1; the optional-import pattern was the
  Stage-1 bridge and dies there. (2) The OpenAI re-judge routing for
  gc-003/016/018 is Stage-2 item 3, using openai_family_judge() with the
  model-family validation tightened to REQUIRE an "openai/" prefix (not merely
  reject Anthropic ids) before OpenAI provenance is assigned. Both land before
  Gate A is evaluated. Codex's two audit updates above are verified by CE
  (see commit log) and stand as delivered.
- Status: RESOLVED

## D-004  [RESOLVED]  — Live Stage-2 calibration fails the ES per-dimension gate
- Raised by: Codex
- Date: 2026-06-12
- File(s): calibration/results/stage2_initial.json,
  calibration/results/stage2_predictions_cache.json, src/trait/judge/prompt.py
- Problem: The credentialed post-D-003 run scored all 26 chats with no judge
  failures and 100% coverage. Shadow overall MAE is 0.2771, below the 0.2994
  ratchet, but Gate A fails because ES MAE is 0.4600, above the 0.375
  per-dimension ceiling. ES has only five applicable gold targets. The largest
  errors are gc-004 (target 0.25, prediction 1.00) and gc-023 (target 0.25,
  prediction 1.00); together they contribute 1.50 of the total 2.30 ES absolute
  error. The other ES rows are gc-010 (0.55 -> 0.90), gc-027 (0.80 -> 1.00),
  and gc-028 (0.25 -> 0.00). Full suite after the run: 344 passed.
- Proposed fix: Chief Engineer should inspect the ES prompt anchors and evidence
  interpretation for saturation at 1.00, especially on gc-004 and gc-023,
  without changing frozen gold targets merely to pass the gate. Add focused
  judge-prompt regression fixtures for low-ES chats, then re-judge the five
  ES-applicable chats and rerun the calibration report. The required OpenAI
  family re-judge for gc-003/016/018 remains separate and still needs an
  OPENROUTER_API_KEY.
- Decision: CONFIRMED — same diagnosis reached independently by CE: v2.0 gave ES
  a definition but no graded anchors, so the judge collapsed to topic salience
  with a binary scale ("ethics content present ≠ ethics behavior demonstrated").
  Fix shipped as judge prompt v2.1: ES calibration anchors in the v1.3-EC-anchor
  style (0.80 / 0.25 pinned to gold band centers; >0.9 reserved for multiple
  distinct safeguarding behaviors), with prompt regression pins in
  tests/unit/test_judge.py. Full rationale: adr/0005-judge-prompt-v2.1-es-anchors.md
  (read it before touching the ES prompt again). Gold targets unchanged. A FULL
  26-chat re-run under v2.1 (not just the five ES chats — one prompt version per
  report) replaces stage2_initial.json; v2.0 results preserved at
  calibration/results/stage2_prompt_v2.0.json. OpenRouter key tracked as D-005.
- Status: RESOLVED

## D-005  [RESOLVED]  — OPENROUTER_API_KEY missing: gc-003/016/018 re-judge blocked
- Raised by: Chief Engineer
- Date: 2026-06-12
- File(s): calibration/run_stage2.py (--rejudge-conflicts), src/trait/judge/client.py
  (openai_family_judge), data/gold/metadata.json (judge_family_conflicts)
- Problem: The only remaining hard Stage-2 item besides the v2.1 confirm is
  re-judging the three Gemini-partner gold chats (gc-003, gc-016, gc-018) with
  an OpenAI-family judge via OpenRouter (D-001; non-negotiable #20). The code
  path is built, tested, and routed (`python -m calibration.run_stage2
  --rejudge-conflicts --only gc-003 gc-016 gc-018`), but no OPENROUTER_API_KEY
  exists in the environment or .env. Until then the headline pool stays n=23.
- Proposed fix: Human provides an OpenRouter key (gitignored .env,
  OPENROUTER_API_KEY=...). The re-judge is a 3-chat, <5-minute run.
- Decision: Stage 2 may close on the n=23 headline + n=26 shadow numbers with
  this item explicitly deferred and visible (to be recorded in ADR-0006). The
  re-judge run is the FIRST action when the key lands; nothing else blocks on it.
- Resolution (2026-06-12, key landed): the provided OpenRouter key carries zero
  credits (402 on paid models), so the default openai/gpt-4o-mini was unusable.
  Re-judged all three with **openai/gpt-oss-120b:free** (open-weight OpenAI
  model on OpenRouter — passes the openai/ prefix guard, satisfies
  non-negotiable #20: family=openai ≠ partner family=google). All three scored
  clean: judge_family_conflict=false, judge_unavailable=false. Metadata
  conflicts list cleared (history preserved in the note + D-001); headline pool
  restored to n=26. Full-corpus report: MAE 0.2505, coverage 100%,
  ratchet_passed=true (`calibration/results/stage2_rejudged.json`). Note: the
  free-tier model is a weaker judge than gpt-4o-mini; if credits land later, a
  one-command re-run upgrades the three judgments (SAF_REJUDGE_MODEL env var).
- Status: RESOLVED

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
