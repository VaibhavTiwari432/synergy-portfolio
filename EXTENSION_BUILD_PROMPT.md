# Extension Build Prompt — Database-Centric Architecture
**For Claude Code. Read entirely before writing any file.**
**All CLAUDE.md non-negotiables remain binding. All contracts/ schemas remain frozen.**
**K-12 / minor protection stays as a dormant structural guard — not a build focus.**

---

## 0. Architecture shift from the earlier brief

The extension is no longer a direct API caller. The database is the
intermediary for everything. The flow is:

```
BROWSER EXTENSION
  ↓ (1) history import on first login + live capture of new chats
POSTGRES DATABASE  ←──────────────────────────────────────────┐
  ↓ (2) raw chats + telemetry + metadata written here          │
SCORING WORKER (background process)                            │
  ↓ (3) polls DB for unscored chats, calls Chat Analyser API   │
CHAT ANALYSER API (existing src/api/)                         │
  ↓ (4) scores the chat, returns full ScoreResponse            │
POSTGRES DATABASE  (5) scores + model self-rating + feedback   │
  ↓ written back here ──────────────────────────────────────────┘
BROWSER EXTENSION
  (6) polls for updated scores → renders portfolio
```

The extension writes to the DB. The worker reads from DB, scores,
writes back. The extension reads results from DB. The API never
receives raw payloads from the extension directly — the DB is the
single source of truth.

---

## 1. Database schema (Postgres, Docker local)

### Setup
Docker compose file at `infra/docker-compose.yml`:
```yaml
services:
  db:
    image: postgres:16
    environment:
      POSTGRES_DB: saf_brain
      POSTGRES_USER: saf
      POSTGRES_PASSWORD: saf_local
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
volumes:
  pgdata:
```

### Four core tables (exactly what the project lead specified)

```sql
-- 1. Raw transcripts
CREATE TABLE raw_chats (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_ref        TEXT NOT NULL,
    conversation_id TEXT NOT NULL,          -- from ChatGPT URL /c/{id}
    source          TEXT NOT NULL,          -- 'chatgpt_history' | 'chatgpt_live'
    partner_model   JSONB NOT NULL,         -- PartnerModel schema
    turns           JSONB NOT NULL,         -- [{role, text, timestamp_ms, turn_index}]
    turn_count      INTEGER NOT NULL,
    captured_at     TIMESTAMPTZ DEFAULT NOW(),
    status          TEXT DEFAULT 'pending', -- 'pending'|'scoring'|'scored'|'failed'
    UNIQUE(user_ref, conversation_id)
);

-- 2. Telemetry + metadata
CREATE TABLE telemetry (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chat_id         UUID NOT NULL REFERENCES raw_chats(id) ON DELETE CASCADE,
    dwell_ms        INTEGER[],              -- per-turn dwell times
    copy_events     INTEGER[],              -- per-turn copy counts
    edit_detected   BOOLEAN[],             -- per-turn edit flags
    selector_health TEXT,                  -- 'ok'|'selector_miss'|'stream_incomplete'
    capture_mode    TEXT NOT NULL,         -- 'history_import'|'live_capture'
    imported_at     TIMESTAMPTZ DEFAULT NOW(),
    metadata        JSONB DEFAULT '{}'     -- conversation title, URL, any extras
);

-- 3. ARI scores + model self-rating
CREATE TABLE scores (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chat_id             UUID NOT NULL REFERENCES raw_chats(id) ON DELETE CASCADE,
    scored_at           TIMESTAMPTZ DEFAULT NOW(),
    prompt_version      TEXT NOT NULL,     -- e.g. 'v2.1' — which judge prompt
    tier                INTEGER NOT NULL,  -- 1 or 2
    profile             JSONB NOT NULL,    -- 8-dim scores with CI + n_eff + rung
    composite           JSONB,             -- value, gates_passed, caveat, rung
    state_strip         JSONB,             -- per-turn state labels
    state_validity      JSONB,
    flags               JSONB,             -- fluent_incompetence, debt_flag etc.
    reaction_signatures JSONB,             -- FTM + 5 transition metrics
    regime_overlay      JSONB,             -- occupancy + strip
    sustainability      JSONB,             -- s_human_hat, debt_ewma, lambda
    report              JSONB,             -- observed[], inferred[], hypothesized[]
    -- Model self-rating (the AI partner rates the human's ARI performance)
    self_rating_raw     JSONB,             -- raw model output, never shown to user
    self_rating_prompt_version TEXT,       -- which self-rating prompt was used
    self_rating_at      TIMESTAMPTZ,       -- when the model rated
    self_rating_status  TEXT DEFAULT 'pending', -- 'pending'|'received'|'skipped'
    UNIQUE(chat_id)
);

-- 4. User feedback (after portfolio updates with scores)
CREATE TABLE feedback (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chat_id         UUID NOT NULL REFERENCES raw_chats(id) ON DELETE CASCADE,
    user_ref        TEXT NOT NULL,
    match_rating    TEXT NOT NULL,         -- 'yes'|'partial'|'no'
    comment         TEXT,                  -- max 280 chars, optional
    scores_snapshot JSONB NOT NULL,        -- the score state at time of feedback
    submitted_at    TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_raw_chats_user_ref ON raw_chats(user_ref);
CREATE INDEX idx_raw_chats_status ON raw_chats(status);
CREATE INDEX idx_raw_chats_captured_at ON raw_chats(captured_at);
CREATE INDEX idx_scores_chat_id ON scores(chat_id);
CREATE INDEX idx_feedback_user_ref ON feedback(user_ref);
```

