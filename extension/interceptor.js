'use strict';

/**
 * interceptor.js — runs in the MAIN world (manifest `world: "MAIN"`).
 * OWNER: Chief Engineer.  ADR-0007 / D-015 §1.
 *
 * WHY MAIN world: a content script in the default isolated world does NOT share
 * the page's `window.fetch` / `XMLHttpRequest`, so it cannot observe the
 * conversation-tree response the ChatGPT app fetches from its own backend. This
 * file patches those two APIs in the page's own realm, watches for the
 * conversation endpoint, and hands the parsed JSON to the isolated-world bridge
 * (content.js, Codex / D-015 §1-§9) via `window.postMessage`.
 *
 * It captures the response the page ALREADY makes — it never originates a request
 * and never touches auth tokens or headers. It reads no DOM and holds no state
 * beyond a one-shot "have I warned about a shape change" flag.
 *
 * Completeness is fixed by construction here: the payload is the whole
 * conversation tree regardless of scroll position / virtualization. The bridge
 * walks the active path; the server gates on expected-vs-captured turn count.
 */

(function initInterceptor(win) {
  // Idempotent: a duplicate injection (SPA soft-nav, re-inject) must not stack
  // patches on top of patches.
  if (win.__SAF_INTERCEPTOR_INSTALLED__) return;
  win.__SAF_INTERCEPTOR_INSTALLED__ = true;

  // ── VERIFY-IN-NETTAB (ADR-0007 / D-015 §3) ────────────────────────────────
  // These are ChatGPT internals and shift over time. They live in THIS ONE block
  // and the D-015 §3 field list — nowhere else. Confirm against a live network
  // tab before trusting capture; do not edit elsewhere.
  const CONVERSATION_URL_RE =
    /\/backend-api\/conversation\/[0-9a-f-]{16,}(?:[/?#]|$)/i; // VERIFY path
  const REQUIRED_FIELDS = Object.freeze([
    'mapping',       // VERIFY: object keyed by node id
    'current_node',  // VERIFY: id of the displayed leaf
  ]);

  const SOURCE = 'saf-capture';
  const ORIGIN = win.location.origin;

  let warnedShape = false;

  function looksLikeConversation(value) {
    return Boolean(
      value &&
      typeof value === 'object' &&
      value.mapping &&
      typeof value.mapping === 'object',
    );
  }

  // Runtime field-presence assertion (D-015 CE scope / ADR-0007 §4): the first
  // time a captured payload is missing a VERIFY field, emit ONE structured
  // warning so a ChatGPT shape change surfaces in logs within hours, not weeks.
  function assertShapeOnce(convo, url) {
    if (warnedShape) return;
    const missing = REQUIRED_FIELDS.filter((f) => !(f in convo));
    // Probe one message node for the per-message fields the bridge needs.
    let sampleMissing = [];
    try {
      const node = Object.values(convo.mapping || {}).find((n) => n && n.message);
      if (node) {
        const m = node.message;
        if (!m.author || typeof m.author.role !== 'string') sampleMissing.push('message.author.role');
        if (!m.content || !Array.isArray(m.content.parts)) sampleMissing.push('message.content.parts');
        if (typeof m.create_time !== 'number') sampleMissing.push('message.create_time');
      }
    } catch (_) { /* defensive — never throw from the interceptor */ }

    if (missing.length || sampleMissing.length) {
      warnedShape = true;
      // Structured, single-line, no transcript content — just field names.
      win.console?.warn?.(
        '[SAF interceptor] conversation payload shape changed — capture may degrade. ' +
        JSON.stringify({
          url: String(url || '').split('?')[0],
          missing_top_level: missing,
          missing_message_fields: sampleMissing,
        }),
      );
    }
  }

  function publish(convo, url) {
    if (!looksLikeConversation(convo)) return;
    assertShapeOnce(convo, url);
    try {
      win.postMessage(
        { source: SOURCE, kind: 'conversation_json', url: String(url || ''), convo, capturedAt: Date.now() },
        ORIGIN,
      );
    } catch (_) {
      // postMessage can throw on un-cloneable payloads; never break the page.
    }
  }

  function urlOf(input) {
    if (typeof input === 'string') return input;
    if (input && typeof input === 'object') return input.url || '';
    return '';
  }

  // ── patch fetch ────────────────────────────────────────────────────────────
  const _fetch = win.fetch;
  if (typeof _fetch === 'function') {
    win.fetch = async function safFetch(...args) {
      const res = await _fetch.apply(this, args);
      try {
        const url = urlOf(args[0]);
        if (CONVERSATION_URL_RE.test(url)) {
          // clone() so the page's own consumer still reads the body intact.
          res.clone().json().then((convo) => publish(convo, url)).catch(() => {});
        }
      } catch (_) { /* never interfere with the page's fetch result */ }
      return res;
    };
  }

  // ── patch XMLHttpRequest (the app may use XHR for this call) ────────────────
  const XHR = win.XMLHttpRequest;
  if (XHR && XHR.prototype) {
    const _open = XHR.prototype.open;
    const _send = XHR.prototype.send;

    XHR.prototype.open = function safOpen(method, url, ...rest) {
      try {
        this.__saf_url = typeof url === 'string' ? url : '';
        this.__saf_watch = CONVERSATION_URL_RE.test(this.__saf_url);
      } catch (_) { this.__saf_watch = false; }
      return _open.call(this, method, url, ...rest);
    };

    XHR.prototype.send = function safSend(...args) {
      if (this.__saf_watch) {
        this.addEventListener('load', function onLoad() {
          try {
            // responseType '' or 'text' → parse responseText; 'json' → response.
            const raw = this.responseType === 'json'
              ? this.response
              : (this.responseText ? JSON.parse(this.responseText) : null);
            if (raw) publish(raw, this.__saf_url);
          } catch (_) { /* not JSON / parse failure → ignore */ }
        });
      }
      return _send.apply(this, args);
    };
  }
})(window);
