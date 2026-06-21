'use strict';

const { afterEach, beforeEach, test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const clientPath = path.resolve(__dirname, '../../extension/utils/api_client.js');

const originalFetch = globalThis.fetch;
const originalStorage = globalThis.SAFStorage;
const originalChrome = globalThis.chrome;
const originalSetTimeout = globalThis.setTimeout;
const originalClearTimeout = globalThis.clearTimeout;
const originalWarn = console.warn;

function loadClient({ endpoint = 'http://api.local', key = 'secret-test-key' } = {}) {
  delete require.cache[clientPath];
  globalThis.SAFStorage = {
    STORAGE_KEYS: {
      API_ENDPOINT: 'api_endpoint',
      API_KEY: 'api_key',
    },
    async getMany() {
      return {
        api_endpoint: endpoint,
        api_key: key,
      };
    },
  };
  return require(clientPath);
}

beforeEach(() => {
  delete require.cache[clientPath];
});

afterEach(() => {
  delete require.cache[clientPath];
  globalThis.fetch = originalFetch;
  globalThis.SAFStorage = originalStorage;
  globalThis.chrome = originalChrome;
  globalThis.setTimeout = originalSetTimeout;
  globalThis.clearTimeout = originalClearTimeout;
  console.warn = originalWarn;
});

test('user-scoped helpers fail locally when userRef is missing', async () => {
  const api = loadClient();
  let fetchCalls = 0;
  globalThis.fetch = async () => {
    fetchCalls += 1;
    return { ok: true, status: 200, async json() { return {}; } };
  };

  const result = await api.getChatList('');

  assert.deepEqual(result, { ok: false, error: 'user_ref_required', status: 0 });
  assert.equal(fetchCalls, 0);
});

test('requests use configured endpoint and API key without logging key on HTTP errors', async () => {
  const api = loadClient({ key: 'secret-never-log' });
  const warnings = [];
  console.warn = (...args) => warnings.push(args.join(' '));
  let request;
  globalThis.fetch = async (url, options) => {
    request = { url, options };
    return {
      ok: false,
      status: 503,
      async json() {
        return { detail: 'service unavailable' };
      },
    };
  };

  const result = await api.getSettings('user-1');

  assert.equal(request.url, 'http://api.local/v1/users/user-1/settings');
  assert.equal(request.options.headers['X-API-Key'], 'secret-never-log');
  assert.equal(result.ok, false);
  assert.equal(result.status, 503);
  assert.equal(result.detail, 'service unavailable');
  assert.ok(!warnings.join('\n').includes('secret-never-log'));
});

test('network timeout resolves as api_unreachable instead of hanging', async () => {
  const api = loadClient();
  const realSetTimeout = globalThis.setTimeout;
  globalThis.setTimeout = (fn) => {
    fn();
    return 1;
  };
  globalThis.clearTimeout = () => {};
  globalThis.fetch = async (_url, options) => {
    assert.equal(options.signal.aborted, true);
    throw new Error('aborted');
  };

  const result = await api.getPortfolio('user-1');

  assert.deepEqual(result, { ok: false, error: 'api_unreachable', status: 0 });
  globalThis.setTimeout = realSetTimeout;
});

test('triggerAnalysis resolves with analysis_timeout when background never replies', async () => {
  const api = loadClient();
  globalThis.setTimeout = (fn) => {
    fn();
    return 1;
  };
  globalThis.clearTimeout = () => {};
  globalThis.chrome = {
    runtime: {
      lastError: null,
      sendMessage() {},
    },
  };

  const result = await api.triggerAnalysis('chat-1');

  assert.deepEqual(result, { ok: false, error: 'analysis_timeout' });
});

test('submitFeedback maps thumb without value to a valid backend body', async () => {
  const api = loadClient();
  let request;
  globalThis.fetch = async (url, options) => {
    request = { url, options };
    return { ok: true, status: 200, async json() { return { received: true }; } };
  };

  const result = await api.submitFeedback('user-1', 'chat-1', { type: 'thumb' });

  assert.equal(result.ok, true);
  assert.equal(request.url, 'http://api.local/v1/users/user-1/chats/chat-1/feedback');
  assert.deepEqual(JSON.parse(request.options.body), { match_rating: 'no' });
});
