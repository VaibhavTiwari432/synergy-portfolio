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
      timeoutCallbacks.push(callback);
      return timeoutCallbacks.length;
    },
    clearTimeout,
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
  return { self: context, calls, values, listeners, timeoutCallbacks, chrome };
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
