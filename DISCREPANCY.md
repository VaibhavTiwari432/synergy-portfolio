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
