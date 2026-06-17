'use strict';

/**
 * background.js — MV3 service worker. OWNER: Chief Engineer.
 *
 * Receives capture snapshots from content.js, builds ingest payloads,
 * calls the saf-brain API, manages the collector bag for retries,
 * and handles all panel ↔ background communication.
 *
 * Ingest is consent-gated (EXTENSION_BUILD_PROMPT.md §3):
 *   - Consent OFF → local-ephemeral; nothing written, no self-rating call.
 *   - API key / OpenAI key never appear in logs or error messages.
 */

importScripts(
  'utils/storage.js',
  'utils/payload_builder.js',
  'utils/api_client.js',
);

/* globals SAFStorage, SAFPayloadBuilder, SAFApiClient */

const SK = SAFStorage.STORAGE_KEYS;
const HEALTH_POLL_ALARM = 'saf_health_poll';
const COLLECTOR_BAG_KEY = 'saf_collector_bag';
const MAX_BAG_SIZE = 50;

// In-memory: tabId → most recent capture snapshot sent by content.js
const _latestCapture = new Map();
const _latestReadyCapture = new Map();
const _analyseProgress = new Map();

// In-memory: conversation_id → last content hash we forwarded to the API.
// Best-effort only — MV3 workers sleep and lose this; the DB content_hash is
// the real guard. Worst case after a wake is one redundant forward that the
// server's idempotent upsert collapses to a no-op. (D-006)
const _lastForwardedHash = new Map();

function _setAnalyseProgress(tabId, patch) {
  if (tabId == null) return null;
  const current = _analyseProgress.get(tabId) || {};
  const next = {
    ...current,
    ...patch,
    active: patch.active ?? current.active ?? true,
    percent: Math.max(0, Math.min(100, Math.round(Number(patch.percent ?? current.percent ?? 0)))),
    updatedAt: Date.now(),
  };
  _analyseProgress.set(tabId, next);
  return next;
}

// ── health polling ────────────────────────────────────────────────────────────

async function _updateHealth() {
  const healthy = await SAFApiClient.checkHealth();
  await SAFStorage.set(SK.HEALTH_STATUS, healthy ? 'ok' : 'error');
  if (healthy) await _flushBag();
}

self.chrome.alarms.create(HEALTH_POLL_ALARM, { periodInMinutes: 1 });
self.chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === HEALTH_POLL_ALARM) _updateHealth().catch(console.warn);
});

// ── collector bag ─────────────────────────────────────────────────────────────

async function _getBag() {
  return (await SAFStorage.get(COLLECTOR_BAG_KEY, [])) || [];
}

async function _addToBag(payload) {
  const bag = await _getBag();
  if (bag.length >= MAX_BAG_SIZE) {
    console.warn('[SAF] collector bag full — oldest item dropped');
    bag.shift();
  }
  bag.push({ payload, queuedAt: Date.now() });
  await SAFStorage.set(COLLECTOR_BAG_KEY, bag);
}

async function _flushBag() {
  const bag = await _getBag();
  if (!bag.length) return;
  const remaining = [];
  for (const item of bag) {
    const result = await SAFApiClient.ingestChat(item.payload);
    if (!result.ok) remaining.push(item);
  }
  await SAFStorage.set(COLLECTOR_BAG_KEY, remaining);
}

// ── badge notification ────────────────────────────────────────────────────────

const DEFAULT_TITLE = 'SAF — AI Collaboration Analyser';

function _setBadge(text, color, title) {
  self.chrome.action.setBadgeText({ text: text || '' }).catch(() => {});
  if (color) {
    self.chrome.action.setBadgeBackgroundColor({ color }).catch(() => {});
  }
  self.chrome.action.setTitle({ title: title || DEFAULT_TITLE }).catch(() => {});
}

function _clearBadge() {
  _setBadge('', null, DEFAULT_TITLE);
}

