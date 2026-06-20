# AGENT_UD.md — Browser Extension UI Build
## Codex (Junior Dev A) Task Directive

**Issued by:** CE (Vaibhav)
**Review partner:** Claude (technical review)
**Scope:** `extension/` directory — Codex-owned leaf files only
**Authority boundary:** Codex owns DOM-facing and UI files. CE owns backend, schema, API routes, `background.js`, and `manifest.json`. Do NOT cross the boundary.
**Coordination files in effect:** CLAUDE.md (21 non-negotiables), TEAM.md, this document
**Status of this directive:** ACTIVE — supersedes all prior extension UI instructions

> **REWORK cover note (CE, 2026-06-20).** The prior `injected_icon.js`
> consolidation (1803 lines) is **rejected per the REWORK verdict**. S1 starts
> fresh against the §11 file split. Do not carry forward the monolithic
> structure — `injected_icon.js` is the FAB + modal host + overlay only; sidebar
> and views live in `panel/sidebar.js` and `panel/views/*.js` as §11 specifies.

---

## 0. Read This First — Non-Negotiables Before Any Code

These rules apply to every line Codex writes in this build. Violations are not acceptable at diff review.

1. **No single composite score ever rendered.** The UI shows per-dimension bars with CI. Never a total, never a percentage rank, never the word "synergy."
2. **CI is mandatory on every score emission.** Render as `0.72 ±.08`. If the API returns no CI, show `±?` and log a console warning — do not silently drop it.
3. **Four reporting states, never collapsed.** `STRUCTURAL_NA` · `INSUFFICIENT_SAMPLE` · `MEASUREMENT_SATURATED` · scored. Each maps to a distinct visual. Never merge any two.
4. **Claim language is enforced in copy.** Permitted: "collaboration quality", "process pattern", "dimension profile". Forbidden: "synergy", "cognitive debt proven", "score of X/100", any ranking vs other users.
5. **No `position: fixed` inside the shadow DOM modal.** The modal is `position: fixed` at the `injected_icon.js` level (root document), but nothing *inside* the modal uses `position: fixed`. Use flex/grid for internal layout.
6. **Trajectory is past→present→trend only.** Never render a projection or prediction. The trend arrow is a directional indicator with uncertainty, not a forecast.
7. **`background.js` and `manifest.json` are CE files.** Codex must not touch them. If a UI feature requires a message to background, Codex writes the `chrome.runtime.sendMessage()` call in the content/panel file and CE wires the receiver.
8. **Three logical commits per unit of work.** Structure: (1) markup/HTML, (2) styles, (3) JS/logic. Never squash. Commit messages use the format `[EXT-UI] <step>: <what changed>`.
9. **Every diff to CE before merge.** No autonomous merges. Post the diff in the coordination channel and wait for explicit "LGTM" from CE.
10. **Logo usage is governed by §2 of this document.** Do not improvise with the Sangillence logo. Follow the spec exactly.

---

## 1. What You Are Building — Full Feature Map

The browser extension currently has a floating circular button (`#saf-fab`) that opens a small bottom-right panel. You are replacing that with a **centred, full-featured modal overlay** that is the primary user interface for the entire SAF extension experience.

The modal has three columns: **Sidebar · Main Panel · Detail Drawer**.

### 1.1 Feature inventory by build step

| Step | What | Files owned by Codex | Depends on |
|------|------|----------------------|------------|
| S1 | Modal shell — replace bottom-right panel with centred overlay | `injected_icon.js`, `panel/panel.html`, `panel/panel.css` | Nothing — CSS only |
| S2 | Sangillence logo + FAB redesign | `injected_icon.js`, `panel/panel.css` | §2 of this doc |
| S3 | Sidebar nav — Portfolio · Projects · Chats · Settings · Profile | `panel/panel.html`, `panel/sidebar.js`, `panel/panel.css` | S1 |
| S4 | Chat list — search, status badges, Analyse/See CTAs | `panel/views/chats.js`, `panel/panel.css` | S1, existing API |
| S5 | Detail drawer — dimension bars + CI + flags + remarks | `panel/views/detail.js`, `panel/panel.css` | S4, existing score API |
| S6 | Remarks / feedback widget | `panel/views/detail.js` | S5, existing feedback API |
| S7 | Portfolio view — trajectory radar, past→present→trend | `panel/views/portfolio.js`, `panel/panel.css` | S3, existing portfolio API |
| S8 | Projects view — list, create, assign chats | `panel/views/projects.js`, `panel/panel.css` | S3, **CE must ship projects API first** |
| S9 | Project detail — combined radar, strength/weakness cards | `panel/views/project_detail.js` | S8 |
| S10 | Settings / Profile views | `panel/views/settings.js`, `panel/views/profile.js` | S3 |

