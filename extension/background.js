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

// SELF-CONTAINED WORKER (build 0.2.0): the three utility modules are INLINED here
// rather than pulled in with importScripts(). On some Chrome builds a service-worker
// UPDATE fails to fetch importScripts() targets ("An unknown error occurred when
// fetching the script") — the new worker then never installs and Chrome keeps the
// OLD worker alive, so code changes silently never take effect. Inlining removes
// that fetch entirely: the worker has no external dependency and always installs.
// The utils remain separate files for the content-script / panel contexts (manifest).
console.info('[SAF] background service worker build 0.5.1-toolbar-open starting');

(function initStorage(globalScope) {
  const STORAGE_KEYS = Object.freeze({
    ONBOARDING_COMPLETE: "onboarding_complete",
    USER_REF: "user_ref",
    API_ENDPOINT: "api_endpoint",
    API_KEY: "api_key",
    OPENAI_API_KEY: "openai_api_key",
    CONSENT_ENABLED: "consent_enabled",
    LAST_CAPTURE: "last_capture",
    HEALTH_STATUS: "health_status",
  });

  function storageArea() {
    const area = globalScope.chrome?.storage?.local;
    if (!area) {
      throw new Error("chrome.storage.local is unavailable");
    }
    return area;
  }

  function lastRuntimeError() {
    return globalScope.chrome?.runtime?.lastError;
  }

  function invoke(method, ...args) {
    return new Promise((resolve, reject) => {
      let settled = false;
      const callback = (result) => {
        if (settled) return;
        settled = true;
        const error = lastRuntimeError();
        if (error) {
          reject(new Error(error.message || String(error)));
          return;
        }
        resolve(result);
      };

      try {
        const returned = storageArea()[method](...args, callback);
        if (returned && typeof returned.then === "function") {
          returned.then(callback, reject);
        }
      } catch (error) {
        reject(error);
      }
    });
  }

  async function get(key, fallback = undefined) {
    if (typeof key !== "string" || !key) {
      throw new TypeError("storage key must be a non-empty string");
    }
    const values = await invoke("get", key);
    return Object.prototype.hasOwnProperty.call(values || {}, key) && values[key] !== undefined
      ? values[key]
      : fallback;
  }

  async function getMany(keys = null) {
    if (
      keys !== null &&
      !Array.isArray(keys) &&
      (typeof keys !== "object" || keys === null)
    ) {
      throw new TypeError("keys must be an array, defaults object, or null");
    }
    return (await invoke("get", keys)) || {};
  }

  async function set(keyOrValues, value = undefined) {
    const values =
      typeof keyOrValues === "string"
        ? { [keyOrValues]: value }
        : keyOrValues;

    if (!values || typeof values !== "object" || Array.isArray(values)) {
      throw new TypeError("set expects a key/value pair or an object");
    }
    await invoke("set", values);
  }

  async function remove(keys) {
    if (
      !(typeof keys === "string" && keys) &&
      !(Array.isArray(keys) && keys.every((key) => typeof key === "string" && key))
    ) {
      throw new TypeError("remove expects a key or array of keys");
    }
    await invoke("remove", keys);
  }

  async function clear() {
    await invoke("clear");
  }

  async function update(key, updater, fallback = undefined) {
    if (typeof updater !== "function") {
      throw new TypeError("updater must be a function");
    }
    const next = await updater(await get(key, fallback));
    await set(key, next);
    return next;
  }

  globalScope.SAFStorage = Object.freeze({
    STORAGE_KEYS, get, getMany, set, remove, clear, update,
  });
})(self);

