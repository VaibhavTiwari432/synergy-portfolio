const POLL_MS = 4000;

export function initChatsView(shadowRoot) {
  const state = {
    chats: [],
    summary: { total: 0, scored: 0, pending: 0, failed: 0 },
    selectedChatId: null,
    searchTerm: '',
    pollTimer: null,
    loading: false,
  };

  const els = {
    counts: shadowRoot.getElementById('saf-chat-counts'),
    status: shadowRoot.getElementById('saf-chat-status'),
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

  function setStatus(message, isError = false) {
    if (!els.status) return;
    els.status.textContent = message;
    els.status.classList.toggle('is-error', isError);
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
    button.textContent = cta.label;
    button.disabled = Boolean(cta.disabled);
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

  function startPolling() {
    stopPolling();
    if (!hasPendingWork()) return;
    state.pollTimer = globalThis.setInterval(() => {
      void loadChats({ silent: true });
    }, POLL_MS);
  }

  function stopPolling() {
    if (state.pollTimer) globalThis.clearInterval(state.pollTimer);
    state.pollTimer = null;
  }

  async function analyseChat(chat) {
    const apiClient = api();
    if (!apiClient?.triggerAnalysis) {
      setStatus('Analysis is unavailable in this tab.', true);
      return;
    }
    setLocalStatus(chat.chat_id, 'scoring');
    setStatus('Starting analysis...');
    startPolling();

    const result = await apiClient.triggerAnalysis(chat.chat_id);
    if (!result?.ok) {
      setLocalStatus(chat.chat_id, chat.status || 'failed');
      setStatus(result?.message || result?.error || 'Analysis could not start.', true);
      if (!hasPendingWork()) stopPolling();
      return;
    }

    setStatus('Analysis started.');
    await loadChats({ silent: true });
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
        throw new Error(result?.detail || result?.error || 'Could not load chats.');
      }

      const data = result.data || {};
      state.chats = Array.isArray(data.chats) ? data.chats : [];
      state.summary = data.summary || { total: state.chats.length, scored: 0, pending: 0, failed: 0 };
      setStatus(state.chats.length ? '' : 'No chats captured yet.');
      render();
      startPolling();
    } catch (error) {
      if (els.retry) els.retry.hidden = false;
      setStatus(error.message || 'Could not load chats.', true);
      renderEmpty(els.list, 'Could not load chats.');
    } finally {
      state.loading = false;
    }
  }

  function handleSearchInput(event) {
    state.searchTerm = String(event.target.value || '');
    render();
  }

  els.search?.addEventListener('input', handleSearchInput);
  els.retry?.addEventListener('click', () => {
    void loadChats();
  });

  void loadChats();

  return () => {
    stopPolling();
    els.search?.removeEventListener('input', handleSearchInput);
  };
}
