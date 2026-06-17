"use strict";

(function initStorage(globalScope) {
  const STORAGE_KEYS = Object.freeze({
    ONBOARDING_COMPLETE: "onboarding_complete",
    USER_REF: "user_ref",
    API_ENDPOINT: "api_endpoint",
    API_KEY: "api_key",
    OPENAI_API_KEY: "openai_api_key",
    CONSENT_ENABLED: "consent_enabled",
    LAST_CAPTURE: "last_capture",
    HEALTH_STATUS: "health_status",
  });

  function storageArea() {
    const area = globalScope.chrome?.storage?.local;
    if (!area) {
      throw new Error("chrome.storage.local is unavailable");
    }
    return area;
  }

  function lastRuntimeError() {
    return globalScope.chrome?.runtime?.lastError;
  }

  function invoke(method, ...args) {
    return new Promise((resolve, reject) => {
      let settled = false;
      const callback = (result) => {
        if (settled) return;
        settled = true;
        const error = lastRuntimeError();
        if (error) {
          reject(new Error(error.message || String(error)));
          return;
        }
        resolve(result);
      };

      try {
        const returned = storageArea()[method](...args, callback);
        if (returned && typeof returned.then === "function") {
          returned.then(callback, reject);
        }
      } catch (error) {
        reject(error);
      }
    });
  }

  /** @template T @param {string} key @param {T} [fallback] @returns {Promise<T>} */
  async function get(key, fallback = undefined) {
    if (typeof key !== "string" || !key) {
      throw new TypeError("storage key must be a non-empty string");
    }
    const values = await invoke("get", key);
    return Object.prototype.hasOwnProperty.call(values || {}, key) && values[key] !== undefined
      ? values[key]
      : fallback;
  }

  /** @param {string[]|Record<string, unknown>|null} [keys] */
  async function getMany(keys = null) {
    if (
      keys !== null &&
      !Array.isArray(keys) &&
      (typeof keys !== "object" || keys === null)
    ) {
      throw new TypeError("keys must be an array, defaults object, or null");
    }
    return (await invoke("get", keys)) || {};
  }

  /**
   * @param {string|Record<string, unknown>} keyOrValues
   * @param {unknown} [value]
   */
  async function set(keyOrValues, value = undefined) {
    const values =
      typeof keyOrValues === "string"
        ? { [keyOrValues]: value }
        : keyOrValues;

    if (!values || typeof values !== "object" || Array.isArray(values)) {
      throw new TypeError("set expects a key/value pair or an object");
    }
    await invoke("set", values);
  }

  /** @param {string|string[]} keys */
  async function remove(keys) {
    if (
      !(typeof keys === "string" && keys) &&
      !(Array.isArray(keys) && keys.every((key) => typeof key === "string" && key))
    ) {
      throw new TypeError("remove expects a key or array of keys");
    }
    await invoke("remove", keys);
  }

  async function clear() {
    await invoke("clear");
  }

  /** @template T @param {string} key @param {(current: T) => T|Promise<T>} updater @param {T} [fallback] */
  async function update(key, updater, fallback = undefined) {
    if (typeof updater !== "function") {
      throw new TypeError("updater must be a function");
    }
    const next = await updater(await get(key, fallback));
    await set(key, next);
    return next;
  }

  const api = Object.freeze({
    STORAGE_KEYS,
    get,
    getMany,
    set,
    remove,
    clear,
    update,
  });

  globalScope.SAFStorage = api;
  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  }
})(typeof globalThis !== "undefined" ? globalThis : self);
