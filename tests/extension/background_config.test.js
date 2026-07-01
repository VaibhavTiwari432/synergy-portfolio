"use strict";

const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const backgroundPath = path.resolve(__dirname, "../../extension/background.js");

function loadBackground({ storageValues = {} } = {}) {
  const calls = [];
  const timeoutCallbacks = [];
  // live timers by id — clearTimeout removes, so the map reflects only ARMED
  // timers (used by the capture-watchdog tests to assert reset behaviour).
  const timers = new Map();
  const values = { ...storageValues };
  const listeners = {
    alarm: [],
    message: [],
    action: [],
    updated: [],
  };

  const chrome = {
    runtime: {
      id: "saf-extension",
      lastError: null,
      onMessage: { addListener(listener) { listeners.message.push(listener); } },
      sendMessage(_message, callback) { callback?.(); },
    },
    storage: {
      local: {
        get(keys, callback) {
          if (keys === null) callback({ ...values });
          else if (typeof keys === "string") callback({ [keys]: values[keys] });
          else if (Array.isArray(keys)) callback(Object.fromEntries(keys.map((key) => [key, values[key]])));
          else callback({ ...keys, ...values });
        },
        set(next, callback) {
          Object.assign(values, next);
          callback?.();
        },
        remove(keys, callback) {
          for (const key of [].concat(keys)) delete values[key];
          callback?.();
        },
      },
    },
    alarms: {
      create() {},
      onAlarm: { addListener(listener) { listeners.alarm.push(listener); } },
    },
    action: {
      setBadgeText() { return Promise.resolve(); },
      setBadgeBackgroundColor() { return Promise.resolve(); },
      setTitle() { return Promise.resolve(); },
      onClicked: { addListener(listener) { listeners.action.push(listener); } },
    },
    tabs: {
      query(_query, callback) {
        callback?.([]);
        return Promise.resolve([]);
      },
      sendMessage(_tabId, _message, callback) { callback?.(); },
      reload(_tabId, _options, callback) { callback?.(); },
      create() {},
      onUpdated: { addListener(listener) { listeners.updated.push(listener); } },
    },
  };

  const context = {
    console,
    chrome,
    URL,
    AbortController,
    setTimeout(callback) {
      const id = timeoutCallbacks.push(callback); // 1-based id
      timers.set(id, callback);
      return id;
    },
    clearTimeout(id) {
      timers.delete(id);
    },
    fetch: async (url, options = {}) => {
      calls.push({ url: String(url), options });
      return {
        ok: true,
        status: 200,
        async json() {
          if (String(url).endsWith("/v1/ingest")) {
            return { chat_id: "chat-1", status: "pending", message: "queued" };
          }
          return { ok: true };
        },
      };
    },
  };
  context.self = context;

  vm.runInNewContext(fs.readFileSync(backgroundPath, "utf8"), context, {
    filename: backgroundPath,
  });
  timeoutCallbacks.length = 0;
  timers.clear(); // discard any timers armed during startup
  return { self: context, calls, values, listeners, timeoutCallbacks, timers, chrome };
}

test("background API client uses local endpoint without inventing a shared API key", async () => {
  const { self, calls } = loadBackground();

  const result = await self.SAFApiClient.ingestChat({ any: "payload" });

  assert.equal(result.ok, true);
  const ingest = calls.find((call) => call.url.endsWith("/v1/ingest"));
  assert.ok(ingest);
  assert.equal(ingest.url, "http://127.0.0.1:8000/v1/ingest");
  assert.equal(ingest.options.headers["X-API-Key"], undefined);
});

test("background API client preserves explicit remote endpoint and key", async () => {
  const { self, calls } = loadBackground({
    storageValues: {
      api_endpoint: "https://api.example.test",
      api_key: "remote-key",
    },
  });

  await self.SAFApiClient.getPortfolio("user-1");

  const request = calls.find((call) => call.url.endsWith("/v1/users/user-1/portfolio"));
  assert.ok(request);
  assert.equal(request.url, "https://api.example.test/v1/users/user-1/portfolio");
  assert.equal(request.options.headers["X-API-Key"], "remote-key");
});

test("background API client strips trailing slashes from configured endpoints", async () => {
  const { self, calls } = loadBackground({
    storageValues: {
      api_endpoint: "https://api.example.test///",
      api_key: "remote-key",
    },
  });

  await self.SAFApiClient.getPortfolio("user-1");

  const request = calls.find((call) => call.url.endsWith("/v1/users/user-1/portfolio"));
  assert.ok(request);
  assert.equal(request.url, "https://api.example.test/v1/users/user-1/portfolio");
});

test("background API client falls back when stored endpoint is blank", async () => {
  const { self, calls } = loadBackground({
    storageValues: {
      api_endpoint: "   ",
    },
  });

  await self.SAFApiClient.getPortfolio("user-1");

  const request = calls.find((call) => call.url.endsWith("/v1/users/user-1/portfolio"));
  assert.ok(request);
  assert.equal(request.url, "http://127.0.0.1:8000/v1/users/user-1/portfolio");
  assert.equal(request.options.headers["X-API-Key"], undefined);
});

// ── capture watchdog (long-chat capture must not be guillotined) ──────────────

// NB: these assert on the watchdog's OWN timer ids, not the global timers.size.
// Background startup arms-then-clears its own timers on the microtask queue, so
// the global count is nondeterministic across an `await`; the watchdog's two ids
// are captured synchronously and tracked individually.

