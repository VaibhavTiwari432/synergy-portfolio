"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");

function loadStorage(initial = {}) {
  const values = { ...initial };
  global.chrome = {
    runtime: { lastError: null },
    storage: {
      local: {
        get(keys, callback) {
          if (keys === null) return callback({ ...values });
          if (typeof keys === "string") return callback({ [keys]: values[keys] });
          if (Array.isArray(keys)) {
            return callback(Object.fromEntries(keys.map((key) => [key, values[key]])));
          }
          callback({ ...keys, ...values });
        },
        set(next, callback) {
          Object.assign(values, next);
          callback();
        },
        remove(keys, callback) {
          for (const key of [].concat(keys)) delete values[key];
          callback();
        },
        clear(callback) {
          for (const key of Object.keys(values)) delete values[key];
          callback();
        },
      },
    },
  };
  const path = require.resolve("../../extension/utils/storage.js");
  delete require.cache[path];
  return { api: require(path), values };
}

test("storage wrapper gets, sets, updates, removes, and clears values", async () => {
  const { api, values } = loadStorage({ count: 1 });
  assert.equal(await api.get("count", 0), 1);
  assert.equal(await api.get("missing", "fallback"), "fallback");

  await api.set("enabled", true);
  await api.set({ name: "SAF" });
  assert.equal(await api.update("count", (count) => count + 1, 0), 2);
  assert.deepEqual(values, { count: 2, enabled: true, name: "SAF" });

  await api.remove(["enabled", "name"]);
  assert.deepEqual(values, { count: 2 });
  await api.clear();
  assert.deepEqual(values, {});
});

test("storage wrapper rejects unavailable chrome storage", async () => {
  const { api } = loadStorage();
  delete global.chrome.storage;
  await assert.rejects(api.get("key"), /chrome.storage.local is unavailable/);
});
