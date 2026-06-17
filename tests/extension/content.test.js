"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");

const {
  SELECTORS,
  conversationIdFromUrl,
  createCaptureController,
  detectPartnerModel,
  modelIdFromText,
  queryUsingFallbacks,
} = require("../../extension/content.js");

test("SELECTORS preserves the ordered contract fallbacks", () => {
  assert.deepEqual(SELECTORS.turnContainer, [
    'article[data-testid^="conversation-turn-"]',
    '[data-testid^="conversation-turn-"]',
  ]);
  assert.deepEqual(SELECTORS.roleTurn, [
    '[data-message-author-role]',
  ]);
  assert.deepEqual(SELECTORS.userTurn, [
    '[data-message-author-role="user"]',
    'article[data-testid^="conversation-turn-"] .user',
    ".group.w-full .whitespace-pre-wrap",
  ]);
  assert.equal(SELECTORS.stopButton.length, 2);
});

test("queryUsingFallbacks stops at the first selector with matches", () => {
  const calls = [];
  const documentRef = {
    querySelectorAll(selector) {
      calls.push(selector);
      return selector === "second" ? [{ id: 1 }] : [];
    },
  };
  const result = queryUsingFallbacks(documentRef, ["first", "second", "third"]);
  assert.equal(result.selector, "second");
  assert.deepEqual(calls, ["first", "second"]);
});

test("partner detection hardcodes OpenAI family and capture era", () => {
  const node = { innerText: "GPT-4o mini" };
  const documentRef = {
    querySelector(selector) {
      return selector === SELECTORS.modelSelector[0] ? node : null;
    },
  };
  assert.deepEqual(
    detectPartnerModel(documentRef, new Date("2026-06-14T00:00:00Z")),
    { family: "openai", model_id: "gpt-4o-mini", era_key: "2026-06" },
  );
});

test("model and conversation identifiers degrade safely", () => {
  assert.equal(modelIdFromText("Auto"), "unknown");
  assert.equal(modelIdFromText("Use o3-mini"), "o3-mini");
  assert.equal(modelIdFromText("ChatGPT 4o mini"), "gpt-4o-mini");
  assert.equal(modelIdFromText("GPT-5.2 Thinking"), "gpt-5.2");
  assert.equal(conversationIdFromUrl("https://chat.openai.com/c/abc-123"), "abc-123");
  assert.equal(conversationIdFromUrl("not a URL"), null);
});

test("controller orders six captured turns and emits the three-pair ready signal", () => {
  function turn(role, order, text) {
    const container = {
      getAttribute(name) {
        return name === "data-testid" ? `conversation-turn-${order}` : null;
      },
    };
    return {
      innerText: text,
      order,
      closest() {
        return container;
      },
      compareDocumentPosition(other) {
        return this.order < other.order ? 4 : 2;
      },
      contains() {
        return false;
      },
      role,
    };
  }

  const turns = [
    turn("user", 0, "u1"),
    turn("assistant", 1, "a1"),
    turn("user", 2, "u2"),
    turn("assistant", 3, "a2"),
    turn("user", 4, "u3"),
    turn("assistant", 5, "a3"),
  ];
  const documentRef = {
    title: "Test chat | ChatGPT",
    body: {},
    documentElement: {},
    querySelectorAll(selector) {
      if (selector === SELECTORS.userTurn[0]) {
        return turns.filter((item) => item.role === "user");
      }
      if (selector === SELECTORS.aiTurn[0]) {
        return turns.filter((item) => item.role === "assistant");
      }
      return [];
    },
    querySelector(selector) {
      if (selector === "main") return null;
      if (selector === SELECTORS.modelSelector[0]) return { innerText: "GPT-4o" };
      return null;
    },
    addEventListener() {},
    removeEventListener() {},
  };
  const messages = [];
  let clock = 1000;
  class FakeMutationObserver {
    observe() {}
    disconnect() {}
  }

  const controller = createCaptureController({
    document: documentRef,
    location: { href: "https://chat.openai.com/c/chat-123" },
    MutationObserver: FakeMutationObserver,
    now: () => (clock += 100),
    setTimeout: () => 1,
    clearTimeout: () => {},
    sendMessage: (message) => messages.push(message),
  });

  controller.captureUsers();
  controller.captureCompletedAssistants();

  const ready = messages.filter((message) => message.type === "SAF_CAPTURE_READY");
  assert.equal(ready.length, 1);
  assert.deepEqual(
    ready[0].capture.turns.map(({ role, text, turn_index }) => ({
      role,
      text,
      turn_index,
    })),
    [
      { role: "user", text: "u1", turn_index: 0 },
      { role: "assistant", text: "a1", turn_index: 1 },
      { role: "user", text: "u2", turn_index: 2 },
      { role: "assistant", text: "a2", turn_index: 3 },
      { role: "user", text: "u3", turn_index: 4 },
      { role: "assistant", text: "a3", turn_index: 5 },
    ],
  );
  assert.equal(ready[0].capture.telemetry.dwell_ms.length, 6);
  assert.equal(ready[0].capture.partner_model.family, "openai");
  assert.equal(controller.maybeQueueCapture(), false);
});

