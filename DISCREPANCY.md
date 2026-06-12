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
