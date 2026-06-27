const POLL_MS = 4000;
const MAX_POLL_ATTEMPTS = 30;
// After MAX_POLL_ATTEMPTS the UI reloads from the server. If the server still
// shows pending/scoring work, we reset the counter and keep polling for another
// full cycle rather than fake-failing — Gemini scoring a large chat can take
// 10+ minutes, far beyond the original 120 s hard cutoff.
const MAX_POLL_CYCLES = 3;

export function initChatsView(shadowRoot) {
  const state = {
    chats: [],
    summary: { total: 0, scored: 0, pending: 0, failed: 0 },
    selectedChatId: null,
    searchTerm: '',
    pollTimer: null,
    pollAttempts: 0,
    pollCycles: 0,
    analysingChatIds: new Set(),
    analysingCurrent: false,
    loading: false,
  };

  const els = {
    counts: shadowRoot.getElementById('saf-chat-counts'),
    status: shadowRoot.getElementById('saf-chat-status'),
    analyseCurrent: shadowRoot.getElementById('saf-analyse-current'),
    retry: shadowRoot.getElementById('saf-chat-retry'),
    search: shadowRoot.querySelector('.saf-search-input'),
    currentSection: shadowRoot.getElementById('saf-current-chat-section'),
    currentList: shadowRoot.getElementById('saf-current-chat-list'),
    list: shadowRoot.getElementById('saf-chat-list'),
  };

  function api() {
    return globalThis.SAFApiClient;
  }

  function storage() {
    return globalThis.SAFStorage;
  }

  function activeConversationId() {
    try {
      const match = new URL(globalThis.location.href).pathname.match(/\/c\/([^/?#]+)/);
      return match ? decodeURIComponent(match[1]) : null;
    } catch (_) {
      return null;
    }
  }

  function normaliseStatus(status) {
    const value = String(status || 'unsubmitted').toLowerCase();
    if (value === 'scored' || value === 'pending' || value === 'scoring' || value === 'failed') {
      return value;
    }
    return 'unsubmitted';
  }

  function shortId(value) {
    const text = String(value || 'unknown');
    if (text.length <= 12) return text;
    return `${text.slice(0, 6)}...${text.slice(-4)}`;
  }

  function chatLabel(chat) {
    return `Conversation ${shortId(chat.conversation_id || chat.chat_id)}`;
  }

  function formatDate(value) {
    if (!value) return '';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return '';
    return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
  }

  function chatMeta(chat) {
    const parts = [];
    const captured = formatDate(chat.captured_at);
    if (captured) parts.push(captured);
    if (Number.isFinite(Number(chat.turn_count))) parts.push(`${Number(chat.turn_count)} turns`);
    if (chat.source) parts.push(String(chat.source).replace(/_/g, ' '));
    return parts.join(' / ');
  }

  function statusLabel(status) {
    return {
      scored: 'Scored',
      pending: 'Pending',
      scoring: 'Scoring',
      failed: 'Failed',
      unsubmitted: 'New',
    }[status] || 'New';
  }

  function ctaFor(status) {
    if (status === 'scored') return { label: 'See', action: 'see', className: '' };
    if (status === 'failed') return { label: 'Retry', action: 'analyse', className: 'saf-chat-cta--danger' };
    if (status === 'scoring') return { label: 'Scoring...', action: 'none', className: '', disabled: true };
    return { label: 'Analyse', action: 'analyse', className: 'saf-chat-cta--primary' };
  }

  function friendlyError(result, fallback = 'Something went wrong.') {
    const message = result?.message || result?.detail || result?.error || result?.message;
    if (result?.status === 401 || /invalid or missing X-API-Key/i.test(String(message || ''))) {
      return 'API key is missing or invalid. Open Settings and save the API key for this backend.';
    }
    if (message === 'api_unreachable') {
      return 'SAF backend is not reachable. Start the backend or update the API endpoint in Settings.';
    }
    if (message === 'user_ref_required' || message === 'no_user') {
      return 'Set your user ID in Settings before analysing chats.';
    }
    if (message === 'consent_off') {
      return 'Enable capture consent in Settings before analysing chats.';
    }
    if (message === 'runtime_unavailable') {
      return 'Analysis is unavailable in this tab. Reload the ChatGPT tab and try again.';
    }
    if (message === 'analysis_timeout') {
      return 'Capture timed out. Reload the ChatGPT tab and try again.';
    }
    return message || fallback;
  }

  async function readinessWarning(apiClient, summary) {
    if (!apiClient?.getHealth) return '';
    const pending = Number(summary?.pending || 0);
    const failed = Number(summary?.failed || 0);
    if (pending <= 0 && failed <= 0) return '';
    try {
      const health = await apiClient.getHealth();
      if (!health?.ok) return '';
      if (health.data?.db === 'unavailable') {
        return 'Backend is reachable, but Postgres is unavailable. Start the database and restart SAF.';
      }
      if (health.data?.scoring === 'missing_judge_key') {
        return 'Scoring is not configured. Set GEMINI_API_KEY or GOOGLE_API_KEY, then restart the SAF worker.';
      }
      if (health.data?.worker === 'down') {
        return 'Scoring worker is offline — captured chats stay pending until it runs. Start it with start_saf.ps1.';
      }
    } catch (_) {
      return '';
    }
    return '';
  }

  function formatProgress(progress) {
    // content.js already plumbs percent + captured_turns through background → api_client;
    // surface them so a long capture shows live "% / N turns", not a frozen message.
    const pct = Number(progress.percent);
    const turns = Number(progress.captured_turns);
    const head = Number.isFinite(pct) && pct > 0 ? `${Math.round(pct)}% · ` : '';
    const tail = Number.isFinite(turns) && turns > 0 ? ` · ${turns} turns` : '';
    return `${head}${progress.message || 'Capturing...'}${tail}`;
  }

  function setStatus(message, isError = false) {
    if (!els.status) return;
    els.status.textContent = message;
    els.status.classList.toggle('is-error', isError);
  }

  function setAnalyseCurrentBusy(isBusy) {
    state.analysingCurrent = isBusy;
    if (!els.analyseCurrent) return;
    els.analyseCurrent.disabled = isBusy;
    els.analyseCurrent.textContent = isBusy ? 'Capturing...' : 'Analyse current';
  }

  function setCounts(summary) {
    if (!els.counts) return;
    const scored = Number(summary?.scored || 0);
    const pending = Number(summary?.pending || 0);
    const failed = Number(summary?.failed || 0);
    els.counts.textContent = `${scored} scored / ${pending} pending / ${failed} failed`;
  }

  function sortChats(chats) {
    return [...chats].sort((left, right) => {
      const leftTime = Date.parse(left.captured_at || '') || 0;
      const rightTime = Date.parse(right.captured_at || '') || 0;
      return rightTime - leftTime;
    });
  }

  function filteredChats(chats) {
    const term = state.searchTerm.trim().toLowerCase();
    if (!term) return chats;
    return chats.filter((chat) => {
      const haystack = [
        chatLabel(chat),
        chat.conversation_id,
        chat.chat_id,
        chat.status,
        chat.source,
      ].join(' ').toLowerCase();
      return haystack.includes(term);
    });
  }

  function clearList(node) {
    if (!node) return;
    node.replaceChildren();
  }

  function renderEmpty(node, message) {
    clearList(node);
    const empty = document.createElement('div');
    empty.className = 'saf-chat-empty';
    empty.textContent = message;
    node?.appendChild(empty);
  }

  function renderRow(chat) {
    const status = normaliseStatus(chat.status);
    const cta = ctaFor(status);
    const isAnalysing = state.analysingChatIds.has(chat.chat_id);
    const row = document.createElement('div');
    row.className = 'saf-chat-row';
    row.dataset.chatId = chat.chat_id || '';
    row.dataset.status = status;
    if (state.selectedChatId && state.selectedChatId === chat.chat_id) {
      row.classList.add('is-selected');
    }

    const dot = document.createElement('span');
    dot.className = 'saf-chat-dot';
    dot.setAttribute('aria-hidden', 'true');
    row.appendChild(dot);

    const titleWrap = document.createElement('div');
    titleWrap.className = 'saf-chat-title';
    titleWrap.textContent = chatLabel(chat);
    const meta = document.createElement('span');
    meta.className = 'saf-chat-meta';
    meta.textContent = chatMeta(chat);
    titleWrap.appendChild(meta);
    row.appendChild(titleWrap);

    const badge = document.createElement('span');
    badge.className = `saf-badge saf-badge--${status}`;
    badge.textContent = statusLabel(status);
    row.appendChild(badge);

    const button = document.createElement('button');
    button.className = `saf-chat-cta ${cta.className}`.trim();
    button.type = 'button';
    button.textContent = isAnalysing ? 'Scoring...' : cta.label;
    button.disabled = Boolean(cta.disabled || isAnalysing);
    button.dataset.action = cta.action;
    row.appendChild(button);

    button.addEventListener('click', () => {
      if (cta.action === 'see') selectChat(chat.chat_id);
      if (cta.action === 'analyse') void analyseChat(chat);
    });

    return row;
  }

  function render() {
    const activeId = activeConversationId();
    const sorted = sortChats(state.chats);
    const visible = filteredChats(sorted);
    const current = activeId ? visible.find((chat) => chat.conversation_id === activeId) : null;
    const recent = current ? visible.filter((chat) => chat !== current) : visible;

    setCounts(state.summary);
    if (els.currentSection) els.currentSection.hidden = !current;
    clearList(els.currentList);
    clearList(els.list);

    if (current) els.currentList.appendChild(renderRow(current));
    if (recent.length) recent.forEach((chat) => els.list.appendChild(renderRow(chat)));
    else renderEmpty(els.list, state.searchTerm ? 'No chats match this search.' : 'No chats captured yet.');
  }

  function selectedChatEvent(chatId) {
    shadowRoot.dispatchEvent(new CustomEvent('saf-chat-selected', {
      bubbles: true,
      detail: { chatId },
    }));
  }

  function selectChat(chatId) {
    state.selectedChatId = chatId;
    selectedChatEvent(chatId);
    render();
  }

  function setLocalStatus(chatId, status) {
    state.chats = state.chats.map((chat) => (
      chat.chat_id === chatId ? { ...chat, status } : chat
    ));
    render();
  }

  function hasPendingWork() {
    return state.chats.some((chat) => {
      const status = normaliseStatus(chat.status);
      return status === 'pending' || status === 'scoring';
    });
  }

  async function markPendingTimedOut() {
    // Reload from the server before fake-failing. Scoring a large chat via Gemini
    // can legitimately take 10+ minutes — the 120 s poll window is too short.
    // If the server still has pending/scoring work, reset the counter and continue
    // polling for another cycle rather than lying to the user.
    await loadChats({ silent: true });
    if (hasPendingWork()) {
      state.pollAttempts = 0;
      state.pollCycles += 1;
      if (state.pollCycles < MAX_POLL_CYCLES) {
        setStatus('Analysis is taking longer than expected — still waiting...', false);
        startPolling();
        return;
      }
    }
    // Either no pending work remains (all done or genuinely failed) or we have
    // exhausted MAX_POLL_CYCLES — show the sticky error banner now.
    state.pollCycles = 0;
    const hasFailed = state.chats.some((c) => normaliseStatus(c.status) === 'failed');
    if (hasFailed) {
      setStatus('Analysis is taking longer than expected. Retry from the chat row.', true);
    }
    render();
  }

  function startPolling() {
    stopPolling();
    if (!hasPendingWork()) return;
    state.pollTimer = globalThis.setInterval(() => {
      state.pollAttempts += 1;
      if (state.pollAttempts > MAX_POLL_ATTEMPTS) {
        stopPolling();
        void markPendingTimedOut();
        return;
      }
      void loadChats({ silent: true });
    }, POLL_MS);
  }

  function stopPolling() {
    if (state.pollTimer) globalThis.clearInterval(state.pollTimer);
    state.pollTimer = null;
    if (!hasPendingWork()) {
      state.pollAttempts = 0;
      state.pollCycles = 0;
    }
  }

  async function analyseChat(chat = {}) {
    if (state.analysingChatIds.has(chat.chat_id)) return;
    const apiClient = api();
    if (!apiClient?.triggerAnalysis) {
      setStatus('Analysis is unavailable in this tab.', true);
      return;
    }
    if (chat.chat_id) {
      state.analysingChatIds.add(chat.chat_id);
      setLocalStatus(chat.chat_id, 'scoring');
    }
    setStatus('Starting analysis...');
    startPolling();

    // For an already-ingested failed chat, requeue it directly rather than
    // re-capturing the active tab (which may be a different conversation).
    const isFailed = normaliseStatus(chat.status) === 'failed';
    let result;
    if (isFailed && chat.chat_id && apiClient.requeueChat) {
      const storageApi = storage();
      const userRef = storageApi ? await storageApi.get(storageApi.STORAGE_KEYS.USER_REF, '') : '';
      if (userRef) {
        result = await apiClient.requeueChat(userRef, chat.chat_id);
        // 409 = chat is already pending/scoring — treat as success (already in queue)
        if (!result?.ok && result?.status === 409) {
          result = { ok: true, data: { status: result.detail?.status || 'pending' } };
        }
      }
    }
    // Fall back to full capture for unsubmitted chats or if requeue unavailable.
    if (!result) {
      result = await apiClient.triggerAnalysis(chat.chat_id);
    }

    if (!result?.ok) {
      if (chat.chat_id) {
        state.analysingChatIds.delete(chat.chat_id);
        setLocalStatus(chat.chat_id, 'failed');
      }
      setStatus(friendlyError(result, 'Analysis could not start.'), true);
      if (!hasPendingWork()) stopPolling();
      return;
    }

    setStatus('Analysis started.');
    await loadChats({ silent: true });
    if (chat.chat_id) state.analysingChatIds.delete(chat.chat_id);
    render();
  }

  async function analyseCurrentChat() {
    if (state.analysingCurrent) return;
    const apiClient = api();
    if (!apiClient?.triggerAnalysis) {
      setStatus('Analysis is unavailable in this tab. Reload the page and try again.', true);
      return;
    }

    setAnalyseCurrentBusy(true);
    setStatus('Capturing current chat...');

    let progressPoll = null;
    if (apiClient.getAnalysisProgress) {
      progressPoll = globalThis.setInterval(async () => {
        const progress = await apiClient.getAnalysisProgress();
        if (progress) setStatus(formatProgress(progress));
      }, 2000);
    }

    try {
      const result = await apiClient.triggerAnalysis();
      if (!result?.ok) {
        setStatus(friendlyError(result, 'Could not capture this chat.'), true);
        return;
      }
      setStatus('Chat captured. Loading score status...');
      await loadChats({ silent: true });
      startPolling();
    } catch (error) {
      setStatus(friendlyError(error, 'Could not capture this chat.'), true);
    } finally {
      if (progressPoll) globalThis.clearInterval(progressPoll);
      setAnalyseCurrentBusy(false);
    }
  }

  async function loadChats({ silent = false } = {}) {
    if (state.loading) return;
    const storageApi = storage();
    const apiClient = api();

    if (!storageApi || !apiClient?.getChatList) {
      setStatus('SAF API client is unavailable.', true);
      return;
    }

    state.loading = true;
    if (els.retry) els.retry.hidden = true;
    if (!silent) setStatus('Loading chats...');

    try {
      const userRef = await storageApi.get(storageApi.STORAGE_KEYS.USER_REF, '');
      if (!userRef) {
        state.chats = [];
        state.summary = { total: 0, scored: 0, pending: 0, failed: 0 };
        setCounts(state.summary);
        setStatus('Setup needed.');
        render();
        renderEmpty(els.list, 'Set your user ID in Settings first.');
        return;
      }

      const result = await apiClient.getChatList(userRef);
      if (!result?.ok) {
        throw new Error(friendlyError(result, 'Could not load chats.'));
      }

      const data = result.data || {};
      state.chats = Array.isArray(data.chats) ? data.chats : [];
      state.summary = data.summary || { total: state.chats.length, scored: 0, pending: 0, failed: 0 };
      const warning = await readinessWarning(apiClient, state.summary);
      setStatus(warning || (state.chats.length ? '' : 'No chats captured yet.'), Boolean(warning));
      render();
      if (!hasPendingWork()) state.pollAttempts = 0;
      startPolling();
    } catch (error) {
      if (els.retry) els.retry.hidden = false;
      const message = friendlyError(error, 'Could not load chats.');
      setStatus(message, true);
      renderEmpty(els.list, message);
    } finally {
      state.loading = false;
    }
  }

  function handleSearchInput(event) {
    state.searchTerm = String(event.target.value || '');
    render();
  }

  function handleAnalyseCurrentClick() {
    void analyseCurrentChat();
  }

  function handleSettingsUpdated() {
    void loadChats();
  }

  els.search?.addEventListener('input', handleSearchInput);
  els.analyseCurrent?.addEventListener('click', handleAnalyseCurrentClick);
  els.retry?.addEventListener('click', () => {
    void loadChats();
  });
  shadowRoot.addEventListener?.('saf-settings-updated', handleSettingsUpdated);

  void loadChats();

  return () => {
    stopPolling();
    els.search?.removeEventListener('input', handleSearchInput);
    els.analyseCurrent?.removeEventListener('click', handleAnalyseCurrentClick);
    shadowRoot.removeEventListener?.('saf-settings-updated', handleSettingsUpdated);
  };
}