**Steps S1–S7 are unblocked today.** S8–S9 are blocked until CE ships the `projects` and `project_chats` tables and `/v1/users/{user}/projects` API. Do not stub S8/S9 with fake data — leave the sidebar item visible but disabled with a "Coming soon" tooltip until CE signals the API is live.

---

## 2. The Sangillence Logo — Exact Usage Specification

### 2.1 What the logo is

Sangillence has a wordmark and a logomark. For the browser extension, you will use the **logomark only** — the abstract mark, not the full wordmark text. The mark is an SVG.

Since the actual asset file lives at `extension/assets/sangillence_mark.svg`, reference it from there. **Do not hardcode the SVG inline** in `injected_icon.js` — reference the asset path via `chrome.runtime.getURL('assets/sangillence_mark.svg')` and set it as the `src` of an `<img>` tag inside the FAB, or as a CSS `mask-image`.

### 2.2 The Floating Action Button (FAB) — exact spec

The FAB is the entry point. It sits fixed in the bottom-right of chatgpt.com pages.

```
Position:     fixed, bottom: 24px, right: 24px
Shape:        circle, 48px × 48px
Background:   #0D1117 (near-black — works on ChatGPT's white and dark themes)
Border:       1.5px solid rgba(255,255,255,0.12)
Border-radius: 50%
Box-shadow:   0 2px 12px rgba(0,0,0,0.35)
Logo inside:  Sangillence mark, white version, 24px × 24px, centred
Hover state:  background #1A2232, box-shadow 0 4px 20px rgba(0,0,0,0.45), scale(1.05)
Active state: scale(0.97)
Transition:   all 150ms ease
z-index:      2147483647 (top of stack)
```

The FAB must NOT have any text label. The logo alone is the identifier.

When the user has an **unscored chat** that is ready to analyse, add a notification dot:
```
Dot:          8px circle, background #F59E0B (amber), border 2px solid #0D1117
Position:     absolute, top: 2px, right: 2px
```

When the modal is open, the FAB gets an `aria-expanded="true"` attribute and the dot hides.

### 2.3 Logo inside the modal header

The modal header (top of the sidebar column) shows the Sangillence mark at 20px × 20px in white, followed by the text `SAF` in 13px, weight 500, color #E2E8F0. This is the only place the `SAF` text label appears near the logo.

Do not show the full "Sangillence" wordmark anywhere in the extension UI. The product name in copy is `SAF` (short form) or `Sangillence Assessment Framework` (full form, settings page only).

### 2.4 Logo colour rules

| Context | Mark colour |
|---------|-------------|
| FAB on any background | White (`#FFFFFF`) |
| Modal header (dark sidebar) | White (`#FFFFFF`) |
| If a light sidebar variant is ever added | Dark (`#0D1117`) |

Never use the logo in any colour other than white or near-black. Never apply opacity to the logo itself — adjust the container background instead.

---

## 3. The Modal Shell — Exact Layout Specification

### 3.1 Overlay

```css
#saf-modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.55);
  backdrop-filter: blur(2px);
  z-index: 2147483646;
  display: flex;
  align-items: center;
  justify-content: center;
}
```

Clicking the overlay outside the modal closes it (add `mousedown` listener on the overlay, check `event.target === overlay`).

### 3.2 Modal container

