'use strict';

const { afterEach, test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const detailPath = path.resolve(__dirname, '../../extension/panel/views/detail.js');

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
}

class FakeStyle {
  constructor() {
    this.values = new Map();
  }

  setProperty(name, value) {
    this.values.set(name, value);
  }
}

class FakeElement {
  constructor(tagName = 'div') {
    this.tagName = tagName.toUpperCase();
    this.children = [];
    this.listeners = new Map();
    this.classList = new FakeClassList();
    this.dataset = {};
    this.style = new FakeStyle();
    this.hidden = false;
    this.disabled = false;
    this.textContent = '';
    this.value = '';
    this.className = '';
    this.title = '';
  }

  appendChild(child) {
    if (child?.isFragment) {
      this.children.push(...child.children);
      return child;
    }
    this.children.push(child);
    return child;
  }

  replaceChildren(...children) {
    this.children = [...children];
  }

  setAttribute(name, value) {
    this[name] = String(value);
  }

  addEventListener(type, handler) {
    if (!this.listeners.has(type)) this.listeners.set(type, new Set());
    this.listeners.get(type).add(handler);
  }

  removeEventListener(type, handler) {
    this.listeners.get(type)?.delete(handler);
  }
}

class FakeFragment extends FakeElement {
  constructor() {
    super('fragment');
    this.isFragment = true;
  }
}

class FakeShadowRoot {
  constructor() {
    this.nodes = new Map();
    this.listeners = new Map();
    [
      'saf-detail-empty',
      'saf-detail-content',
      'saf-detail-title',
      'saf-detail-meta',
      'saf-dimension-list',
      'saf-trend-section',
      'saf-flags-section',
      'saf-flag-list',
      'saf-remarks-text',
      'saf-feedback-up',
      'saf-feedback-down',
      'saf-feedback-note',
      'saf-feedback-count',
      'saf-feedback-submit',
      'saf-feedback-status',
    ].forEach((id) => this.nodes.set(id, new FakeElement()));
  }

  getElementById(id) {
    return this.nodes.get(id) || null;
  }

  addEventListener(type, handler) {
    if (!this.listeners.has(type)) this.listeners.set(type, new Set());
    this.listeners.get(type).add(handler);
  }

  removeEventListener(type, handler) {
    this.listeners.get(type)?.delete(handler);
  }

  dispatchEvent(event) {
    this.listeners.get(event.type)?.forEach((handler) => handler(event));
  }
}

function loadInitDetailView() {
  const source = fs.readFileSync(detailPath, 'utf8')
    .replace('export function initDetailView', 'function initDetailView');
  const sandboxGlobal = {
    SAFApiClient: globalThis.SAFApiClient,
    SAFStorage: globalThis.SAFStorage,
  };
  const context = {
    console,
    HTMLButtonElement: FakeElement,
    document: {
      createElement: (tagName) => new FakeElement(tagName),
      createDocumentFragment: () => new FakeFragment(),
    },
    globalThis: sandboxGlobal,
  };
  vm.runInNewContext(`${source}\nthis.initDetailView = initDetailView;`, context);
  return context.initDetailView;
}

async function flush() {
  await new Promise((resolve) => setImmediate(resolve));
}

afterEach(() => {
  delete globalThis.SAFApiClient;
  delete globalThis.SAFStorage;
});

test('detail view ignores extra score fields and falls back when CI is missing', async () => {
  globalThis.SAFStorage = {
    STORAGE_KEYS: { USER_REF: 'user_ref' },
    async get() { return 'user-1'; },
  };
  globalThis.SAFApiClient = {
    async getChatScore() {
      return {
        ok: true,
        data: {
          session_id: 'chat-1',
          conversation_id: 'conv-1',
          tier: 1,
          feedback_given: false,
          profile: {
            EC: { status: 'OK', value: 0.55, extra_future_field: true },
          },
          flags: { future_flag: false },
          report: {
            observed: ['Observed note'],
            unexpected_future_section: ['ignored'],
          },
          profile_radar_past: { EC: 0.4 },
          profile_radar_present: { EC: 0.55 },
        },
      };
    },
  };

  const shadow = new FakeShadowRoot();
  const initDetailView = loadInitDetailView();
  initDetailView(shadow);
  shadow.dispatchEvent({ type: 'saf-chat-selected', detail: { chatId: 'chat-1' } });
  await flush();
  await flush();

  const dimensionList = shadow.getElementById('saf-dimension-list');
  const ecRow = dimensionList.children.find((row) => row.children[0]?.textContent === 'EC');
  assert.ok(ecRow, 'EC row should render');
  assert.match(ecRow.children[3].textContent, /\?/);
  assert.equal(shadow.getElementById('saf-detail-meta').textContent, 'Tier 1');
  assert.match(shadow.getElementById('saf-remarks-text').value, /Observed note/);
});
