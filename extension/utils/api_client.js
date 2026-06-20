/**
 * utils/api_client.js — all calls to the saf-brain localhost API.
 * OWNER: Chief Engineer
 *
 * IIFE pattern matching storage.js / payload_builder.js so this file can be
 * loaded via importScripts() in the service worker OR <script> in the panel.
 *
 * Reads API endpoint + key from SAFStorage on every call so the user can
 * change settings without reloading the extension.
 * Key is NEVER logged or included in error messages.
 *
 * All exported functions return {ok: true, data: ...} or {ok: false, error: string}.
 * Callers decide whether to surface the error; this module never throws.
 */

'use strict';

(function initApiClient(globalScope) {
  const DEFAULT_ENDPOINT = 'http://localhost:8000';
  const API_REQUEST_TIMEOUT_MS = 15000;
  const TRIGGER_ANALYSIS_TIMEOUT_MS = 30000;

  async function _getConfig() {
    const storage = globalScope.SAFStorage;
    if (!storage) throw new Error('SAFStorage not loaded');
    const keys = storage.STORAGE_KEYS;
    const values = await storage.getMany([keys.API_ENDPOINT, keys.API_KEY]);
    return {
      endpoint: values[keys.API_ENDPOINT] || DEFAULT_ENDPOINT,
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

  function _requireUserRef(userRef) {
    return typeof userRef === 'string' && userRef.trim() ? userRef : null;
  }

  function _missingUserRef() {
    return { ok: false, error: 'user_ref_required', status: 0 };
  }

  async function _request(method, path, body, extraHeaders = null) {
    let cfg;
    try {
      cfg = await _getConfig();
    } catch (err) {
      return { ok: false, error: 'storage_unavailable' };
    }

    const headers = { 'Content-Type': 'application/json' };
    if (cfg.key) headers['X-API-Key'] = cfg.key;
    // optional per-call headers (If-Match for optimistic concurrency,
    // Idempotency-Key for create dedupe — Scope-C §3.3/§3.4)
    if (extraHeaders) Object.assign(headers, extraHeaders);

    try {
      const res = await _fetchWithTimeout(`${cfg.endpoint}${path}`, {
        method,
        headers,
        body: body != null ? JSON.stringify(body) : undefined,
      });

      if (!res.ok) {
        console.warn(`[SAF API] ${method} ${path} → ${res.status}`);
        let detail = null;       // human string, kept for back-compat callers
        let detailData = null;   // structured object when the server sends one
        try {
          const data = await res.json();
          if (typeof data?.detail === 'string') {
            detail = data.detail;
          } else if (data?.detail && typeof data.detail === 'object') {
            // Structured 422 (capture completeness gate, ADR-0007): surface the
            // server's human message AND carry the structured fields through.
            detailData = data.detail;
            detail = typeof data.detail.message === 'string' ? data.detail.message : null;
          }
        } catch (_) {
          detail = null;
        }
        // status carried through so callers can distinguish auth/config (4xx/503)
        // from a genuinely unreachable server (status 0). Never log the key.
        return { ok: false, error: `HTTP ${res.status}`, status: res.status, detail, detailData };
      }
      return { ok: true, data: await res.json(), status: res.status };
    } catch (err) {
      console.warn(`[SAF API] ${method} ${path} unreachable`);
      return { ok: false, error: 'api_unreachable', status: 0 };
    }
  }

  // ── endpoint functions ────────────────────────────────────────────────────

  async function ingestChat(payload) {
    return _request('POST', '/v1/ingest', payload);
  }

  async function listChats(userRef) {
    const ref = _requireUserRef(userRef);
    if (!ref) return _missingUserRef();
    return _request('GET', `/v1/users/${encodeURIComponent(ref)}/chats`);
  }

  async function getScore(userRef, chatId) {
    const ref = _requireUserRef(userRef);
    if (!ref) return _missingUserRef();
    return _request('GET', `/v1/users/${encodeURIComponent(ref)}/chats/${encodeURIComponent(chatId)}/score`);
  }

  async function postFeedback(userRef, chatId, body) {
    const ref = _requireUserRef(userRef);
    if (!ref) return _missingUserRef();
    return _request('POST', `/v1/users/${encodeURIComponent(ref)}/chats/${encodeURIComponent(chatId)}/feedback`, body);
  }

  async function getPortfolio(userRef) {
    const ref = _requireUserRef(userRef);
    if (!ref) return _missingUserRef();
    return _request('GET', `/v1/users/${encodeURIComponent(ref)}/portfolio`);
  }

  async function acknowledgePortfolio(userRef, snapshotHash) {
    const ref = _requireUserRef(userRef);
    if (!ref) return _missingUserRef();
    return _request(
      'POST',
      `/v1/users/${encodeURIComponent(ref)}/portfolio/ack`,
      { snapshot_hash: snapshotHash },
    );
  }

  // Directive §9 (CODEX_AGENT_UI.md) names the chat-list / chat-score calls
  // getChatList / getChatScore. These are additive aliases over the shipped
  // listChats / getScore so Codex can call the contract vocabulary without us
  // renaming (or touching) the existing functions.
  const getChatList = listChats;
  const getChatScore = getScore;

  // submitFeedback — the UI feedback model ({type,value,text}) mapped to the
  // backend feedback body. 👍 → match_rating:'yes', 👎 → match_rating:'no',
  // note → comment. The backend REQUIRES a match_rating, so a standalone note
  // (no thumb) is sent as the neutral 'partial' rating; the note text is the
  // comment. Delegates to the existing postFeedback (path untouched).
  async function submitFeedback(userRef, chatId, feedback = {}) {
    const { type, value, text } = feedback;
    const body = {};
    if (type === 'thumb') {
      body.match_rating = Number(value) > 0 ? 'yes' : 'no';
    } else if (type === 'note') {
      body.match_rating = 'partial';   // backend requires a rating; a lone note is neutral
      body.comment = text;
    }
    return postFeedback(userRef, chatId, body);
  }

  // triggerAnalysis — the "Analyse" CTA does NOT hit the API directly. Analysis
  // is driven by the background worker (capture → ingest → score), so this sends
  // SAF_PANEL_ANALYSE_NOW and resolves when background acknowledges. Returns the
  // same {ok, data|error} envelope as the HTTP helpers. (CODEX_AGENT_UI.md §4.4)
  function triggerAnalysis(chatId) {
    return new Promise((resolve) => {
      const runtime = globalScope.chrome?.runtime;
      if (!runtime?.sendMessage) {
        resolve({ ok: false, error: 'runtime_unavailable' });
        return;
      }
      let settled = false;
      let timer = null;
      const finish = (result) => {
        if (settled) return;
        settled = true;
        globalScope.clearTimeout(timer);
        resolve(result);
      };
      timer = globalScope.setTimeout(() => {
        finish({ ok: false, error: 'analysis_timeout' });
      }, TRIGGER_ANALYSIS_TIMEOUT_MS);
      try {
        runtime.sendMessage({ type: 'SAF_PANEL_ANALYSE_NOW', chatId }, (res) => {
          const err = runtime.lastError;
          if (err) { finish({ ok: false, error: err.message || 'send_failed' }); return; }
          finish(res || { ok: false, error: 'no_response' });
        });
      } catch (e) {
        finish({ ok: false, error: String(e?.message || e) });
      }
    });
  }

  // ── Scope-C projects (migration 012 routes, contract §4.1–4.2) ──────────────

  function _newIdempotencyKey() {
    const c = globalScope.crypto;
    return c?.randomUUID
      ? c.randomUUID()
      : `idem-${Date.now()}-${Math.random().toString(16).slice(2)}`;
  }

  // POST /projects — Idempotency-Key dedupes a double-tap (§3.4); auto-generated
  // when the caller does not supply one.
  async function createProject(userRef, { name, description = null } = {}, idempotencyKey) {
    const ref = _requireUserRef(userRef);
    if (!ref) return _missingUserRef();
    return _request(
      'POST',
      `/v1/users/${encodeURIComponent(ref)}/projects`,
      { name, description },
      { 'Idempotency-Key': idempotencyKey || _newIdempotencyKey() },
    );
  }

  // GET /projects?limit=&cursor= — keyset page (§3.2)
  async function listProjects(userRef, { limit, cursor } = {}) {
    const ref = _requireUserRef(userRef);
    if (!ref) return _missingUserRef();
    const params = new URLSearchParams();
    if (limit != null) params.set('limit', String(limit));
    if (cursor) params.set('cursor', cursor);
    const qs = params.toString();
    return _request(
      'GET',
      `/v1/users/${encodeURIComponent(ref)}/projects${qs ? `?${qs}` : ''}`,
    );
  }

  async function getProject(userRef, projectId) {
    const ref = _requireUserRef(userRef);
    if (!ref) return _missingUserRef();
    return _request(
      'GET',
      `/v1/users/${encodeURIComponent(ref)}/projects/${encodeURIComponent(projectId)}`,
    );
  }

  // PATCH /projects/{id} — If-Match carries the version (optimistic concurrency,
  // §3.3); a stale version returns HTTP 409 → result.status === 409.
  async function updateProject(userRef, projectId, patch, version) {
    const ref = _requireUserRef(userRef);
    if (!ref) return _missingUserRef();
    return _request(
      'PATCH',
      `/v1/users/${encodeURIComponent(ref)}/projects/${encodeURIComponent(projectId)}`,
      patch,
      { 'If-Match': String(version) },
    );
  }

  async function deleteProject(userRef, projectId, version) {
    const ref = _requireUserRef(userRef);
    if (!ref) return _missingUserRef();
    return _request(
      'DELETE',
      `/v1/users/${encodeURIComponent(ref)}/projects/${encodeURIComponent(projectId)}`,
      null,
      { 'If-Match': String(version) },
    );
  }

  // POST /projects/{id}/sessions — chat_ids ARE saf_session_ids (§1)
  async function addProjectSessions(userRef, projectId, chatIds) {
    const ref = _requireUserRef(userRef);
    if (!ref) return _missingUserRef();
    return _request(
      'POST',
      `/v1/users/${encodeURIComponent(ref)}/projects/${encodeURIComponent(projectId)}/sessions`,
      { chat_ids: chatIds },
    );
  }

  async function removeProjectSession(userRef, projectId, sessionId) {
    const ref = _requireUserRef(userRef);
    if (!ref) return _missingUserRef();
    return _request(
      'DELETE',
      `/v1/users/${encodeURIComponent(ref)}/projects/${encodeURIComponent(projectId)}/sessions/${encodeURIComponent(sessionId)}`,
    );
  }

  // ── Settings (S10: migration-013 routes) ────────────────────────────────────

  async function getSettings(userRef) {
    const ref = _requireUserRef(userRef);
    if (!ref) return _missingUserRef();
    return _request('GET', `/v1/users/${encodeURIComponent(ref)}/settings`);
  }

  // patch = { auto_analyse?: bool, calibration_opt_in?: bool } — partial update
  async function updateSettings(userRef, patch) {
    const ref = _requireUserRef(userRef);
    if (!ref) return _missingUserRef();
    return _request('PATCH', `/v1/users/${encodeURIComponent(ref)}/settings`, patch);
  }

  async function deleteUser(userRef) {
    const ref = _requireUserRef(userRef);
    if (!ref) return _missingUserRef();
    return _request('DELETE', `/v1/users/${encodeURIComponent(ref)}`);
  }

  async function checkHealth() {
    let cfg;
    try {
      cfg = await _getConfig();
    } catch {
      return false;
    }
    try {
      const res = await _fetchWithTimeout(`${cfg.endpoint}/v1/health`);
      return res.ok;
    } catch {
      return false;
    }
  }

  const api = Object.freeze({
    ingestChat,
    listChats,
    getScore,
    postFeedback,
    getPortfolio,
    acknowledgePortfolio,
    getChatList,
    getChatScore,
    submitFeedback,
    triggerAnalysis,
    createProject,
    listProjects,
    getProject,
    updateProject,
    deleteProject,
    addProjectSessions,
    removeProjectSession,
    getSettings,
    updateSettings,
    deleteUser,
    checkHealth,
    DEFAULT_ENDPOINT,
  });

  globalScope.SAFApiClient = api;
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = api;
  }
})(typeof globalThis !== 'undefined' ? globalThis : self);
