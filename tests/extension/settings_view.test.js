"use strict";

const { afterEach, test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const settingsPath = path.resolve(__dirname, "../../extension/panel/views/settings.js");

class FakeClassList {
  constructor() {
    this.values = new Set();
  }

  toggle(value, enabled) {
    if (enabled) this.values.add(value);
    else this.values.delete(value);
  }
}

class FakeElement {
  constructor() {
    this.listeners = new Map();
    this.classList = new FakeClassList();
    this.textContent = "";
    this.value = "";
    this.checked = false;
    this.disabled = false;
    this.hidden = false;
  }

  addEventListener(type, handler) {
    if (!this.listeners.has(type)) this.listeners.set(type, new Set());
    this.listeners.get(type).add(handler);
  }

  removeEventListener(type, handler) {
    this.listeners.get(type)?.delete(handler);
  }

  click() {
    this.listeners.get("click")?.forEach((handler) => handler({ target: this, currentTarget: this }));
  }
}

class FakeShadowRoot {
  constructor() {
    this.nodes = new Map();
    [
      "saf-settings-status",
      "saf-settings-retry",
      "saf-setting-user-ref",
      "saf-setting-api-endpoint",
      "saf-setting-api-key",
      "saf-setting-consent",
      "saf-settings-save-connection",
      "saf-setting-auto-analyse",
      "saf-setting-notification-dot",
      "saf-setting-calibration-opt-in",
      "saf-settings-delete-data",
    ].forEach((id) => this.nodes.set(id, new FakeElement()));
    this.events = [];
  }

  getElementById(id) {
    return this.nodes.get(id) || null;
  }

  dispatchEvent(event) {
    this.events.push(event);
  }
}

function loadInitSettingsView() {
  const source = fs.readFileSync(settingsPath, "utf8")
    .replace("export function initSettingsView", "function initSettingsView");
  const context = {
    console,
    URL,
    CustomEvent: class {
      constructor(type, init = {}) {
        this.type = type;
        this.detail = init.detail;
        this.bubbles = init.bubbles;
      }
    },
    globalThis,
  };
  vm.runInNewContext(`${source}\nthis.initSettingsView = initSettingsView;`, context);
  return context.initSettingsView;
}

async function flush() {
  await new Promise((resolve) => setImmediate(resolve));
  await new Promise((resolve) => setImmediate(resolve));
}

afterEach(() => {
  delete globalThis.SAFStorage;
  delete globalThis.SAFApiClient;
});

test("saving a remote connection with a blank key clears any stale stored API key", async () => {
  const values = {
    user_ref: "user-1",
    api_endpoint: "http://localhost:8000",
    api_key: "old-key",
    consent_enabled: true,
  };
  const removed = [];
  const setCalls = [];
  globalThis.SAFStorage = {
    STORAGE_KEYS: {
      ONBOARDING_COMPLETE: "onboarding_complete",
      USER_REF: "user_ref",
      API_ENDPOINT: "api_endpoint",
      API_KEY: "api_key",
      CONSENT_ENABLED: "consent_enabled",
    },
    async get(key, fallback) {
      return Object.prototype.hasOwnProperty.call(values, key) ? values[key] : fallback;
    },
    async getMany(keys) {
      return Object.fromEntries(keys.map((key) => [key, values[key]]));
    },
    async set(next) {
      setCalls.push(next);
      Object.assign(values, next);
    },
    async remove(keys) {
      for (const key of [].concat(keys)) {
        removed.push(key);
        delete values[key];
      }
    },
  };
  globalThis.SAFApiClient = {
    DEFAULT_ENDPOINT: "http://localhost:8000",
    async getSettings() {
      return { ok: true, data: { auto_analyse: false, calibration_opt_in: false } };
    },
    async checkHealth() {
      return false;
    },
  };

  const shadow = new FakeShadowRoot();
  const initSettingsView = loadInitSettingsView();
  initSettingsView(shadow);
  await flush();

  shadow.getElementById("saf-setting-user-ref").value = "user-1";
  shadow.getElementById("saf-setting-api-endpoint").value = "https://api.example.test";
  shadow.getElementById("saf-setting-api-key").value = "";
  shadow.getElementById("saf-setting-consent").checked = true;
  shadow.getElementById("saf-settings-save-connection").click();
  await flush();

  assert.deepEqual(removed, ["api_key"]);
  assert.equal(values.api_key, undefined);
  assert.equal(values.api_endpoint, "https://api.example.test");
  assert.equal(setCalls.at(-1).api_key, undefined);
  assert.equal(shadow.events.at(-1).type, "saf-settings-updated");
});

test("saving connection rejects non-http endpoints before storage changes", async () => {
  const values = {
    user_ref: "user-1",
    api_endpoint: "http://localhost:8000",
    consent_enabled: true,
  };
  let setCalls = 0;
  let removeCalls = 0;
  globalThis.SAFStorage = {
    STORAGE_KEYS: {
      ONBOARDING_COMPLETE: "onboarding_complete",
      USER_REF: "user_ref",
      API_ENDPOINT: "api_endpoint",
      API_KEY: "api_key",
      CONSENT_ENABLED: "consent_enabled",
    },
    async get(key, fallback) {
      return Object.prototype.hasOwnProperty.call(values, key) ? values[key] : fallback;
    },
    async getMany(keys) {
      return Object.fromEntries(keys.map((key) => [key, values[key]]));
    },
    async set() {
      setCalls += 1;
    },
    async remove() {
      removeCalls += 1;
    },
  };
  globalThis.SAFApiClient = {
    DEFAULT_ENDPOINT: "http://localhost:8000",
    async getSettings() {
      return { ok: true, data: { auto_analyse: false, calibration_opt_in: false } };
    },
    async checkHealth() {
      return true;
    },
  };

  const shadow = new FakeShadowRoot();
  const initSettingsView = loadInitSettingsView();
  initSettingsView(shadow);
  await flush();

  shadow.getElementById("saf-setting-user-ref").value = "user-1";
  shadow.getElementById("saf-setting-api-endpoint").value = "localhost:8000";
  shadow.getElementById("saf-settings-save-connection").click();
  await flush();

  assert.equal(setCalls, 0);
  assert.equal(removeCalls, 0);
  assert.match(shadow.getElementById("saf-settings-status").textContent, /must start with http/);
});

test("saving connection warns when backend lacks a scoring judge key", async () => {
  const values = {
    user_ref: "user-1",
    api_endpoint: "http://localhost:8000",
    consent_enabled: true,
  };
  globalThis.SAFStorage = {
    STORAGE_KEYS: {
      ONBOARDING_COMPLETE: "onboarding_complete",
      USER_REF: "user_ref",
      API_ENDPOINT: "api_endpoint",
      API_KEY: "api_key",
      CONSENT_ENABLED: "consent_enabled",
    },
    async get(key, fallback) {
      return Object.prototype.hasOwnProperty.call(values, key) ? values[key] : fallback;
    },
    async getMany(keys) {
      return Object.fromEntries(keys.map((key) => [key, values[key]]));
    },
    async set(next) {
      Object.assign(values, next);
    },
    async remove(keys) {
      for (const key of [].concat(keys)) delete values[key];
    },
  };
  globalThis.SAFApiClient = {
    DEFAULT_ENDPOINT: "http://localhost:8000",
    async getSettings() {
      return { ok: true, data: { auto_analyse: false, calibration_opt_in: false } };
    },
    async getHealth() {
      return { ok: true, data: { status: "ok", db: "ok", scoring: "missing_judge_key" } };
    },
  };

  const shadow = new FakeShadowRoot();
  const initSettingsView = loadInitSettingsView();
  initSettingsView(shadow);
  await flush();

  shadow.getElementById("saf-setting-user-ref").value = "user-1";
  shadow.getElementById("saf-setting-api-endpoint").value = "http://localhost:8000";
  shadow.getElementById("saf-setting-api-key").value = "local-key";
  shadow.getElementById("saf-settings-save-connection").click();
  await flush();

  assert.match(shadow.getElementById("saf-settings-status").textContent, /GEMINI_API_KEY or GOOGLE_API_KEY/);
  assert.equal(shadow.getElementById("saf-settings-status").classList.values.has("is-error"), true);
});
