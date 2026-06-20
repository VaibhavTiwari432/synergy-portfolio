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
      const res = await fetch(`${cfg.endpoint}${path}`, {
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
    return _request('GET', `/v1/users/${encodeURIComponent(userRef)}/chats`);
  }

  async function getScore(userRef, chatId) {
    return _request('GET', `/v1/users/${encodeURIComponent(userRef)}/chats/${encodeURIComponent(chatId)}/score`);
  }

  async function postFeedback(userRef, chatId, body) {
    return _request('POST', `/v1/users/${encodeURIComponent(userRef)}/chats/${encodeURIComponent(chatId)}/feedback`, body);
  }

  async function getPortfolio(userRef) {
    return _request('GET', `/v1/users/${encodeURIComponent(userRef)}/portfolio`);
  }

  async function acknowledgePortfolio(userRef, snapshotHash) {
    return _request(
      'POST',
      `/v1/users/${encodeURIComponent(userRef)}/portfolio/ack`,
      { snapshot_hash: snapshotHash },
    );
  }

  // Directive §9 (CODEX_AGENT_UI.md) names the chat-list / chat-score calls
  // getChatList / getChatScore. These are additive aliases over the shipped
  // listChats / getScore so Codex can call the contract vocabulary without us
  // renaming (or touching) the existing functions.
  const getChatList = listChats;
  const getChatScore = getScore;

  async function deleteUser(userRef) {
    return _request('DELETE', `/v1/users/${encodeURIComponent(userRef)}`);
  }

  async function checkHealth() {
    let cfg;
    try {
      cfg = await _getConfig();
    } catch {
      return false;
    }
    try {
      const res = await fetch(`${cfg.endpoint}/v1/health`);
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
    deleteUser,
    checkHealth,
    DEFAULT_ENDPOINT,
  });

  globalScope.SAFApiClient = api;
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = api;
  }
})(typeof globalThis !== 'undefined' ? globalThis : self);
