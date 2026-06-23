"use strict";

const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const injectedIconPath = path.resolve(__dirname, "../../extension/injected_icon.js");

class FakeElement {
  constructor(tagName, ownerDocument) {
    this.tagName = tagName.toUpperCase();
    this.ownerDocument = ownerDocument;
    this.children = [];
    this.parentNode = null;
    this.attributes = new Map();
    this.dataset = {};
    this.listeners = new Map();
    this.id = "";
    this.href = "";
    this.rel = "";
    this.type = "";
    this.className = "";
    this.alt = "";
  }

  appendChild(child) {
    child.parentNode = this;
    this.children.push(child);
    this.ownerDocument?._register(child);
    return child;
  }

  remove() {
    if (this.parentNode) {
      this.parentNode.children = this.parentNode.children.filter((child) => child !== this);
      this.parentNode = null;
    }
    this.ownerDocument?._unregister(this);
  }

  setAttribute(name, value) {
    this.attributes.set(name, String(value));
  }

  getAttribute(name) {
    return this.attributes.get(name) ?? null;
  }

  addEventListener(type, handler) {
    if (!this.listeners.has(type)) this.listeners.set(type, new Set());
    this.listeners.get(type).add(handler);
  }

  attachShadow() {
    const shadow = new FakeElement("#shadow-root", this.ownerDocument);
    this.shadowRoot = shadow;
    return shadow;
  }

  querySelectorAll(selector) {
    const results = [];
    const visit = (node) => {
      if (selector === "img[data-saf-logo]" && node.tagName === "IMG" && node.dataset.safLogo) {
        results.push(node);
      }
      node.children.forEach(visit);
    };
    this.children.forEach(visit);
    return results;
  }

  getElementById(id) {
    return this.ownerDocument?.getElementById(id) || null;
  }

  focus() {}
}

class FakeTemplateElement {}

class FakeDocument {
  constructor() {
    this.nodes = new Map();
    this.head = new FakeElement("head", this);
    this.body = new FakeElement("body", this);
    this.eventListeners = new Map();
  }

  createElement(tagName) {
    return new FakeElement(tagName, this);
  }

  getElementById(id) {
    return this.nodes.get(id) || null;
  }

  importNode(node) {
    return node;
  }

  addEventListener(type, handler) {
    if (!this.eventListeners.has(type)) this.eventListeners.set(type, new Set());
    this.eventListeners.get(type).add(handler);
  }

  removeEventListener(type, handler) {
    this.eventListeners.get(type)?.delete(handler);
  }

  _register(node) {
    if (node.id) this.nodes.set(node.id, node);
  }

  _unregister(node) {
    if (node.id && this.nodes.get(node.id) === node) this.nodes.delete(node.id);
    node.children.forEach((child) => this._unregister(child));
  }
}

function deferred() {
  let resolve;
  const promise = new Promise((done) => {
    resolve = done;
  });
  return { promise, resolve };
}

function loadInjectedIcon(fetchDeferred) {
  const document = new FakeDocument();
  const listeners = [];
  const context = {
    console,
    document,
    window: {
      setTimeout,
      clearTimeout,
    },
    requestAnimationFrame(callback) {
      callback();
    },
    fetch: () => fetchDeferred.promise,
    DOMParser: class {
      parseFromString() {
        const template = new FakeTemplateElement();
        template.content = new FakeElement("fragment", document);
        return {
          getElementById(id) {
            return id === "saf-modal-template" ? template : null;
          },
        };
      }
    },
    HTMLTemplateElement: FakeTemplateElement,
    chrome: {
      runtime: {
        getURL: (resourcePath) => `chrome-extension://test/${resourcePath}`,
        onMessage: {
          addListener(listener) {
            listeners.push(listener);
          },
        },
      },
    },
  };

  vm.runInNewContext(fs.readFileSync(injectedIconPath, "utf8"), context, {
    filename: injectedIconPath,
  });

  return { document, listeners };
}

test("closing while modal shell is still loading leaves no stale open state", async () => {
  const pendingFetch = deferred();
  const { document, listeners } = loadInjectedIcon(pendingFetch);

  listeners[0]({ type: "SAF_OPEN_MODAL" });
  assert.ok(document.getElementById("saf-modal-host"));

  listeners[0]({ type: "SAF_OPEN_MODAL" });
  assert.equal(document.getElementById("saf-modal-host"), null);

  pendingFetch.resolve({
    ok: true,
    async text() {
      return '<template id="saf-modal-template"></template>';
    },
  });
  await Promise.resolve();
  await Promise.resolve();

  assert.equal(document.getElementById("saf-modal-host"), null);
  assert.equal(document.getElementById("saf-fab").getAttribute("aria-expanded"), "false");
});