test("controller prefers explicit role containers over broad fallback selectors", () => {
  function roleTurn(role, order, text) {
    return {
      innerText: text,
      order,
      getAttribute(name) {
        if (name === "data-message-author-role") return role;
        if (name === "data-testid") return `message-${order}`;
        return null;
      },
      closest() {
        return {
          getAttribute: () => `conversation-turn-${order}`,
        };
      },
      compareDocumentPosition(other) {
        return this.order < other.order ? 4 : 2;
      },
      contains() {
        return false;
      },
    };
  }

  const roleNodes = [
    roleTurn("user", 0, "real user"),
    roleTurn("assistant", 1, "real assistant"),
  ];
  const noisyFallbackNodes = [
    roleTurn("user", 2, "fallback should not be captured as user"),
    roleTurn("user", 3, "another fallback duplicate"),
  ];
  const documentRef = {
    title: "ChatGPT",
    body: {},
    documentElement: {},
    querySelectorAll(selector) {
      if (selector === SELECTORS.roleTurn[0]) return roleNodes;
      if (selector === SELECTORS.userTurn[2]) return noisyFallbackNodes;
      return [];
    },
    querySelector() {
      return null;
    },
    addEventListener() {},
    removeEventListener() {},
  };
  class FakeMutationObserver {
    observe() {}
    disconnect() {}
  }

  const controller = createCaptureController({
    document: documentRef,
    location: { href: "https://chat.openai.com/c/chat-123" },
    MutationObserver: FakeMutationObserver,
    setTimeout: () => 1,
    clearTimeout: () => {},
    warn: () => {},
  });

  controller.captureUsers(true);
  controller.captureCompletedAssistants(true);
  assert.deepEqual(
    controller.snapshot().turns.map(({ role, text }) => ({ role, text })),
    [
      { role: "user", text: "real user" },
      { role: "assistant", text: "real assistant" },
    ],
  );
});

test("controller falls back for assistants when only user role containers exist", () => {
  function node(role, order, text, explicitRole = null) {
    return {
      innerText: text,
      order,
      getAttribute(name) {
        if (name === "data-message-author-role") return explicitRole;
        if (name === "data-testid") return `message-${order}`;
        return null;
      },
      closest() {
        return {
          getAttribute: () => `conversation-turn-${order}`,
        };
      },
      compareDocumentPosition(other) {
        return this.order < other.order ? 4 : 2;
      },
      contains() {
        return false;
      },
      role,
    };
  }

  const explicitUser = node("user", 0, "real user", "user");
  const assistantFallback = node("assistant", 1, "real assistant");
  const documentRef = {
    title: "ChatGPT",
    body: {},
    documentElement: {},
    querySelectorAll(selector) {
      if (selector === SELECTORS.roleTurn[0]) return [explicitUser];
      if (selector === SELECTORS.aiTurn[0]) return [assistantFallback];
      return [];
    },
    querySelector() {
      return null;
    },
    addEventListener() {},
    removeEventListener() {},
  };
  class FakeMutationObserver {
    observe() {}
    disconnect() {}
  }

  const controller = createCaptureController({
    document: documentRef,
    location: { href: "https://chat.openai.com/c/chat-123" },
    MutationObserver: FakeMutationObserver,
    setTimeout: () => 1,
    clearTimeout: () => {},
    warn: () => {},
  });

  controller.captureUsers(true);
  controller.captureCompletedAssistants(true);
  assert.deepEqual(
    controller.snapshot().turns.map(({ role, text }) => ({ role, text })),
    [
      { role: "user", text: "real user" },
      { role: "assistant", text: "real assistant" },
    ],
  );
});

