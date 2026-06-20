"use strict";

/**
 * tests/extension/interception_race.test.js — D-016 / ADR-0008.
 *
 * The document_start → document_idle race: interceptor.js (MAIN world,
 * document_start) patches fetch immediately, but content.js (isolated world,
 * document_idle) attaches its `saf-capture` listener only after the async consent
 * check. A conversation already open when the extension loads is fetched before the
 * listener exists, and postMessage is not buffered — so without the cache-and-replay
 * handshake that first-load payload is lost and capture degrades to the DOM fallback.
 *
 * This test reproduces that ordering against a shared window message bus and asserts
 * the cached payload is replayed (labelled source_: 'cache_replay') and ingested by
 * content.js as a high-fidelity interception capture.
 */

const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");

const INTERCEPTOR = path.resolve(__dirname, "..", "..", "extension", "interceptor.js");
const { createCaptureController, INTERCEPT_SOURCE } = require("../../extension/content.js");

const MATCH_URL =
  "https://chatgpt.com/backend-api/conversation/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee";

const tick = () => new Promise((resolve) => setImmediate(resolve));

const preCachedConvo = () => ({
  current_node: "n1",
  mapping: {
    n1: {
      parent: null,
      message: {
        id: "n1",
        author: { role: "user" },
        content: { content_type: "text", parts: ["question from before install"] },
        create_time: 1,
      },
    },
  },
});

// A shared window: interceptor.js (MAIN) and content.js (isolated) both register
// here, and postMessage is delivered ASYNCHRONOUSLY to match real browser semantics
// (the property the "ping then attach" ordering relies on).
function makeBus() {
  const listeners = [];
  const messages = [];
  const bus = {
    location: { origin: "https://chatgpt.com", href: "https://chatgpt.com/c/abc" },
    console: { warn() {} },
    addEventListener(type, fn) {
      if (type === "message") listeners.push(fn);
    },
    removeEventListener(type, fn) {
      if (type !== "message") return;
      const i = listeners.indexOf(fn);
      if (i >= 0) listeners.splice(i, 1);
    },
    postMessage(data, origin) {
      messages.push({ data, origin });
      Promise.resolve().then(() => {
        for (const fn of listeners.slice()) {
          fn({ origin: bus.location.origin, data, source: bus });
        }
      });
    },
    __messages: messages,
  };
  return bus;
}

function loadInterceptor(win) {
  delete require.cache[require.resolve(INTERCEPTOR)];
  global.window = win;
  try {
    require(INTERCEPTOR);
  } finally {
    delete global.window;
  }
}

function fetchReturning(convo) {
  return async (_url) => ({ clone: () => ({ json: async () => convo }) });
}

function fakeDocument() {
  return {
    title: "Pre-cached chat",
    body: {},
    documentElement: {},
    querySelector: () => null,
    querySelectorAll: () => [],
    addEventListener: () => {},
    removeEventListener: () => {},
  };
}

class FakeMutationObserver {
  observe() {}
  disconnect() {}
}

test("cache-and-replay rescues a conversation that loaded before the bridge attached", async () => {
  const convo = preCachedConvo();
  const bus = makeBus();
  bus.fetch = fetchReturning(convo);

  // ── document_start: interceptor installs and the page fetches the conversation
  //    while content.js does not yet exist (no isolated-world listener). ──
  loadInterceptor(bus);
  await bus.fetch(MATCH_URL);
  await tick(); // let the interceptor's clone().json().then(publish) run → caches

  // The immediate post happened but had no consumer; nothing was ingested yet.
  assert.equal(
    bus.__messages.filter((m) => m.data.source_ === "cache_replay").length,
    0,
    "no replay before the bridge pings",
  );

  // ── document_idle: content.js comes up and consent passes → enableCapture
  //    sends the ready-ping and attaches its listener. ──
  const sent = [];
  const controller = createCaptureController({
    document: fakeDocument(),
    location: bus.location,
    window: bus,
    MutationObserver: FakeMutationObserver,
    now: () => 1000,
    setTimeout: () => 1,
    clearTimeout: () => {},
    sendMessage: (message) => sent.push(message),
    warn: () => {},
  });
  controller.enableCapture();
  await tick(); // drain: ready-ping → interceptor replay → content.js ingest

  // The interceptor re-emitted the cached payload, labelled for measurement.
  const replay = bus.__messages.find(
    (m) => m.data.kind === "conversation_json" && m.data.source_ === "cache_replay",
  );
  assert.ok(replay, "interceptor replayed the cached payload as cache_replay");
  assert.deepEqual(replay.data.convo, convo);

  // content.js ingested the replay as a high-fidelity interception capture, not the
  // DOM fallback.
  const ready = sent.find((m) => m.type === "SAF_CAPTURE_READY");
  assert.ok(ready, "content.js emitted a capture from the replayed payload");
  assert.equal(ready.capture.capture_method, "interception");
  assert.equal(ready.capture.capture_complete, true);
  assert.deepEqual(
    ready.capture.turns.map((t) => t.text),
    ["question from before install"],
  );
});

test("the cache is replayed only once per ping — a second ping is a no-op", async () => {
  const bus = makeBus();
  bus.fetch = fetchReturning(preCachedConvo());
  loadInterceptor(bus);
  await bus.fetch(MATCH_URL);
  await tick();

  // First ping replays.
  bus.postMessage({ source: INTERCEPT_SOURCE, kind: "ready-ping" }, bus.location.origin);
  await tick();
  // Second ping after the cache was cleared → no further replay.
  bus.postMessage({ source: INTERCEPT_SOURCE, kind: "ready-ping" }, bus.location.origin);
  await tick();

  const replays = bus.__messages.filter((m) => m.data.source_ === "cache_replay");
  assert.equal(replays.length, 1, "exactly one replay; the cache does not re-fire");
});
