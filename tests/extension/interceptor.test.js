'use strict';

/**
 * tests/extension/interceptor.test.js — MAIN-world conversation-JSON interceptor.
 * OWNER: Chief Engineer (next to extension/interceptor.js).  ADR-0007 / D-015 §1.
 *
 * interceptor.js is an IIFE invoked with the global `window`. We exercise it by
 * injecting a mock window as `global.window`, clearing the require cache so it
 * re-runs per test, then asserting it patches fetch/XHR and publishes the
 * page's conversation payload via postMessage.
 */

const test = require('node:test');
const assert = require('node:assert');
const path = require('node:path');

const INTERCEPTOR = path.resolve(__dirname, '..', '..', 'extension', 'interceptor.js');
const MATCH_URL = 'https://chatgpt.com/backend-api/conversation/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee';

function loadInterceptor(win) {
  delete require.cache[require.resolve(INTERCEPTOR)];
  global.window = win;
  try {
    require(INTERCEPTOR);
  } finally {
    delete global.window;
  }
}

function makeWin(overrides = {}) {
  const messages = [];
  const warnings = [];
  return {
    location: { origin: 'https://chatgpt.com', href: 'https://chatgpt.com/c/abc' },
    console: { warn: (m) => warnings.push(m) },
    postMessage: (msg, origin) => messages.push({ msg, origin }),
    fetch: overrides.fetch,
    XMLHttpRequest: overrides.XHR,
    __messages: messages,
    __warnings: warnings,
  };
}

const tick = () => new Promise((r) => setImmediate(r));

const goodConvo = () => ({
  current_node: 'n1',
  mapping: {
    n1: {
      parent: null,
      message: {
        author: { role: 'user' },
        content: { content_type: 'text', parts: ['hi'] },
        create_time: 1,
      },
    },
  },
});

function fetchReturning(convo) {
  return async (_url) => ({ clone: () => ({ json: async () => convo }) });
}

test('publishes saf-capture on a matching conversation URL', async () => {
  const convo = goodConvo();
  const win = makeWin({ fetch: fetchReturning(convo) });
  loadInterceptor(win);

  const res = await win.fetch(MATCH_URL);
  assert.ok(res, 'original response is returned to the page');
  await tick();

  assert.equal(win.__messages.length, 1);
  const { msg, origin } = win.__messages[0];
  assert.equal(msg.source, 'saf-capture');
  assert.equal(msg.kind, 'conversation_json');
  assert.deepEqual(msg.convo, convo);
  assert.equal(origin, 'https://chatgpt.com');
  assert.equal(win.__warnings.length, 0, 'a well-formed payload emits no shape warning');
});

test('ignores non-conversation URLs', async () => {
  const win = makeWin({ fetch: fetchReturning(goodConvo()) });
  loadInterceptor(win);

  await win.fetch('https://chatgpt.com/backend-api/me');
  await tick();
  assert.equal(win.__messages.length, 0);
});

test('does not publish a body that is not a conversation tree', async () => {
  const win = makeWin({ fetch: fetchReturning({ foo: 1 }) });
  loadInterceptor(win);

  await win.fetch(MATCH_URL);
  await tick();
  assert.equal(win.__messages.length, 0, 'no mapping → not a conversation → no publish');
});

test('emits a structured shape warning when a VERIFY field is missing', async () => {
  const convo = goodConvo();
  // current_node is intentionally absent — inferCurrentNode rescues it, so it no
  // longer appears in missing_top_level. The per-message field is still missing.
  delete convo.current_node;
  delete convo.mapping.n1.message.create_time;     // per-message field gone
  const win = makeWin({ fetch: fetchReturning(convo) });
  loadInterceptor(win);

  await win.fetch(MATCH_URL);
  await tick();

  assert.equal(win.__warnings.length, 1);
  assert.match(win.__warnings[0], /shape changed/);
  assert.match(win.__warnings[0], /message\.create_time/);
  // current_node is now absent from the warning because inferCurrentNode adds it back
  assert.doesNotMatch(win.__warnings[0], /current_node/);
});

test('install is idempotent — a second run does not re-wrap fetch', () => {
  const win = makeWin({ fetch: fetchReturning(goodConvo()) });
  loadInterceptor(win);
  const patched = win.fetch;
  loadInterceptor(win);                            // second injection, same window
  assert.equal(win.fetch, patched, 'patch is applied once');
});

test('captures the conversation payload via XHR as well', async () => {
  class FakeXHR {
    constructor() { this._listeners = {}; }
    open() {}
    send() {}
    addEventListener(type, fn) { (this._listeners[type] ||= []).push(fn); }
    _fire(type) { (this._listeners[type] || []).forEach((fn) => fn.call(this)); }
  }
  const convo = goodConvo();
  const win = makeWin({ fetch: fetchReturning(convo), XHR: FakeXHR });
  loadInterceptor(win);

  const xhr = new win.XMLHttpRequest();
  xhr.open('GET', MATCH_URL);
  xhr.responseText = JSON.stringify(convo);
  xhr.send();
  xhr._fire('load');
  await tick();

  assert.equal(win.__messages.length, 1);
  assert.deepEqual(win.__messages[0].msg.convo, convo);
});