test("controller captures existing conversation-turn articles without assistant role attributes", () => {
  function article(role, order, text) {
    const textNode = {
      innerText: text,
      order,
      getAttribute() {
        return null;
      },
      closest() {
        return node;
      },
      compareDocumentPosition(other) {
        return this.order < other.order ? 4 : 2;
      },
      contains() {
        return false;
      },
    };
    const node = {
      innerText: text,
      order,
      matches(selector) {
        return selector === 'article[data-testid^="conversation-turn-"]';
      },
      getAttribute(name) {
        return name === "data-testid" ? `conversation-turn-${order}` : null;
      },
      querySelector(selector) {
        if (selector === "[data-message-author-role]" && role === "user") {
          return {
            ...textNode,
            getAttribute(name) {
              return name === "data-message-author-role" ? "user" : null;
            },
          };
        }
        if (selector.includes(".markdown") && role === "assistant") return textNode;
        if (selector.includes(".whitespace-pre-wrap") && role === "user") return textNode;
        return null;
      },
      closest() {
        return node;
      },
      compareDocumentPosition(other) {
        return this.order < other.order ? 4 : 2;
      },
      contains(other) {
        return other === textNode;
      },
    };
    return node;
  }

  const turns = [
    article("user", 0, "already open question"),
    article("assistant", 1, "already open answer"),
  ];
  const documentRef = {
    title: "ChatGPT",
    body: {},
    documentElement: {},
    querySelectorAll(selector) {
      if (selector === SELECTORS.turnContainer[0]) return turns;
      return [];
    },
    querySelector() {
      return null;
    },
    addEventListener() {},
    removeEventListener() {},
  };
  class FakeMutationObserver {
    observe() {}
    disconnect() {}
  }
  const messages = [];

  const controller = createCaptureController({
    document: documentRef,
    location: { href: "https://chat.openai.com/c/chat-123" },
    MutationObserver: FakeMutationObserver,
    setTimeout: () => 1,
    clearTimeout: () => {},
    sendMessage: (message) => messages.push(message),
    warn: () => {},
  });

  controller.enableCapture();
  controller.captureUsers(true);
  controller.captureCompletedAssistants(true);
  assert.equal(controller.maybeQueueCapture(true), true);
  const ready = messages.filter((message) => message.type === "SAF_CAPTURE_READY").at(-1);
  assert.deepEqual(
    ready.capture.turns.map(({ role, text }) => ({ role, text })),
    [
      { role: "user", text: "already open question" },
      { role: "assistant", text: "already open answer" },
    ],
  );
});

test("controller stays passive until capture is explicitly enabled", () => {
  let observeCalls = 0;
  const listeners = [];
  class FakeMutationObserver {
    observe() {
      observeCalls += 1;
    }
    disconnect() {}
  }
  const documentRef = {
    title: "ChatGPT",
    body: {},
    documentElement: {},
    querySelectorAll() {
      return [];
    },
    querySelector() {
      return null;
    },
    addEventListener() {},
    removeEventListener() {},
  };
  const previousChrome = global.chrome;
  global.chrome = {
    runtime: {
      onMessage: {
        addListener(listener) {
          listeners.push(listener);
        },
        removeListener() {},
      },
    },
  };

  try {
    const controller = createCaptureController({
      document: documentRef,
      location: { href: "https://chat.openai.com/" },
      MutationObserver: FakeMutationObserver,
      setTimeout: () => 1,
      clearTimeout: () => {},
    }).start(false);

    assert.equal(observeCalls, 0);
    assert.equal(listeners.length, 1);
    controller.enableCapture();
    assert.equal(observeCalls, 1);
  } finally {
    global.chrome = previousChrome;
  }
});