```css
#saf-modal {
  width: 860px;
  max-width: calc(100vw - 48px);
  height: 580px;
  max-height: calc(100vh - 48px);
  background: #0F172A;
  border-radius: 14px;
  border: 1px solid rgba(255,255,255,0.08);
  box-shadow: 0 24px 80px rgba(0,0,0,0.6);
  display: grid;
  grid-template-columns: 180px 1fr 260px;
  overflow: hidden;
}
```

### 3.3 Three-column structure

**Column A — Sidebar** (`180px`, background `#080E1A`, right border `1px solid rgba(255,255,255,0.06)`)

```
[Sangillence mark 20px + "SAF" text]    ← header, 48px tall
─────────────────────────────────────
[ ≡ Chats ]                             ← active by default
[ ⊞ Projects ]                          ← disabled until CE API ships
[ ◉ Portfolio ]
────────────────────────── (spacer flex-1)
[ ⚙ Settings ]
[ ○ Profile ]
```

Active nav item: `background: rgba(255,255,255,0.07)`, left border `2px solid #6366F1` (indigo accent), text `#E2E8F0`.
Inactive: text `#64748B`, no background.
Hover: `background: rgba(255,255,255,0.04)`, text `#94A3B8`.

**Column B — Main Panel** (`flex: 1`, background `#0F172A`, padding `16px`)

Content is view-dependent. See §4 (Chats view), §5 (Portfolio view), §7 (Projects view).

**Column C — Detail Drawer** (`260px`, background `#0A111E`, left border `1px solid rgba(255,255,255,0.06)`, padding `14px`)

Content renders the selected chat's score profile. See §6. When nothing is selected, show the empty state: Sangillence mark in dim white at 32px centre, text "Select a chat to see its profile" in `#334155`, 13px.

### 3.4 Open/close animation

```css
#saf-modal-overlay {
  opacity: 0;
  transition: opacity 180ms ease;
}
#saf-modal-overlay.saf-open {
  opacity: 1;
}
#saf-modal {
  transform: scale(0.96) translateY(8px);
  transition: transform 200ms cubic-bezier(0.34, 1.56, 0.64, 1);
}
#saf-modal-overlay.saf-open #saf-modal {
  transform: scale(1) translateY(0);
}
```

Add the `saf-open` class on the next animation frame after insertion (to trigger the transition). On close: remove `saf-open`, wait for the transition to finish (`transitionend`), then remove the overlay from the DOM.

### 3.5 Close button

Top-right of the modal, `20px × 20px`, `×` symbol in `#475569`, hover `#E2E8F0`. Positioned absolutely inside the modal header row. Keyboard: `Escape` key closes the modal.

---

## 4. Chats View — Main Panel (Column B)

This is the default view when the modal opens.

### 4.1 Header row

```
"Your chats"  [13px, weight 500, #E2E8F0]        "3 scored · 2 pending"  [11px, #475569]
```

### 4.2 Search input

Full-width, 36px tall, `background: #1E293B`, `border: 1px solid rgba(255,255,255,0.08)`, `border-radius: 8px`, placeholder "Search chats…" in `#334155`, `font-size: 13px`, `color: #E2E8F0`. On input, filter the chat list client-side by title substring match (case-insensitive).

### 4.3 Current chat section

Label `"Current chat"` in 11px `#475569` above the row.

The current chat is the one whose URL matches `window.location.href` when the modal opens. Detect the conversation ID from the URL path (`/c/<id>`). If there is no active conversation, this section is hidden.

### 4.4 Chat row component

```html
<div class="saf-chat-row" data-chat-id="<id>" data-status="<status>">
  <div class="saf-chat-icon"><!-- status dot --></div>
  <span class="saf-chat-title">Chat title here</span>
  <span class="saf-badge saf-badge--<status>"><status label></span>
  <button class="saf-cta">Analyse</button>  <!-- or "See" -->
</div>
```

**Status dot** (8px circle, left of title):
- `scored` → `#22C55E` (green)
- `pending` / `scoring` → `#F59E0B` (amber), pulse animation
- `failed` → `#EF4444` (red)
- `unsubmitted` (not yet sent to backend) → `#475569` (grey)