// Map an ingest failure to a badge + a health verdict. Amber = server is up but
// needs setup (auth/config); red = genuinely unreachable. A missing key must
// never look like a dead server. (D-009) Key value is never read or logged.
function _statusFor(result) {
  switch (result.status) {
    case 401:
      return { badge: '!', color: '#f79009', reachable: true,
               title: 'SAF — Not authorized · check API key in settings' };
    case 403:
      return { badge: '!', color: '#f79009', reachable: true,
               title: 'SAF — Forbidden · consent or key issue' };
    case 422:
      return { badge: '!', color: '#f79009', reachable: true,
               title: 'SAF — Capture incomplete · reload ChatGPT and try again' };
    case 503:
      return { badge: '!', color: '#f79009', reachable: true,
               title: 'SAF — API not configured · SAF_API_KEY missing on server' };
    case 0:
    case undefined:
      return { badge: '!', color: '#f04438', reachable: false,
               title: 'SAF — API unreachable · turns queued' };
    default:
      return { badge: '!', color: '#f04438', reachable: false,
               title: `SAF — API error ${result.status} · turns queued` };
  }
}

// Cheap, stable content hash (djb2 over role|text + turn count). Only needs to
// be deterministic for dedupe, not cryptographic.
function _hashCapture(capture) {
  const turns = (capture && capture.turns) || [];
  let h = 5381;
  for (const t of turns) {
    const s = `${t.role}${t.text || ''}`;
    for (let i = 0; i < s.length; i++) h = ((h << 5) + h + s.charCodeAt(i)) | 0;
  }
  return `${h >>> 0}:${turns.length}`;
}

function _badgeForChat(chat, capture) {
  if (chat.status === 'scored') {
    _setBadge('✓', '#12b76a', 'SAF — Chat score ready · open panel to view');
  } else if (chat.status === 'failed') {
    _setBadge('!', '#f04438', 'SAF — Scoring failed · re-analyse to retry');
  } else {
    const n = (capture && capture.turns ? capture.turns.length : 0);
    _setBadge('…', '#1a6fa0', `SAF — ${n} turns saved · analysing…`);
  }
}

function _captureHasTurns(capture) {
  return Array.isArray(capture?.turns) && capture.turns.length > 0;
}

function _captureValidationError(capture) {
  const turns = Array.isArray(capture?.turns) ? capture.turns : [];
  if (!turns.length) return 'capture has no turns';

  const counts = { user: 0, assistant: 0 };
  for (const turn of turns) {
    const role = String(turn?.role || '').toLowerCase();
    const text = String(turn?.text || '').trim();
    if (!text) continue;
    if (role === 'user' || role === 'human') counts.user += 1;
    else if (role === 'assistant' || role === 'ai') counts.assistant += 1;
    else return `unsupported turn role: ${role || '<empty>'}`;
  }

  if (counts.user === 0) return 'capture has no user turns';
  if (counts.assistant === 0) return 'capture has no assistant turns';
  if (Math.abs(counts.user - counts.assistant) > 1) {
    return `capture turn roles are imbalanced (user=${counts.user}, assistant=${counts.assistant})`;
  }
  return null;
}

async function _findChat(userRef, conversationId) {
  const res = await SAFApiClient.listChats(userRef);
  if (!res.ok) return null;
  return (res.data?.chats || []).find((c) => c.conversation_id === conversationId) || null;
}

// ── ingest ────────────────────────────────────────────────────────────────────

/**
 * Resolve a capture to a persisted chat. Returns a structured outcome so callers
 * (push path AND analyse-now) can react precisely — never a silent return.
 *   { ok: true,  data: { chatId, status, conversationId }, noop? }
 *   { ok: false, skipped: 'consent_off' | 'no_user', message }
 *   { ok: false, error, message }                       (build/API failure)
 */