(function initPayloadBuilder(globalScope) {
  const SOURCE_MAP = Object.freeze({
    history: "chatgpt_history",
    history_import: "chatgpt_history",
    chatgpt_history: "chatgpt_history",
    live: "chatgpt_live",
    live_capture: "chatgpt_live",
    chatgpt_live: "chatgpt_live",
  });

  const ROLE_MAP = Object.freeze({
    human: "user",
    user: "user",
    ai: "assistant",
    assistant: "assistant",
  });

  function requireString(value, field) {
    if (typeof value !== "string" || !value.trim()) {
      throw new TypeError(`${field} must be a non-empty string`);
    }
    return value.trim();
  }

  function normaliseSource(source) {
    const mapped = SOURCE_MAP[String(source || "live").toLowerCase()];
    if (!mapped) {
      throw new TypeError(`unsupported capture source: ${source}`);
    }
    return mapped;
  }

  function normaliseTimestamp(value) {
    if (value === null || value === undefined || value === "") return null;
    const timestamp = Number(value);
    return Number.isFinite(timestamp) && timestamp >= 0
      ? Math.trunc(timestamp)
      : null;
  }

  function normaliseTurns(turns) {
    if (!Array.isArray(turns)) {
      throw new TypeError("turns must be an array");
    }

    return turns.reduce((result, turn, sourceIndex) => {
      const role = ROLE_MAP[String(turn?.role || "").toLowerCase()];
      const text = typeof turn?.text === "string" ? turn.text.trim() : "";
      if (!role || !text) return result;

      result.push({
        role,
        text,
        timestamp_ms: normaliseTimestamp(turn.timestamp_ms ?? turn.timestamp),
        turn_index: result.length,
        _sourceIndex: sourceIndex,
      });
      return result;
    }, []);
  }

  function validInteger(value) {
    if (value === null || value === undefined || value === "") return null;
    const number = Number(value);
    return Number.isFinite(number) && number >= 0 ? Math.trunc(number) : null;
  }

  function mapCompleteIntegerArray(values, sourceIndices) {
    if (!Array.isArray(values)) return undefined;
    const mapped = sourceIndices.map((index) => validInteger(values[index]));
    return mapped.every((value) => value !== null) ? mapped : undefined;
  }

  function mapCompleteBooleanArray(values, sourceIndices) {
    if (!Array.isArray(values)) return undefined;
    const mapped = sourceIndices.map((index) => values[index]);
    return mapped.every((value) => typeof value === "boolean") ? mapped : undefined;
  }

  function normaliseTelemetry(telemetry, sourceIndices) {
    if (!telemetry || typeof telemetry !== "object") return undefined;

    const result = {};
    const dwell = mapCompleteIntegerArray(telemetry.dwell_ms, sourceIndices);
    const copies = mapCompleteIntegerArray(telemetry.copy_events, sourceIndices);
    const edits = mapCompleteBooleanArray(telemetry.edit_detected, sourceIndices);

    if (dwell) result.dwell_ms = dwell;
    if (copies) result.copy_events = copies;
    if (edits) result.edit_detected = edits;
    if (
      typeof telemetry.selector_health === "string" &&
      telemetry.selector_health.trim()
    ) {
      result.selector_health = telemetry.selector_health.trim();
    }

    return Object.keys(result).length ? result : undefined;
  }

  function currentEraKey(now = new Date()) {
    return now.toISOString().slice(0, 7);
  }

  function normalisePartnerModel(partnerModel, now) {
    const model = partnerModel && typeof partnerModel === "object" ? partnerModel : {};
    const eraKey = /^(\d{4}-\d{2}|unknown)$/.test(String(model.era_key || ""))
      ? String(model.era_key)
      : currentEraKey(now);
    const family = ["anthropic", "openai", "google", "unknown"].includes(
      String(model.family || "").toLowerCase(),
    )
      ? String(model.family).toLowerCase()
      : "openai";

    return {
      family,
      model_id:
        typeof model.model_id === "string" && model.model_id.trim()
          ? model.model_id.trim()
          : "unknown",
      era_key: eraKey,
    };
  }

  function normaliseMetadata(metadata) {
    if (!metadata || typeof metadata !== "object" || Array.isArray(metadata)) {
      return undefined;
    }
    return { ...metadata };
  }

  function buildIngestPayload(input, now = new Date()) {
    if (!input || typeof input !== "object") {
      throw new TypeError("payload input must be an object");
    }

    const turnsWithIndices = normaliseTurns(input.turns);
    if (!turnsWithIndices.length) {
      throw new TypeError("at least one non-empty turn is required");
    }

    const sourceIndices = turnsWithIndices.map((turn) => turn._sourceIndex);
    const turns = turnsWithIndices.map(({ _sourceIndex, ...turn }) => turn);
    const telemetry = normaliseTelemetry(input.telemetry, sourceIndices);
    const metadata = normaliseMetadata(input.metadata);

    const payload = {
      user_ref: requireString(input.user_ref ?? input.userRef, "user_ref"),
      conversation_id: requireString(
        input.conversation_id ?? input.conversationId,
        "conversation_id",
      ),
      source: normaliseSource(input.source),
      partner_model: normalisePartnerModel(
        input.partner_model ?? input.partnerModel,
        now,
      ),
      turns,
    };

    if (telemetry) payload.telemetry = telemetry;
    if (metadata) payload.metadata = metadata;
    if (typeof input.capture_method === "string" && input.capture_method.trim()) {
      payload.capture_method = input.capture_method.trim();
    }
    const expectedTurnCount = validInteger(input.expected_turn_count ?? input.expectedTurnCount);
    if (expectedTurnCount !== null) payload.expected_turn_count = expectedTurnCount;
    payload.captured_turn_count = turns.length;
    if (typeof input.capture_complete === "boolean") {
      payload.capture_complete = input.capture_complete;
    }
    if (typeof input.raw_retention_flag === "string" && input.raw_retention_flag.trim()) {
      payload.raw_retention_flag = input.raw_retention_flag.trim();
    }
    return payload;
  }

  globalScope.SAFPayloadBuilder = Object.freeze({
    SOURCE_MAP, ROLE_MAP, buildIngestPayload, normalisePartnerModel,
    normaliseSource, normaliseTelemetry, normaliseTurns,
  });
})(self);

