"use strict";

(function initContentCapture(globalScope) {
  const SELECTORS = Object.freeze({
    turnContainer: Object.freeze([
      'article[data-testid^="conversation-turn-"]',
      '[data-testid^="conversation-turn-"]',
    ]),
    roleTurn: Object.freeze([
      '[data-message-author-role]',
    ]),
    userTurn: Object.freeze([
      '[data-message-author-role="user"]',
      'article[data-testid^="conversation-turn-"] .user',
      ".group.w-full .whitespace-pre-wrap",
    ]),
    aiTurn: Object.freeze([
      '[data-message-author-role="assistant"]',
      'article[data-testid^="conversation-turn-"] .assistant',
      'article[data-testid^="conversation-turn-"] .prose',
      ".group.w-full .markdown",
    ]),
    stopButton: Object.freeze([
      'button[aria-label="Stop generating"]',
      'button[data-testid="stop-button"]',
    ]),
    modelSelector: Object.freeze([
      '[data-testid="model-switcher-dropdown-button"]',
      'button[aria-label*="model"]',
    ]),
    historyItems: Object.freeze([
      'nav [data-testid="history-item"]',
      "nav ol li a",
      "nav .relative.group a",
    ]),
  });

  const MESSAGE_TYPES = Object.freeze({
    CAPTURE_UPDATED: "SAF_CAPTURE_UPDATED",
    CAPTURE_READY: "SAF_CAPTURE_READY",
    GET_CAPTURE_STATE: "SAF_GET_CAPTURE_STATE",
    GET_HISTORY_ITEMS: "SAF_GET_HISTORY_ITEMS",
    ANALYSE_NOW: "SAF_ANALYSE_NOW",
  });

  const STREAM_IDLE_MS = 1500;
  const PAIRS_PER_UPLOAD = 3;
  const MANUAL_SCROLL_SETTLE_MS = 220;
  const MANUAL_SCROLL_MAX_STEPS = 90;
  const MIN_SCROLL_HARVEST_DELTA = 80;

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
    return null;
  }

  function closestTurnContainer(node) {
    return node?.closest?.('article[data-testid^="conversation-turn-"], [data-testid^="conversation-turn-"]') || null;
  }

  function candidateKey(candidate) {
    const container = closestTurnContainer(candidate.node);
    const stableId =
      container?.getAttribute?.("data-testid") ||
      candidate.node.getAttribute?.("data-testid");
    return stableId
      ? `${candidate.role}:${stableId}`
      : `${candidate.role}:text-${stableHash(textOf(candidate.node).slice(0, 500))}`;
  }

  function modelIdFromText(value) {
    const text = String(value || "").toLowerCase().replace(/[–—]/g, "-");
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

  function detectPartnerModel(documentRef, now = new Date()) {
    const { node } = firstUsingFallbacks(documentRef, SELECTORS.modelSelector);
    return {
      family: "openai",
      model_id: modelIdFromText(textOf(node)),
      era_key: now.toISOString().slice(0, 7),
    };
  }

  function conversationIdFromUrl(url) {
    try {
      const match = new URL(url).pathname.match(/\/c\/([^/?#]+)/);
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

  function createCaptureController(options = {}) {
    const documentRef = options.document || globalScope.document;
    const locationRef = options.location || globalScope.location;
    const now = options.now || Date.now;
    const cryptoRef = options.crypto || globalScope.crypto;
    const MutationObserverRef = options.MutationObserver || globalScope.MutationObserver;
    const setTimeoutRef = options.setTimeout || globalScope.setTimeout.bind(globalScope);
    const clearTimeoutRef = options.clearTimeout || globalScope.clearTimeout.bind(globalScope);
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
      captureEnabled: false,
      started: false,
      stopped: false,
      warned: new Set(),
      domOrderOffset: 0,
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
      return {
        family: "openai",
        model_id: modelIdFromText(textOf(node)),
        era_key: new Date(now()).toISOString().slice(0, 7),
      };
    }

    function allCandidates() {
      const containers = queryUsingFallbacks(documentRef, SELECTORS.turnContainer);
      const containerCandidates = [];
      const roleCounts = { user: 0, assistant: 0 };
      let previousRole = null;
      for (const container of containers.nodes) {
        const explicit = container.matches?.("[data-message-author-role]")
          ? container
          : container.querySelector?.("[data-message-author-role]");
        const markdown = container.querySelector?.(".markdown, .prose");
        const userBody = container.querySelector?.(
          '[data-message-author-role="user"], [data-testid*="user"], .user, .whitespace-pre-wrap',
        );

        let role = roleFromAuthorNode(explicit);
        let node = explicit || container;
        if (!role && markdown) {
          role = "assistant";
          node = markdown;
        } else if (!role && userBody && !markdown) {
          role = "user";
          node = userBody;
        } else if (!role && previousRole) {
          role = previousRole === "user" ? "assistant" : "user";
        }
        if (!role) continue;

        const roleIndex = roleCounts[role]++;
        previousRole = role;
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
      add(documentRef.scrollingElement);
      add(documentRef.documentElement);
      add(documentRef.body);

      const nested = Array.from(
        documentRef.querySelectorAll?.("main, main *, [class*='overflow'], [data-testid*='conversation']") || [],
      );
      for (const node of nested) add(node);

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

    async function captureFullConversationForManual() {
      enableCapture();
      syncConversation();
      state.awaitingFreshSubmit = false;
      await captureVisibleConversation(true);

      const root = scrollRoot();
      const maxScroll = () => Math.max(0, Number(root?.scrollHeight || 0) - Number(root?.clientHeight || 0));
      if (!root || maxScroll() <= 0) return maybeQueueCapture(true);

      const originalTop = Number(root.scrollTop || globalScope.scrollY || 0);
      const stepSize = () => Math.max(320, Math.floor(Number(root.clientHeight || globalScope.innerHeight || 800) * 0.75));
      let lastTop = -1;

      try {
        scrollToY(root, 0);
        await sleep(MANUAL_SCROLL_SETTLE_MS);
        for (let step = 0; step < MANUAL_SCROLL_MAX_STEPS; step += 1) {
          state.domOrderOffset = Math.floor(Number(root.scrollTop || 0) * 1000);
          await captureVisibleConversation(true);

          const currentTop = Number(root.scrollTop || 0);
          const bottom = maxScroll();
          if (currentTop >= bottom - 8) break;

          const nextTop = Math.min(bottom, currentTop + stepSize());
          if (nextTop === lastTop || nextTop === currentTop) break;
          lastTop = currentTop;
          scrollToY(root, nextTop);
          await sleep(MANUAL_SCROLL_SETTLE_MS);
        }
        state.domOrderOffset = Math.floor(Number(root.scrollTop || 0) * 1000);
        await captureVisibleConversation(true);
      } finally {
        state.domOrderOffset = 0;
        scrollToY(root, originalTop);
      }
      return maybeQueueCapture(true);
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
          title: String(documentRef.title || "").replace(/\s*[|\-]\s*ChatGPT\s*$/i, ""),
          url: locationRef?.href || "",
        },
      };
    }

    function notifyUpdated() {
      sendMessage({ type: MESSAGE_TYPES.CAPTURE_UPDATED, capture: snapshot() });
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
        captureFullConversationForManual()
          .then((ok) => sendResponse?.({ ok, capture: snapshot() }))
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

    function enableCapture() {
      if (state.stopped || state.captureEnabled) return false;
      if (!root) throw new Error("conversation container is unavailable");
      state.captureEnabled = true;
      observer.observe(root, { childList: true, subtree: true, characterData: true });
      documentRef.addEventListener("submit", handleSubmit, true);
      documentRef.addEventListener("copy", handleCopy, true);
      state.stopWasPresent = stopButtonPresent();
      captureUsers();
      scheduleIdleCompletion();
      return true;
    }

    function disableCapture() {
      if (!state.captureEnabled) return false;
      state.captureEnabled = false;
      observer.disconnect();
      if (state.idleTimer) {
        clearTimeoutRef(state.idleTimer);
        state.idleTimer = null;
      }
      documentRef.removeEventListener("submit", handleSubmit, true);
      documentRef.removeEventListener("copy", handleCopy, true);
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
      scrapeHistory: () => historyItems(documentRef),
    });
    return controller;
  }

  const api = Object.freeze({
    SELECTORS,
    MESSAGE_TYPES,
    STREAM_IDLE_MS,
    PAIRS_PER_UPLOAD,
    conversationIdFromUrl,
    createCaptureController,
    detectPartnerModel,
    historyItems,
    modelIdFromText,
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
