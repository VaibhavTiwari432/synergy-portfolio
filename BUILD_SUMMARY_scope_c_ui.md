# Build Summary — Scope-C + Extension UI (S1–S10)

**Branch:** `feat/capture-interception-spine`
**As of:** 2026-06-20
**Status:** S1–S9 complete and LGTM'd; S10 backend prereqs complete; **S10 views
(settings.js / profile.js) still pending Codex's diff.** Not a complete build yet.

---

## 1. Commit range & summary

Backend (Scope-C contract + extension data path) + the staged extension UI build.
Two authors: `[CE]` (backend / api_client / manifest / directives / reviews) and
`[EXT-UI]` (Codex — DOM-facing views).

| Area | Commits |
|------|---------|
| Artifact persistence (migration 011) | `394a8d3`, `4ff3cf4` |
| Scope-C contract freeze (D-012) | `b48202e` |
| Scope-C backend (migration 012, routers, composite removal) | `7a5d2d0` |
| Directive + api_client wiring (ack, READY emit, feedback/analyse) | `d25ed01`, `64e810b`, `da889eb` |
| S1 modal shell | `b9eb46d`, `426bc81`, `4e8883d` (+ prereq `419e50d`) |
| S2 logo + FAB | `251acef`, `7892f29`, `009fd9e` (+ prereq `419e50d`) |
| S3 sidebar nav | `d2829b3`, `17c31b5`, `38cffd6` (+ prereq `207c848`) |
| S4 chat list | `f139277`, `88ed270`, `c618981` (+ prereq `bdb0184`) |
| S5 detail drawer | `8ad13b7`, `df85d34`, `1e2e4b6` |
| S6 feedback widget | `402d4f4`, `2bfb5f4`, `c4a0d1f` (+ D-023 `aea7d4d`) |
| S7 portfolio | `9433d85`, `968309d`, `696f24f` (+ D-024 `6b488b8`) |
| S8 projects CRUD + assign | `4592959`, `9d76412`, `9ab7916`, `fb4cc00` (+ prereq `925febc`) |
| S9 project detail radar | `fa5faa5`, `1dd824b`, `6d9d18b` |
| S10 backend prereqs (migration 013) | `316119a` (+ D-026 `2a8bcae`) |
| **S10 views (settings/profile)** | **pending Codex** |

---

## 2. What users see, by step

- **S1 — Modal shell.** Centred overlay in a closed Shadow DOM; FAB toggles it;
  Escape + overlay-click close; three-column layout (sidebar · main · drawer).
- **S2 — Logo + FAB.** Sangillence mark (asset via `getURL`) on a 48px FAB;
  amber notification dot; `aria-expanded` toggles.
- **S3 — Sidebar nav.** Chats / Projects / Portfolio / Settings / Profile;
  active-state indigo border; Projects disabled until its view loads (D-025).
- **S4 — Chat list.** Real chat list + summary counts; status dots/badges
  (scored/pending/scoring/failed/unsubmitted); search; current-chat pin by
  `/c/<id>`; Analyse/See/Retry CTAs; 4s polling while scoring.
- **S5 — Detail drawer.** 8 dimension rows with four distinct reporting states
  (scored / N/A / insufficient / saturated) + CI; flags (debt tooltip verbatim);
  trajectory hidden (no per-dim data). No composite.
- **S6 — Feedback.** 👍/👎 + note (≤280) via `submitFeedback`; inline errors;
  submit-only (pre-population deferred, D-023).
- **S7 — Portfolio.** Present-only radar (vanilla SVG, unlabelled axes);
  `<3 sessions` fallback; ack gate; "personal baseline, not a ranking"; past
  shape deferred (D-024).
- **S8 — Projects.** Create (Idempotency-Key + double-tap guard), list (keyset
  paging), update/delete (If-Match 409 inline), assign chats. Per-dim profile.
- **S9 — Project detail radar.** Present-only radar; four-state dimension rows;
  `<3 sessions` fallback; no composite.
- **S10 — Settings + Profile (pending).** Settings: auto-analyse + data opt-in
  toggles (+ verbatim consent copy), notification-dot (local), delete-my-data.
  Profile: read-only username/join/scored-count/streak + placeholder account link.

---

## 3. Deferred tickets (tracked in DISCREPANCY.md)

- **D-022** — `is_minor` defaults False on the live scoring path; minor protection
  (#15) unenforced there. *Rationale:* the field isn't persisted on ingest;
  Scope-C responses are already minor-safe by construction (no bare composite), so
  not a live exposure — fix needs an ingest/migration change.
- **D-023** — Feedback pre-population deferred; S6 is submit-only. *Rationale:* the
  score API returns only `feedback_given: bool`, and feedback is append-per-call
  (a note overwrites `match_rating` to `partial`); clean recall needs a read path
  + a storage-model decision.
- **D-024** — Portfolio past/present radar deferred; S7/S9 are present-only.
  *Rationale:* `getPortfolio`/`getProject` return one per-dim mean; per-dim
  time-windowed past/present needs windowed aggregation + a window definition.
- **D-026** — Profile "manage account" link is a `#` placeholder. *Rationale:* the
  web-app URL doesn't exist yet; built as a disabled "coming soon" affordance,
  one-line swap when live.

---

## 4. Known limitations / placeholders

- **Logo asset** — `extension/assets/sangillence_mark.svg` is a CE-provided
  monochrome placeholder; swap the official brand asset at the same path (no code
  change).
- **Profile account link** — `href="#"`, disabled visual + "coming soon" (D-026).
- **Past-baseline radar** — present-only; second shape lands when the windowed
  endpoint ships (D-024).
- **`auto_analyse`** — stored as a preference; acting on it (auto-scoring) is not
  wired.

---

## 5. Test coverage

- **Backend:** full suite **576 passed** (PHASE1_GATE + live Postgres at
  migration 013). Includes Scope-C projects/sessions/ack (8), settings round-trip
  (1), artifact round-trip + evidence persistence (6), API contract (10).
- **Extension JS:** payload-builder / content / self-rating suites green
  (55–60 depending on set). Per-step gates S1–S9 closed (CE review,
  `node --check` + `git diff --check` each).

---

## 6. What remains

- **Extension:** S10 views (`panel/views/settings.js`, `panel/views/profile.js`)
  + their `sidebar.js` import wiring — pending Codex. Then the S10 gate closes the
  build.
- **Backend:** none for S10 (prereqs complete). Open backend follow-ups are the
  deferred tickets (D-022/023/024) when prioritised.