(function initApiClient(globalScope) {
  const DEFAULT_ENDPOINT = 'http://localhost:8000';
  const API_REQUEST_TIMEOUT_MS = 15000;

  function _forceIpv4Local(endpoint) {
    try {
      const url = new URL(endpoint);
      if (url.hostname === 'localhost' || url.hostname === '[::1]' || url.hostname === '::1') {
        url.hostname = '127.0.0.1';
        return url.toString().replace(/\/+$/, '');
      }
    } catch (_) { /* keep original endpoint */ }
    return String(endpoint || '').replace(/\/+$/, '');
  }

  async function _getConfig() {
    const storage = globalScope.SAFStorage;
    if (!storage) throw new Error('SAFStorage not loaded');
    const keys = storage.STORAGE_KEYS;
    const values = await storage.getMany([keys.API_ENDPOINT, keys.API_KEY]);
    const rawEndpoint = String(values[keys.API_ENDPOINT] || '').trim() || DEFAULT_ENDPOINT;
    return {
      endpoint: _forceIpv4Local(rawEndpoint),
      key: values[keys.API_KEY] || '',
    };
  }

  async function _fetchWithTimeout(url, options = {}, timeoutMs = API_REQUEST_TIMEOUT_MS) {
    if (!globalScope.AbortController || timeoutMs <= 0) {
      return fetch(url, options);
    }
    const controller = new globalScope.AbortController();
    const timer = globalScope.setTimeout(() => controller.abort(), timeoutMs);
    try {
      return await fetch(url, { ...options, signal: controller.signal });
    } finally {
      globalScope.clearTimeout(timer);
    }
  }

  async function _request(method, path, body) {
    let cfg;
    try {
      cfg = await _getConfig();
    } catch (err) {
      return { ok: false, error: 'storage_unavailable' };
    }

    const headers = { 'Content-Type': 'application/json' };
    if (cfg.key) headers['X-API-Key'] = cfg.key;

    try {
      const res = await _fetchWithTimeout(`${cfg.endpoint}${path}`, {
        method,
        headers,
        body: body != null ? JSON.stringify(body) : undefined,
      });

      if (!res.ok) {
        console.warn(`[SAF API] ${method} ${path} → ${res.status}`);
        let detail = null;
        let detailData = null;
        try {
          const data = await res.json();
          if (typeof data?.detail === 'string') {
            detail = data.detail;
          } else if (data?.detail && typeof data.detail === 'object') {
            detailData = data.detail;
            detail = typeof data.detail.message === 'string' ? data.detail.message : null;
          }
        } catch (_) {
          detail = null;
        }
        return { ok: false, error: `HTTP ${res.status}`, status: res.status, detail, detailData };
      }
      return { ok: true, data: await res.json(), status: res.status };
    } catch (err) {
      console.warn(`[SAF API] ${method} ${path} unreachable`);
      return { ok: false, error: 'api_unreachable', status: 0 };
    }
  }

  globalScope.SAFApiClient = Object.freeze({
    ingestChat: (payload) => _request('POST', '/v1/ingest', payload),
    listChats: (userRef) => _request('GET', `/v1/users/${encodeURIComponent(userRef)}/chats`),
    getScore: (userRef, chatId) =>
      _request('GET', `/v1/users/${encodeURIComponent(userRef)}/chats/${encodeURIComponent(chatId)}/score`),
    postFeedback: (userRef, chatId, body) =>
      _request('POST', `/v1/users/${encodeURIComponent(userRef)}/chats/${encodeURIComponent(chatId)}/feedback`, body),
    getPortfolio: (userRef) => _request('GET', `/v1/users/${encodeURIComponent(userRef)}/portfolio`),
    // Scope-C (D-012): used only to PROBE whether the projects API is live so the
    // worker can emit SAF_PROJECTS_API_READY. The panel/content api_client.js is
    // the surface Codex calls for the full projects suite.
    listProjects: (userRef) => _request('GET', `/v1/users/${encodeURIComponent(userRef)}/projects`),
    deleteUser: (userRef) => _request('DELETE', `/v1/users/${encodeURIComponent(userRef)}`),
    checkHealth: async () => {
      let cfg;
      try { cfg = await _getConfig(); } catch { return false; }
      try {
        const res = await _fetchWithTimeout(`${cfg.endpoint}/v1/health`, {}, API_REQUEST_TIMEOUT_MS);
        return res.ok;
      } catch { return false; }
    },
    DEFAULT_ENDPOINT,
  });
})(self);

