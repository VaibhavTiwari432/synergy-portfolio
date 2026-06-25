const DIMENSIONS = ['AL', 'PR', 'EC', 'ES', 'CS', 'CD', 'AUI', 'CA'];
const DEBT_FLAG_TOOLTIP = 'Pattern detected — not proven without retention probe.';
const MAX_FEEDBACK_CHARS = 280;

// Every emitted claim carries exactly one evidence rung (#14). The badge makes
// the rung visible next to the number so a value is never read as more certain
// than its rung allows.
const RUNG_META = {
  DESIGNED: { abbr: 'DSGN', cls: 'saf-rung--designed', title: 'Designed — specified, not yet measured on data.' },
  MEASURABLE: { abbr: 'MEAS', cls: 'saf-rung--measurable', title: 'Measurable — computed from this session’s evidence.' },
  VALIDATED: { abbr: 'VALID', cls: 'saf-rung--validated', title: 'Validated — checked against held-out outcomes.' },
  ASPIRATIONAL: { abbr: 'ASPIR', cls: 'saf-rung--aspirational', title: 'Aspirational — research goal, not yet built.' },
};

// Per-turn cognitive-load label for the state-strip tooltip.
const LOAD_LABEL = {
  LOW_LOAD: 'low load',
  MODERATE_LOAD: 'moderate load',
  HIGH_LOAD: 'high load',
  SATURATED: 'saturated',
};

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
    feedbackRecorded: false,
    feedbackSubmitting: false,
  };

  const els = {
    empty: shadowRoot.getElementById('saf-detail-empty'),
    resultsOverlay: shadowRoot.getElementById('saf-results-overlay'),
    resultsClose: shadowRoot.getElementById('saf-results-close'),
    content: shadowRoot.getElementById('saf-detail-content'),
    title: shadowRoot.getElementById('saf-detail-title'),
    meta: shadowRoot.getElementById('saf-detail-meta'),
    compositeCard: shadowRoot.getElementById('saf-composite-card'),
    compositeValue: shadowRoot.getElementById('saf-composite-value'),
    compositeRung: shadowRoot.getElementById('saf-composite-rung'),
    compositeCi: shadowRoot.getElementById('saf-composite-ci'),
    compositeSub: shadowRoot.getElementById('saf-composite-sub'),
    stateSection: shadowRoot.getElementById('saf-state-section'),
    stateSummary: shadowRoot.getElementById('saf-state-summary'),
    stateStrip: shadowRoot.getElementById('saf-state-strip'),
    stateReadout: shadowRoot.getElementById('saf-state-readout'),
    stateNote: shadowRoot.getElementById('saf-state-note'),
    cslSection: shadowRoot.getElementById('saf-csl-section'),
    cslLevels: shadowRoot.getElementById('saf-csl-levels'),
    cslNote: shadowRoot.getElementById('saf-csl-note'),
    dimensionList: shadowRoot.getElementById('saf-dimension-list'),
    trendSection: shadowRoot.getElementById('saf-trend-section'),
    flagSection: shadowRoot.getElementById('saf-flags-section'),
    flagList: shadowRoot.getElementById('saf-flag-list'),
    remarks: shadowRoot.getElementById('saf-remarks-text'),
    feedbackUp: shadowRoot.getElementById('saf-feedback-up'),
    feedbackDown: shadowRoot.getElementById('saf-feedback-down'),
    feedbackNote: shadowRoot.getElementById('saf-feedback-note'),
    feedbackCount: shadowRoot.getElementById('saf-feedback-count'),
    feedbackSubmit: shadowRoot.getElementById('saf-feedback-submit'),
    feedbackStatus: shadowRoot.getElementById('saf-feedback-status'),
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

  // ARI scores are stored on the [0,1] scale; users read them on a 0–100 scale
  // to two decimals (e.g. 0.7632 -> "76.32"). Used for the composite and every
  // dimension value/CI; NOT for n_eff (a count) or epistemic state (signed).
  function pct(value) {
    const number = numeric(value);
    if (number == null) return null;
    return (number * 100).toFixed(2);
  }

  function formatCI(dim, score) {
    const ci = score?.ci;
    const low = numeric(ci?.low);
    const high = numeric(ci?.high);
    if (low == null || high == null) {
      console.warn('[SAF] scored dimension missing ci', dim, score);
      return '±?';
    }
    return `±${((high - low) / 2 * 100).toFixed(2)}`;
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

  function rungBadge(rung) {
    const meta = RUNG_META[rung];
    if (!meta) return null;
    const el = document.createElement('span');
    el.className = `saf-rung-badge ${meta.cls}`;
    el.textContent = meta.abbr;
    el.title = meta.title;
    return el;
  }

  // The overall index is never shown bare: always with its CI and its rung (#6,
  // #14). If the server gates the composite (status !== OK — e.g. minor / low
  // validation), we surface the gate instead of a number.
  function renderComposite(score) {
    if (!els.compositeCard) return;
    const comp = score?.composite;
    if (!comp) {
      els.compositeCard.hidden = true;
      return;
    }
    els.compositeCard.hidden = false;

    const low = numeric(comp.ci?.low);
    const high = numeric(comp.ci?.high);
    const value = numeric(comp.value);
    const presentable = comp.status === 'OK' && value != null && low != null && high != null;

    if (els.compositeValue) {
      els.compositeValue.textContent = presentable ? pct(value) : '—';
      els.compositeValue.style.setProperty(
        'color',
        presentable ? colorForValue(clampUnit(value) ?? 0) : 'var(--saf-text-dim)',
      );
    }
    if (els.compositeCi) {
      els.compositeCi.textContent = presentable
        ? `CI ${pct(low)}–${pct(high)}`
        : `not shown — ${String(comp.status || 'gated').toLowerCase()}`;
    }
    if (els.compositeRung) {
      clear(els.compositeRung);
      const badge = rungBadge(comp.rung);
      if (badge) els.compositeRung.appendChild(badge);
    }
    if (els.compositeSub) {
      const bits = [];
      const strip = score?.regime_overlay?.strip;
      if (Array.isArray(strip) && strip.length) bits.push(`Regime ${strip.join(' → ')}`);
      if (comp.state_compromised_caveat) bits.push('state-compromised — evidence widened');
      const failed = Object.entries(comp.gates_passed || {})
        .filter(([, ok]) => ok === false)
        .map(([gate]) => gate);
      if (failed.length) bits.push(`gate not met: ${failed.join(', ')}`);
      els.compositeSub.textContent = bits.join('   ·   ');
      els.compositeSub.hidden = bits.length === 0;
    }
  }

  // Per-turn state ribbon from state_strip: bar height/colour track the
  // epistemic estimate, opacity dims passive turns. We never surface the
  // surrender construct here (#5) — only load / metacognition / epistemic.
  function signed(value) {
    const number = numeric(value);
    if (number == null) return null;
    return number >= 0 ? `+${number.toFixed(2)}` : number.toFixed(2);
  }

  function dominant(strip, key) {
    const counts = {};
    strip.forEach((sv) => {
      const k = sv?.[key];
      if (k) counts[k] = (counts[k] || 0) + 1;
    });
    const top = Object.entries(counts).sort((a, b) => b[1] - a[1])[0];
    return top ? top[0] : null;
  }

  function renderStateStrip(score) {
    if (!els.stateSection || !els.stateStrip) return;
    clear(els.stateStrip);
    if (els.stateReadout) clear(els.stateReadout);
    const strip = Array.isArray(score?.state_strip) ? score.state_strip : [];
    if (!strip.length) {
      els.stateSection.hidden = true;
      if (els.stateSummary) els.stateSummary.hidden = true;
      if (els.stateNote) els.stateNote.hidden = true;
      return;
    }
    els.stateSection.hidden = false;

    const fragment = document.createDocumentFragment();
    strip.forEach((sv) => {
      const cell = document.createElement('span');
      cell.className = 'saf-state-cell';
      const metacog = String(sv?.metacog || '').toLowerCase();
      cell.dataset.metacog = metacog;
      const epistemic = numeric(sv?.epistemic);
      const norm = epistemic == null ? 0.5 : (clampUnit((epistemic + 1) / 2) ?? 0.5);
      cell.style.setProperty('--saf-state-h', `${Math.round(20 + norm * 80)}%`);
      cell.style.setProperty('--saf-state-color', colorForValue(norm));
      const load = LOAD_LABEL[sv?.load] || '';
      cell.title = [
        `Turn ${sv?.turn_index ?? '?'}`,
        sv?.metacog ? String(sv.metacog).toLowerCase() : null,
        load || null,
        epistemic == null ? null : `epistemic ${epistemic.toFixed(2)}`,
      ]
        .filter(Boolean)
        .join(' · ');
      fragment.appendChild(cell);
    });
    els.stateStrip.appendChild(fragment);

    // Numeric + named summary so the ribbon is not read as a bare picture. These
    // are MEASURABLE CSPC state estimates (signed epistemic, named load /
    // metacognition); surrender is never surfaced here (#5).
    if (els.stateSummary) {
      const bits = [];
      const epMean = signed(score?.state_validity?.epistemic_mean);
      if (epMean != null) bits.push(`Epistemic mean ${epMean}`);
      const mc = dominant(strip, 'metacog');
      if (mc) bits.push(`mostly ${String(mc).toLowerCase()} metacognition`);
      const ld = dominant(strip, 'load');
      if (ld) bits.push(`${LOAD_LABEL[ld] || String(ld).toLowerCase()} typical`);
      els.stateSummary.textContent = bits.join('   ·   ');
      els.stateSummary.hidden = bits.length === 0;
    }

    if (els.stateReadout) {
      const readout = document.createDocumentFragment();
      strip.forEach((sv) => {
        const row = document.createElement('div');
        row.className = 'saf-state-readout-row';

        const turn = document.createElement('span');
        turn.className = 'saf-state-turn';
        turn.textContent = `T${sv?.turn_index ?? '?'}`;
        row.appendChild(turn);

        const desc = document.createElement('span');
        desc.className = 'saf-state-desc';
        const ep = signed(sv?.epistemic);
        const tom = signed(sv?.tom_signal);
        desc.textContent = [
          sv?.metacog ? String(sv.metacog).toLowerCase() : null,
          LOAD_LABEL[sv?.load] || null,
          ep == null ? null : `epistemic ${ep}`,
          tom == null ? null : `ToM ${tom}`,
        ]
          .filter(Boolean)
          .join('  ·  ');
        row.appendChild(desc);

        readout.appendChild(row);
      });
      els.stateReadout.appendChild(readout);
    }

    if (els.stateNote) {
      const caveats = Array.isArray(score?.state_validity?.caveats) ? score.state_validity.caveats : [];
      els.stateNote.textContent = caveats.length ? caveats.join(' · ') : '';
      els.stateNote.hidden = caveats.length === 0;
    }
  }

  // CSL (Cognitive Work Layer): per-ACF-level displayed contribution. This is a
  // DESCRIPTIVE layer served by a separate route — never an ARI score (#2), and
  // never collapsed into one whole-session human/AI number (csl/ownership Do-NOT
  // #5): we render the 7 levels independently. Levels with thin evidence show a
  // status, never a fabricated 50/50 (#12).
  const CSL_STATUS_LABEL = {
    'N/A': 'not applicable',
    INSUFFICIENT_SAMPLE: 'not enough evidence',
    MEASUREMENT_SATURATED: 'saturated',
  };

  function renderCSLRow(lvl) {
    const row = document.createElement('div');
    row.className = 'saf-csl-row';

    const label = document.createElement('span');
    label.className = 'saf-csl-label';
    label.textContent = `${lvl?.level || '?'} ${lvl?.label || ''}`.trim();
    row.appendChild(label);

    const bar = document.createElement('span');
    bar.className = 'saf-csl-bar';
    row.appendChild(bar);

    const val = document.createElement('span');
    val.className = 'saf-csl-val';
    row.appendChild(val);

    const human = numeric(lvl?.human_pct);
    const ai = numeric(lvl?.ai_pct);
    if (lvl?.status === 'OK' && human != null && ai != null) {
      const hSeg = document.createElement('span');
      hSeg.className = 'saf-csl-seg saf-csl-seg--human';
      hSeg.style.setProperty('--saf-csl-w', `${Math.round(human * 100)}%`);
      const aSeg = document.createElement('span');
      aSeg.className = 'saf-csl-seg saf-csl-seg--ai';
      aSeg.style.setProperty('--saf-csl-w', `${Math.round(ai * 100)}%`);
      bar.appendChild(hSeg);
      bar.appendChild(aSeg);
      val.textContent = `${(human * 100).toFixed(0)}% you · ${(ai * 100).toFixed(0)}% AI`;
    } else {
      row.classList.add('is-empty');
      bar.classList.add('is-empty');
      val.textContent = CSL_STATUS_LABEL[lvl?.status] || 'no data';
    }
    return row;
  }

  function renderCSL(work) {
    if (!els.cslSection || !els.cslLevels) return;
    clear(els.cslLevels);
    const levels = Array.isArray(work?.levels) ? work.levels : [];
    if (work?.status !== 'ok' || !levels.length) {
      els.cslSection.hidden = true;
      if (els.cslNote) els.cslNote.hidden = true;
      return;
    }
    els.cslSection.hidden = false;
    const fragment = document.createDocumentFragment();
    levels.forEach((lvl) => fragment.appendChild(renderCSLRow(lvl)));
    els.cslLevels.appendChild(fragment);
    if (els.cslNote) {
      els.cslNote.textContent = work?.note || '';
      els.cslNote.hidden = !work?.note;
    }
  }

  function hideRichSections() {
    if (els.compositeCard) els.compositeCard.hidden = true;
    if (els.stateSection) els.stateSection.hidden = true;
    if (els.stateSummary) els.stateSummary.hidden = true;
    if (els.stateNote) els.stateNote.hidden = true;
    if (els.cslSection) els.cslSection.hidden = true;
    clear(els.stateStrip);
    clear(els.stateReadout);
    clear(els.cslLevels);
  }

  // The full results render into a large scrollable overlay layered over the
  // panel. Selecting a chat opens it; its own close button / backdrop dismiss it
  // (never bound to Esc — that already closes the whole SAF modal).
  function openResults() {
    if (els.resultsOverlay) els.resultsOverlay.hidden = false;
  }

  function closeResults() {
    if (els.resultsOverlay) els.resultsOverlay.hidden = true;
    if (els.empty) els.empty.hidden = false;
  }

  function handleOverlayClick(event) {
    if (event?.target === els.resultsOverlay) closeResults();
  }

  function feedbackButtons() {
    return [els.feedbackUp, els.feedbackDown].filter(Boolean);
  }

  function updateFeedbackCount() {
    if (!els.feedbackCount) return;
    const count = String(els.feedbackNote?.value || '').length;
    els.feedbackCount.textContent = `${count}/${MAX_FEEDBACK_CHARS}`;
  }

  function setFeedbackStatus(message = '', isError = false) {
    if (!els.feedbackStatus) return;
    els.feedbackStatus.textContent = message;
    els.feedbackStatus.classList.toggle('is-error', isError);
  }

  function setFeedbackDisabled(disabled) {
    feedbackButtons().forEach((button) => {
      button.disabled = disabled;
    });
    if (els.feedbackNote) els.feedbackNote.disabled = disabled;
    if (els.feedbackSubmit) els.feedbackSubmit.disabled = disabled;
  }

  function setThumbSelection(value) {
    feedbackButtons().forEach((button) => {
      button.setAttribute('aria-pressed', button.dataset.feedbackValue === String(value) ? 'true' : 'false');
    });
  }

  function resetFeedback(feedbackRecorded = false) {
    state.feedbackRecorded = Boolean(feedbackRecorded);
    state.feedbackSubmitting = false;
    setThumbSelection(null);
    if (els.feedbackNote) els.feedbackNote.value = '';
    updateFeedbackCount();
    setFeedbackDisabled(state.feedbackRecorded);
    setFeedbackStatus(state.feedbackRecorded ? 'Feedback recorded.' : '');
  }

  function setFeedbackLoading() {
    state.feedbackRecorded = false;
    state.feedbackSubmitting = false;
    setThumbSelection(null);
    if (els.feedbackNote) els.feedbackNote.value = '';
    updateFeedbackCount();
    setFeedbackDisabled(true);
    setFeedbackStatus('');
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
    value.textContent = scoreValue == null ? '-' : pct(scoreValue);
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
    value.textContent = `${symbol} ${pct(bound)}`;
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
    hideRichSections();
    if (els.remarks) els.remarks.value = '';
    setFeedbackLoading();
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
    hideRichSections();
    setFeedbackLoading();
  }

  function renderScore(chatId, score) {
    if (els.empty) els.empty.hidden = true;
    if (els.content) els.content.hidden = false;
    if (els.title) els.title.textContent = `Conversation ${shortId(score?.conversation_id || score?.session_id || chatId)}`;
    if (els.meta) els.meta.textContent = score?.tier ? `Tier ${score.tier}` : 'Score loaded';
    if (els.trendSection) els.trendSection.hidden = true;
    renderComposite(score || {});
    renderStateStrip(score || {});
    renderProfile(score?.profile || {});
    renderFlags(score?.flags || {});
    renderRemarks(score?.report || {});
    resetFeedback(Boolean(score?.feedback_given));
  }

  async function submitFeedback(feedback) {
    if (!state.chatId || state.feedbackRecorded || state.feedbackSubmitting) return;
    const chatId = state.chatId;

    const storageApi = storage();
    const apiClient = api();
    if (!storageApi || !apiClient?.submitFeedback) {
      setFeedbackStatus('Feedback is unavailable in this tab.', true);
      return;
    }

    state.feedbackSubmitting = true;
    setFeedbackDisabled(true);
    setFeedbackStatus('Sending feedback...');

    try {
      const userRef = await storageApi.get(storageApi.STORAGE_KEYS.USER_REF, '');
      if (state.chatId !== chatId) return;
      if (!userRef) throw new Error('Set your user ID in Settings first.');

      const result = await apiClient.submitFeedback(userRef, chatId, feedback);
      if (state.chatId !== chatId) return;
      if (!result?.ok) {
        throw new Error(result?.detail || result?.error || 'Could not send feedback.');
      }

      state.feedbackRecorded = true;
      setFeedbackDisabled(true);
      setFeedbackStatus('Feedback recorded.');
    } catch (error) {
      if (state.chatId !== chatId) return;
      state.feedbackSubmitting = false;
      setFeedbackDisabled(false);
      setFeedbackStatus(error.message || 'Could not send feedback.', true);
    }
  }

  function handleThumbClick(event) {
    const button = event.currentTarget;
    if (!(button instanceof HTMLButtonElement)) return;
    const value = Number(button.dataset.feedbackValue);
    if (value !== 1 && value !== -1) return;
    setThumbSelection(value);
    void submitFeedback({ type: 'thumb', value });
  }

  function handleFeedbackInput() {
    const text = String(els.feedbackNote?.value || '');
    if (text.length > MAX_FEEDBACK_CHARS && els.feedbackNote) {
      els.feedbackNote.value = text.slice(0, MAX_FEEDBACK_CHARS);
    }
    updateFeedbackCount();
    if (!state.feedbackRecorded) setFeedbackStatus('');
  }

  function handleNoteSubmit() {
    const text = String(els.feedbackNote?.value || '').trim();
    if (!text) {
      setFeedbackStatus('Add a note before sending.', true);
      return;
    }
    if (text.length > MAX_FEEDBACK_CHARS) {
      setFeedbackStatus('Keep notes to 280 characters.', true);
      return;
    }
    void submitFeedback({ type: 'note', text });
  }

  async function loadScore(chatId) {
    const requestId = state.requestId + 1;
    state.requestId = requestId;
    state.chatId = chatId;
    openResults();
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
      void loadWork(chatId, requestId, userRef);
    } catch (error) {
      if (requestId !== state.requestId) return;
      setShellError(chatId, error.message || 'Could not load score.');
    }
  }

  // CSL is a separate read-only route; fetched after the score so a CSL outage
  // never blocks the ARI results. A stale response (request superseded) is dropped.
  async function loadWork(chatId, requestId, userRef) {
    const apiClient = api();
    if (!apiClient?.getChatWork) {
      renderCSL(null);
      return;
    }
    try {
      const result = await apiClient.getChatWork(userRef, chatId);
      if (requestId !== state.requestId) return;
      renderCSL(result?.ok ? result.data || {} : null);
    } catch (_error) {
      if (requestId !== state.requestId) return;
      renderCSL(null);
    }
  }

  function handleChatSelected(event) {
    const chatId = event?.detail?.chatId;
    if (!chatId) return;
    void loadScore(chatId);
  }

  shadowRoot.addEventListener('saf-chat-selected', handleChatSelected);
  els.resultsClose?.addEventListener('click', closeResults);
  els.resultsOverlay?.addEventListener('click', handleOverlayClick);
  els.feedbackUp?.addEventListener('click', handleThumbClick);
  els.feedbackDown?.addEventListener('click', handleThumbClick);
  els.feedbackNote?.addEventListener('input', handleFeedbackInput);
  els.feedbackSubmit?.addEventListener('click', handleNoteSubmit);
  setFeedbackLoading();

  return () => {
    state.requestId += 1;
    shadowRoot.removeEventListener('saf-chat-selected', handleChatSelected);
    els.resultsClose?.removeEventListener('click', closeResults);
    els.resultsOverlay?.removeEventListener('click', handleOverlayClick);
    els.feedbackUp?.removeEventListener('click', handleThumbClick);
    els.feedbackDown?.removeEventListener('click', handleThumbClick);
    els.feedbackNote?.removeEventListener('input', handleFeedbackInput);
    els.feedbackSubmit?.removeEventListener('click', handleNoteSubmit);
  };
}