### Cascade deletion (GDPR/DPDP right to erasure)
The `ON DELETE CASCADE` on all child tables means:
`DELETE FROM raw_chats WHERE user_ref = $1` removes everything —
telemetry, scores, self-ratings, feedback. One delete, full propagation.
The existing `DELETE /v1/users/{user_ref}` endpoint uses this.
Write an explicit test: insert a full row set, delete by user_ref,
verify all four tables are empty for that user_ref.

---

## 2. Scoring worker

New file: `src/worker/scorer.py`

```python
# Pseudocode — implement exactly this logic

async def run():
    while True:
        # Claim a batch of pending chats (atomic — prevent double-scoring)
        chats = await db.fetch("""
            UPDATE raw_chats SET status='scoring'
            WHERE id IN (
                SELECT id FROM raw_chats
                WHERE status='pending'
                ORDER BY captured_at ASC
                LIMIT 5
            )
            RETURNING *
        """)

        for chat in chats:
            try:
                # Build CanonicalSession from stored turns + partner_model
                session = build_canonical_session(chat)

                # Call the existing pipeline (not the HTTP API — import directly)
                result = await score_session(session)

                # Write scores back to DB
                await db.execute("""
                    INSERT INTO scores (chat_id, ...) VALUES (...)
                    ON CONFLICT (chat_id) DO UPDATE SET ...
                """)
                await db.execute(
                    "UPDATE raw_chats SET status='scored' WHERE id=$1", chat.id
                )

                # Trigger model self-rating (async, non-blocking)
                asyncio.create_task(request_self_rating(chat.id))

            except Exception as e:
                await db.execute(
                    "UPDATE raw_chats SET status='failed' WHERE id=$1", chat.id
                )
                log.error(f"Scoring failed for {chat.id}: {e}")

        await asyncio.sleep(3)  # poll interval, configurable
```

**Critical:** the worker calls `score_session()` by importing the pipeline
directly — NOT via HTTP. This avoids a network hop for local testing and
keeps the worker and API as siblings, not client/server to each other.

New entry point: `python -m src.worker.scorer`
Add to README run instructions.

---

## 3. Model self-rating

New file: `src/worker/self_rater.py`