async function _handleCaptureReady(capture) {
  const invalid = _captureValidationError(capture);
  if (invalid) {
    return { ok: false, error: 'capture_invalid',
             message: `Capture incomplete — ${invalid}. Try Analyse now again after the page finishes scanning.` };
  }

  // ADR-0007: a PROVEN-incomplete interception (capture_complete === false) is
  // quarantined before the network call — the server would 422 it anyway. null
  // (unknown: scroll-probe / dom-live fallback) is NOT blocked here; it defers to
  // the server's role-balance gate.
  if (capture && capture.capture_complete === false) {
    const exp = capture.expected_turn_count;
    const got = capture.captured_turn_count;
    const counts = (exp != null && got != null) ? ` (captured ${got} of ${exp} turns)` : '';
    return { ok: false, error: 'capture_incomplete',
             message: `Capture incomplete${counts} — reload ChatGPT and try Analyse now again.` };
  }

  const consent = await SAFStorage.get(SK.CONSENT_ENABLED, false);
  if (!consent) {
    // Consent OFF: local-ephemeral, nothing written (#3 spec) — but say so (D-007).
    return { ok: false, skipped: 'consent_off',
             message: 'Capture is off — enable consent in settings to analyse.' };
  }

  const userRef = await SAFStorage.get(SK.USER_REF);
  if (!userRef) {
    return { ok: false, skipped: 'no_user',
             message: 'Not signed in — complete setup in the panel first.' };
  }

  let payload;
  try {
    payload = SAFPayloadBuilder.buildIngestPayload({
      ...capture,
      user_ref: userRef,
      // Track 0: the OpenAI key is NO LONGER sent to the server. Self-rating
      // uses a server-side OPENAI_API_KEY env secret; per-user keys must never
      // enter the corpus at rest (credential-at-rest / DPDP).
      metadata: { ...(capture.metadata || {}) },
    });
  } catch (err) {
    console.warn('[SAF] payload build failed:', err.message);
    return { ok: false, error: 'payload_build_failed',
             message: 'Could not read the conversation — try again.' };
  }

  const convId = payload.conversation_id;
  const hash = _hashCapture(capture);

  // Nothing new since we last forwarded this conversation: don't re-ingest
  // (no redundant judge call), but still resolve the existing chat_id so the
  // panel can poll/show it. (D-006)
  if (_lastForwardedHash.get(convId) === hash) {
    const existing = await _findChat(userRef, convId);
    if (existing) {
      _badgeForChat(existing, capture);
      return { ok: true, noop: true,
               data: { chatId: existing.chat_id, status: existing.status, conversationId: convId } };
    }
    // hash map stale (worker slept / data cleared) → fall through and ingest
  }

  const result = await SAFApiClient.ingestChat(payload);
  if (!result.ok) {
    const s = _statusFor(result);
    if (result.status !== 422) await _addToBag(payload);
    await SAFStorage.set(SK.HEALTH_STATUS, s.reachable ? 'ok' : 'error');
    _setBadge(s.badge, s.color, s.title);
    return {
      ok: false,
      error: result.error,
      message: result.status === 422 && result.detail
        ? result.detail.replace(/^invalid capture:\s*/i, '')
        : s.title.replace(/^SAF — /, ''),
    };
  }

  _lastForwardedHash.set(convId, hash);
  await SAFStorage.set(SK.HEALTH_STATUS, 'ok');
  const turnCount = (capture.turns || []).length;
  _setBadge('…', '#1a6fa0', `SAF — ${turnCount} turns saved · analysing…`);
  return { ok: true,
           data: { chatId: result.data.chat_id, status: result.data.status, conversationId: convId } };
}

// ── message router ────────────────────────────────────────────────────────────