/* globals SAFStorage, SAFPayloadBuilder, SAFApiClient */

const SK = SAFStorage.STORAGE_KEYS;
const HEALTH_POLL_ALARM = 'saf_health_poll';
const COLLECTOR_BAG_KEY = 'saf_collector_bag';
const MAX_BAG_SIZE = 50;
const AUTO_CAPTURE_DEBOUNCE_MS = 1200;
const CONTENT_CAPTURE_TIMEOUT_MS = 45000;

// In-memory: tabId → most recent capture snapshot sent by content.js
const _latestCapture = new Map();
const _latestReadyCapture = new Map();
const _analyseProgress = new Map();
const _pendingAutomaticCaptures = new Map();

// In-memory: conversation_id → last content hash we forwarded to the API.
// Best-effort only — MV3 workers sleep and lose this; the DB content_hash is
// the real guard. Worst case after a wake is one redundant forward that the
// server's idempotent upsert collapses to a no-op. (D-006)
const _lastForwardedHash = new Map();

// In-memory: conversation_id → turn count of the best capture forwarded so far.
// Guards against a DOM partial (3 turns) arriving after a full interception capture
// (30 turns) and overwriting the complete transcript at the DB layer (race condition
// between concurrent SAF_CAPTURE_READY messages for the same conversation).
const _lastForwardedTurnCount = new Map();