**The prompt sent to the user's ChatGPT model** (stored in
`contracts/self_rating_prompt.txt` — versioned separately):

```
You participated in the following conversation as the AI assistant.
Rate the HUMAN participant's collaborative behavior on these 8 dimensions,
each on a scale of 0.0 to 1.0.

Dimensions:
AL (AI Literacy): Does the human understand what AI can and cannot do?
PR (Prompt Reasoning): Does the human engineer prompts or just chat?
EC (Error Correction): Does the human verify and challenge your outputs?
ES (Ethics Sensitivity): Does the human show awareness of ethical implications?
CS (Contextual Synthesis): Does the human integrate your outputs with their own thinking?
CD (Creative Divergence): Does the human push beyond your suggestions?
AUI (Augmentation Instinct): Does the human use AI to extend capability, not replace effort?
CA (Collaborative Agency): Does the human maintain their own direction and judgment?

Return ONLY valid JSON in this exact format, no other text:
{
  "AL": 0.0, "PR": 0.0, "EC": 0.0, "ES": 0.0,
  "CS": 0.0, "CD": 0.0, "AUI": 0.0, "CA": 0.0,
  "confidence": 0.0,
  "evidence_notes": "one sentence"
}

[CONVERSATION TRANSCRIPT]
{transcript}
```