**Status badge** (pill, right of title):
- `scored` → background `rgba(34,197,94,0.12)`, text `#4ADE80`, border `rgba(34,197,94,0.2)`
- `pending` → background `rgba(245,158,11,0.12)`, text `#FCD34D`, border `rgba(245,158,11,0.2)`
- `scoring` → background `rgba(99,102,241,0.12)`, text `#A5B4FC`, border `rgba(99,102,241,0.2)` + spinner
- `failed` → background `rgba(239,68,68,0.12)`, text `#FCA5A5`, border `rgba(239,68,68,0.2)`

**CTA button:**
- Status `scored` → button label `See`, style: outline, `border: 1px solid rgba(255,255,255,0.1)`, text `#94A3B8`
- Status `pending` or `unsubmitted` → button label `Analyse`, style: filled, `background: #4F46E5`, text `#E0E7FF`
- Status `scoring` → button label `Scoring…`, disabled, opacity 0.5
- Status `failed` → button label `Retry`, style: outline red

**Click behaviour:**
- `See` → load this chat's score into the Detail Drawer (Column C); mark the row as selected (`border-left: 2px solid #6366F1`)
- `Analyse` → call `api_client.js` `triggerAnalysis(chatId)`, immediately switch badge to `scoring`, start polling for completion
- `Retry` → same as `Analyse`

**Title truncation:** `max-width: 180px`, `white-space: nowrap`, `overflow: hidden`, `text-overflow: ellipsis`.

### 4.5 Data loading

On modal open, call `api_client.js` `getChatList(userId)`. This returns an array of `{ chat_id, title, status, updated_at }`. Sort descending by `updated_at`. The current chat (if any) is pinned at top.

Poll for status updates every 4 seconds while any chat has status `scoring`. Stop polling when the modal closes.

If the API call fails, show a non-blocking inline error: `"Could not load chats. Retry."` with a retry button. Do not show an alert or block the modal.

---

## 5. Detail Drawer — Column C

Renders the score profile for the selected chat.

### 5.1 Header

```
Chat title (truncated to 1 line, 13px weight 500, #E2E8F0)
Jun 18 · 24 turns  (11px, #334155)
```

### 5.2 Dimension profile section

Label `"Collaboration profile"` in 11px `#475569`.

For each of the 8 ARI dimensions (AL, PR, EC, ES, CS, CD, AUI, CA), render one row:

```
[dim code 28px]  [bar background]  [score value]  [±CI]
```

Bar:
- Background: `#1E293B`, height `5px`, border-radius `3px`, full width
- Fill: width = `score × 100%`, colour mapped as:
  - `score ≥ 0.65` → `#22C55E` (green)
  - `0.40 ≤ score < 0.65` → `#F59E0B` (amber)
  - `score < 0.40` → `#EF4444` (red)
  - State `STRUCTURAL_NA` → grey bar with `N/A` label, no score
  - State `INSUFFICIENT_SAMPLE` → grey bar with `—` label, no score
  - State `MEASUREMENT_SATURATED` → full-width bar with pattern fill + `≥ max` label

Score value: `12px`, `#E2E8F0`, weight 500
CI: `10px`, `#334155` (e.g. `±.08`)

**NEVER render a total or average across the 8 dimensions.** There is no row for "Overall". This is enforced by the claims charter.

### 5.3 Reporting states — four, never collapsed

```js
const STATE_RENDERERS = {
  scored:               renderScoreBar,      // bar + value + CI
  STRUCTURAL_NA:        renderNA,            // grey bar, "N/A", no CI
  INSUFFICIENT_SAMPLE:  renderInsufficient,  // grey bar, "—", tooltip: "Too few turns"
  MEASUREMENT_SATURATED: renderSaturated,    // patterned bar, "≥ max", amber border
};
```

Each renderer is a separate function. Never use an `if/else if` chain that shares rendering logic between states. If the API returns an unknown state string, log a console error and render as `STRUCTURAL_NA` with a tooltip "Unknown state".

### 5.4 Trajectory section