test("analyse-now assigns a stable draft id for the same unsaved chat", async () => {
  function turn(role, order, text) {
    return {
      innerText: text,
      order,
      closest: () => ({ getAttribute: () => `${role}-${order}` }),
      compareDocumentPosition(other) {
        return this.order < other.order ? 4 : 2;
      },
      contains() {
        return false;
      },
      role,
    };
  }

  async function runCapture(randomId) {
    const turns = [
      turn("user", 0, "same first question"),
      turn("assistant", 1, "same answer"),
    ];
    let listener;
    const previousChrome = global.chrome;
    global.chrome = {
      runtime: {
        onMessage: {
          addListener(fn) {
            listener = fn;
          },
          removeListener() {},
        },
      },
    };
    const messages = [];
    const documentRef = {
      title: "Stable draft | ChatGPT",
      body: {},
      documentElement: {},
      querySelectorAll(selector) {
        if (selector === SELECTORS.userTurn[0]) return turns.filter((item) => item.role === "user");
        if (selector === SELECTORS.aiTurn[0]) return turns.filter((item) => item.role === "assistant");
        return [];
      },
      querySelector(selector) {
        if (selector === "main") return null;
        return null;
      },
      addEventListener() {},
      removeEventListener() {},
    };
    class FakeMutationObserver {
      observe() {}
      disconnect() {}
    }

    try {
      createCaptureController({
        document: documentRef,
        location: { href: "https://chat.openai.com/" },
        MutationObserver: FakeMutationObserver,
        crypto: { randomUUID: () => randomId },
        setTimeout: (fn) => {
          fn();
          return 1;
        },
        clearTimeout: () => {},
        sendMessage: (message) => messages.push(message),
        warn: () => {},
      }).start(false);

      const response = await new Promise((resolve) => {
        listener({ type: "SAF_ANALYSE_NOW" }, null, resolve);
      });
      assert.equal(response.ok, true);
      return messages.find((message) => message.type === "SAF_CAPTURE_READY")
        .capture.conversation_id;
    } finally {
      global.chrome = previousChrome;
    }
  }

  const first = await runCapture("random-one");
  const second = await runCapture("random-two");
  assert.equal(first, second);
  assert.match(first, /^draft-/);
  assert.notEqual(first, "draft-random-one");
});

test("direct manual capture works on an already-open draft chat", () => {
  function turn(role, order, text) {
    return {
      innerText: text,
      order,
      closest: () => ({ getAttribute: () => `${role}-${order}` }),
      compareDocumentPosition(other) {
        return this.order < other.order ? 4 : 2;
      },
      contains() {
        return false;
      },
      role,
    };
  }

  const turns = [
    turn("user", 0, "draft question"),
    turn("assistant", 1, "draft answer"),
  ];
  const messages = [];
  const documentRef = {
    title: "Draft chat | ChatGPT",
    body: {},
    documentElement: {},
    querySelectorAll(selector) {
      if (selector === SELECTORS.userTurn[0]) return turns.filter((item) => item.role === "user");
      if (selector === SELECTORS.aiTurn[0]) return turns.filter((item) => item.role === "assistant");
      return [];
    },
    querySelector() {
      return null;
    },
    addEventListener() {},
    removeEventListener() {},
  };
  class FakeMutationObserver {
    observe() {}
    disconnect() {}
  }

  const controller = createCaptureController({
    document: documentRef,
    location: { href: "https://chat.openai.com/" },
    MutationObserver: FakeMutationObserver,
    setTimeout: () => 1,
    clearTimeout: () => {},
    sendMessage: (message) => messages.push(message),
    warn: () => {},
  });

  controller.enableCapture();
  controller.captureUsers(true);
  controller.captureCompletedAssistants(true);
  assert.equal(controller.maybeQueueCapture(true), true);

  const ready = messages.filter((message) => message.type === "SAF_CAPTURE_READY").at(-1);
  assert.equal(ready.capture.turns.length, 2);
  assert.match(ready.capture.conversation_id, /^draft-/);
});