**Handling rules (non-negotiable #10):**
- Store as `self_rating_raw` — NEVER shown to the user in any form
- Provenance tag: `annotation_source: "partner_self_rating"`
- Dawid–Skene correction happens at corpus analysis time, not here
- If the model returns malformed JSON: store null, set status='skipped'
- This is a side-channel call — uses the user's own OpenAI API key
  stored in the extension settings. If no key: skip silently.
- For bulk imports: batch these calls with a 1-second delay between
  them. Do not fire 50 self-rating calls simultaneously.

---

## 4. Browser extension

### Repo layout
```
extension/
├── manifest.json
├── background.js
├── content.js              ← DOM observer (ChatGPT)
├── panel/
│   ├── panel.html
│   ├── panel.js
│   └── panel.css
└── utils/
    ├── payload_builder.js
    ├── storage.js          ← chrome.storage.local wrapper
    ├── api_client.js       ← calls localhost API endpoints
    └── self_rating_prompt.js
```

### manifest.json
```json
{
  "manifest_version": 3,
  "name": "SAF — AI Collaboration Analyser",
  "version": "0.1.0",
  "permissions": ["storage", "activeTab", "scripting"],
  "host_permissions": [
    "https://chat.openai.com/*",
    "http://localhost/*"
  ],
  "content_scripts": [{
    "matches": ["https://chat.openai.com/*"],
    "js": ["content.js"],
    "run_at": "document_idle"
  }],
  "background": { "service_worker": "background.js" },
  "action": { "default_popup": "panel/panel.html" }
}
```

---

## 5. First-login onboarding flow (the most important UX moment)

**When:** the first time the extension popup opens on chat.openai.com.
**Trigger:** `onboarding_complete` not set in chrome.storage.local.

**Step 1 — Welcome screen:**
```
"SAF analyses how you collaborate with AI — not what you asked,
but how you worked together. Your conversations stay local and
are only shared if you choose to."

[Get Started]
```

**Step 2 — Chat selection (the core of what you specified):**

A full-panel dropdown/list appears showing the user's conversation
history scraped from the ChatGPT sidebar.

**DOM scraping for history:**
- Target: the sidebar conversation list on chat.openai.com
- Primary selector: `nav [data-testid="history-item"]`
- Fallback: `nav ol li a`, `nav .relative.group`
- Extract: conversation title + conversation_id from href (/c/{id})
- Fallback if DOM unavailable: show manual export upload option

**The selection UI:**
```
┌─────────────────────────────────────────────────────┐
│  Select chats to analyse                            │
│  ─────────────────────────────────────────────────  │
│  [✓ Select all]  or choose individually             │
│                                                     │
│  ✓  Python debugging session     · 3 days ago       │
│  ✓  Research paper outline       · 1 week ago       │
│  ✓  Marketing strategy           · 1 week ago       │
│  ✓  Code review discussion       · 2 weeks ago      │
│  □  Personal journal entry       · 3 weeks ago      │
│     (deselected by user)                            │
│  ✓  Job interview prep           · 1 month ago      │
│                                                     │
│  [Load more ↓]                                      │
│  ─────────────────────────────────────────────────  │
│  23 chats selected · [Deselect all]                 │
│  [Upload selected chats →]                          │
└─────────────────────────────────────────────────────┘
```

**Behaviour:**
- Default: ALL chats pre-ticked with checkmarks
- User can deselect individual chats or use "Deselect all"
- "Load more" paginates the history list (scroll or button)
- The user must be aware: show a note below the list:
  "Selected chats will be stored locally and analysed.
   Only you can see the results."
- On "Upload selected chats →": scrape the full transcript for each
  selected conversation, write to DB as `status: 'pending'`,
  show a progress bar ("Uploading 23 chats..."), then hand off to
  the scoring worker.
- Set `onboarding_complete: true` in chrome.storage.local after upload.

---

## 6. Live capture (every new chat, automatically)

After onboarding, `content.js` observes every new conversation.

**Turn capture:**
- MutationObserver on the conversation container
- Human turn: capture on submit
- AI turn: capture on stream completion (stop-button disappears OR
  1500ms of no DOM mutation — whichever first). NEVER mid-stream.
- Each turn: `{ role, text, timestamp_ms, turn_index }`
- Telemetry: `dwell_ms`, `copy_events`, `edit_detected`

**New chat detection:**
- 3 completed turn-pairs (3 human + 3 AI turns) triggers automatic upload
- When triggered: POST to `/v1/ingest` (new endpoint — see §7)
- Panel shows a subtle notification: "3 new turns saved — analysing..."
- Notification disappears after 4 seconds. Non-blocking.

**Selector strategy (defensive):**
```javascript
const SELECTORS = {
  userTurn: [
    '[data-message-author-role="user"]',
    'article[data-testid^="conversation-turn-"] .user',
    '.group.w-full .whitespace-pre-wrap'
  ],
  aiTurn: [
    '[data-message-author-role="assistant"]',
    'article[data-testid^="conversation-turn-"] .assistant',
    '.group.w-full .markdown'
  ],
  stopButton: ['button[aria-label="Stop generating"]',
               'button[data-testid="stop-button"]'],
  modelSelector: [
    '[data-testid="model-switcher-dropdown-button"]',
    'button[aria-label*="model"]'
  ],
  historyItems: [
    'nav [data-testid="history-item"]',
    'nav ol li a',
    'nav .relative.group a'
  ]
}
// Try each in order; log warning and degrade gracefully on all-miss
```

**Partner model detection:**
- Read model selector text → map to PartnerModel
- `family` is ALWAYS `"openai"` on chat.openai.com — hardcoded guard
- `era_key`: YYYY-MM of capture date

---

## 7. API additions (add to src/api/)

### POST /v1/ingest
Receives raw chat from extension. Writes to DB. Returns immediately.
Scoring happens asynchronously via the worker.
```
body: {
  user_ref: str,
  conversation_id: str,
  source: "chatgpt_history" | "chatgpt_live",
  partner_model: PartnerModel,
  turns: [TurnPayload],
  telemetry?: { dwell_ms[], copy_events[], edit_detected[] },
  metadata?: { title, url }
}
→ { chat_id, status: "pending", message: "queued for scoring" }
```
Idempotent on conversation_id + user_ref (upsert, not duplicate).

### GET /v1/users/{user_ref}/chats
Returns all chats for a user with their scoring status.
```
→ {
    chats: [{
      chat_id, conversation_id, title, captured_at,
      status: "pending"|"scoring"|"scored"|"failed",
      turn_count, source
    }],
    summary: { total, scored, pending, failed }
  }
```

### GET /v1/users/{user_ref}/chats/{chat_id}/score
Returns the full score for one chat.
```
→ ScoreResponse (existing schema) + {
    self_rating_status: "pending"|"received"|"skipped",
    feedback_given: boolean
  }
```

### POST /v1/users/{user_ref}/chats/{chat_id}/feedback
```
body: { match_rating: "yes"|"partial"|"no", comment?: str }
→ { received: true }
```
Stores with scores_snapshot (the current score state at submission time).
Non-blocking from the extension — fire and forget.

### GET /v1/users/{user_ref}/portfolio
```
→ {
    profile_radar: { AL, PR, EC, ES, CS, CD, AUI, CA },  // means across scored chats
    archetype: "Verifier"|"Explorer"|"Synthesizer"|"Scaffolder"|"Balanced",
    trajectory: { sessions[], trend_direction, uncertainty_band },
                  // INSUFFICIENT_HISTORY if < 3 scored chats
    growth_summary: { strongest_dim, growing_dim, watch_dim },
    sessions_analysed: int,
    first_analysed_at: datetime
  }
```

### PATCH /v1/sessions/{id}/turns (keep from earlier)
For live capture appending new turns mid-conversation.

### DELETE /v1/users/{user_ref}
Existing endpoint — verify cascade deletion covers all 4 new tables.
Test explicitly.

---

## 8. Panel UI

### Main view (after onboarding, after at least 1 scored chat)

**Three sections — positive first, always:**

**Section 1 — WHAT WORKED**
Top 2 items from `report.observed` across recent scored chats.
Plain sentences. No scores, no dimension names, no jargon.
> "You pushed back on the model's first answer — that's the habit
>  that separates strong AI collaborators."

**Section 2 — ONE THING TO BUILD**
One sentence from `report.inferred[0]`. Framed as a next action.
Never a deficit label. Never a dimension name.
> "Before your next task, try writing your constraint first —
>  it shifts the conversation from extractive to generative."

**Section 3 — SESSION AT A GLANCE**
- Regime bar: stacked horizontal, hover for percentages
  (generative=teal, verification=blue, extractive=amber,
   drift=grey, accept_run=coral)
- Flag pills (amber, only if triggered):
  [accept run detected] [debt flag] [state compromised]
- Health dot: green=ok, amber=selector issues, red=api/key error

**Controls:**
- [Analyse now] — manual trigger for current conversation
- [See full analysis] toggle — reveals 8-dim radar (SVG, no lib)
  Label: "Research data — not a performance score."
  CI bars on hover. Dimension abbreviations only.
  **No composite number anywhere in the panel, ever.**

### Pending state (chats uploaded, scoring in progress)
```
┌──────────────────────────────────┐
│  ⏳ Analysing your chats         │
│  ████████░░░░░░ 12 / 23 scored  │
│  Results update automatically.  │
└──────────────────────────────────┘
```
Poll `GET /v1/users/{user_ref}/chats` every 5 seconds.
Update the progress bar in place. No page refresh.

### New chat notification (live capture)
Subtle banner at top of panel, auto-dismisses in 4 seconds:
"3 new turns saved — analysing..."
Not a modal. Not blocking. Not alarming.

### Portfolio view (separate panel view, icon in nav)
- Collaboration Profile radar (reuse SVG component)
- Growth trajectory: Past→Present→Trend (vanilla SVG line chart)
  Personal baseline only. No peer comparison. Ever.
- Archetype label with one-sentence description
- Sessions analysed count + first analysis date
- If < 3 scored chats: "Analyse more conversations to see your
  growth trend" — not an empty chart

### Feedback prompt (appears after portfolio updates with new score)
Shown once per chat_id, after `status` transitions to 'scored':
```
"Does this match your experience with that conversation?"
[Yes, that's right] [Partially] [Not really]
```
On Partially/No: text field appears: "What did we miss?" (280 chars max)
[Submit] — fires POST /v1/.../feedback, then disappears.
If API call fails: drop silently. Never retry a feedback call.

### Settings (gear icon)
- API endpoint (default: http://localhost:8000)
- API key
- OpenAI API key (for self-rating calls — optional, labelled clearly:
  "Used only to ask ChatGPT to rate your collaboration style.
   Optional. Never used for any other purpose.")
- Anonymous ID (auto-generated, editable, shown in full)
- Consent toggle: "Share conversations to improve scoring"
  OFF by default. Clear explanation of what ON means.
- [Clear all my data] — calls DELETE /v1/users/{user_ref},
  then clears chrome.storage.local. Confirm dialog. Non-reversible.

---

## 9. Build sequence (phases, gated)

### Phase 1 — DB + worker + ingest endpoint
- `infra/docker-compose.yml` + DB schema migration (use Alembic)
- `src/worker/scorer.py` (polling worker, direct pipeline import)
- `src/worker/self_rater.py` (async, batched, skippable)
- `POST /v1/ingest` + `GET /v1/users/{user_ref}/chats`
- Cascade deletion test (all 4 tables)

**Gate:** insert 3 raw chats via ingest endpoint, run worker manually,
verify all 3 reach `status='scored'` with full scores in the scores table.

### Phase 2 — Extension core (manifest, content.js, background.js)
- manifest.json
- content.js: MutationObserver, turn capture, telemetry, partner detection
- background.js: session management, ingest calls, health tracking
- utils/: payload_builder, storage, api_client
- First-login onboarding: welcome screen + chat selection UI

**Gate:** load unpacked extension on chat.openai.com. Have a 10-turn
real conversation. Verify turns captured correctly, ingest called,
chat appears in DB as pending, worker scores it.

### Phase 3 — Panel UI
- panel.html / panel.js / panel.css
- Three sections (positive first)
- Pending progress bar (polling)
- [Analyse now] + [See full analysis] toggle + radar SVG
- Settings view

**Gate:** after Phase 2 gate conversation is scored, open panel.
Verify Section 1 has text, regime bar renders, no forbidden words,
no composite number visible, radar appears under toggle.

### Phase 4 — Portfolio + feedback + collector bag
- Portfolio view (radar + trajectory + archetype)
- Feedback prompt (post-score, once per chat)
- Collector bag: add-to-bag, bag count badge, bulk push
- Self-rating (if OpenAI key present in settings)
- New chat notification ("3 new turns saved")

**Gate:** analyse 3+ conversations. Portfolio shows trajectory.
Feedback prompt appears after each new score. Bag accumulates and
flushes correctly. Clear-my-data removes everything.

---

## 10. Non-negotiables (all CLAUDE.md §8 rules — key reminders for this build)

- No composite number anywhere in the panel. Not even under the toggle.
- "synergy", "surrender", "dependent", "decline" never in panel text.
- Section 1 (strengths) always renders before Section 2 (growth nudge).
- self_rating_raw never shown to user in any form.
- Consent OFF = local-ephemeral: score and show, nothing written to
  the collection dataset, no self-rating call, no feedback stored.
- API key and OpenAI key never in code, logs, or error messages.
- The collector bag never loses turns silently — buffer and retry.
- partner_model.family is hardcoded "openai" for chat.openai.com.
- Minor protection guard stays structurally in panel.js (dormant).
- Cascade deletion is tested explicitly, not assumed.
- Self-rating is a side-channel call — never in the user's active chat.
- Bulk self-rating: 1-second delay between calls, never fire all at once.

---

## 11. Commit format

[EXT-P1] <file>: what + test/gate result
[EXT-P2] <file>: what
[EXT-P3] <file>: what
[EXT-P4] <file>: what
[API] <file>: what + test count
[DB] <file>: what

---

*Start with Phase 1. DB schema first, then worker, then ingest endpoint.
Report back after Phase 1 gate passes.*