function _captureTurnCount(capture) {
  return Array.isArray(capture?.turns) ? capture.turns.length : 0;
}

function _captureConversationId(capture) {
  return typeof capture?.conversation_id === 'string' && capture.conversation_id.trim()
    ? capture.conversation_id.trim()
    : null;
}

function _captureRank(capture) {
  return {
    turns: _captureTurnCount(capture),
    complete: capture?.capture_complete === true ? 1 : 0,
  };
}

function _isBetterCapture(candidate, current) {
  if (!current) return true;
  const next = _captureRank(candidate);
  const prev = _captureRank(current);
  if (next.turns !== prev.turns) return next.turns > prev.turns;
  return next.complete > prev.complete;
}

function _rememberBestReadyCapture(tabId, capture) {
  if (tabId == null || _captureValidationError(capture)) return;
  const current = _latestReadyCapture.get(tabId);
  if (_isBetterCapture(capture, current)) {
    _latestReadyCapture.set(tabId, capture);
  }
}

function _claimAutomaticCapture(capture) {
  const convId = _captureConversationId(capture);
  if (!convId) return { accepted: true };
  const turnCount = _captureTurnCount(capture);
  const bestCount = _lastForwardedTurnCount.get(convId) || 0;
  if (turnCount < bestCount) {
    return { accepted: false, reason: 'stale_partial', bestCount, turnCount };
  }
  _lastForwardedTurnCount.set(convId, Math.max(turnCount, bestCount));
  return { accepted: true };
}

function _scheduleAutomaticCapture(capture) {
  const convId = _captureConversationId(capture);
  if (!convId) {
    _handleCaptureReady(capture).catch(console.warn);
    return;
  }
  const pending = _pendingAutomaticCaptures.get(convId);
  const bestCapture = _isBetterCapture(capture, pending?.capture)
    ? capture
    : pending.capture;
  if (pending?.timer) clearTimeout(pending.timer);
  const timer = setTimeout(() => {
    const item = _pendingAutomaticCaptures.get(convId);
    _pendingAutomaticCaptures.delete(convId);
    if (item?.capture) _handleCaptureReady(item.capture).catch(console.warn);
  }, AUTO_CAPTURE_DEBOUNCE_MS);
  _pendingAutomaticCaptures.set(convId, { capture: bestCapture, timer });
}

function _sendAnalyseNowToTab(tabId) {
  return new Promise((resolve, reject) => {
    let settled = false;
    const timer = setTimeout(() => {
      if (settled) return;
      settled = true;
      reject(new Error('capture_timeout'));
    }, CONTENT_CAPTURE_TIMEOUT_MS);

    self.chrome.tabs.sendMessage(tabId, { type: 'SAF_ANALYSE_NOW' }, (res) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      const err = self.chrome.runtime.lastError;
      if (err) reject(new Error(err.message || 'send_failed'));
      else resolve(res);
    });
  });
}

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

// ── Scope-C projects API readiness (D-012) ─────────────────────────────────────
// The panel's Projects nav stays disabled until CE confirms the projects API is
// actually reachable (migration 012 applied + routers deployed). Readiness is
// NEVER announced blindly at startup — only after a probe of the live route
// succeeds. sidebar.js (CODEX_AGENT_UI.md §7) listens for SAF_PROJECTS_API_READY
// to unlock the nav. Emitted once per worker session (the unlock is idempotent).

let _projectsApiAnnounced = false;

async function _probeProjectsApi() {
  const userRef = await SAFStorage.get(SK.USER_REF);
  if (!userRef) return false;                 // no owner yet → cannot probe
  const res = await SAFApiClient.listProjects(userRef);
  // 200 = route live (migration 012 + router). 404 = not deployed, 5xx = table
  // missing, 0 = unreachable — none of those count as ready.
  return res.ok && res.status === 200;
}

