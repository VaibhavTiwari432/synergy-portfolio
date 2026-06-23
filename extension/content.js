"use strict";

(function initContentCapture(globalScope) {
  const SELECTORS = Object.freeze({
    turnContainer: Object.freeze([
      '[data-message-id]',
    ]),
    roleTurn: Object.freeze([
      '[data-message-author-role]',
      '[data-testid="user-message"], [data-testid="human-message"], [data-testid="assistant-message"]',
    ]),
    userTurn: Object.freeze([
      '[data-message-author-role="user"]',
      '[data-testid="user-message"]',
      '[data-testid="human-message"]',
    ]),
    aiTurn: Object.freeze([
      '[data-message-author-role="assistant"]',
      '[data-testid="assistant-message"]',
    ]),
    stopButton: Object.freeze([
      'button[aria-label="Stop generating"]',
      'button[data-testid="stop-button"]',
    ]),
    modelSelector: Object.freeze([
      '[data-testid="model-switcher-dropdown-button"]',
      '[data-testid="model-selector-dropdown"]',
      '[data-testid="model-selector"]',
      'button[aria-label*="model"]',
    ]),
    historyItems: Object.freeze([
      'nav [data-testid="history-item"]',
      "nav ol li a",
    ]),
  });

  const MESSAGE_TYPES = Object.freeze({
    CAPTURE_UPDATED: "SAF_CAPTURE_UPDATED",
    CAPTURE_READY: "SAF_CAPTURE_READY",
    ANALYSE_PROGRESS: "SAF_ANALYSE_PROGRESS",
    GET_CAPTURE_STATE: "SAF_GET_CAPTURE_STATE",
    GET_HISTORY_ITEMS: "SAF_GET_HISTORY_ITEMS",
    ANALYSE_NOW: "SAF_ANALYSE_NOW",
  });

  const STREAM_IDLE_MS = 1500;
  const PAIRS_PER_UPLOAD = 3;
  const MANUAL_SCROLL_SETTLE_MS = 180;
  // The DOM scroll harvest is bounded by ELAPSED TIME, not a fixed step count: a
  // long chat virtualizes thousands of turns and a fixed step cap either stops
  // short (truncated/imbalanced capture → hard reject → "not available") or, with
  // a high cap, blows past the background's CONTENT_CAPTURE_TIMEOUT_MS (45 s) and
  // shows "capture timed out". The budget keeps the harvest safely under that
  // timeout while still reaching the bottom of any chat that fits in the window.
  const MANUAL_SCROLL_BUDGET_MS = 26000;
  const MANUAL_SCROLL_MAX_STEPS = 1200; // hard safety ceiling; the budget governs.
  const MIN_SCROLL_HARVEST_DELTA = 80;
  // A long chat's /backend-api/conversation/<id> response is larger and resolves
  // LATER than a short one's. Poll for the passively-intercepted tree before
  // demoting to the DOM scroll, so a late-arriving complete capture is preferred
  // over a partial virtualized-DOM harvest (ADR-0007 / D-015 §1-§6). Kept short so
  // poll + scroll budget stays under the background CONTENT_CAPTURE_TIMEOUT_MS.
  const INTERCEPTION_POLL_MS = 300;
  const INTERCEPTION_QUICK_TICKS = 3;  // ~0.9 s: catch an already-cached/replayed tree
  const INTERCEPTION_POLL_TICKS = 12;  // ~3.6 s fallback poll after the backend fetch

  // ── network interception bridge (ADR-0007 / D-015 §1-§6) ────────────────────
  // The MAIN-world interceptor.js posts the conversation-tree JSON the ChatGPT app
  // already fetched. We consume it here — it is the PRIMARY capture path; the DOM
  // scroll harvest below is the demoted fallback. These two strings are the §1
  // postMessage discriminator and must match interceptor.js exactly.
  const INTERCEPT_SOURCE = "saf-capture";
  const INTERCEPT_KIND = "conversation_json";
  const INTERCEPTION_MAX_RETRIES = 20;

  function queryUsingFallbacks(documentRef, selectors) {
    for (const selector of selectors) {
      const nodes = Array.from(documentRef.querySelectorAll(selector));
      if (nodes.length) return { nodes, selector };
    }
    return { nodes: [], selector: null };
  }

  function firstUsingFallbacks(documentRef, selectors) {
    for (const selector of selectors) {
      const node = documentRef.querySelector(selector);
      if (node) return { node, selector };
    }
    return { node: null, selector: null };
  }

  function textOf(node) {
    return String(node?.innerText ?? node?.textContent ?? "").trim();
  }

  function compareDocumentOrder(left, right) {
    if (left === right) return 0;
    const position = left.compareDocumentPosition?.(right) ?? 0;
    const following = globalScope.Node?.DOCUMENT_POSITION_FOLLOWING ?? 4;
    const preceding = globalScope.Node?.DOCUMENT_POSITION_PRECEDING ?? 2;
    if (position & following) return -1;
    if (position & preceding) return 1;
    return 0;
  }

  function roleFromAuthorNode(node) {
    const role = String(node?.getAttribute?.("data-message-author-role") || "").toLowerCase();
    if (role === "user" || role === "assistant") return role;
    const testId = String(node?.getAttribute?.("data-testid") || "").toLowerCase();
    if (testId === "user-message" || testId === "human-message") return "user";
    if (testId === "assistant-message") return "assistant";
    return null;
  }

  function closestTurnContainer(node) {
    return node?.closest?.("[data-message-id]") || null;
  }

  function candidateKey(candidate) {
    const container = closestTurnContainer(candidate.node);
    const stableId =
      container?.getAttribute?.("data-message-id") ||
      candidate.node.getAttribute?.("data-message-id");
    return stableId
      ? `${candidate.role}:${stableId}`
      : `${candidate.role}:idx-${candidate.roleIndex}:text-${stableHash(textOf(candidate.node).slice(0, 500))}`;
  }

  function platformFromUrl(url) {
    try {
      const hostname = new URL(String(url || "")).hostname.toLowerCase();
      if (hostname === "claude.ai" || hostname.endsWith(".claude.ai")) return "claude";
      if (
        hostname === "chatgpt.com" ||
        hostname.endsWith(".chatgpt.com") ||
        hostname === "chat.openai.com"
      ) {
        return "chatgpt";
      }
    } catch (_) {
      // Legacy tests call helpers without a URL.
    }
    return "chatgpt";
  }

  function modelIdFromText(value, platform = "chatgpt") {
    const text = String(value || "").toLowerCase().replace(/[–—]/g, "-");
    if (platform === "claude") {
      const claude = text.match(
        /\bclaude\s*(opus|sonnet|haiku)?\s*(\d+(?:[.]\d+)?)?(?:\s*([a-z]+))?\b/,
      );
      if (claude) {
        return ["claude", claude[1], claude[2], claude[3]]
          .filter(Boolean)
          .map((part) => part.replace(/\s+/g, "-"))
          .join("-");
      }
      return "unknown";
    }

    const gpt = text.match(
      /\b(?:chat)?gpt[\s-]*(\d+(?:[.]\d+)?o?)(?:[\s-]+(mini|nano|pro))?\b/,
    );
    if (gpt) return `gpt-${gpt[1]}${gpt[2] ? `-${gpt[2]}` : ""}`;

    const reasoning = text.match(/\b(o\d+(?:[.]\d+)?)(?:[\s-]+(mini|nano|pro))?\b/);
    if (reasoning) {
      return `${reasoning[1]}${reasoning[2] ? `-${reasoning[2]}` : ""}`;
    }
    return "unknown";
  }

  function detectPartnerModel(documentRef, now = new Date(), locationRef = null) {
    const { node } = firstUsingFallbacks(documentRef, SELECTORS.modelSelector);
    const platform = platformFromUrl(locationRef?.href || locationRef || "");
    return {
      family: platform === "claude" ? "anthropic" : "openai",
      model_id: modelIdFromText(textOf(node), platform),
      era_key: now.toISOString().slice(0, 7),
    };
  }

  function conversationIdFromUrl(url) {
    try {
      const parsed = new URL(url);
      const platform = platformFromUrl(parsed.href);
      const match = platform === "claude"
        ? parsed.pathname.match(/\/(?:chat|chats)\/([^/?#]+)/)
        : parsed.pathname.match(/\/c\/([^/?#]+)/);
      return match ? decodeURIComponent(match[1]) : null;
    } catch (_) {
      return null;
    }
  }

  function historyItems(documentRef) {
    const { nodes } = queryUsingFallbacks(documentRef, SELECTORS.historyItems);
    const seen = new Set();
    return nodes.reduce((items, node) => {
      const anchor = node.matches?.("a[href]") ? node : node.querySelector?.("a[href]");
      const href = anchor?.href || node.href;
      const conversationId = conversationIdFromUrl(href);
      if (!conversationId || seen.has(conversationId)) return items;
      seen.add(conversationId);
      items.push({
        conversation_id: conversationId,
        title: textOf(node) || textOf(anchor) || "Untitled conversation",
        url: href,
      });
      return items;
    }, []);
  }

  function createDraftId(cryptoRef, now) {
    const random = cryptoRef?.randomUUID?.();
    return `draft-${random || now().toString(36)}`;
  }

  function stableHash(value) {
    let hash = 2166136261;
    const text = String(value || "");
    for (let i = 0; i < text.length; i += 1) {
      hash ^= text.charCodeAt(i);
      hash = Math.imul(hash, 16777619);
    }
    return (hash >>> 0).toString(36);
  }

  // The conversation id ChatGPT's own backend call carries, e.g.
  // /backend-api/conversation/<uuid>. Used to anchor an intercepted capture to the
  // right conversation even before the /c/<id> URL settles.
  function conversationIdFromBackendUrl(url) {
    try {
      const match = String(url || "").match(
        /\/backend-api\/conversation\/([0-9a-f-]{16,})/i,
      );
      return match ? match[1] : null;
    } catch (_) {
      return null;
    }
  }

  function collectTextParts(value, depth = 0) {
    if (depth > 6 || value == null) return [];
    if (typeof value === "string") return [value];
    if (Array.isArray(value)) {
      return value.flatMap((item) => collectTextParts(item, depth + 1));
    }
    if (typeof value !== "object") return [];
    const preferred = [];
    for (const key of ["text", "content", "value"]) {
      if (typeof value[key] === "string") preferred.push(value[key]);
    }
    if (preferred.length) return preferred;
    return [];
  }

  function textFromMessageContent(content) {
    if (!content || typeof content !== "object") return null;
    const parts = Array.isArray(content.parts)
      ? collectTextParts(content.parts)
      : collectTextParts(content.text ?? content.content ?? content);
    const text = parts.join("\n").trim();
    return text || null;
  }

  function inferCurrentNode(mapping) {
    if (!mapping || typeof mapping !== "object") return null;
    const ids = Object.keys(mapping);
    const referencedParents = new Set();
    const referencedChildren = new Set();
    for (const [id, node] of Object.entries(mapping)) {
      if (!node || typeof node !== "object") continue;
      if (node.parent) referencedParents.add(String(node.parent));
      if (Array.isArray(node.children)) {
        for (const child of node.children) referencedChildren.add(String(child));
      }
      if (Array.isArray(node.child_ids)) {
        for (const child of node.child_ids) referencedChildren.add(String(child));
      }
      if (node.parent && mapping[String(node.parent)] && !referencedChildren.has(id)) {
        referencedChildren.add(id);
      }
    }
    const leaves = ids.filter((id) => {
      const node = mapping[id];
      const children = Array.isArray(node?.children) ? node.children : node?.child_ids;
      return !referencedParents.has(id) && (!Array.isArray(children) || children.length === 0);
    });
    const candidates = leaves.length ? leaves : ids.filter((id) => !referencedChildren.has(id));
    let best = null;
    let bestDepth = -1;
    for (const id of candidates) {
      let depth = 0;
      let cursor = id;
      const seen = new Set();
      while (cursor && mapping[cursor] && !seen.has(cursor)) {
        seen.add(cursor);
        depth += 1;
        cursor = mapping[cursor].parent;
      }
      if (depth > bestDepth) {
        best = id;
        bestDepth = depth;
      }
    }
    return best;
  }

  function conversationPayloadFromValue(value, depth = 0, seen = new Set()) {
    if (!value || typeof value !== "object" || depth > 10 || seen.has(value)) return null;
    seen.add(value);
    if (value.mapping && typeof value.mapping === "object") {
      const currentNode = value.current_node || value.currentNode || inferCurrentNode(value.mapping);
      if (currentNode) return { ...value, current_node: currentNode };
    }
    if (Array.isArray(value)) {
      for (const item of value) {
        const found = conversationPayloadFromValue(item, depth + 1, seen);
        if (found) return found;
      }
      return null;
    }
    for (const key of [
      "conversation",
      "data",
      "shared_conversation",
      "share",
      "item",
      "props",
      "pageProps",
      "dehydratedState",
      "queries",
      "state",
      "result",
      "response",
    ]) {
      if (key in value) {
        const found = conversationPayloadFromValue(value[key], depth + 1, seen);
        if (found) return found;
      }
    }
    for (const child of Object.values(value)) {
      const found = conversationPayloadFromValue(child, depth + 1, seen);
      if (found) return found;
    }
    return null;
  }

  /**
   * activePathFromMapping(convo) — ADR-0007 / D-015 §2.
   *
   * ChatGPT stores a conversation as a TREE (`mapping`); the thread the user sees
   * is the single path from `current_node` up to the root, reversed into display
   * order. This walks that active branch ONLY — alternate/edited branches are never
   * included — and returns turns in the existing snapshot shape.
   *
   * Fail-closed (§4): any structural problem yields `{ complete: false, reason }`
   * with no turns, so a shape mismatch degrades to the DOM fallback instead of
   * silently emitting a partial transcript. Reused for export backfill (§9): takes
   * a single `convo` object, no DOM dependency.
   */
  function activePathFromMapping(convo) {
    convo = conversationPayloadFromValue(convo) || convo;
    if (!convo || typeof convo !== "object") {
      return { turns: [], expected_turn_count: 0, complete: false, reason: "no_convo" };
    }
    let nodeId = convo.current_node; // VERIFY: current_node
    if (!nodeId) {
      nodeId = inferCurrentNode(convo.mapping);
      if (!nodeId) {
        return { turns: [], expected_turn_count: 0, complete: false, reason: "no_current_node" };
      }
    }
    const mapping = convo.mapping; // VERIFY: mapping
    if (!mapping || typeof mapping !== "object") {
      return { turns: [], expected_turn_count: 0, complete: false, reason: "no_mapping" };
    }

    const chain = [];
    const seen = new Set();
    while (nodeId) {
      if (seen.has(nodeId)) {
        return { turns: [], expected_turn_count: 0, complete: false, reason: "cycle" };
      }
      seen.add(nodeId);
      const node = mapping[nodeId];
      if (node === undefined) {
        return { turns: [], expected_turn_count: 0, complete: false, reason: "broken_chain" };
      }
      chain.push(node);
      nodeId = node.parent; // VERIFY: node.parent (null/undefined at root → stop)
    }
    chain.reverse(); // root → current_node (display order)

    let modelSlug = null;
    const turns = [];
    for (const node of chain) {
      const message = node && node.message; // VERIFY: node.message
      if (!message) continue;
      const role = message.author && message.author.role; // VERIFY: message.author.role
      if (role !== "user" && role !== "assistant") continue; // drop system/tool
      if (message.metadata && message.metadata.is_visually_hidden_from_conversation) {
        continue; // VERIFY: metadata.is_visually_hidden_from_conversation
      }
      const text = textFromMessageContent(message.content);
      if (!text) continue;
      if (
        role === "assistant" &&
        message.metadata &&
        typeof message.metadata.model_slug === "string" // VERIFY: metadata.model_slug
      ) {
        modelSlug = message.metadata.model_slug;
      }
      const createTime = message.create_time; // VERIFY: message.create_time (seconds)
      turns.push({
        role,
        text,
        message_id: typeof message.id === "string" ? message.id : null,
        timestamp_ms: Number.isFinite(createTime) ? Math.round(createTime * 1000) : null,
        turn_index: turns.length,
      });
    }

    if (!turns.length) {
      return { turns: [], expected_turn_count: 0, complete: false, reason: "no_visible_turns" };
    }
    return {
      turns,
      expected_turn_count: turns.length,
      complete: true,
      reason: null,
      model_slug: modelSlug,
    };
  }

  function createCaptureController(options = {}) {
    const documentRef = options.document || globalScope.document;
    const locationRef = options.location || globalScope.location;
    const windowRef = options.window || globalScope;
    const now = options.now || Date.now;
    const cryptoRef = options.crypto || globalScope.crypto;
    const MutationObserverRef = options.MutationObserver || globalScope.MutationObserver;
    const setTimeoutRef = options.setTimeout || globalScope.setTimeout.bind(globalScope);
    const clearTimeoutRef = options.clearTimeout || globalScope.clearTimeout.bind(globalScope);
    const fetchRef =
      options.fetch ||
      (typeof globalScope.fetch === "function" ? globalScope.fetch.bind(globalScope) : null);
    const warn = options.warn || ((message) => globalScope.console?.warn?.(message));
    const sendMessage = options.sendMessage || ((message) => {
      try {
        globalScope.chrome?.runtime?.sendMessage?.(message, () => {
          void globalScope.chrome?.runtime?.lastError;
        });
      } catch (_) {
        // The extension may have reloaded while this page remained open.
      }
    });

    if (!documentRef || !MutationObserverRef) {
      throw new Error("content capture requires a document and MutationObserver");
    }

    const initialConversationId =
      conversationIdFromUrl(locationRef?.href) || createDraftId(cryptoRef, now);
    const state = {
      conversationId: initialConversationId,
      records: new Map(),
      pendingTelemetry: new Map(),
      selectorHealth: "ok",
      selectorMisses: new Set(),
      lastCaptureAt: now(),
      autoUploadQueued: false,
      idleTimer: null,
      stopWasPresent: false,
      pendingHumanCapture: false,
      awaitingAssistant: false,
      awaitingFreshSubmit: initialConversationId.startsWith("draft-"),
      lastCaptureMethod: null,
      expectedTurnCount: null,
      captureComplete: null,
      captureEnabled: false,
      started: false,
      stopped: false,
      warned: new Set(),
      domOrderOffset: 0,
      lastHref: String(locationRef?.href || ""),
      locationCaptureTimer: null,
      locationCaptureInFlight: false,
      lastConvo: null,
      interceptionConvoId: null,
      lastInterceptionCapture: null,
      interceptionRetries: 0,
      interceptionRetryTimer: null,
      backendFetchStatus: null,
    };

    function warnOnce(key, message) {
      if (state.warned.has(key)) return;
      state.warned.add(key);
      warn(`[SAF] ${message}`);
    }

    function markSelectorMiss(selectorGroup, warning) {
      state.selectorMisses.add(selectorGroup);
      if (state.selectorHealth !== "stream_incomplete") {
        state.selectorHealth = "selector_miss";
      }
      if (warning) warnOnce(selectorGroup, warning);
    }

    function markSelectorSuccess(selectorGroup) {
      state.selectorMisses.delete(selectorGroup);
      if (
        state.selectorHealth === "selector_miss" &&
        state.selectorMisses.size === 0
      ) {
        state.selectorHealth = "ok";
      }
    }

    function partnerModelSnapshot() {
      const { node } = firstUsingFallbacks(documentRef, SELECTORS.modelSelector);
      if (node) markSelectorSuccess("modelSelector");
      else markSelectorMiss("modelSelector", "all model selectors missed");
      const platform = platformFromUrl(locationRef?.href || "");
      return {
        family: platform === "claude" ? "anthropic" : "openai",
        model_id: modelIdFromText(textOf(node), platform),
        era_key: new Date(now()).toISOString().slice(0, 7),
      };
    }

    function pageTitle() {
      const suffix = platformFromUrl(locationRef?.href || "") === "claude" ? "Claude" : "ChatGPT";
      return String(documentRef.title || "").replace(new RegExp(`\\s*[|\\-]\\s*${suffix}\\s*$`, "i"), "");
    }

    function allCandidates() {
      const containers = queryUsingFallbacks(documentRef, SELECTORS.turnContainer);
      const containerCandidates = [];
      const roleCounts = { user: 0, assistant: 0 };
      for (const container of containers.nodes) {
        const explicit = container.matches?.("[data-message-author-role]")
          ? container
          : container.querySelector?.("[data-message-author-role]");

        let role = roleFromAuthorNode(explicit);
        let node = explicit || container;
        if (!role) continue;

        const roleIndex = roleCounts[role]++;
        containerCandidates.push({ node, role, roleIndex });
      }

      if (
        containerCandidates.some((candidate) => candidate.role === "user") &&
        containerCandidates.some((candidate) => candidate.role === "assistant")
      ) {
        const combined = containerCandidates.sort((left, right) =>
          compareDocumentOrder(left.node, right.node),
        );
        combined.forEach((candidate, domOrder) => {
          candidate.domOrder = state.domOrderOffset + domOrder;
          candidate.key = candidateKey(candidate);
        });
        return {
          combined,
          users: {
            nodes: combined.filter((candidate) => candidate.role === "user").map((c) => c.node),
            selector: containers.selector,
          },
          assistants: {
            nodes: combined.filter((candidate) => candidate.role === "assistant").map((c) => c.node),
            selector: containers.selector,
          },
        };
      }

      const roleTurns = queryUsingFallbacks(documentRef, SELECTORS.roleTurn);
      const explicitUsers = roleTurns.nodes
        .filter((node) => roleFromAuthorNode(node) === "user")
        .map((node, roleIndex) => ({ node, role: "user", roleIndex }));
      const explicitAssistants = roleTurns.nodes
        .filter((node) => roleFromAuthorNode(node) === "assistant")
        .map((node, roleIndex) => ({ node, role: "assistant", roleIndex }));

      const userFallback = explicitUsers.length
        ? { nodes: explicitUsers.map((candidate) => candidate.node), selector: roleTurns.selector }
        : queryUsingFallbacks(documentRef, SELECTORS.userTurn);
      const assistantFallback = explicitAssistants.length
        ? { nodes: explicitAssistants.map((candidate) => candidate.node), selector: roleTurns.selector }
        : queryUsingFallbacks(documentRef, SELECTORS.aiTurn);

      const users = userFallback;
      const assistants = assistantFallback;
      const combined = [
        ...(explicitUsers.length
          ? explicitUsers
          : users.nodes.map((node, roleIndex) => ({ node, role: "user", roleIndex }))),
        ...(explicitAssistants.length
          ? explicitAssistants
          : assistants.nodes.map((node, roleIndex) => ({
              node,
              role: "assistant",
              roleIndex,
            }))),
      ].sort((left, right) => compareDocumentOrder(left.node, right.node));

      combined.forEach((candidate, domOrder) => {
        candidate.domOrder = state.domOrderOffset + domOrder;
        candidate.key = candidateKey(candidate);
      });
      return { combined, users, assistants };
    }

    function orderedRecords() {
      return Array.from(state.records.values()).sort(
        (left, right) => left.domOrder - right.domOrder,
      );
    }

    function sleep(ms) {
      return new Promise((resolve) => setTimeoutRef(resolve, ms));
    }

    function scrollRoot() {
      const seen = new Set();
      const candidates = [];
      const add = (node) => {
        if (!node || seen.has(node)) return;
        seen.add(node);
        candidates.push(node);
      };

      add(documentRef.querySelector?.("main"));
      add(documentRef.querySelector?.('[role="main"]'));
      add(documentRef.scrollingElement);
      add(documentRef.documentElement);
      add(documentRef.body);

      const nested = Array.from(
        documentRef.querySelectorAll?.(
          'main, [role="main"], [data-testid*="conversation"], [data-message-id], [data-message-author-role]',
        ) || [],
      );
      for (const node of nested) {
        add(node);
        let parent = node.parentElement;
        while (parent && parent !== documentRef.body && parent !== documentRef.documentElement) {
          add(parent);
          parent = parent.parentElement;
        }
      }

      const best = candidates
        .map((node) => ({
          node,
          delta: Number(node.scrollHeight || 0) - Number(node.clientHeight || 0),
        }))
        .filter((item) => item.delta > MIN_SCROLL_HARVEST_DELTA)
        .sort((left, right) => right.delta - left.delta)[0];
      return best?.node || documentRef.scrollingElement || documentRef.documentElement || documentRef.body;
    }

    function scrollToY(root, top) {
      if (!root) return;
      if (typeof root.scrollTo === "function") {
        root.scrollTo({ top, behavior: "instant" });
      } else {
        root.scrollTop = top;
      }
      if (root === documentRef.scrollingElement && typeof globalScope.scrollTo === "function") {
        globalScope.scrollTo(0, top);
      }
    }

    async function captureVisibleConversation(reportMiss = false) {
      const userChanged = captureUsers(reportMiss);
      const aiChanged = captureCompletedAssistants(reportMiss);
      return Boolean(userChanged || aiChanged);
    }

    function harvestEmbeddedConversation() {
      const scripts = Array.from(documentRef.querySelectorAll?.("script") || []);
      for (const script of scripts) {
        const raw = String(script.textContent || "").trim();
        if (!raw || (!raw.includes("mapping") && !raw.includes("current_node"))) continue;
        try {
          const parsed = JSON.parse(raw);
          const convo = conversationPayloadFromValue(parsed);
          if (convo) return convo;
        } catch (_) {
          // Non-JSON scripts are ignored. Network interception remains primary.
        }
      }
      return null;
    }

    function captureFromEmbeddedConversation() {
      const convo = harvestEmbeddedConversation();
      if (!convo) return null;
      return ingestInterception(convo, locationRef?.href || "");
    }

    async function scrollToLoadThenExtract(reportMiss = true) {
      const root = scrollRoot();
      if (!root) {
        await captureVisibleConversation(reportMiss);
        return { loaded: false, capturedTurns: orderedRecords().length };
      }

      const maxScroll = () => Math.max(
        0,
        Number(root.scrollHeight || 0) - Number(root.clientHeight || 0),
      );
      const height = () => Number(root.scrollHeight || 0);
      const stepSize = () => Math.max(
        320,
        Math.floor(Number(root.clientHeight || globalScope.innerHeight || 800) * 0.75),
      );
      const originalTop = Number(root.scrollTop || globalScope.scrollY || 0);
      const deadline = now() + MANUAL_SCROLL_BUDGET_MS;
      let previousHeight = -1;
      let stableAtBottom = 0;

      try {
        scrollToY(root, 0);
        await sleep(MANUAL_SCROLL_SETTLE_MS);
        await captureVisibleConversation(reportMiss);

        for (let step = 0; step < MANUAL_SCROLL_MAX_STEPS; step += 1) {
          state.domOrderOffset = Math.floor(Number(root.scrollTop || 0) * 1000);
          await captureVisibleConversation(reportMiss);

          const currentTop = Number(root.scrollTop || 0);
          const bottom = maxScroll();
          const currentHeight = height();
          const atBottom = currentTop >= bottom - 8;
          const heightStable = currentHeight === previousHeight;
          const scanPct = bottom > 0 ? 10 + ((Math.min(currentTop, bottom) / bottom) * 65) : 75;
          notifyAnalyseProgress("capturing", scanPct, "Loading full chat...");

          if (atBottom && heightStable) {
            stableAtBottom += 1;
            if (stableAtBottom >= 2) break;
          } else {
            stableAtBottom = 0;
          }

          // Time budget, not a fixed step count: stop before the background's
          // capture timeout rather than truncating a long chat at an arbitrary step.
          if (now() >= deadline) {
            warnOnce(
              "scroll_budget_exhausted",
              "DOM scroll budget exhausted before reaching the end of the chat",
            );
            break;
          }

          previousHeight = currentHeight;
          const nextTop = atBottom ? bottom : Math.min(bottom, currentTop + stepSize());
          scrollToY(root, nextTop);
          await sleep(MANUAL_SCROLL_SETTLE_MS);
        }

        state.domOrderOffset = Math.floor(Number(root.scrollTop || 0) * 1000);
        await captureVisibleConversation(reportMiss);
        return { loaded: true, capturedTurns: orderedRecords().length };
      } finally {
        state.domOrderOffset = 0;
        scrollToY(root, originalTop);
      }
    }

    async function captureFullConversationForManual() {
      enableCapture();
      // D-016: always send a fresh ready-ping so the interceptor replays any cached
      // conversation payload. enableCapture() sends the ping on the FIRST call, but
      // if capture was already enabled from page load the second call returns early
      // and no ping is sent — the interceptor's cache is never replayed. Sending an
      // extra ping is harmless (the interceptor no-ops when its cache is empty).
      try {
        windowRef.postMessage?.(
          { source: INTERCEPT_SOURCE, kind: "ready-ping" },
          ownOrigin() || "*",
        );
      } catch (_) { /* never break capture on postMessage failure */ }
      syncConversation();
      state.awaitingFreshSubmit = false;
      const isSharePage = /\/share\//.test(String(locationRef?.href || ""));
      const embedded = captureFromEmbeddedConversation();
      if (embedded) {
        notifyAnalyseProgress("captured", 85, "Full chat captured.");
        return true;
      }
      // Helper: has passive interception (handleWindowMessage on a live/replayed
      // post) already produced a complete capture for THIS conversation? If a tree
      // arrived but hasn't emitted (listener race / deferred mid-stream retry), force
      // the walk — ingestInterception no-ops while the assistant is still streaming.
      const tryInterception = () => {
        if (state.lastConvo && state.interceptionConvoId === state.conversationId) return true;
        if (state.lastConvo && ingestInterception(state.lastConvo, locationRef?.href || "")) return true;
        return false;
      };

      // 1) A brief wait for an interception that is essentially already here (the
      //    document_start fetch the interceptor cached, replayed on our ready-ping).
      for (let tick = 0; tick < INTERCEPTION_QUICK_TICKS; tick += 1) {
        await sleep(INTERCEPTION_POLL_MS);
        if (tryInterception()) {
          notifyAnalyseProgress("captured", 85, "Full chat captured.");
          return true;
        }
      }

      // 2) D-015 §9: actively fetch the conversation endpoint ourselves. This is the
      //    authoritative, virtualization-proof path — it works even when ChatGPT
      //    server-rendered the page and never fetched the tree (interception silent),
      //    which is exactly the case where the DOM scroll loses long assistant turns
      //    and the balance gate then rejects the capture. Runs for share pages too
      //    (their /backend-api/share/<id> tree), since their DOM is equally
      //    virtualized. Never originates with our own credentials — the browser
      //    attaches the existing session cookie.
      notifyAnalyseProgress("capturing", 40, "Fetching the full chat…");
      const backfilled = await fetchConversationFromBackend();
      if (backfilled) {
        notifyAnalyseProgress("captured", 85, "Full chat captured.");
        return true;
      }

      // 3) Backend fetch unavailable (e.g. cookie auth rejected). Keep polling for a
      //    passively-intercepted tree the page may still be fetching, re-sending the
      //    ready-ping each tick, before demoting to the DOM scroll.
      for (let tick = 0; tick < INTERCEPTION_POLL_TICKS; tick += 1) {
        await sleep(INTERCEPTION_POLL_MS);
        if (tryInterception()) {
          notifyAnalyseProgress("captured", 85, "Full chat captured.");
          return true;
        }
        notifyAnalyseProgress("capturing", 30, "Waiting for the full chat to load…");
        try {
          windowRef.postMessage?.(
            { source: INTERCEPT_SOURCE, kind: "ready-ping" },
            ownOrigin() || "*",
          );
        } catch (_) { /* never break capture on postMessage failure */ }
      }
      notifyAnalyseProgress("capturing", 8, "Scanning visible chat...");
      await scrollToLoadThenExtract(true);
      // D-015 §7: the scroll harvest is a best-effort FALLBACK — it cannot PROVE
      // completeness against virtualization, so completeness is UNKNOWN (null), never
      // true and never false. null routes the server to its legacy role-balance gate.
      state.lastCaptureMethod = "scroll_probe";
      state.captureComplete = null;
      state.expectedTurnCount = null;
      notifyAnalyseProgress("captured", 75, "Chat captured.");
      if (isSharePage) {
        markSelectorMiss(
          "shareConversationJson",
          "shared conversation JSON unavailable; refusing partial DOM capture",
        );
        notifyAnalyseProgress(
          "error",
          0,
          "Full shared chat was not available. Reload the share page and try again.",
        );
        return false;
      }
      return maybeQueueCapture(true);
    }

    // ── network interception consumer (ADR-0007 / D-015 §1-§6) ─────────────────

    function ownOrigin() {
      try {
        return (
          locationRef?.origin ||
          (locationRef?.href ? new URL(locationRef.href).origin : null)
        );
      } catch (_) {
        return null;
      }
    }

    function mergeInterceptionTurns(activePath, includeDomTail = true) {
      // §6: the active path is the authoritative HISTORY (everything virtualization
      // hid); the DOM record store owns only the freshly-streamed tail. Dedupe by the
      // stable `role:message_id` key — ChatGPT's DOM data-message-id === mapping
      // message.id, so a turn captured both ways collapses to one. JSON wins; any
      // DOM-only tail turns (newer than the fetched JSON) append in document order.
      const activeKeys = new Set(
        activePath.turns
          .filter((turn) => turn.message_id)
          .map((turn) => `${turn.role}:${turn.message_id}`),
      );
      const tail = includeDomTail
        ? orderedRecords().filter((record) => !activeKeys.has(record.key))
        : [];
      const merged = [
        ...activePath.turns.map((turn) => ({
          role: turn.role,
          text: turn.text,
          timestamp_ms: turn.timestamp_ms,
        })),
        ...tail.map((record) => ({
          role: record.role,
          text: record.text,
          timestamp_ms: record.timestampMs,
        })),
      ];
      return merged.map((turn, turnIndex) => ({ ...turn, turn_index: turnIndex }));
    }

    function buildInterceptionCapture(activePath, url) {
      const isSharePage = /\/share\//.test(String(locationRef?.href || url || ""));
      const turns = mergeInterceptionTurns(activePath, !isSharePage);
      const partner = partnerModelSnapshot();
      // §5: prefer the JSON's model_slug; family stays hardcoded "openai" (#20).
      const modelId =
        typeof activePath.model_slug === "string" && activePath.model_slug.trim()
          ? activePath.model_slug.trim()
          : partner.model_id;
      return {
        conversation_id: state.conversationId,
        source: "chatgpt_live",
        partner_model: { family: partner.family, model_id: modelId, era_key: partner.era_key },
        turns,
        telemetry: { selector_health: "ok" },
        metadata: {
          title: pageTitle(),
          url: locationRef?.href || url || "",
        },
        capture_method: "interception",
        expected_turn_count: activePath.expected_turn_count,
        // §7: captured_turn_count MUST equal turns.length (the server re-derives it).
        captured_turn_count: turns.length,
        capture_complete: true,
      };
    }

    function emitInterception(activePath, url) {
      const convoId = conversationIdFromBackendUrl(url);
      if (convoId && convoId !== state.conversationId) {
        // The backend URL's id is authoritative over a draft/placeholder DOM id.
        state.conversationId = convoId;
      }
      const capture = buildInterceptionCapture(activePath, url);
      state.lastCaptureMethod = "interception";
      state.captureComplete = true;
      state.expectedTurnCount = activePath.expected_turn_count;
      state.interceptionConvoId = state.conversationId;
      state.lastInterceptionCapture = capture;
      state.interceptionRetries = 0;
      sendMessage({
        type: MESSAGE_TYPES.CAPTURE_READY,
        reason: "interception",
        capture,
      });
      notifyUpdated();
      return capture;
    }

    function scheduleInterceptionRetry(url) {
      if (state.interceptionRetryTimer) clearTimeoutRef(state.interceptionRetryTimer);
      if (state.interceptionRetries >= INTERCEPTION_MAX_RETRIES) return;
      state.interceptionRetries += 1;
      state.interceptionRetryTimer = setTimeoutRef(() => {
        state.interceptionRetryTimer = null;
        if (!state.lastConvo) return;
        // §4: still streaming → keep buffering, never discard.
        if (stopButtonPresent()) {
          scheduleInterceptionRetry(url);
          return;
        }
        const activePath = activePathFromMapping(state.lastConvo);
        if (activePath.complete) emitInterception(activePath, url);
      }, STREAM_IDLE_MS);
    }

    // §1-§6: consume a MAIN-world `saf-capture` payload, walk the active path, and
    // emit the existing SAF_CAPTURE_READY snapshot. Returns the emitted capture, or
    // null when the walk did not PROVE completeness (caller falls back to the demoted
    // DOM scroll harvest). Never sets capture_complete=false here — §4 edge cases
    // fall through to the fallback (null), only the server quarantines on false.
    function ingestInterception(convo, url) {
      const activePath = activePathFromMapping(convo);
      if (!activePath.complete) return null;
      state.lastConvo = convo;
      if (stopButtonPresent()) {
        // §4: the last kept turn may be mid-stream — buffer and retry, do not discard.
        scheduleInterceptionRetry(url);
        return null;
      }
      return emitInterception(activePath, url);
    }

    // Active backfill (D-015 §9): the interceptor only PASSIVELY observes the fetch
    // the page makes. On a hard reload ChatGPT may server-render the conversation
    // and never fetch /backend-api/conversation/<id>, so interception delivers
    // nothing and the DOM scroll is left to fight virtualization (long assistant
    // turns get unmounted before they can be read → a lopsided user/assistant
    // count → the balance gate rejects the capture). When passive interception has
    // produced nothing, request that same endpoint ourselves from the page's own
    // origin. The browser attaches the existing session cookie automatically — we
    // never read, store, or forward any auth token; a 401/non-JSON response just
    // returns null and the caller falls through to the DOM scroll. The mapping is
    // the whole tree, so the active-path walk is complete and balanced by
    // construction.
    // The backend endpoint that returns this page's conversation tree. Normal chats
    // live at /backend-api/conversation/<id>; a read-only SHARE page (no /c/ id,
    // virtualized DOM, no composer) exposes the same tree at /backend-api/share/<id>.
    function backendConversationEndpoint() {
      const origin = ownOrigin();
      if (!origin) return null;
      const href = String(locationRef?.href || "");
      const convoId = conversationIdFromUrl(href);
      if (convoId) return `${origin}/backend-api/conversation/${convoId}`;
      const shareMatch = href.match(/\/share\/(?:e\/)?([^/?#]+)/);
      if (shareMatch) return `${origin}/backend-api/share/${shareMatch[1]}`;
      return null;
    }

    function isExpectedInterceptionUrl(value) {
      const expected = backendConversationEndpoint();
      if (!expected) return false;
      try {
        const actual = new URL(String(value || ""), ownOrigin());
        const target = new URL(expected);
        return actual.origin === target.origin && actual.pathname === target.pathname;
      } catch (_) {
        return false;
      }
    }

    // The short-lived access token the ChatGPT web app itself obtains from its own
    // cookie-authed /api/auth/session endpoint. ChatGPT's /backend-api authorizes
    // with `Authorization: Bearer <token>`, not the cookie alone, so a cookie-only
    // backfill is rejected 401. We read this token transiently to authorize reading
    // the user's OWN conversation; it is never logged, persisted, or sent to the SAF
    // server (Track 0: credentials never enter the corpus at rest).
    async function fetchSessionAccessToken() {
      const origin = ownOrigin();
      if (!origin || !fetchRef) return null;
      try {
        const res = await fetchRef(`${origin}/api/auth/session`, {
          credentials: "include",
          headers: { accept: "application/json" },
        });
        if (!res || !res.ok) return null;
        const data = await res.json();
        return data && typeof data.accessToken === "string" && data.accessToken
          ? data.accessToken
          : null;
      } catch (_) {
        return null;
      }
    }

    async function fetchConversationFromBackend() {
      if (!fetchRef) {
        state.backendFetchStatus = "no_fetch_api";
        return null;
      }
      const url = backendConversationEndpoint();
      if (!url) {
        state.backendFetchStatus = "no_conversation_id";
        return null;
      }
      const attempt = (authHeader) =>
        fetchRef(url, {
          credentials: "include",
          headers: authHeader
            ? { accept: "application/json", authorization: authHeader }
            : { accept: "application/json" },
        });
      try {
        let res = await attempt(null);
        // Cookie alone rejected → retry once with the page's own bearer token.
        if (res && (res.status === 401 || res.status === 403)) {
          const token = await fetchSessionAccessToken();
          if (token) {
            state.backendFetchStatus = "retry_with_token";
            res = await attempt(`Bearer ${token}`);
          }
        }
        if (!res || !res.ok) {
          state.backendFetchStatus = res ? `http_${res.status}` : "no_response";
          warnOnce(
            "backend_fetch_failed",
            `backend conversation fetch returned ${res ? res.status : "no response"}`,
          );
          return null;
        }
        const json = await res.json();
        syncConversation();
        const capture = ingestInterception(json, url);
        state.backendFetchStatus = capture ? "ok" : "ok_but_incomplete";
        return capture;
      } catch (error) {
        state.backendFetchStatus = "error";
        warnOnce("backend_fetch_error", `backend conversation fetch failed: ${error.message}`);
        return null;
      }
    }

    function handleWindowMessage(event) {
      if (state.stopped || !state.captureEnabled) return;
      if (!event || event.origin !== ownOrigin()) return; // §1 origin guard
      const data = event.data;
      if (!data || typeof data !== "object") return;
      // §1 source/kind guard — trust nothing that fails this.
      if (data.source !== INTERCEPT_SOURCE || data.kind !== INTERCEPT_KIND) return;
      if (!isExpectedInterceptionUrl(data.url)) return;
      try {
        syncConversation();
        ingestInterception(data.convo, data.url);
      } catch (error) {
        warnOnce("interception_failed", `interception failed: ${error.message}`);
      }
    }

    function stableDraftConversationId() {
      const firstUser = orderedRecords().find((record) => record.role === "user");
      if (!firstUser?.text) return null;
      const title = String(documentRef.title || "").replace(/\s*[|\-]\s*ChatGPT\s*$/i, "");
      const url = (() => {
        try {
          const parsed = new URL(locationRef?.href || "");
          return `${parsed.origin}${parsed.pathname}`;
        } catch (_) {
          return String(locationRef?.href || "");
        }
      })();
      return `draft-${stableHash(`${url}\n${title}\n${firstUser.text.slice(0, 500)}`)}`;
    }

    // A human-readable account of WHY a manual capture produced nothing usable —
    // surfaced in the widget and the console so a failure is diagnosable in one
    // attempt instead of a blind retry. Names the path that ran (interception vs
    // DOM scroll), the user/assistant turn counts, and any missed selector groups.
    function captureDiagnostic() {
      const records = orderedRecords();
      const userCount = records.filter((r) => r.role === "user").length;
      const assistantCount = records.filter((r) => r.role === "assistant").length;
      const interceptionFired = Boolean(state.lastConvo);
      const misses = Array.from(state.selectorMisses);
      let path = "";
      try { path = new URL(String(locationRef?.href || "")).pathname; } catch (_) { path = String(locationRef?.href || ""); }
      const parts = [
        `captured user=${userCount}, assistant=${assistantCount}`,
        `interception=${interceptionFired ? "delivered" : "none"}`,
        `backend_fetch=${state.backendFetchStatus || "not_tried"}`,
        `url=${path}`,
        `selectors=${state.selectorHealth}`,
      ];
      if (misses.length) parts.push(`missed=[${misses.join(",")}]`);
      let reason;
      if (userCount === 0 && assistantCount === 0) {
        reason = interceptionFired
          ? "the conversation tree arrived but no user/assistant turns could be read from it"
          : "no chat turns were found on the page (selectors may not match this ChatGPT layout)";
      } else if (Math.abs(userCount - assistantCount) > 1) {
        reason = "the captured turns are imbalanced — part of the chat did not load before capture finished";
      } else {
        reason = "capture did not complete";
      }
      const detail = `${reason} — ${parts.join("; ")}.`;
      try { globalScope.console?.warn?.(`[SAF] capture failed: ${detail}`); } catch (_) {}
      return detail;
    }

    function snapshot() {
      const records = orderedRecords();
      return {
        conversation_id: state.conversationId,
        source: "chatgpt_live",
        partner_model: partnerModelSnapshot(),
        turns: records.map((record, turnIndex) => ({
          role: record.role,
          text: record.text,
          timestamp_ms: record.timestampMs,
          turn_index: turnIndex,
        })),
        telemetry: {
          dwell_ms: records.map((record) => record.dwellMs),
          copy_events: records.map((record) => record.copyEvents),
          edit_detected: records.map((record) => record.editDetected),
          selector_health: state.selectorHealth,
        },
        metadata: {
          title: pageTitle(),
          url: locationRef?.href || "",
        },
        capture_method: state.lastCaptureMethod,
        expected_turn_count: state.expectedTurnCount,
        captured_turn_count: records.length,
        capture_complete: state.captureComplete,
      };
    }

    function notifyUpdated() {
      sendMessage({ type: MESSAGE_TYPES.CAPTURE_UPDATED, capture: snapshot() });
    }

    function notifyAnalyseProgress(stage, percent, message) {
      sendMessage({
        type: MESSAGE_TYPES.ANALYSE_PROGRESS,
        progress: {
          stage,
          percent: Math.max(0, Math.min(100, Math.round(Number(percent) || 0))),
          message,
          captured_turns: orderedRecords().length,
          capture: snapshot(),
          updated_at: Date.now(),
        },
      });
    }

    function maybeQueueCapture(force = false) {
      syncConversation();
      const records = orderedRecords();
      const userCount = records.filter((record) => record.role === "user").length;
      const assistantCount = records.filter((record) => record.role === "assistant").length;
      const completedPairs = Math.min(userCount, assistantCount);
      if (completedPairs === 0) return false;
      if (Math.abs(userCount - assistantCount) > 1) {
        markSelectorMiss(
          "turnBalance",
          "captured turn counts are imbalanced; refusing incomplete transcript",
        );
        return false;
      }
      if (!force && (completedPairs < PAIRS_PER_UPLOAD || state.autoUploadQueued)) {
        return false;
      }
      if (!force) state.autoUploadQueued = true;
      sendMessage({
        type: MESSAGE_TYPES.CAPTURE_READY,
        reason: force ? "manual" : "three_completed_pairs",
        capture: snapshot(),
      });
      return true;
    }

    function captureCandidate(candidate) {
      const text = textOf(candidate.node);
      if (!text || state.records.has(candidate.key)) return false;

      const capturedAt = now();
      const pending = state.pendingTelemetry.get(candidate.key) || {};
      state.records.set(candidate.key, {
        key: candidate.key,
        role: candidate.role,
        text,
        timestampMs: capturedAt,
        domOrder: candidate.domOrder,
        dwellMs: Math.max(0, capturedAt - state.lastCaptureAt),
        copyEvents: pending.copyEvents || 0,
        editDetected: Boolean(pending.editDetected),
      });
      state.pendingTelemetry.delete(candidate.key);
      state.lastCaptureAt = capturedAt;
      return true;
    }

    function refreshCapturedCandidates(candidates) {
      let changed = false;
      for (const candidate of candidates) {
        const record = state.records.get(candidate.key);
        if (!record) continue;
        record.domOrder = candidate.domOrder;
        const currentText = textOf(candidate.node);
        if (currentText && currentText !== record.text) {
          record.text = currentText;
          record.editDetected = true;
          changed = true;
          if (record.role === "assistant") {
            state.selectorHealth = "stream_incomplete";
            warnOnce(
              "stream_incomplete",
              "assistant content changed after capture; marking stream incomplete",
            );
          }
        }
      }
      return changed;
    }

    function captureUsers(reportMiss = false) {
      const candidates = allCandidates();
      if (!candidates.users.nodes.length) {
        if (reportMiss) {
          markSelectorMiss("userTurn", "all user-turn selectors missed");
        }
        return false;
      }
      markSelectorSuccess("userTurn");
      let changed = refreshCapturedCandidates(candidates.combined);
      let capturedUser = false;
      for (const candidate of candidates.combined) {
        if (candidate.role === "user") {
          const captured = captureCandidate(candidate);
          capturedUser = captured || capturedUser;
          changed = captured || changed;
        }
      }
      if (capturedUser) state.pendingHumanCapture = false;
      if (changed) {
        notifyUpdated();
        maybeQueueCapture();
      }
      return changed;
    }

    function captureCompletedAssistants(reportMiss = false) {
      if (state.awaitingFreshSubmit && !reportMiss) return false;
      if (reportMiss) state.awaitingFreshSubmit = false;
      const candidates = allCandidates();
      if (!candidates.assistants.nodes.length) {
        if (reportMiss) {
          markSelectorMiss("aiTurn", "all assistant-turn selectors missed");
        }
        return false;
      }
      markSelectorSuccess("aiTurn");
      let changed = refreshCapturedCandidates(candidates.combined);
      let capturedAssistant = false;
      for (const candidate of candidates.combined) {
        if (candidate.role === "assistant") {
          const captured = captureCandidate(candidate);
          capturedAssistant = captured || capturedAssistant;
          changed = captured || changed;
        }
      }
      if (capturedAssistant) state.awaitingAssistant = false;
      if (changed) {
        notifyUpdated();
        maybeQueueCapture();
      }
      return changed;
    }

    function stopButtonPresent() {
      return Boolean(firstUsingFallbacks(documentRef, SELECTORS.stopButton).node);
    }

    function scheduleIdleCompletion() {
      if (state.idleTimer) clearTimeoutRef(state.idleTimer);
      state.idleTimer = setTimeoutRef(() => {
        state.idleTimer = null;
        captureCompletedAssistants(state.awaitingAssistant);
      }, STREAM_IDLE_MS);
    }

    function syncConversation() {
      const detected = conversationIdFromUrl(locationRef?.href);
      if (!detected) {
        if (state.conversationId.startsWith("draft-")) {
          const stableDraft = stableDraftConversationId();
          if (stableDraft && stableDraft !== state.conversationId) {
            state.conversationId = stableDraft;
            notifyUpdated();
            return true;
          }
          return false;
        }
        resetConversation(createDraftId(cryptoRef, now));
        notifyUpdated();
        return true;
      }
      if (detected === state.conversationId) return false;
      if (state.conversationId.startsWith("draft-")) {
        state.conversationId = detected;
        notifyUpdated();
        return true;
      }

      resetConversation(detected);
      notifyUpdated();
      return true;
    }

    function resetConversation(conversationId) {
      state.conversationId = conversationId;
      state.records.clear();
      state.pendingTelemetry.clear();
      state.selectorHealth = "ok";
      state.selectorMisses.clear();
      state.lastCaptureAt = now();
      state.autoUploadQueued = false;
      state.stopWasPresent = stopButtonPresent();
      state.pendingHumanCapture = false;
      state.awaitingAssistant = false;
      state.awaitingFreshSubmit = conversationId.startsWith("draft-");
      state.lastCaptureMethod = null;
      state.expectedTurnCount = null;
      state.captureComplete = null;
      state.lastConvo = null;
      state.interceptionConvoId = null;
      state.lastInterceptionCapture = null;
      state.interceptionRetries = 0;
      if (state.interceptionRetryTimer) {
        clearTimeoutRef(state.interceptionRetryTimer);
        state.interceptionRetryTimer = null;
      }
      state.warned.clear();
      if (state.captureEnabled) scheduleIdleCompletion();
    }

    function handleMutations() {
      if (state.stopped || !state.captureEnabled) return;
      syncConversation();
      if (state.pendingHumanCapture) captureUsers(true);
      const candidates = allCandidates();
      if (refreshCapturedCandidates(candidates.combined)) notifyUpdated();

      const stopIsPresent = stopButtonPresent();
      if (state.stopWasPresent && !stopIsPresent) {
        captureCompletedAssistants();
      }
      state.stopWasPresent = stopIsPresent;
      scheduleIdleCompletion();
    }

    function scheduleLocationExtraction() {
      if (state.stopped || !state.captureEnabled) return;
      if (state.locationCaptureTimer) clearTimeoutRef(state.locationCaptureTimer);
      state.locationCaptureTimer = setTimeoutRef(async () => {
        state.locationCaptureTimer = null;
        if (state.locationCaptureInFlight) return;
        state.locationCaptureInFlight = true;
        try {
          syncConversation();
          if (!conversationIdFromUrl(locationRef?.href)) return;
          await captureFullConversationForManual();
        } catch (error) {
          warnOnce("location_capture_failed", `location capture failed: ${error.message}`);
        } finally {
          state.locationCaptureInFlight = false;
        }
      }, MANUAL_SCROLL_SETTLE_MS);
    }

    function handleDocumentMutations() {
      const href = String(locationRef?.href || "");
      if (href === state.lastHref) return;
      state.lastHref = href;
      scheduleLocationExtraction();
    }

    function handleSubmit() {
      state.awaitingFreshSubmit = false;
      state.pendingHumanCapture = true;
      state.awaitingAssistant = true;
      setTimeoutRef(() => captureUsers(true), 0);
      setTimeoutRef(() => captureUsers(true), 100);
      setTimeoutRef(() => captureUsers(true), 300);
      scheduleIdleCompletion();
    }

    function candidateForNode(node) {
      if (!node) return null;
      const candidates = allCandidates().combined;
      return candidates.find(
        (candidate) =>
          candidate.node === node ||
          candidate.node.contains?.(node) ||
          node.contains?.(candidate.node),
      );
    }

    function handleCopy() {
      const selectionNode = documentRef.getSelection?.()?.anchorNode;
      const candidate = candidateForNode(selectionNode?.parentElement || selectionNode);
      if (!candidate) return;
      const record = state.records.get(candidate.key);
      if (record) {
        record.copyEvents += 1;
        notifyUpdated();
        return;
      }
      const pending = state.pendingTelemetry.get(candidate.key) || { copyEvents: 0 };
      pending.copyEvents += 1;
      state.pendingTelemetry.set(candidate.key, pending);
    }

    function handleMessage(message, _sender, sendResponse) {
      if (!message || typeof message.type !== "string") return undefined;
      if (message.type === MESSAGE_TYPES.GET_CAPTURE_STATE) {
        sendResponse?.({ ok: true, capture: snapshot() });
      } else if (message.type === MESSAGE_TYPES.GET_HISTORY_ITEMS) {
        const items = historyItems(documentRef);
        if (!items.length) warnOnce("history_miss", "all history-item selectors missed");
        sendResponse?.({ ok: true, items });
      } else if (message.type === MESSAGE_TYPES.ANALYSE_NOW) {
        syncConversation();
        // D-015 §6: prefer a proven-complete interception capture for this
        // conversation; the DOM scroll harvest is the demoted fallback and runs only
        // when interception has not produced a complete capture.
        if (state.lastConvo && state.interceptionConvoId === state.conversationId) {
          const capture = ingestInterception(state.lastConvo, locationRef?.href || "");
          if (capture) {
            sendResponse?.({ ok: true, capture });
            return true;
          }
        }
        captureFullConversationForManual()
          .then((ok) => {
            // A long chat's backend fetch can resolve during the manual wait. Prefer
            // that complete interception capture over the partial DOM snapshot —
            // background's reconciler would otherwise favour reply.capture when it
            // has any turns, letting a virtualized-DOM partial win.
            const intercepted =
              state.lastConvo && state.interceptionConvoId === state.conversationId
                ? state.lastInterceptionCapture
                : null;
            const capture =
              intercepted && Array.isArray(intercepted.turns) && intercepted.turns.length
                ? intercepted
                : snapshot();
            sendResponse?.({
              ok,
              capture,
              message: ok ? undefined : `Couldn't capture the chat — ${captureDiagnostic()} Reload ChatGPT and try again.`,
            });
          })
          .catch((error) => {
            warnOnce("manual_capture_failed", `manual capture failed: ${error.message}`);
            sendResponse?.({ ok: false, error: error.message, capture: snapshot() });
          });
        return true;
      } else {
        return undefined;
      }
      return false;
    }

    const root = documentRef.querySelector("main") || documentRef.body || documentRef.documentElement;
    const observer = new MutationObserverRef(handleMutations);
    const locationObserver = new MutationObserverRef(handleDocumentMutations);

    function enableCapture() {
      if (state.stopped || state.captureEnabled) return false;
      if (!root) throw new Error("conversation container is unavailable");
      state.captureEnabled = true;
      observer.observe(root, { childList: true, subtree: true, characterData: true });
      locationObserver.observe(documentRef.documentElement || documentRef, {
        childList: true,
        subtree: true,
      });
      documentRef.addEventListener("submit", handleSubmit, true);
      documentRef.addEventListener("copy", handleCopy, true);
      // D-016 / ADR-0008: ask interceptor.js to replay any conversation JSON it
      // cached before our listener existed (the document_start → document_idle
      // race). postMessage delivery is asynchronous, so the listener attached on
      // the next line is in place before any replay can arrive.
      try {
        windowRef.postMessage?.(
          { source: INTERCEPT_SOURCE, kind: "ready-ping" },
          ownOrigin() || "*",
        );
      } catch (_) {
        // never break capture on a postMessage failure
      }
      windowRef.addEventListener?.("message", handleWindowMessage); // D-015 §1 bridge
      state.stopWasPresent = stopButtonPresent();
      captureUsers();
      scheduleIdleCompletion();
      return true;
    }

    function disableCapture() {
      if (!state.captureEnabled) return false;
      state.captureEnabled = false;
      observer.disconnect();
      locationObserver.disconnect();
      if (state.idleTimer) {
        clearTimeoutRef(state.idleTimer);
        state.idleTimer = null;
      }
      if (state.locationCaptureTimer) {
        clearTimeoutRef(state.locationCaptureTimer);
        state.locationCaptureTimer = null;
      }
      if (state.interceptionRetryTimer) {
        clearTimeoutRef(state.interceptionRetryTimer);
        state.interceptionRetryTimer = null;
      }
      documentRef.removeEventListener("submit", handleSubmit, true);
      documentRef.removeEventListener("copy", handleCopy, true);
      windowRef.removeEventListener?.("message", handleWindowMessage);
      return true;
    }

    function start(captureEnabled = true) {
      if (state.started) {
        if (captureEnabled) enableCapture();
        return controller;
      }
      state.started = true;
      globalScope.chrome?.runtime?.onMessage?.addListener?.(handleMessage);
      if (captureEnabled) enableCapture();
      return controller;
    }

    function stop() {
      state.stopped = true;
      disableCapture();
      globalScope.chrome?.runtime?.onMessage?.removeListener?.(handleMessage);
    }

    const controller = Object.freeze({
      start,
      stop,
      enableCapture,
      disableCapture,
      snapshot,
      captureUsers,
      captureCompletedAssistants,
      captureFullConversationForManual,
      maybeQueueCapture,
      ingestInterception,
      handleWindowMessage,
      scrapeHistory: () => historyItems(documentRef),
    });
    return controller;
  }

  const api = Object.freeze({
    SELECTORS,
    MESSAGE_TYPES,
    STREAM_IDLE_MS,
    PAIRS_PER_UPLOAD,
    INTERCEPT_SOURCE,
    INTERCEPT_KIND,
    activePathFromMapping,
    conversationPayloadFromValue,
    conversationIdFromBackendUrl,
    conversationIdFromUrl,
    createCaptureController,
    detectPartnerModel,
    historyItems,
    modelIdFromText,
    platformFromUrl,
    queryUsingFallbacks,
  });

  globalScope.SAFContentCapture = api;
  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  }

  if (
    globalScope.document &&
    globalScope.MutationObserver &&
    !globalScope.__SAF_CONTENT_CAPTURE_CONTROLLER__
  ) {
    try {
      const controller = createCaptureController().start(false);
      globalScope.__SAF_CONTENT_CAPTURE_CONTROLLER__ = controller;

      const applyOnboardingState = (complete) => {
        if (complete === true) controller.enableCapture();
        else controller.disableCapture();
      };
      globalScope.chrome?.storage?.local?.get?.("onboarding_complete", (values) => {
        void globalScope.chrome?.runtime?.lastError;
        applyOnboardingState(values?.onboarding_complete);
      });
      globalScope.chrome?.storage?.onChanged?.addListener?.((changes, areaName) => {
        if (areaName === "local" && changes.onboarding_complete) {
          applyOnboardingState(changes.onboarding_complete.newValue);
        }
      });
    } catch (error) {
      globalScope.console?.warn?.(`[SAF] content capture did not start: ${error.message}`);
    }
  }
})(typeof globalThis !== "undefined" ? globalThis : self);
