# Deploy Runbook — Scope-C + Extension UI (branch `feat/capture-interception-spine`)

Covers the API + worker + Chrome extension changes through migration 013.
Order matters: **migrate before restarting the app**, and the asyncpg pool caches
prepared statements, so a **restart is mandatory** after any migration.

---

## 0. Pre-flight

- [ ] On the deploy host, `git` at the intended commit of
      `feat/capture-interception-spine`; working tree clean.
- [ ] `python -m alembic heads` → **single head `013`** (no branches).
- [ ] `python -m alembic current` → record the current DB rev (expect `010`–`012`
      depending on environment; migrations 011→013 will apply).
- [ ] Backup the database (011/013 are additive, but 011's downgrade and any
      data deletion are irreversible — back up first).

## 1. Environment variables

| Var | Required | Purpose / note |
|-----|----------|----------------|
| `DATABASE_URL` | yes | Postgres DSN. If unset, defaults to local Docker DSN. |
| `SAF_API_KEY` | yes | API auth. **Unset → all Scope-B/C routes 503** (fail-closed). |
| `GEMINI_API_KEY` / `GOOGLE_API_KEY` | yes (scoring) | Judge model (Gemini — never an Anthropic judge, #20). |
| `OPENAI_API_KEY` | optional | Server-side self-rater (Track 0). Absent → self-rater skips gracefully; never per-user. |
| `OPENROUTER_API_KEY` | optional | Alt model routing if configured. |
| `SELF_RATING_MODEL` | optional | Overrides the self-rating model id. |
| `WORKER_POLL_INTERVAL`, `LEASE_TIMEOUT_SECONDS` | optional | Worker cadence / stuck-lease recovery. |
| `SAF_GIT_SHA` | recommended | Stamped into score provenance (Track 1). |

## 2. Migrations (in order)

```bash
python -m alembic upgrade head          # applies 011 → 012 → 013
```
- **011** — `scores.csl` / `question_quality` / `reliance` JSONB (artifact blobs).
- **012** — `projects`, `project_sessions`, `portfolio_ack` (Scope-C).
- **013** — `user_settings` (auto_analyse / calibration_opt_in).

Verify:
```bash
python -m alembic current               # → 013 (head)
```

## 3. Restart (MANDATORY, after migration)

- [ ] Restart the **API app** — picks up the new routes (projects/sessions/
      portfolio-ack/settings) and clears asyncpg's prepared-statement cache.
- [ ] Restart the **scoring worker** — picks up migration-011 artifact upserts.
- Order: migrate → restart. Restarting before migrating risks "column/table does
  not exist" against the cached statements.

## 4. Extension (WAR + manifest verification)

The modal loads its panel/views/assets via `chrome.runtime.getURL`, which requires
`web_accessible_resources`. Confirm `extension/manifest.json` WAR includes:
- [ ] `panel/panel.html`, `panel/panel.css`
- [ ] `panel/sidebar.js`, `panel/views/*.js`
- [ ] `assets/sangillence_mark.svg`, `icons/icon.png`
- [ ] `background.js` emits `SAF_PROJECTS_API_READY` only after the projects route
      probes 200 (Projects nav stays disabled until `projects.js` imports — D-025).
- [ ] Swap the placeholder logo at `assets/sangillence_mark.svg` if the official
      brand asset is available.
- Load unpacked / repackage; confirm the SW console shows the current build stamp.

## 5. Smoke checks (against the live API + extension)

Run with a valid `X-API-Key`. Replace `{u}` with a test user_ref.

- [ ] **Health** — `GET /v1/health` → 200; `GET /v1/contracts` → versions.
- [ ] **Setup/login** — extension onboarding stores `USER_REF` + endpoint + key;
      health badge goes green.
- [ ] **Chat list** — `GET /v1/users/{u}/chats` → `{chats, summary}`; modal Chats
      view renders rows + counts.
- [ ] **Score load** — analyse a chat (or pre-seed), then `GET .../chats/{id}/score`
      → detail drawer shows 8 dims + CI, four states, no composite.
- [ ] **Projects** — `POST .../projects` (201 + `version`), `GET .../projects`
      (keyset), assign a chat (`POST .../projects/{id}/sessions`), `GET .../projects/{id}`
      radar; `PATCH`/`DELETE` with `If-Match` (stale → 409).
- [ ] **Portfolio** — `GET .../portfolio` → `profile_radar` + `snapshot_hash` + `ack`;
      `POST .../portfolio/ack` with the returned hash (stale hash → 409).
- [ ] **Settings save** — `PATCH .../settings {auto_analyse:true}` → reflected on
      `GET .../settings`; defaults when never set.
- [ ] **Delete user** — `DELETE /v1/users/{u}` → cascades (raw_chats, scores,
      evidence, subjects, projects, project_sessions, portfolio_ack, user_settings);
      re-`GET` shows empty / defaults.

## 6. Rollback

- App/worker: redeploy the prior commit + restart.
- DB: `alembic downgrade 010` reverses 013→012→011 (additive tables/columns drop).
  ⚠️ **Do not** downgrade past 004 (credential purge) — irreversible by design.

## 7. Not-yet-live (carry into release notes)

- S10 settings/profile **views** pending Codex (backend ready).
- Deferred: D-022 (is_minor scoring-path), D-023 (feedback prefill), D-024
  (past/present radar), D-026 (Profile account URL).