function _broadcastProjectsApiReady() {
  const msg = { type: 'SAF_PROJECTS_API_READY' };
  try {
    self.chrome.runtime.sendMessage(msg, () => void self.chrome.runtime.lastError);
  } catch (_) { /* no panel/popup open — fine */ }
  self.chrome.tabs.query({}, (tabs) => {
    for (const tab of tabs || []) {
      if (tab.id == null) continue;
      try {
        self.chrome.tabs.sendMessage(tab.id, msg, () => void self.chrome.runtime.lastError);
      } catch (_) { /* tab has no content script — fine */ }
    }
  });
}

async function _maybeAnnounceProjectsApi() {
  if (_projectsApiAnnounced) return;          // once per worker session — no spam
  if (await _probeProjectsApi()) {
    _projectsApiAnnounced = true;
    _broadcastProjectsApiReady();
    console.info('[SAF] projects API confirmed live → SAF_PROJECTS_API_READY emitted');
  }
}

// ── health polling ────────────────────────────────────────────────────────────

async function _updateHealth() {
  const healthy = await SAFApiClient.checkHealth();
  await SAFStorage.set(SK.HEALTH_STATUS, healthy ? 'ok' : 'error');
  if (healthy) {
    await _flushBag();
    // Emit point: only after the server is healthy AND the projects route probes
    // live. Gated by _projectsApiAnnounced so a healthy server with the route
    // already announced does not re-fire on every 1-min poll / startup.
    await _maybeAnnounceProjectsApi();
  }
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

// A bagged payload is only worth retrying if the failure was TRANSIENT — the
// server was unreachable (status 0/undefined) or errored internally (5xx, e.g. a
// server still starting up). A 422 is a PERMANENT rejection (capture incomplete /
// count mismatch): the same payload will be rejected every time, so re-queuing it
// makes the health poll re-POST it forever (a self-sustaining flood). Drop those —
// and any other 4xx — instead of retrying. (Mirrors _addToBag, which already
// refuses to bag a 422 on the live path.)
function _isRetryableIngestFailure(result) {
  const status = result?.status;
  return status === 0 || status === undefined || (status >= 500 && status <= 599);
}

async function _flushBag() {
  const bag = await _getBag();
  if (!bag.length) return;
  const remaining = [];
  for (const item of bag) {
    const result = await SAFApiClient.ingestChat(item.payload);
    if (result.ok) continue;            // ingested → drop from bag
    if (_isRetryableIngestFailure(result)) {
      remaining.push(item);             // transient → keep for the next poll
    } else {
      console.warn(`[SAF] dropping un-ingestable bagged capture (HTTP ${result.status})`);
    }
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
async function _handleCaptureReady(capture, { force = false } = {}) {
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

  if (force) {
    const convId = _captureConversationId(capture);
    if (convId) {
      _lastForwardedTurnCount.set(
        convId,
        Math.max(_captureTurnCount(capture), _lastForwardedTurnCount.get(convId) || 0),
      );
    }
  } else {
    const claim = _claimAutomaticCapture(capture);
    if (!claim.accepted) {
      return {
        ok: true,
        noop: true,
        skipped: claim.reason,
        data: {
          chatId: null,
          status: 'skipped_partial',
          conversationId: _captureConversationId(capture),
          bestTurnCount: claim.bestCount,
          skippedTurnCount: claim.turnCount,
        },
      };
    }
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
  const turnCount = _captureTurnCount(capture);

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

  // Race-condition guard (D-015): a DOM partial (e.g. 3 visible turns) can arrive
  // concurrently with a full interception capture (30 turns). Both have different
  // hashes so both pass the dedupe check above, but whichever hits the DB last wins
  // — if the partial lands after the full, the worker scores the partial transcript.
  // Skip any automatic capture that has fewer turns than the best we already sent,
  // unless the caller is an explicit Analyse Now (force=true).
  if (!force) {
    const bestCount = _lastForwardedTurnCount.get(convId) || 0;
    if (turnCount < bestCount) {
      const existing = await _findChat(userRef, convId);
      if (existing) {
        _badgeForChat(existing, capture);
        return { ok: true, noop: true,
                 data: { chatId: existing.chat_id, status: existing.status, conversationId: convId } };
      }
      return {
        ok: true,
        noop: true,
        skipped: 'stale_partial',
        data: {
          chatId: null,
          status: 'skipped_partial',
          conversationId: convId,
          bestTurnCount: bestCount,
          skippedTurnCount: turnCount,
        },
      };
    }
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
  _lastForwardedTurnCount.set(convId, Math.max(turnCount, _lastForwardedTurnCount.get(convId) || 0));
  await SAFStorage.set(SK.HEALTH_STATUS, 'ok');
  _setBadge('…', '#1a6fa0', `SAF — ${turnCount} turns saved · analysing…`);
  return { ok: true,
           data: { chatId: result.data.chat_id, status: result.data.status, conversationId: convId } };
}

// ── message router ────────────────────────────────────────────────────────────

self.chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (!message || typeof message.type !== 'string') return undefined;
  if (!_isTrustedSafMessageSender(sender)) return undefined;

  // ── content.js push messages ──────────────────────────────────────────────
  if (message.type === 'SAF_CAPTURE_UPDATED') {
    if (sender.tab?.id != null) {
      const current = _latestCapture.get(sender.tab.id);
      if (_isBetterCapture(message.capture, current)) {
        _latestCapture.set(sender.tab.id, message.capture);
      }
    }
    return undefined; // no response
  }

  if (message.type === 'SAF_ANALYSE_PROGRESS') {
    const tabId = sender.tab?.id;
    if (tabId != null) {
      const progress = message.progress || {};
      if (progress.capture) {
        const current = _latestCapture.get(tabId);
        if (_isBetterCapture(progress.capture, current)) {
          _latestCapture.set(tabId, progress.capture);
        }
      }
      _setAnalyseProgress(tabId, {
        active: progress.stage === 'error' ? false : undefined,
        stage: progress.stage || 'capturing',
        percent: progress.stage === 'error' ? 100 : (progress.percent ?? 0),
        message: progress.message || 'Capturing chat...',
        capturedTurns: progress.captured_turns || progress.capture?.turns?.length || 0,
        conversationId: progress.capture?.conversation_id || null,
      });
    }
    return undefined;
  }

  if (message.type === 'SAF_CAPTURE_READY') {
    if (sender.tab?.id != null) {
      const current = _latestCapture.get(sender.tab.id);
      if (_isBetterCapture(message.capture, current)) {
        _latestCapture.set(sender.tab.id, message.capture);
      }
      _rememberBestReadyCapture(sender.tab.id, message.capture);
    }
    _scheduleAutomaticCapture(message.capture);
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
          reply = await _sendAnalyseNowToTab(tabId);
        } catch (err) {
          sendError = err;
        }

        const fallbackCapture = _latestReadyCapture.get(tabId);
        // When the content script returned an EXPLICIT failure, that diagnosis is
        // authoritative: the manual capture ran the full path (interception poll +
        // backend backfill + DOM scroll), a superset of the passive auto-capture, and
        // its message carries the real reason (backend_fetch status, turn counts).
        // Masking it with a stale, likely-worse auto-capture hides why it failed. Only
        // fall back to the auto-capture when the manual reply was LOST (sendError / no
        // reply), not when it explicitly said ok:false.
        const replyFailedExplicitly = reply != null && reply.ok === false;
        // The content script never answered (channel closed / no response). This is
        // the orphaned-content-script state after an extension update: the page is
        // running a disconnected old script. A stale in-memory auto-capture must NOT
        // be used here — validating it surfaces a misleading "imbalanced" verdict for
        // a capture that isn't even from this attempt. The real fix is reloading the
        // tab, so say exactly that.
        const contentUnreachable = reply == null;
        const capture =
          reply?.ok === true && _captureHasTurns(reply?.capture) ? reply.capture
            : (!replyFailedExplicitly && !contentUnreachable && _captureHasTurns(fallbackCapture))
              ? fallbackCapture
              : null;

        // D-010: honour the content script's own ok/capture — do not assume success.
        if (!capture) {
          const e = new Error(sendError?.message || 'nothing_captured');
          e.userMessage = sendError?.message === 'capture_timeout'
            ? 'Capture timed out — reload the ChatGPT tab (F5) and try again.'
            : contentUnreachable
              ? 'SAF lost its connection to this tab — this happens right after the extension is updated. Reload the ChatGPT tab (F5), then click Analyse again.'
              : (reply?.message || reply?.error || 'No full conversation captured yet — reload ChatGPT and try again.');
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
        const outcome = await _handleCaptureReady(capture, { force: true });
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
        const { userRef, apiEndpoint, apiKey, consent } = message;
        if (userRef !== undefined) updates[SK.USER_REF] = userRef;
        if (apiEndpoint !== undefined) updates[SK.API_ENDPOINT] = apiEndpoint;
        // SAF API key is stored raw but never echoed back or logged.
        if (apiKey !== undefined) updates[SK.API_KEY] = apiKey;
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

// ── toolbar icon click ─────────────────────────────────────────────────────────
// manifest has no default_popup (panel.html is an in-page shadow-DOM template,
// not a standalone popup document). Clicking the toolbar icon opens the in-page
// SAF modal on a supported tab; on any other tab it opens ChatGPT so the user
// lands somewhere the FAB exists.
const _SAF_SUPPORTED_HOSTS = ['chatgpt.com', 'chat.openai.com', 'claude.ai'];
const _pendingModalOpenAfterReload = new Set();
const MODAL_OPEN_RETRY_MS = 400;
const MODAL_OPEN_MAX_ATTEMPTS = 8;

function _isSupportedSafTab(url) {
  try {
    return _SAF_SUPPORTED_HOSTS.includes(new URL(url).hostname);
  } catch (_) {
    return false;
  }
}

function _isTrustedSafMessageSender(sender) {
  if (!sender) return false;
  const runtimeId = self.chrome.runtime.id;
  if (runtimeId && sender.id && sender.id !== runtimeId) return false;
  if (sender.tab) return _isSupportedSafTab(sender.tab.url || sender.url);
  return Boolean(runtimeId && sender.id === runtimeId);
}

function _requestModalOpen(tabId, attempt = 1) {
  self.chrome.tabs.sendMessage(tabId, { type: 'SAF_OPEN_MODAL' }, () => {
    if (!self.chrome.runtime.lastError) return;
    if (attempt >= MODAL_OPEN_MAX_ATTEMPTS) return;
    setTimeout(() => _requestModalOpen(tabId, attempt + 1), MODAL_OPEN_RETRY_MS);
  });
}

self.chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (!_pendingModalOpenAfterReload.has(tabId)) return;
  if (changeInfo.status !== 'complete') return;
  if (!_isSupportedSafTab(tab.url)) {
    _pendingModalOpenAfterReload.delete(tabId);
    return;
  }
  _pendingModalOpenAfterReload.delete(tabId);
  _requestModalOpen(tabId);
});

self.chrome.action.onClicked.addListener((tab) => {
  if (tab?.id != null && _isSupportedSafTab(tab.url)) {
    self.chrome.tabs.sendMessage(tab.id, { type: 'SAF_OPEN_MODAL' }, () => {
      // content script not injected yet (e.g. tab opened before reload) →
      // reload so the content scripts attach, then the FAB is available.
      if (self.chrome.runtime.lastError) {
        _pendingModalOpenAfterReload.add(tab.id);
        self.chrome.tabs.reload(tab.id, {}, () => void self.chrome.runtime.lastError);
      }
    });
    return;
  }
  self.chrome.tabs.create({ url: 'https://chatgpt.com/' });
});

// Initial health check when service worker starts
_updateHealth().catch(console.warn);