self.chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (!message || typeof message.type !== 'string') return undefined;

  // ── content.js push messages ──────────────────────────────────────────────
  if (message.type === 'SAF_CAPTURE_UPDATED') {
    if (sender.tab?.id != null) _latestCapture.set(sender.tab.id, message.capture);
    return undefined; // no response
  }

  if (message.type === 'SAF_ANALYSE_PROGRESS') {
    const tabId = sender.tab?.id;
    if (tabId != null) {
      const progress = message.progress || {};
      if (progress.capture) _latestCapture.set(tabId, progress.capture);
      _setAnalyseProgress(tabId, {
        stage: progress.stage || 'capturing',
        percent: progress.percent ?? 0,
        message: progress.message || 'Capturing chat...',
        capturedTurns: progress.captured_turns || progress.capture?.turns?.length || 0,
        conversationId: progress.capture?.conversation_id || null,
      });
    }
    return undefined;
  }

  if (message.type === 'SAF_CAPTURE_READY') {
    if (sender.tab?.id != null) _latestCapture.set(sender.tab.id, message.capture);
    if (sender.tab?.id != null && !_captureValidationError(message.capture)) {
      _latestReadyCapture.set(sender.tab.id, message.capture);
    }
    _handleCaptureReady(message.capture).catch(console.warn);
    return undefined; // no response
  }

  // ── panel messages (all async; return true to keep sendResponse open) ─────
  function respond(promise) {
    promise
      .then((data) => sendResponse({ ok: true, data }))
      .catch((err) => sendResponse({
        ok: false,
        error: String(err.message || err),
        // user-facing copy when the thrower set one (D-007/D-009 surfacing)
        message: err.userMessage || undefined,
      }));
    return true;
  }

  switch (message.type) {

    case 'SAF_PANEL_GET_STATUS': {
      return respond((async () => {
        const vals = await SAFStorage.getMany([
          SK.USER_REF,
          SK.API_ENDPOINT,
          SK.CONSENT_ENABLED,
          SK.HEALTH_STATUS,
          SK.ONBOARDING_COMPLETE,
        ]);

        // Most recent capture (any tab); panel uses conversation_id to poll score
        let latestCapture = null;
        for (const [, cap] of _latestCapture) latestCapture = cap;

        let analysisProgress = null;
        for (const [, progress] of _analyseProgress) analysisProgress = progress;

        // Panel is open — clear the "analysing" badge
        _clearBadge();

        return {
          userRef: vals[SK.USER_REF] || null,
          apiEndpoint: vals[SK.API_ENDPOINT] || SAFApiClient.DEFAULT_ENDPOINT,
          consent: Boolean(vals[SK.CONSENT_ENABLED]),
          health: vals[SK.HEALTH_STATUS] || 'unknown',
          onboardingComplete: Boolean(vals[SK.ONBOARDING_COMPLETE]),
          latestCapture,
          analysisProgress,
          bagSize: (await _getBag()).length,
        };
      })());
    }

    case 'SAF_PANEL_ANALYSE_NOW': {
      return respond((async () => {
        // panel.js passes tabId queried from popup context (reliable); fall back to window query
        let tabId = message.tabId || sender.tab?.id;
        if (!tabId) {
          const [tab] = await self.chrome.tabs.query({ active: true, lastFocusedWindow: true });
          tabId = tab?.id;
        }
        if (!tabId) {
          const e = new Error('no_active_tab');
          e.userMessage = 'Open ChatGPT in a tab, then try again.';
          throw e;
        }
        _setAnalyseProgress(tabId, {
          stage: 'capturing',
          percent: 3,
          message: 'Starting chat capture...',
          capturedTurns: 0,
        });

        let reply = null;
        let sendError = null;
        try {
          reply = await new Promise((resolve, reject) => {
            self.chrome.tabs.sendMessage(tabId, { type: 'SAF_ANALYSE_NOW' }, (res) => {
              const err = self.chrome.runtime.lastError;
              if (err) reject(new Error(err.message || 'send_failed'));
              else resolve(res);
            });
          });
        } catch (err) {
          sendError = err;
        }

        const fallbackCapture = _latestReadyCapture.get(tabId);
        const capture =
          _captureHasTurns(reply?.capture) ? reply.capture
            : _captureHasTurns(fallbackCapture) ? fallbackCapture
              : null;

        // D-010: honour the content script's own ok/capture — do not assume success.
        if (!capture || (reply && reply.ok !== true && !_captureHasTurns(reply.capture))) {
          const e = new Error(sendError?.message || 'nothing_captured');
          e.userMessage = 'No conversation captured yet — start chatting first.';
          _setAnalyseProgress(tabId, {
            active: false,
            stage: 'error',
            percent: 100,
            message: e.userMessage,
          });
          throw e;
        }

        const invalid = _captureValidationError(capture);
        if (invalid) {
          const e = new Error('capture_invalid');
          e.userMessage = `Capture incomplete — ${invalid}. Try Analyse now again after the page finishes scanning.`;
          _setAnalyseProgress(tabId, {
            active: false,
            stage: 'error',
            percent: 100,
            message: e.userMessage,
            capturedTurns: capture.turns?.length || 0,
            conversationId: capture.conversation_id || null,
          });
          throw e;
        }

        // D-008: ingest now and hand the chat_id back so the panel can poll the
        // real score instead of spinning forever at 90%.
        _setAnalyseProgress(tabId, {
          stage: 'ingesting',
          percent: 82,
          message: `Chat captured: ${capture.turns?.length || 0} turns. Sending to scorer...`,
          capturedTurns: capture.turns?.length || 0,
          conversationId: capture.conversation_id || null,
        });
        const outcome = await _handleCaptureReady(capture);
        if (!outcome.ok) {
          const e = new Error(outcome.skipped || outcome.error || 'ingest_failed');
          e.userMessage = outcome.message;
          _setAnalyseProgress(tabId, {
            active: false,
            stage: 'error',
            percent: 100,
            message: e.userMessage,
            capturedTurns: capture.turns?.length || 0,
            conversationId: capture.conversation_id || null,
          });
          throw e;
        }
        _setAnalyseProgress(tabId, {
          active: outcome.data?.status !== 'scored',
          stage: outcome.data?.status === 'scored' ? 'complete' : 'scoring',
          percent: outcome.data?.status === 'scored' ? 100 : 90,
          message: outcome.data?.status === 'scored' ? 'Score ready.' : 'Scoring in progress...',
          capturedTurns: capture.turns?.length || 0,
          chatId: outcome.data?.chatId || null,
          conversationId: outcome.data?.conversationId || capture.conversation_id || null,
        });
        return outcome.data; // { chatId, status, conversationId }
      })());
    }

    case 'SAF_PANEL_GET_SCORE': {
      const { userRef, chatId } = message;
      return respond(
        SAFApiClient.getScore(userRef, chatId).then((r) => {
          if (!r.ok) throw new Error(r.error);
          return r.data;
        }),
      );
    }

    case 'SAF_PANEL_GET_PORTFOLIO': {
      return respond(
        SAFApiClient.getPortfolio(message.userRef).then((r) => {
          if (!r.ok) throw new Error(r.error);
          return r.data;
        }),
      );
    }

    case 'SAF_PANEL_LIST_CHATS': {
      return respond(
        SAFApiClient.listChats(message.userRef).then((r) => {
          if (!r.ok) throw new Error(r.error);
          return r.data;
        }),
      );
    }

    case 'SAF_PANEL_POST_FEEDBACK': {
      const { userRef, chatId, body } = message;
      return respond(
        SAFApiClient.postFeedback(userRef, chatId, body).then((r) => {
          if (!r.ok) throw new Error(r.error);
          return r.data;
        }),
      );
    }

    case 'SAF_PANEL_SAVE_SETTINGS': {
      return respond((async () => {
        const updates = {};
        const { userRef, apiEndpoint, apiKey, openaiApiKey, consent } = message;
        if (userRef !== undefined) updates[SK.USER_REF] = userRef;
        if (apiEndpoint !== undefined) updates[SK.API_ENDPOINT] = apiEndpoint;
        // Keys stored raw but never echoed back or logged
        if (apiKey !== undefined) updates[SK.API_KEY] = apiKey;
        if (openaiApiKey !== undefined) updates[SK.OPENAI_API_KEY] = openaiApiKey;
        if (consent !== undefined) updates[SK.CONSENT_ENABLED] = Boolean(consent);
        if (Object.keys(updates).length) await SAFStorage.set(updates);
        await _updateHealth(); // reflect new endpoint immediately
        return { saved: true };
      })());
    }

    case 'SAF_PANEL_ONBOARDING_COMPLETE': {
      return respond((async () => {
        await SAFStorage.set(SK.ONBOARDING_COMPLETE, true);
        return { done: true };
      })());
    }

    case 'SAF_PANEL_DELETE_DATA': {
      return respond((async () => {
        const result = await SAFApiClient.deleteUser(message.userRef);
        if (!result.ok) throw new Error(result.error);
        await SAFStorage.remove([SK.USER_REF, SK.ONBOARDING_COMPLETE]);
        _latestCapture.clear();
        _latestReadyCapture.clear();
        return result.data;
      })());
    }

    default:
      return undefined;
  }
});

// Initial health check when service worker starts
_updateHealth().catch(console.warn);
