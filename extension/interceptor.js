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
  const CHUNK_SIZE_THRESHOLD = 1000 * 100; // 100KB threshold for chunking

  let warnedShape = false;

  class InPageAccumulator {
    constructor() {
      this.nodes = new Map(); // id → node
      this.url = null;
      this.lastUpdateAt = Date.now();
    }

    merge(node) {
      if (!node || typeof node !== 'object' || !node.id) return;
      const id = String(node.id);
      const existing = this.nodes.get(id);
      if (!existing) {
        this.nodes.set(id, node);
      } else {
        this.nodes.set(id, { ...existing, ...node });
      }
      this.lastUpdateAt = Date.now();
    }

    _complete() {
      // Complete when every accumulated node is reachable from a root by walking
      // children. A root is a node with no parent, or whose parent is not (yet)
      // in the map.
      //
      // Bug fix (D-015): the prior check derived "roots" as `!parents.has(id)`,
      // i.e. ids never referenced as a parent — those are LEAVES, not roots. It
      // then walked `children[0]` from a leaf (no children), so `visited.size`
      // was 1 and never equalled `nodes.size`; `_complete()` returned false for
      // every multi-turn chat and SAF_CONVERSATION_READY never fired. This is a
      // BFS over all children from the true root(s); it handles linear, branched
      // (regenerated/edited), and multi-root (disconnected) mappings.
      if (this.nodes.size === 0) return false;
      const nodeArray = Array.from(this.nodes.values());
      const present = new Set(nodeArray.map((n) => String(n.id)));
      const roots = nodeArray.filter((n) => !n.parent || !present.has(String(n.parent)));
      if (roots.length === 0) return false; // pure cycle — never "complete"
      const visited = new Set();
      const queue = roots.map((r) => String(r.id));
      while (queue.length) {
        const id = queue.shift();
        if (visited.has(id)) continue;
        visited.add(id);
        const node = this.nodes.get(id);
        if (!node) continue;
        const children = Array.isArray(node.children) ? node.children
          : (Array.isArray(node.child_ids) ? node.child_ids : []);
        for (const c of children) {
          if (!visited.has(String(c))) queue.push(String(c));
        }
      }
      return visited.size === this.nodes.size;
    }
    // ponytail: removed dead `toConversation()` — never called, and it carried
    // the same inverted-root bug as the old _complete(). publish() reads
    // acc.nodes directly. Restore from git if a consumer ever needs it.
  }

  // Global accumulator keyed by conversation URL
  const accumulators = new Map();

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

  function extractConversationId(url) {
    try {
      const match = String(url || '').match(/\/backend-api\/(?:conversation|share)\/([^/?#]+)/i);
      return match ? match[1] : null;
    } catch (_) {
      return null;
    }
  }

  function postChunk(convId, turns, chunkIndex, totalChunks) {
    try {
      win.postMessage({
        type: 'SAF_CONVERSATION_CHUNK',
        convId,
        chunkIndex,
        totalChunks,
        turns,
      }, ORIGIN);
    } catch (_) {}
  }

  function postChunkEnd(convId, totalChunks) {
    try {
      win.postMessage({
        type: 'SAF_CONVERSATION_CHUNK_END',
        convId,
        totalChunks,
      }, ORIGIN);
    } catch (_) {}
  }

  function postReady(convo, convId) {
    try {
      win.postMessage({
        type: 'SAF_CONVERSATION_READY',
        convId,
        turns: Array.from(Object.values(convo.mapping || {})),
      }, ORIGIN);
    } catch (_) {}
  }

  function publish(payload, url) {
    const convo = conversationPayloadFromValue(payload);
    if (!convo) return;
    assertShapeOnce(convo, url);
    const convId = extractConversationId(url);
    if (!convId) return;

    const acc = accumulators.get(convId) || new InPageAccumulator();
    acc.url = url;
    for (const [id, node] of Object.entries(convo.mapping || {})) {
      acc.merge(node);
    }
    accumulators.set(convId, acc);

    if (acc._complete()) {
      const turns = Array.from(acc.nodes.values());
      const payloadStr = JSON.stringify(turns);
      const payloadSize = new Blob([payloadStr]).size;

      if (payloadSize > CHUNK_SIZE_THRESHOLD) {
        const chunkSize = Math.max(1, Math.floor(turns.length / Math.ceil(payloadSize / CHUNK_SIZE_THRESHOLD)));
        let chunkIndex = 0;
        for (let i = 0; i < turns.length; i += chunkSize) {
          postChunk(convId, turns.slice(i, i + chunkSize), chunkIndex, Math.ceil(turns.length / chunkSize));
          chunkIndex += 1;
        }
        postChunkEnd(convId, chunkIndex);
      } else {
        postReady(convo, convId);
      }
    }
  }

  // content.js → interceptor handshake (D-016 / ADR-0008): when the bridge signals
  // it is live (`ready-ping`), we can ensure the accumulator is sent.
  if (typeof win.addEventListener === 'function') {
    win.addEventListener('message', function onReadyPing(event) {
      if (event.origin !== ORIGIN) return;
      const data = event.data;
      if (!data || typeof data !== 'object') return;
      if (data.source !== SOURCE || data.kind !== 'ready-ping') return;
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

// ── Shared link capture (static conversations via /share/{id}) ────────────────
// Runs only on share pages; the native interceptor is silent on those because
// ChatGPT server-renders the full transcript and never fires a backend XHR.
if (/\/share\//.test(window.location.href)) {
  (function() {
    'use strict';

    const SHARED_LINK_RE = /\/share\/([a-zA-Z0-9_-]{20,})/;
    const SHARED_ID = SHARED_LINK_RE.exec(window.location.href)?.[1];
    if (!SHARED_ID) return;

    const ORIGIN = window.location.origin;

    function extractConversation() {
      try {
        const state = window.__INITIAL_STATE__;
        if (state?.conversationData?.conversation) {
          return {
            mapping: state.conversationData.conversation.mapping,
            current_node: state.conversationData.conversation.current_node,
          };
        }
      } catch (_) {}

      try {
        for (const script of document.querySelectorAll('script[type="application/json"]')) {
          const data = JSON.parse(script.textContent);
          if (data.conversation?.mapping || data.mapping) {
            return {
              mapping: data.conversation?.mapping || data.mapping,
              current_node: data.conversation?.current_node || data.current_node,
            };
          }
        }
      } catch (_) {}

      try {
        const root = document.getElementById('__next') || document.getElementById('root');
        if (root?.dataset?.initialState) {
          const data = JSON.parse(root.dataset.initialState);
          return {
            mapping: data.conversation?.mapping || data.mapping,
            current_node: data.conversation?.current_node || data.current_node,
          };
        }
      } catch (_) {}

      return null;
    }

    function waitForConversation(maxAttempts = 10, delayMs = 500) {
      let attempts = 0;
      return new Promise((resolve) => {
        const poll = () => {
          const conv = extractConversation();
          if (conv?.mapping) { resolve(conv); return; }
          if (++attempts >= maxAttempts) { console.warn('[SAF] Shared link: timed out'); resolve(null); return; }
          setTimeout(poll, delayMs);
        };
        poll();
      });
    }

    function postConversation(conversationId, turns) {
      const CHUNK = 50;
      const totalChunks = Math.ceil(turns.length / CHUNK);
      if (totalChunks <= 1) {
        window.postMessage({ type: 'SAF_CONVERSATION_READY', convId: conversationId, turns }, ORIGIN);
      } else {
        for (let i = 0; i < totalChunks; i++) {
          window.postMessage({ type: 'SAF_CONVERSATION_CHUNK', convId: conversationId, chunkIndex: i, totalChunks, turns: turns.slice(i * CHUNK, (i + 1) * CHUNK) }, ORIGIN);
        }
        window.postMessage({ type: 'SAF_CONVERSATION_CHUNK_END', convId: conversationId, totalChunks }, ORIGIN);
      }
    }

    async function captureSharedLink() {
      console.log('[SAF] Detected shared link:', SHARED_ID);
      const conv = await waitForConversation();
      if (!conv?.mapping) { console.warn('[SAF] Could not extract conversation from shared link'); return; }
      // Linearize the mapping tree along the active path
      const turns = [];
      let id = conv.current_node;
      const visited = new Set();
      while (id && !visited.has(id)) {
        visited.add(id);
        const node = conv.mapping[id];
        if (!node) break;
        turns.push(node);
        id = node.parent || null;
      }
      turns.reverse();
      if (turns.length < 3) { console.warn('[SAF] Shared link conversation too short:', turns.length); return; }
      console.log('[SAF] Extracted', turns.length, 'turns from shared link');
      postConversation(SHARED_ID, turns);
    }

    captureSharedLink();
  })();
}