Label `"Trend"` in 11px `#475569`.

Show three small dots connected by a line for each dimension: `past • present • trend`. Use the trajectory data from the API response (`{ past: float, present: float, trend_direction: 'up'|'down'|'flat', confidence: float }`).

- Dot colours follow the same green/amber/red score scale
- Arrow between present and trend: `↑` green if `up`, `↓` red if `down`, `→` grey if `flat`
- If `confidence < 0.6`, apply `opacity: 0.5` to the trend dot and arrow, add tooltip "Low confidence — more chats needed"
- If no trajectory data, hide the section entirely (not enough sessions)

### 5.5 Flags section

Label `"Flags"` in 11px `#475569`.

Render as pills. Flags are returned by the score API. Known flags and their colours:

| Flag | Label | Colour |
|------|-------|--------|
| `skilled_outsourcer` | Delegation gap | `#F59E0B` amber |
| `fluent_incompetence` | Fluency risk | `#EF4444` red |
| `verifier` | Active verifier | `#22C55E` green |
| `ec_gap` | EC gap | `#F59E0B` amber |
| `cognitive_debt_flag` | Debt flagged* | `#F59E0B` amber |

*"Debt flagged" pill must have a tooltip: "Pattern detected — not proven without retention probe." This is a framework requirement, not optional copy.

Unknown flags: render in grey with the raw flag string. Do not suppress unknown flags.

### 5.6 Remarks section

Label `"Remarks"` in 11px `#475569`.

A `<textarea>` (non-editable, readonly) showing the AI-generated narrative remark from the score response. `background: #1E293B`, `border: 1px solid rgba(255,255,255,0.06)`, `border-radius: 6px`, `font-size: 12px`, `color: #94A3B8`, `padding: 8px`, min-height `64px`, no resize.

Below the textarea:

```
[👍 Agree]   [👎 Dispute]   [+ Note]
```

- **Agree** / **Dispute** → calls `api_client.js` `submitFeedback(chatId, { type: 'thumb', value: 1 or -1 })`. Button turns highlighted after click. Deselects the other.
- **+ Note** → expands a small text input (max 280 chars) with a `Submit` button. Calls `submitFeedback(chatId, { type: 'note', text: '...' })`.

One thumb vote per chat per session. If the API returns existing feedback, pre-select the correct thumb and show the note if present.

---

## 6. Portfolio View

Activated by clicking `Portfolio` in the sidebar.

### 6.1 Layout

Full-width in Column B. Column C shows the portfolio-level radar.

**Column B content:**

Header: `"Your collaboration profile"` (14px, weight 500, `#E2E8F0`)
Sub-header: `"Personal baseline — your trend, not a ranking"` (12px, `#475569`)

Below: a list of the user's projects (once S8 is built) and a `"Recent chats"` list showing the last 10 scored chats, each with a mini score bar.

**Column C content (portfolio radar):**

A spider/radar chart showing the user's personal baseline across 8 dimensions. Use Canvas or SVG — no external chart library. The radar has:
- 8 axes, one per ARI dimension (AL, PR, EC, ES, CS, CD, AUI, CA)
- Two overlaid shapes: `past` (dashed, `rgba(100,116,139,0.4)`) and `present` (solid, `rgba(99,102,241,0.6)`)
- Dimension labels at 12px `#64748B`
- A small legend: `— Past` / `— Present`

**No score values are labelled on the radar axes.** The shape is the signal. Users who want exact values see the Detail Drawer per-chat.

Data: call `api_client.js` `getPortfolio(userId)`. Response: `{ dimensions: { AL: {past, present, ci}, ... }, sessions_count, trend_direction }`.

If `sessions_count < 3`, show: `"Score a few more chats to see your trend"` instead of the radar.

---

## 7. Projects View (Disabled Until CE API Ships)

Sidebar item renders as:
```
[ ⊞ Projects ]   [SOON]
```

The `[SOON]` badge is `background: rgba(99,102,241,0.15)`, text `#818CF8`, `font-size: 10px`, `border-radius: 4px`, `padding: 2px 5px`.