test("manual scroll harvest captures virtualized long chats", async () => {
  function turn(role, order, text) {
    return {
      innerText: text,
      order,
      closest: () => ({ getAttribute: () => `${role}-${order}` }),
      compareDocumentPosition(other) {
        return this.order < other.order ? 4 : 2;
      },
      contains() {
        return false;
      },
      role,
    };
  }

  const pages = [
    [turn("user", 0, "q1"), turn("assistant", 1, "a1")],
    [turn("user", 2, "q2"), turn("assistant", 3, "a2")],
    [turn("user", 4, "q3"), turn("assistant", 5, "a3")],
  ];
  const root = {
    scrollTop: 0,
    scrollHeight: 1400,
    clientHeight: 400,
    scrollTo({ top }) {
      this.scrollTop = top;
    },
  };
  const visiblePage = () => Math.min(2, Math.floor(root.scrollTop / 300));
  const messages = [];
  const documentRef = {
    title: "Long chat | ChatGPT",
    scrollingElement: root,
    body: {},
    documentElement: root,
    querySelectorAll(selector) {
      const visible = pages[visiblePage()];
      if (selector === SELECTORS.userTurn[0]) {
        return visible.filter((item) => item.role === "user");
      }
      if (selector === SELECTORS.aiTurn[0]) {
        return visible.filter((item) => item.role === "assistant");
      }
      return [];
    },
    querySelector() {
      return null;
    },
    addEventListener() {},
    removeEventListener() {},
  };
  class FakeMutationObserver {
    observe() {}
    disconnect() {}
  }

  const controller = createCaptureController({
    document: documentRef,
    location: { href: "https://chat.openai.com/c/long-chat" },
    MutationObserver: FakeMutationObserver,
    setTimeout: (fn) => {
      fn();
      return 1;
    },
    clearTimeout: () => {},
    sendMessage: (message) => messages.push(message),
    warn: () => {},
  });

  assert.equal(await controller.captureFullConversationForManual(), true);
  const ready = messages.filter((message) => message.type === "SAF_CAPTURE_READY").at(-1);
  assert.deepEqual(
    ready.capture.turns.map(({ role, text }) => ({ role, text })),
    [
      { role: "user", text: "q1" },
      { role: "assistant", text: "a1" },
      { role: "user", text: "q2" },
      { role: "assistant", text: "a2" },
      { role: "user", text: "q3" },
      { role: "assistant", text: "a3" },
    ],
  );
  assert.equal(root.scrollTop, 0);
});

test("manual scroll harvest uses nested ChatGPT scroll containers", async () => {
  function turn(role, order, text) {
    return {
      innerText: text,
      order,
      closest: () => ({ getAttribute: () => `${role}-${order}` }),
      compareDocumentPosition(other) {
        return this.order < other.order ? 4 : 2;
      },
      contains() {
        return false;
      },
      role,
    };
  }

  const pages = [
    [turn("user", 0, "nested q1"), turn("assistant", 1, "nested a1")],
    [turn("user", 2, "nested q2"), turn("assistant", 3, "nested a2")],
  ];
  const pageRoot = { scrollTop: 0, scrollHeight: 500, clientHeight: 500 };
  const nestedRoot = {
    scrollTop: 0,
    scrollHeight: 1200,
    clientHeight: 400,
    scrollTo({ top }) {
      this.scrollTop = top;
    },
  };
  const visiblePage = () => Math.min(1, Math.floor(nestedRoot.scrollTop / 300));
  const messages = [];
  const documentRef = {
    title: "Nested long chat | ChatGPT",
    scrollingElement: pageRoot,
    body: pageRoot,
    documentElement: pageRoot,
    querySelectorAll(selector) {
      if (selector === "main, main *, [class*='overflow'], [data-testid*='conversation']") {
        return [nestedRoot];
      }
      const visible = pages[visiblePage()];
      if (selector === SELECTORS.userTurn[0]) {
        return visible.filter((item) => item.role === "user");
      }
      if (selector === SELECTORS.aiTurn[0]) {
        return visible.filter((item) => item.role === "assistant");
      }
      return [];
    },
    querySelector() {
      return null;
    },
    addEventListener() {},
    removeEventListener() {},
  };
  class FakeMutationObserver {
    observe() {}
    disconnect() {}
  }

  const controller = createCaptureController({
    document: documentRef,
    location: { href: "https://chatgpt.com/c/nested-long-chat" },
    MutationObserver: FakeMutationObserver,
    setTimeout: (fn) => {
      fn();
      return 1;
    },
    clearTimeout: () => {},
    sendMessage: (message) => messages.push(message),
    warn: () => {},
  });

  assert.equal(await controller.captureFullConversationForManual(), true);
  const ready = messages.filter((message) => message.type === "SAF_CAPTURE_READY").at(-1);
  assert.deepEqual(
    ready.capture.turns.map(({ role, text }) => ({ role, text })),
    [
      { role: "user", text: "nested q1" },
      { role: "assistant", text: "nested a1" },
      { role: "user", text: "nested q2" },
      { role: "assistant", text: "nested a2" },
    ],
  );
  assert.equal(nestedRoot.scrollTop, 0);
});

