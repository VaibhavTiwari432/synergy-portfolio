'use strict';

const { afterEach, test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const chatsPath = path.resolve(__dirname, '../../extension/panel/views/chats.js');

class FakeClassList {
  constructor() {
    this.values = new Set();
  }

  add(value) {
    this.values.add(value);
  }

  toggle(value, enabled) {
    if (enabled) this.values.add(value);
    else this.values.delete(value);
  }

  contains(value) {
    return this.values.has(value);
  }
}

class FakeElement {
  constructor(tagName = 'div') {
    this.tagName = tagName.toUpperCase();
    this.children = [];
    this.listeners = new Map();
    this.classList = new FakeClassList();
    this.dataset = {};
    this.attributes = new Map();
    this.hidden = false;
    this.disabled = false;
    this.textContent = '';
    this.value = '';
    this.type = '';
    this.className = '';
  }

  appendChild(child) {
    this.children.push(child);
    return child;
  }

  replaceChildren(...children) {
    this.children = [...children];
  }

  setAttribute(name, value) {
    this.attributes.set(name, String(value));
  }

  addEventListener(type, handler) {
    if (!this.listeners.has(type)) this.listeners.set(type, new Set());
    this.listeners.get(type).add(handler);
  }

  removeEventListener(type, handler) {
    this.listeners.get(type)?.delete(handler);
  }

  click() {
    this.listeners.get('click')?.forEach((handler) => handler({ currentTarget: this, target: this }));
  }
}

class FakeShadowRoot {
  constructor() {
    this.nodes = new Map();
    [
      'saf-chat-counts',
      'saf-chat-status',
      'saf-chat-retry',
      'saf-current-chat-section',
      'saf-current-chat-list',
      'saf-chat-list',
    ].forEach((id) => this.nodes.set(id, new FakeElement()));
    this.search = new FakeElement('input');
  }

  getElementById(id) {
    return this.nodes.get(id) || null;
  }

  querySelector(selector) {
    return selector === '.saf-search-input' ? this.search : null;
  }

  dispatchEvent(event) {
    this.lastEvent = event;
  }
}

function loadInitChatsView(contextOverrides = {}) {
  const source = fs.readFileSync(chatsPath, 'utf8')
    .replace('export function initChatsView', 'function initChatsView');
  const sandboxGlobal = {
    SAFApiClient: globalThis.SAFApiClient,
    SAFStorage: globalThis.SAFStorage,
    ...(contextOverrides.globalThis || {}),
  };
  const context = {
    console,
    URL,
    CustomEvent: class {
      constructor(type, init = {}) {
        this.type = type;
        this.detail = init.detail;
      }
    },
    document: {
      createElement: (tagName) => new FakeElement(tagName),
    },
    ...contextOverrides,
    globalThis: sandboxGlobal,
  };
  vm.runInNewContext(`${source}\nthis.initChatsView = initChatsView;`, context);
  return context.initChatsView;
}

async function flush() {
  await new Promise((resolve) => setImmediate(resolve));
}

afterEach(() => {
  delete globalThis.SAFApiClient;
  delete globalThis.SAFStorage;
});

test('Analyse is deduped while a chat analysis request is in flight', async () => {
  let triggerCalls = 0;
  let resolveTrigger;
  globalThis.SAFStorage = {
    STORAGE_KEYS: { USER_REF: 'user_ref' },
    async get() { return 'user-1'; },
  };
  globalThis.SAFApiClient = {
    async getChatList() {
      return {
        ok: true,
        data: {
          chats: [{ chat_id: 'chat-1', conversation_id: 'conv-1', status: 'unsubmitted', captured_at: '2026-06-21T00:00:00Z' }],
          summary: { total: 1, scored: 0, pending: 0, failed: 0 },
        },
      };
    },
    triggerAnalysis() {
      triggerCalls += 1;
      return new Promise((resolve) => {
        resolveTrigger = resolve;
      });
    },
  };

  const initChatsView = loadInitChatsView({
    globalThis: {
      location: { href: 'https://chatgpt.com/' },
      setInterval() { return 1; },
      clearInterval() {},
    },
  });
  const shadow = new FakeShadowRoot();
  initChatsView(shadow);
  await flush();

  const row = shadow.getElementById('saf-chat-list').children[0];
  const button = row.children[row.children.length - 1];
  button.click();
  button.click();

  assert.equal(triggerCalls, 1);
  resolveTrigger({ ok: true });
});

test('stuck pending chats stop polling and become retryable failed rows', async () => {
  let intervalCallback;
  globalThis.SAFStorage = {
    STORAGE_KEYS: { USER_REF: 'user_ref' },
    async get() { return 'user-1'; },
  };
  globalThis.SAFApiClient = {
    async getChatList() {
      return {
        ok: true,
        data: {
          chats: [{ chat_id: 'chat-1', conversation_id: 'conv-1', status: 'pending', captured_at: '2026-06-21T00:00:00Z' }],
          summary: { total: 1, scored: 0, pending: 1, failed: 0 },
        },
      };
    },
    async triggerAnalysis() {
      return { ok: true };
    },
  };

  const initChatsView = loadInitChatsView({
    globalThis: {
      location: { href: 'https://chatgpt.com/' },
      setInterval(callback) {
        intervalCallback = callback;
        return 1;
      },
      clearInterval() {},
    },
  });
  const shadow = new FakeShadowRoot();
  initChatsView(shadow);
  await flush();

  for (let index = 0; index < 31; index += 1) {
    intervalCallback();
    await flush();
  }

  const row = shadow.getElementById('saf-chat-list').children[0];
  assert.equal(row.dataset.status, 'failed');
  assert.match(shadow.getElementById('saf-chat-status').textContent, /taking longer than expected/);
});