Clicking it shows a tooltip: `"Projects require a backend update — coming soon."` Do not navigate to a broken view.

When CE sends the message `SAF_PROJECTS_API_READY` via `chrome.runtime.sendMessage`, the view is unlocked. Listen for this message in `sidebar.js`:

```js
chrome.runtime.onMessage.addListener((msg) => {
  if (msg.type === 'SAF_PROJECTS_API_READY') {
    unlockProjectsNav();
  }
});
```

The full projects build (S8/S9) is specified in a separate directive CE will issue when the API is ready.

---

## 8. Settings + Profile Views

Both are simple forms accessible from the sidebar bottom items.

### 8.1 Settings

| Setting | Control | API action |
|---------|---------|------------|
| Auto-analyse new chats | Toggle | `PATCH /settings { auto_analyse: bool }` |
| Show notification dot | Toggle | Local storage only |
| Data opt-in (feeds calibration pool) | Toggle | `PATCH /settings { calibration_opt_in: bool }` |
| Delete my data | Button (destructive) | Confirm dialog → `DELETE /users/{id}/data` |

The data opt-in toggle must have this copy below it (non-negotiable, framework-required):
> *"Anonymised session data may be used to improve the SAF scoring models. No personally identifiable information is shared. You can withdraw at any time."*

### 8.2 Profile

Shows: username, join date, total scored chats, current streak (days with ≥1 scored chat). Read-only display. No editing in the extension — redirect to the platform web app for account changes.

---

## 9. API Client Contract

Codex calls `extension/utils/api_client.js`. These are the functions Codex is authorised to call. Do not make `fetch()` calls directly from view files — always go through `api_client.js`.

```js
// Chat operations
getChatList(userId)                           // GET /v1/users/{uid}/chats
getChatScore(userId, chatId)                  // GET /v1/users/{uid}/chats/{cid}/score
triggerAnalysis(chatId)                       // POST /v1/ingest/analyse-now
submitFeedback(chatId, { type, value, text }) // POST /v1/users/{uid}/chats/{cid}/feedback

// Portfolio
getPortfolio(userId)                          // GET /v1/users/{uid}/portfolio
acknowledgePortfolio(userId, snapshotHash)    // POST /v1/users/{uid}/portfolio/ack

// Settings
getSettings(userId)                           // GET /v1/users/{uid}/settings
updateSettings(userId, patch)                 // PATCH /v1/users/{uid}/settings
```

If a function is missing from `api_client.js`, do NOT add it yourself — flag it to CE and wait. CE owns `api_client.js` additions that touch backend routes.

### 9.1 Error handling contract

Every API call from a view file must handle three states:

```js
try {
  const data = await api.getChatScore(userId, chatId);
  renderScore(data);
} catch (err) {
  if (err.status === 401) renderAuthError();        // "Please re-login"
  else if (err.status === 404) renderNotFound();    // "Chat not found"
  else if (err.status === 422) renderGateError();   // "Chat could not be scored"
  else renderGenericError(err.message);             // show message, offer retry
}
```

Never `console.error` alone as a response to an API failure visible to the user. Always show an inline UI error state.

---

## 10. CSS Architecture

All styles live in `panel/panel.css`. Do not use inline styles except for dynamic values (bar widths, colours driven by score values). Do not use a CSS framework or import external stylesheets.

Use CSS custom properties for the design tokens:

```css
:root {
  --saf-bg-base:      #0F172A;
  --saf-bg-sidebar:   #080E1A;
  --saf-bg-drawer:    #0A111E;
  --saf-bg-elevated:  #1E293B;
  --saf-border:       rgba(255,255,255,0.06);
  --saf-border-hover: rgba(255,255,255,0.12);
  --saf-text-primary: #E2E8F0;
  --saf-text-muted:   #94A3B8;
  --saf-text-dim:     #475569;
  --saf-text-faint:   #334155;
  --saf-accent:       #6366F1;
  --saf-accent-light: rgba(99,102,241,0.15);
  --saf-green:        #22C55E;
  --saf-amber:        #F59E0B;
  --saf-red:          #EF4444;
  --saf-radius-sm:    6px;
  --saf-radius-md:    8px;
  --saf-radius-lg:    12px;
}
```