test("forced capture never emits an empty or user-only session", () => {
  let turns = [];
  function turn(role, order, text) {
    return {
      innerText: text,
      order,
      closest: () => ({ getAttribute: () => `${role}-${order}` }),
      compareDocumentPosition(other) {
        return this.order < other.order ? 4 : 2;
      },
      contains() {
        return false;
      },
      role,
    };
  }

  const messages = [];
  const documentRef = {
    title: "ChatGPT",
    body: {},
    documentElement: {},
    querySelectorAll(selector) {
      if (selector === SELECTORS.userTurn[0]) return turns.filter((item) => item.role === "user");
      if (selector === SELECTORS.aiTurn[0]) return turns.filter((item) => item.role === "assistant");
      return [];
    },
    querySelector() {
      return null;
    },
    addEventListener() {},
    removeEventListener() {},
  };
  class FakeMutationObserver {
    observe() {}
    disconnect() {}
  }

  const controller = createCaptureController({
    document: documentRef,
    location: { href: "https://chat.openai.com/c/chat-123" },
    MutationObserver: FakeMutationObserver,
    setTimeout: () => 1,
    clearTimeout: () => {},
    sendMessage: (message) => messages.push(message),
  });

  assert.equal(controller.maybeQueueCapture(true), false);
  turns = [turn("user", 0, "draft question")];
  controller.captureUsers(true);
  assert.equal(controller.maybeQueueCapture(true), false);
  assert.equal(messages.filter((message) => message.type === "SAF_CAPTURE_READY").length, 0);
});

test("forced capture can emit a real one-pair session", () => {
  function turn(role, order, text) {
    return {
      innerText: text,
      order,
      closest: () => ({ getAttribute: () => `${role}-${order}` }),
      compareDocumentPosition(other) {
        return this.order < other.order ? 4 : 2;
      },
      contains() {
        return false;
      },
      role,
    };
  }

  const turns = [
    turn("user", 0, "one question"),
    turn("assistant", 1, "one answer"),
  ];
  const messages = [];
  const documentRef = {
    title: "ChatGPT",
    body: {},
    documentElement: {},
    querySelectorAll(selector) {
      if (selector === SELECTORS.userTurn[0]) return turns.filter((item) => item.role === "user");
      if (selector === SELECTORS.aiTurn[0]) return turns.filter((item) => item.role === "assistant");
      return [];
    },
    querySelector() {
      return null;
    },
    addEventListener() {},
    removeEventListener() {},
  };
  class FakeMutationObserver {
    observe() {}
    disconnect() {}
  }

  const controller = createCaptureController({
    document: documentRef,
    location: { href: "https://chat.openai.com/c/chat-123" },
    MutationObserver: FakeMutationObserver,
    setTimeout: () => 1,
    clearTimeout: () => {},
    sendMessage: (message) => messages.push(message),
  });

  controller.captureUsers(true);
  controller.captureCompletedAssistants(true);
  assert.equal(controller.maybeQueueCapture(true), true);
  const ready = messages.filter((message) => message.type === "SAF_CAPTURE_READY");
  assert.equal(ready.length, 1);
  assert.equal(ready[0].capture.turns.length, 2);
});

test("forced capture refuses heavily imbalanced transcripts", () => {
  function turn(role, order, text) {
    return {
      innerText: text,
      order,
      closest: () => ({ getAttribute: () => `${role}-${order}` }),
      compareDocumentPosition(other) {
        return this.order < other.order ? 4 : 2;
      },
      contains() {
        return false;
      },
      role,
    };
  }

  const turns = [];
  for (let i = 0; i < 8; i += 1) turns.push(turn("user", i, `question ${i}`));
  turns.push(turn("assistant", 8, "answer 1"));
  turns.push(turn("assistant", 9, "answer 2"));
  turns.push(turn("assistant", 10, "answer 3"));

  const messages = [];
  const warnings = [];
  const documentRef = {
    title: "ChatGPT",
    body: {},
    documentElement: {},
    querySelectorAll(selector) {
      if (selector === SELECTORS.userTurn[0]) return turns.filter((item) => item.role === "user");
      if (selector === SELECTORS.aiTurn[0]) return turns.filter((item) => item.role === "assistant");
      return [];
    },
    querySelector() {
      return null;
    },
    addEventListener() {},
    removeEventListener() {},
  };
  class FakeMutationObserver {
    observe() {}
    disconnect() {}
  }

  const controller = createCaptureController({
    document: documentRef,
    location: { href: "https://chat.openai.com/c/chat-123" },
    MutationObserver: FakeMutationObserver,
    setTimeout: () => 1,
    clearTimeout: () => {},
    sendMessage: (message) => messages.push(message),
    warn: (message) => warnings.push(message),
  });

  controller.captureUsers(true);
  controller.captureCompletedAssistants(true);
  assert.equal(controller.maybeQueueCapture(true), false);
  assert.equal(messages.filter((message) => message.type === "SAF_CAPTURE_READY").length, 0);
  assert.equal(controller.snapshot().telemetry.selector_health, "selector_miss");
  assert.ok(warnings.some((message) => /imbalanced/.test(message)));
});

