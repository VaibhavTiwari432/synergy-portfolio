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
      'saf-evidence-section',
      'saf-evidence-work',
      'saf-evidence-dims',
      'saf-evidence-log',
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
  // Missing CI now shows a calm "CI n/a" in the CI cell, never a bare "±?".
  assert.equal(textOf(ecRow.children[3]), 'CI n/a');
  assert.doesNotMatch(textOf(ecRow.children[3]), /±/);
  assert.equal(shadow.getElementById('saf-detail-meta').textContent, 'Tier 1');
  assert.match(shadow.getElementById('saf-remarks-text').value, /Observed note/);
});

// Recursively gather visible text from a FakeElement tree (children carry text
// now that CI/chips are nested spans rather than a single textContent).
function textOf(node) {
  if (!node) return '';
  if (node.children && node.children.length) {
    return node.children.map(textOf).join(' ').replace(/\s+/g, ' ').trim();
  }
  return String(node.textContent || '');
}

function tableTexts(wrap) {
  // wrap -> table -> [thead, tbody]; return tbody rows as arrays of cell text.
  const table = wrap.children[0];
  const tbody = table?.children?.find((c) => c.tagName === 'TBODY');
  return (tbody?.children || []).map((tr) => tr.children.map((td) => textOf(td)));
}

function scoreClientWith(data) {
  return {
    async getChatScore() { return { ok: true, data }; },
    async getChatWork() { return { ok: true, data: { status: 'absent', levels: [] } }; },
  };
}

async function renderWith(client) {
  globalThis.SAFStorage = { STORAGE_KEYS: { USER_REF: 'user_ref' }, async get() { return 'user-1'; } };
  globalThis.SAFApiClient = client;
  const shadow = new FakeShadowRoot();
  const initDetailView = loadInitDetailView();
  initDetailView(shadow);
  shadow.dispatchEvent({ type: 'saf-chat-selected', detail: { chatId: 'chat-1' } });
  await flush();
  await flush();
  return shadow;
}

test('uncertainty shows a calm CI range + chip, never a foregrounded ±', async () => {
  const shadow = await renderWith(scoreClientWith({
    session_id: 'chat-1', tier: 2, feedback_given: false,
    profile: {
      AL: { status: 'OK', value: 0.4882, n_eff: 11, ci: { low: 0.0262, high: 0.9502 } },
    },
  }));
  const row = shadow.getElementById('saf-dimension-list').children
    .find((r) => r.children[0]?.textContent === 'AL');
  const ciText = textOf(row.children[3]);
  assert.match(ciText, /CI 2\.62–95\.02/);     // calm range, 0–100 scale
  assert.match(ciText, /Wide interval/);        // half-width 46.2 ≥ 25 → chip
  assert.doesNotMatch(ciText, /±/);             // no foregrounded ± half-width
  assert.match(row.children[3].title, /half-width/); // exact ± kept in tooltip
});

test('limited-evidence chip wins when n_eff is thin', async () => {
  const shadow = await renderWith(scoreClientWith({
    session_id: 'chat-1', tier: 2,
    profile: { CD: { status: 'OK', value: 0.5, n_eff: 1, ci: { low: 0.1, high: 0.9 } } },
  }));
  const row = shadow.getElementById('saf-dimension-list').children
    .find((r) => r.children[0]?.textContent === 'CD');
  assert.match(textOf(row.children[3]), /Limited evidence/);
});

test('N/A row keeps N/A and surfaces the reason as a caveat', async () => {
  const shadow = await renderWith(scoreClientWith({
    session_id: 'chat-1', tier: 2,
    profile: { ES: { status: 'N/A', status_reason: 'no overreach event observed' } },
  }));
  const row = shadow.getElementById('saf-dimension-list').children
    .find((r) => r.children[0]?.textContent === 'ES');
  assert.equal(row.children[2].textContent, 'N/A');
  assert.equal(row.children[3].title, 'no overreach event observed');
});

test('dimension evidence table renders one row per dimension', async () => {
  const shadow = await renderWith(scoreClientWith({
    session_id: 'chat-1', tier: 2,
    profile: {
      AL: { status: 'OK', value: 0.49, n_eff: 11, ci: { low: 0.03, high: 0.95 },
        flags: ['ci_from_disagreement'], raw_counts: { neurons_succeeded: 10, neurons_attempted: 12 } },
    },
  }));
  const rows = tableTexts(shadow.getElementById('saf-evidence-dims'));
  assert.equal(rows.length, 8); // one row per dimension
  const al = rows.find((r) => r[0] === 'AL');
  assert.ok(al, 'AL row present');
  assert.match(al[5], /10\/12 neurons/); // source = neuron coverage
});

test('cognitive work table renders C1–C7 with n_eff once work loads', async () => {
  const shadow = await renderWith({
    async getChatScore() {
      return { ok: true, data: { session_id: 'chat-1', tier: 2, profile: {} } };
    },
    async getChatWork() {
      return { ok: true, data: { status: 'ok', levels: [
        { level: 'C1', label: 'Knowledge Sourcing', status: 'OK', human_pct: 0.38, ai_pct: 0.62, n_eff: 9, flags: [] },
        { level: 'C2', label: 'Framing', status: 'N/A', human_pct: null, ai_pct: null, n_eff: null, flags: ['uncertified_pending_icc'] },
      ] } };
    },
  });
  const rows = tableTexts(shadow.getElementById('saf-evidence-work'));
  assert.equal(rows.length, 2);
  assert.deepEqual(rows[0].slice(0, 5), ['C1', 'Knowledge Sourcing', '38%', '62%', '9']);
  assert.equal(rows[1][2], '—'); // N/A level shows no fabricated percentage
});

test('deduction log shows an empty state naming the missing artifact', async () => {
  const shadow = await renderWith(scoreClientWith({
    session_id: 'chat-1', tier: 2, profile: { AL: { status: 'OK', value: 0.5, n_eff: 4, ci: { low: 0.3, high: 0.7 } } },
    // no neuron_firings field
  }));
  const rows = tableTexts(shadow.getElementById('saf-evidence-log'));
  assert.equal(rows.length, 1);
  assert.match(rows[0][0], /neuron_firings/); // names the missing artifact
});

test('deduction log renders real neuron firings when present', async () => {
  const shadow = await renderWith(scoreClientWith({
    session_id: 'chat-1', tier: 2, profile: {},
    neuron_firings: [
      { neuron_code: 'AL-01', dimension: 'AL', value: 1.0, n_eff: 1, evidence_turn_indices: [3, 5], extractor_version: 'v6.0' },
      { neuron_code: 'EC-06', dimension: 'EC', value: 0.0, n_eff: 2, evidence_turn_indices: [], extractor_version: 'v6.0' },
    ],
  }));
  const rows = tableTexts(shadow.getElementById('saf-evidence-log'));
  assert.equal(rows.length, 2);
  assert.deepEqual(rows[0], ['AL-01', 'AL', '1.00', '1', '3, 5', 'v6.0']);
  assert.match(rows[1][2], /observed/); // 0.0 = observed-0-of-N, not absent
});
