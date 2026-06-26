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
  // Must exceed CAPTURE_ABSOLUTE_TIMEOUT_MS (300s) + API_REQUEST_TIMEOUT_MS (15s) + margin.
  // The heartbeat fix extends capture past the old 30s stall; this must match.
  const TRIGGER_ANALYSIS_TIMEOUT_MS = 330000;
  // The dev server binds IPv4 127.0.0.1 only, but on Windows `localhost` resolves
  // to IPv6 ::1 first — fetch can fail there before falling back. Force IPv4 for
  // the loopback host so the call always lands on the listening socket. Stored /
  // displayed value is untouched; this only affects the URL we fetch.
  function _forceIpv4Local(endpoint) {
    try {
      const url = new URL(endpoint);
      if (url.hostname === 'localhost' || url.hostname === '[::1]' || url.hostname === '::1') {
        url.hostname = '127.0.0.1';
        return url.toString().replace(/\/+$/, '');
      }
    } catch (_) { /* fall through to original */ }
    return String(endpoint || '').replace(/\/+$/, '');
  }

  async function _getConfig() {
    const storage = globalScope.SAFStorage;
    if (!storage) throw new Error('SAFStorage not loaded');
    const keys = storage.STORAGE_KEYS;
    const values = await storage.getMany([keys.API_ENDPOINT, keys.API_KEY]);
    const rawEndpoint = String(values[keys.API_ENDPOINT] || '').trim() || DEFAULT_ENDPOINT;
    const endpoint = _forceIpv4Local(rawEndpoint);
    const storedKey = values[keys.API_KEY] || '';
    return {
      endpoint,
      key: storedKey,
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

  // GET .../chats/{id}/work — read-only CSL (Cognitive Work Layer): the
  // descriptive per-ACF-level human/AI contribution split. Never an ARI score;
  // separate route so the frozen ScoreResponse stays untouched.
  async function getChatWork(userRef, chatId) {
    const ref = _requireUserRef(userRef);
    if (!ref) return _missingUserRef();
    return _request('GET', `/v1/users/${encodeURIComponent(ref)}/chats/${encodeURIComponent(chatId)}/work`);
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

  // requeueChat — re-queue an already-ingested failed chat for scoring without
  // re-capturing from the page. Use this for the Retry CTA on a known chat_id
  // instead of triggerAnalysis, which re-captures whatever tab is active.
  async function requeueChat(userRef, chatId) {
    const ref = _requireUserRef(userRef);
    if (!ref) return _missingUserRef();
    return _request(
      'POST',
      `/v1/users/${encodeURIComponent(ref)}/chats/${encodeURIComponent(chatId)}/requeue`,
    );
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

  async function getHealth() {
    let cfg;
    try {
      cfg = await _getConfig();
    } catch {
      return { ok: false, error: 'storage_unavailable', status: 0 };
    }
    try {
      const res = await _fetchWithTimeout(`${cfg.endpoint}/v1/health`);
      let data = null;
      try {
        data = await res.json();
      } catch (_) {
        data = null;
      }
      if (!res.ok) return { ok: false, error: `HTTP ${res.status}`, status: res.status, data };
      return { ok: true, data, status: res.status };
    } catch {
      return { ok: false, error: 'api_unreachable', status: 0 };
    }
  }

  async function checkHealth() {
    const result = await getHealth();
    return Boolean(result?.ok);
  }

  function getAnalysisProgress() {
    const runtime = globalScope.chrome?.runtime;
    if (!runtime?.sendMessage) return Promise.resolve(null);
    return new Promise((resolve) => {
      runtime.sendMessage({ type: 'SAF_PANEL_GET_STATUS' }, (res) => {
        void runtime.lastError;
        resolve(res?.ok ? (res.data?.analysisProgress ?? null) : null);
      });
    });
  }

  const api = Object.freeze({
    ingestChat,
    listChats,
    getScore,
    postFeedback,
    getPortfolio,
    getChatWork,
    acknowledgePortfolio,
    getChatList,
    getChatScore,
    submitFeedback,
    requeueChat,
    triggerAnalysis,
    getAnalysisProgress,
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
    getHealth,
    checkHealth,
    DEFAULT_ENDPOINT,
  });

  globalScope.SAFApiClient = api;
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = api;
  }
})(typeof globalThis !== 'undefined' ? globalThis : self);
