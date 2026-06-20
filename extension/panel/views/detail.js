const DIMENSIONS = ['AL', 'PR', 'EC', 'ES', 'CS', 'CD', 'AUI', 'CA'];
const DEBT_FLAG_TOOLTIP = 'Pattern detected — not proven without retention probe.';

const FLAG_RENDERERS = {
  debt_flag: {
    label: 'Debt flag',
    className: 'saf-flag-pill--amber',
    title: DEBT_FLAG_TOOLTIP,
  },
};

export function initDetailView(shadowRoot) {
  const state = {
    requestId: 0,
    chatId: null,
  };

  const els = {
    empty: shadowRoot.getElementById('saf-detail-empty'),
    content: shadowRoot.getElementById('saf-detail-content'),
    title: shadowRoot.getElementById('saf-detail-title'),
    meta: shadowRoot.getElementById('saf-detail-meta'),
    dimensionList: shadowRoot.getElementById('saf-dimension-list'),
    trendSection: shadowRoot.getElementById('saf-trend-section'),
    flagSection: shadowRoot.getElementById('saf-flags-section'),
    flagList: shadowRoot.getElementById('saf-flag-list'),
    remarks: shadowRoot.getElementById('saf-remarks-text'),
  };

  function api() {
    return globalThis.SAFApiClient;
  }

  function storage() {
    return globalThis.SAFStorage;
  }

  function shortId(value) {
    const text = String(value || 'unknown');
    if (text.length <= 12) return text;
    return `${text.slice(0, 6)}...${text.slice(-4)}`;
  }

  function numeric(value) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }

  function clampUnit(value) {
    if (value == null) return null;
    return Math.min(1, Math.max(0, value));
  }

  function formatValue(value) {
    const number = numeric(value);
    if (number == null) return '-';
    return number.toFixed(2).replace(/^0/, '');
  }

  function formatCI(dim, score) {
    const ci = score?.ci;
    const low = numeric(ci?.low);
    const high = numeric(ci?.high);
    if (low == null || high == null) {
      console.warn('[SAF] scored dimension missing ci', dim, score);
      return '±?';
    }
    return `±${((high - low) / 2).toFixed(2).replace(/^0/, '')}`;
  }

  function dimensionValue(score) {
    return numeric(score?.value ?? score?.score ?? score?.human_pct);
  }

  function colorForValue(value) {
    if (value >= 0.66) return 'var(--saf-green)';
    if (value >= 0.38) return 'var(--saf-amber)';
    return 'var(--saf-red)';
  }

  function clear(node) {
    node?.replaceChildren();
  }

  function makeDimensionRow(dim, stateName) {
    const row = document.createElement('div');
    row.className = 'saf-dimension-row';
    row.dataset.state = stateName;

    const code = document.createElement('span');
    code.className = 'saf-dimension-code';
    code.textContent = dim;
    row.appendChild(code);

    const track = document.createElement('span');
    track.className = 'saf-dimension-track';
    track.setAttribute('aria-hidden', 'true');
    const fill = document.createElement('span');
    fill.className = 'saf-dimension-fill';
    track.appendChild(fill);
    row.appendChild(track);

    const value = document.createElement('span');
    value.className = 'saf-dimension-value';
    row.appendChild(value);

    const ci = document.createElement('span');
    ci.className = 'saf-dimension-ci';
    row.appendChild(ci);

    return { row, fill, value, ci };
  }

  function renderScoreBar(dim, score) {
    const { row, fill, value, ci } = makeDimensionRow(dim, 'scored');
    const scoreValue = clampUnit(dimensionValue(score));
    const fillValue = scoreValue ?? 0;
    if (scoreValue == null) console.warn('[SAF] scored dimension missing value', dim, score);
    fill.style.setProperty('--saf-dim-fill', `${Math.round(fillValue * 100)}%`);
    fill.style.setProperty('--saf-dim-color', colorForValue(fillValue));
    value.textContent = scoreValue == null ? '-' : formatValue(scoreValue);
    ci.textContent = formatCI(dim, score);
    return row;
  }

  function renderNA(dim, score) {
    const { row, fill, value, ci } = makeDimensionRow(dim, 'STRUCTURAL_NA');
    fill.style.setProperty('--saf-dim-fill', '100%');
    value.textContent = 'N/A';
    ci.textContent = score?.status_reason ? 'note' : '';
    if (score?.status_reason) row.title = score.status_reason;
    return row;
  }

  function renderInsufficient(dim, score) {
    const { row, fill, value, ci } = makeDimensionRow(dim, 'INSUFFICIENT_SAMPLE');
    fill.style.setProperty('--saf-dim-fill', '100%');
    value.textContent = 'Low n';
    ci.textContent = score?.n_eff != null ? `n=${formatValue(score.n_eff)}` : '';
    if (score?.status_reason) row.title = score.status_reason;
    return row;
  }

  function renderSaturated(dim, score) {
    const { row, fill, value, ci } = makeDimensionRow(dim, 'MEASUREMENT_SATURATED');
    const bound = clampUnit(numeric(score?.censored?.bound)) ?? 0;
    const direction = String(score?.censored?.direction || 'high').toLowerCase();
    const symbol = direction === 'low' ? '≤' : '≥';
    fill.classList.add('is-saturated');
    fill.style.setProperty('--saf-dim-fill', `${Math.round(bound * 100)}%`);
    value.textContent = `${symbol} ${formatValue(bound)}`;
    ci.textContent = '';
    return row;
  }

  function renderUnknown(dim, score) {
    const { row, fill, value, ci } = makeDimensionRow(dim, 'UNKNOWN');
    fill.style.setProperty('--saf-dim-fill', '100%');
    value.textContent = String(score?.status || 'Unknown');
    ci.textContent = '';
    return row;
  }

  function renderDimension(dim, score) {
    if (score?.status === 'OK') return renderScoreBar(dim, score);
    if (score?.status === 'N/A') return renderNA(dim, score);
    if (score?.status === 'INSUFFICIENT_SAMPLE') return renderInsufficient(dim, score);
    if (score?.status === 'MEASUREMENT_SATURATED') return renderSaturated(dim, score);
    return renderUnknown(dim, score);
  }

  function renderProfile(profile) {
    clear(els.dimensionList);
    const fragment = document.createDocumentFragment();
    DIMENSIONS.forEach((dim) => {
      fragment.appendChild(renderDimension(dim, profile?.[dim]));
    });
    els.dimensionList?.appendChild(fragment);
  }

  function isDisplayableFlag(value) {
    return value === true;
  }

  function flagLabel(key) {
    return key;
  }

  function renderFlags(flags) {
    clear(els.flagList);
    const activeFlags = Object.entries(flags || {}).filter(([, value]) => isDisplayableFlag(value));
    if (els.flagSection) els.flagSection.hidden = activeFlags.length === 0;

    activeFlags.forEach(([key, value]) => {
      const config = FLAG_RENDERERS[key];
      const pill = document.createElement('span');
      pill.className = `saf-flag-pill ${config?.className || 'saf-flag-pill--grey'}`;
      pill.textContent = config?.label || flagLabel(key);
      if (config?.title) pill.title = config.title;
      els.flagList?.appendChild(pill);
    });
  }

  function renderRemarks(report) {
    const lines = [];
    if (Array.isArray(report?.observed) && report.observed.length) {
      lines.push(...report.observed);
    }
    if (Array.isArray(report?.inferred) && report.inferred.length) {
      lines.push(...report.inferred);
    }
    if (typeof report?.tier_caveat === 'string' && report.tier_caveat) {
      lines.push(report.tier_caveat);
    }
    if (els.remarks) els.remarks.value = lines.length ? lines.join('\n') : 'No remarks available for this chat.';
  }

  function setShellLoading(chatId) {
    if (els.empty) els.empty.hidden = true;
    if (els.content) els.content.hidden = false;
    if (els.title) els.title.textContent = `Conversation ${shortId(chatId)}`;
    if (els.meta) els.meta.textContent = 'Loading score...';
    clear(els.dimensionList);
    clear(els.flagList);
    if (els.flagSection) els.flagSection.hidden = true;
    if (els.trendSection) els.trendSection.hidden = true;
    if (els.remarks) els.remarks.value = '';
  }

  function setShellError(chatId, message) {
    if (els.empty) els.empty.hidden = true;
    if (els.content) els.content.hidden = false;
    if (els.title) els.title.textContent = `Conversation ${shortId(chatId)}`;
    if (els.meta) els.meta.textContent = message;
    clear(els.dimensionList);
    if (els.remarks) els.remarks.value = '';
    if (els.flagSection) els.flagSection.hidden = true;
    if (els.trendSection) els.trendSection.hidden = true;
  }

  function renderScore(chatId, score) {
    if (els.empty) els.empty.hidden = true;
    if (els.content) els.content.hidden = false;
    if (els.title) els.title.textContent = `Conversation ${shortId(score?.conversation_id || score?.session_id || chatId)}`;
    if (els.meta) els.meta.textContent = score?.tier ? `Tier ${score.tier}` : 'Score loaded';
    if (els.trendSection) els.trendSection.hidden = true;
    renderProfile(score?.profile || {});
    renderFlags(score?.flags || {});
    renderRemarks(score?.report || {});
  }

  async function loadScore(chatId) {
    const requestId = state.requestId + 1;
    state.requestId = requestId;
    state.chatId = chatId;
    setShellLoading(chatId);

    const storageApi = storage();
    const apiClient = api();
    if (!storageApi || !apiClient?.getChatScore) {
      setShellError(chatId, 'SAF API client is unavailable.');
      return;
    }

    try {
      const userRef = await storageApi.get(storageApi.STORAGE_KEYS.USER_REF, '');
      if (requestId !== state.requestId) return;
      if (!userRef) {
        setShellError(chatId, 'Set your user ID in Settings first.');
        return;
      }

      const result = await apiClient.getChatScore(userRef, chatId);
      if (requestId !== state.requestId) return;
      if (!result?.ok) {
        throw new Error(result?.detail || result?.error || 'Could not load score.');
      }

      renderScore(chatId, result.data || {});
    } catch (error) {
      if (requestId !== state.requestId) return;
      setShellError(chatId, error.message || 'Could not load score.');
    }
  }

  function handleChatSelected(event) {
    const chatId = event?.detail?.chatId;
    if (!chatId) return;
    void loadScore(chatId);
  }

  shadowRoot.addEventListener('saf-chat-selected', handleChatSelected);

  return () => {
    state.requestId += 1;
    shadowRoot.removeEventListener('saf-chat-selected', handleChatSelected);
  };
}
