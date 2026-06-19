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
    /\/backend-api\/(?:conversation|share)\/[^/?#]+(?:[/?#]|$)/i; // VERIFY path
  const REQUIRED_FIELDS = Object.freeze([
    'mapping',       // VERIFY: object keyed by node id
    'current_node',  // VERIFY: id of the displayed leaf
  ]);

  const SOURCE = 'saf-capture';
  const ORIGIN = win.location.origin;

  let warnedShape = false;

  // The most recent valid conversation payload, kept so it can be replayed across
  // the document_start → document_idle gap (D-016 / ADR-0008). The page may fetch
  // the conversation at document_start — before content.js (isolated world,
  // document_idle) has attached its listener — and postMessage is NOT buffered, so
  // that first-load payload would otherwise be lost and capture would silently fall
  // back to the DOM scroll probe. content.js sends one `ready-ping` once it is live;
  // we replay the cache then.
  let cachedConversationPayload = null;

  function inferCurrentNode(mapping) {
    if (!mapping || typeof mapping !== 'object') return null;
    const ids = Object.keys(mapping);
    const parentIds = new Set();
    for (const node of Object.values(mapping)) {
      if (node && typeof node === 'object' && node.parent) {
        parentIds.add(String(node.parent));
      }
    }
    const leaves = ids.filter((id) => !parentIds.has(id));
    const candidates = leaves.length ? leaves : ids;
    let best = null;
    let bestDepth = -1;
    for (const id of candidates) {
      let cursor = id;
      let depth = 0;
      const seen = new Set();
      while (cursor && mapping[cursor] && !seen.has(cursor)) {
        seen.add(cursor);
        depth += 1;
        cursor = mapping[cursor].parent;
      }
      if (depth > bestDepth) {
        best = id;
        bestDepth = depth;
      }
    }
    return best;
  }

  function conversationPayloadFromValue(value, depth = 0, seen = new Set()) {
    if (!value || typeof value !== 'object' || depth > 10 || seen.has(value)) return null;
    seen.add(value);
    if (value.mapping && typeof value.mapping === 'object') {
      const currentNode = value.current_node || value.currentNode || inferCurrentNode(value.mapping);
      if (currentNode) return { ...value, current_node: currentNode };
    }
    if (Array.isArray(value)) {
      for (const item of value) {
        const found = conversationPayloadFromValue(item, depth + 1, seen);
        if (found) return found;
      }
      return null;
    }
    for (const key of [
      'conversation',
      'data',
      'shared_conversation',
      'share',
      'item',
      'props',
      'pageProps',
      'dehydratedState',
      'queries',
      'state',
      'result',
      'response',
    ]) {
      if (key in value) {
        const found = conversationPayloadFromValue(value[key], depth + 1, seen);
        if (found) return found;
      }
    }
    for (const child of Object.values(value)) {
      const found = conversationPayloadFromValue(child, depth + 1, seen);
      if (found) return found;
    }
    return null;
  }

  function looksLikeConversation(value) {
    return Boolean(conversationPayloadFromValue(value));
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

  function postCapture(convo, url, replay) {
    const message = {
      source: SOURCE,
      kind: 'conversation_json',
      url: String(url || ''),
      convo,
      capturedAt: Date.now(),
    };
    // Label replays so the race-fix's effectiveness (how often the first-load
    // capture was rescued from the cache vs. arrived live) is measurable downstream.
    if (replay) message.source_ = 'cache_replay';
    try {
      win.postMessage(message, ORIGIN);
    } catch (_) {
      // postMessage can throw on un-cloneable payloads; never break the page.
    }
  }

  function publish(convo, url) {
    convo = conversationPayloadFromValue(convo);
    if (!convo) return;
    assertShapeOnce(convo, url);
    // Cache the latest valid payload, then post immediately — the normal SPA-nav
    // path where content.js is already listening and does not race.
    cachedConversationPayload = { convo, url };
    postCapture(convo, url, false);
  }

  // content.js → interceptor handshake (D-016 / ADR-0008): when the bridge signals
  // it is live (`ready-ping`), replay the cached conversation ONCE so a first-load
  // fetch that beat the listener is not lost, then clear the cache so a later ping
  // never replays a stale tree.
  if (typeof win.addEventListener === 'function') {
    win.addEventListener('message', function onReadyPing(event) {
      if (event.origin !== ORIGIN) return;
      const data = event.data;
      if (!data || typeof data !== 'object') return;
      if (data.source !== SOURCE || data.kind !== 'ready-ping') return;
      if (!cachedConversationPayload) return;
      const { convo, url } = cachedConversationPayload;
      cachedConversationPayload = null;
      postCapture(convo, url, true);
    });
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