test("new-chat navigation clears the old transcript and retains fresh draft turns", () => {
  function turn(role, order, text) {
    return {
      innerText: text,
      order,
      closest() {
        return {
          getAttribute: () => `conversation-turn-${order}`,
        };
      },
      compareDocumentPosition(other) {
        return this.order < other.order ? 4 : 2;
      },
      contains() {
        return false;
      },
      role,
    };
  }

  const locationRef = { href: "https://chat.openai.com/c/old-chat" };
  let turns = [turn("user", 0, "old user"), turn("assistant", 1, "old assistant")];
  const eventListeners = {};
  let mutationCallback;
  class FakeMutationObserver {
    constructor(callback) {
      mutationCallback = callback;
    }
    observe() {}
    disconnect() {}
  }
  const documentRef = {
    title: "ChatGPT",
    body: {},
    documentElement: {},
    querySelectorAll(selector) {
      if (selector === SELECTORS.userTurn[0]) {
        return turns.filter((item) => item.role === "user");
      }
      if (selector === SELECTORS.aiTurn[0]) {
        return turns.filter((item) => item.role === "assistant");
      }
      return [];
    },
    querySelector() {
      return null;
    },
    addEventListener(type, listener) {
      eventListeners[type] = listener;
    },
    removeEventListener() {},
  };

  const controller = createCaptureController({
    document: documentRef,
    location: locationRef,
    MutationObserver: FakeMutationObserver,
    setTimeout: () => 1,
    clearTimeout: () => {},
    sendMessage: () => {},
    warn: () => {},
  }).start();
  controller.captureCompletedAssistants();
  assert.equal(controller.snapshot().turns.length, 2);

  locationRef.href = "https://chat.openai.com/";
  mutationCallback();
  assert.equal(controller.snapshot().turns.length, 0);

  turns = [turn("user", 0, "new user")];
  eventListeners.submit();
  mutationCallback();
  locationRef.href = "https://chat.openai.com/c/new-chat";
  mutationCallback();
  turns.push(turn("assistant", 1, "new assistant"));
  controller.captureCompletedAssistants();

  assert.equal(controller.snapshot().conversation_id, "new-chat");
  assert.deepEqual(
    controller.snapshot().turns.map((item) => item.text),
    ["new user", "new assistant"],
  );
});

test("selector health remains degraded until every missed turn selector recovers", () => {
  let users = [];
  let assistants = [];
  function turn(role, order) {
    return {
      innerText: role,
      closest: () => ({ getAttribute: () => `${role}-${order}` }),
      compareDocumentPosition: () => 0,
      contains: () => false,
    };
  }
  const documentRef = {
    title: "ChatGPT",
    body: {},
    documentElement: {},
    querySelectorAll(selector) {
      if (selector === SELECTORS.userTurn[0]) return users;
      if (selector === SELECTORS.aiTurn[0]) return assistants;
      return [];
    },
    querySelector(selector) {
      if (selector === SELECTORS.modelSelector[0]) return { innerText: "GPT-4o" };
      return null;
    },
    addEventListener() {},
    removeEventListener() {},
  };
  class FakeMutationObserver {
    observe() {}
    disconnect() {}
  }
  const controller = createCaptureController({
    document: documentRef,
    location: { href: "https://chat.openai.com/c/chat-1" },
    MutationObserver: FakeMutationObserver,
    setTimeout: () => 1,
    clearTimeout: () => {},
    sendMessage: () => {},
    warn: () => {},
  });

  controller.captureUsers(true);
  controller.captureCompletedAssistants(true);
  users = [turn("user", 0)];
  controller.captureUsers(true);
  assert.equal(controller.snapshot().telemetry.selector_health, "selector_miss");

  assistants = [turn("assistant", 1)];
  controller.captureCompletedAssistants(true);
  assert.equal(controller.snapshot().telemetry.selector_health, "ok");
});