The modal renders inside a Shadow DOM (to avoid ChatGPT's styles leaking in). Codex must inject the modal into a shadow root:

```js
const host = document.createElement('div');
host.id = 'saf-modal-host';
document.body.appendChild(host);
const shadow = host.attachShadow({ mode: 'closed' });
// inject overlay + modal HTML into shadow
// inject <link rel="stylesheet" href="...panel.css"> into shadow
```

`injected_icon.js` is already in the page (not shadow DOM) — only the modal content goes into the shadow root.

---

## 11. File Ownership Summary

```
extension/
├── injected_icon.js          ← CODEX (FAB, modal host, overlay)
├── content.js                ← CODEX (DOM capture, scroll probe)
├── background.js             ← CE ONLY — do not touch
├── manifest.json             ← CE ONLY — do not touch
├── assets/
│   └── sangillence_mark.svg  ← CE provides asset, Codex references only
├── utils/
│   └── api_client.js         ← CE owns additions, Codex calls existing functions only
└── panel/
    ├── panel.html            ← CODEX
    ├── panel.css             ← CODEX
    ├── sidebar.js            ← CODEX
    └── views/
        ├── chats.js          ← CODEX
        ├── detail.js         ← CODEX
        ├── portfolio.js      ← CODEX
        ├── projects.js       ← CODEX (stub/locked until CE API)
        ├── project_detail.js ← CODEX (stub/locked until CE API)
        ├── settings.js       ← CODEX
        └── profile.js        ← CODEX
```

---

## 12. Commit Protocol

Each build step (S1 through S10) produces exactly **three commits**:

```
Commit 1: [EXT-UI] S<n> markup: <description>
Commit 2: [EXT-UI] S<n> styles: <description>
Commit 3: [EXT-UI] S<n> logic: <description>
```

After each step's three commits, Codex posts the diff to CE for review. CE returns one of:
- **LGTM** → proceed to next step
- **REWORK: <reason>** → fix before proceeding, no autonomous override
- **BLOCKED: <reason>** → CE will resolve the blocker

Do not open a PR. Do not merge. Coordinate through the diff review protocol only.

---

## 13. Acceptance Criteria Checklist

Codex self-checks this list before posting any diff:

- [ ] No single composite score rendered anywhere
- [ ] CI shown on every scored dimension (`±.xx` or `±?` if missing from API)
- [ ] Four reporting states render as four distinct visuals — verified with a test fixture
- [ ] "Synergy", "cognitive debt proven", "score of N/100" strings absent from all copy
- [ ] Debt flag pill has the mandatory tooltip copy
- [ ] `background.js` and `manifest.json` untouched (run `git diff --name-only` and confirm)
- [ ] Modal closes on `Escape` key and on overlay click
- [ ] FAB notification dot shows when unscored chats exist; hides when modal is open
- [ ] Projects nav item is disabled with tooltip; no broken view accessible
- [ ] All API calls go through `api_client.js` — no bare `fetch()` in view files
- [ ] Logo loaded via `chrome.runtime.getURL()` — not inline SVG, not hardcoded URL
- [ ] Shadow DOM used for modal content
- [ ] Three commits per step, correct format
- [ ] Diff posted to CE before any merge

---

## 14. What Codex Must NOT Do

- Touch `background.js`, `manifest.json`, or any Python/Hono backend file
- Add API routes or modify `api_client.js` beyond calling existing functions
- Render a number labelled as a total, composite, or overall score
- Use the word "synergy" or "cognitive debt proven" in any user-visible copy
- Import external JS libraries (no lodash, no chart.js, no React) — vanilla JS only
- Use `localStorage` or `sessionStorage` for any score or user data — data lives in the backend
- Make autonomous architecture decisions — surface all forks to CE
- Merge without explicit LGTM from CE

---

*End of AGENT_UD.md — Codex reads this before writing the first line of code.*
*CE issues amendments as separate commit. This document is versioned at v1.0.*