test("capture watchdog arms a stall + absolute timer and fails closed on silence", async () => {
  const { self, chrome, timers } = loadBackground();
  // a capture that never answers (long chat still scanning, or a hung content script)
  chrome.tabs.sendMessage = () => {};

  const pending = self._sendAnalyseNowToTab(42);
  const armed = [...timers.keys()]; // captured before any await — only the watchdog's timers
  assert.equal(armed.length, 2, "stall + absolute watchdog timers armed");

  // firing either timer fails closed with the routed reason (panel shows retry)
  [...timers.values()][0]();
  await assert.rejects(pending, /capture_timeout/);
  assert.ok(armed.every((id) => !timers.has(id)), "watchdog cleaned up its own timers on failure");
});

test("capture watchdog: a progress event re-arms the stall window (long capture survives)", async () => {
  const { self, chrome, listeners, timers } = loadBackground();
  chrome.tabs.sendMessage = () => {}; // hold the capture open

  const pending = self._sendAnalyseNowToTab(42);
  const armed = [...timers.keys()];
  assert.equal(armed.length, 2);

  // a healthy capture keeps emitting progress from its tab; each event must reset
  // the stall timer so the capture is never killed mid-scan. The sender must pass
  // _isTrustedSafMessageSender — a supported-host tab (chatgpt.com).
  listeners.message.forEach((l) =>
    l(
      { type: "SAF_ANALYSE_PROGRESS", progress: { stage: "capturing", percent: 40 } },
      { id: "saf-extension", tab: { id: 42, url: "https://chatgpt.com/c/thread" } },
      () => {},
    ));

  // the absolute timer is untouched; the stall timer was cleared and replaced by
  // a fresh one (new id), so exactly one of the two original ids survives.
  const after = [...timers.keys()];
  assert.equal(after.length, 2, "still exactly two watchdog timers");
  const reused = after.filter((id) => armed.includes(id));
  assert.equal(reused.length, 1, "absolute timer kept, stall timer re-armed with a new id");

  // settle the pending promise so the test leaves nothing dangling
  [...timers.values()][0]();
  await assert.rejects(pending, /capture_timeout/);
});

test("capture watchdog clears cleanly when the capture responds", async () => {
  const { self, chrome, timers } = loadBackground();
  let armedDuringCall = [];
  chrome.tabs.sendMessage = (_tabId, _msg, cb) => {
    armedDuringCall = [...timers.keys()]; // both watchdog timers are live at send time
    cb({ ok: true, capture: { turns: [] } });
  };

  const reply = await self._sendAnalyseNowToTab(42);
  assert.equal(reply.ok, true);
  assert.equal(armedDuringCall.length, 2, "both watchdog timers armed before the response");
  assert.ok(armedDuringCall.every((id) => !timers.has(id)), "both watchdog timers cleared on response");
});

// ── capture validation (role balance tolerates multi-part assistant turns) ────

test("capture validation admits a tool-heavy chat with multi-part assistant turns", () => {
  const { self } = loadBackground();
  // a long, tool-using chat: each user turn draws a 2-node assistant response
  // (preamble + answer). Raw nodes are imbalanced (3 user, 6 assistant) but they
  // are 3 logical assistant turns — the gate must admit it.
  const turns = [];
  for (let i = 0; i < 3; i += 1) {
    turns.push({ role: "user", text: `Question ${i}` });
    turns.push({ role: "assistant", text: `Let me look into ${i}` });
    turns.push({ role: "assistant", text: `Answer ${i}` });
  }
  assert.equal(self._captureValidationError({ turns }), null);
});

test("capture validation still rejects a truncated chat (consecutive users not merged)", () => {
  const { self } = loadBackground();
  const turns = [
    ...Array.from({ length: 8 }, (_v, i) => ({ role: "user", text: `Question ${i}` })),
    { role: "assistant", text: "Answer" },
  ];
  assert.equal(
    self._captureValidationError({ turns }),
    "capture turn roles are imbalanced (user=8, assistant=1)",
  );
});

test("background ignores SAF runtime messages from unsupported senders", async () => {
  const { listeners, calls } = loadBackground();
  let responded = false;

  const result = listeners.message[0](
    { type: "SAF_PANEL_DELETE_DATA", userRef: "user-1" },
    { id: "saf-extension", tab: { id: 12, url: "https://example.com/" } },
    () => { responded = true; },
  );

  assert.equal(result, undefined);
  assert.equal(responded, false);
  assert.equal(calls.some((call) => call.options?.method === "DELETE"), false);
});

test("toolbar reload recovery retries opening the modal until content script is ready", async () => {
  const { listeners, timeoutCallbacks, chrome } = loadBackground();
  let sendAttempts = 0;
  let reloadCalled = false;
  chrome.tabs.sendMessage = (_tabId, _message, callback) => {
    sendAttempts += 1;
    chrome.runtime.lastError = sendAttempts < 3 ? { message: "Receiving end does not exist" } : null;
    callback?.();
  };
  chrome.tabs.reload = (_tabId, _options, callback) => {
    reloadCalled = true;
    callback?.();
  };

  listeners.action[0]({ id: 7, url: "https://chatgpt.com/c/thread" });
  assert.equal(reloadCalled, true);

  listeners.updated[0](7, { status: "complete" }, { url: "https://chatgpt.com/c/thread" });
  assert.equal(timeoutCallbacks.length, 1);
  timeoutCallbacks.shift()();

  assert.equal(sendAttempts, 3);
});
