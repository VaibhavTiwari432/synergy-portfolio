'use strict';

/**
 * panel.js — popup panel logic. OWNER: Chief Engineer.
 *
 * STRUCTURAL NON-NEGOTIABLES (enforced in this file, not just commented):
 *
 *  #4  "synergy" never in Tier-1 user-facing output.
 *  #5  "surrender" never in regime-overlay output.
 *  #6  No bare composite without CI + rung. Panel structurally has no
 *      composite element — we never render data.composite.value.
 *  #10 self_rating_raw never shown in any form.
 *  #14 Every emitted claim carries exactly one rung.
 *  #15 Minor protection: if is_minor: true, minor-guard activates; all
 *      views hidden. Guard is dormant otherwise.
 *
 * Section order:
 *   Section 1 (#section-strengths, data-order="1") is always rendered
 *   before Section 2 (#section-growth, data-order="2"). This code never
 *   reorders DOM nodes — panel.html establishes the order.
 */

(function initPanel() {
  // ── FORBIDDEN WORD GUARD ─────────────────────────────────────────────────
  // Non-negotiables #4 and #5. Applied to every string before DOM insertion.
  const FORBIDDEN = Object.freeze(['synergy', 'surrender', 'dependent', 'decline']);

  function _safeText(text) {
    if (!text) return '';
    let s = String(text);
    for (const word of FORBIDDEN) {
      s = s.replace(new RegExp(word, 'gi'), '···');
    }
    return s;
  }

  // ── DIM METADATA ──────────────────────────────────────────────────────────
  const DIM_LABELS = Object.freeze({
    AL:  'AI Literacy',
    PR:  'Prompt Reasoning',
    EC:  'Error Correction',
    ES:  'Ethics Sensitivity',
    CS:  'Contextual Synthesis',
    CD:  'Creative Divergence',
    AUI: 'Augmentation Instinct',
    CA:  'Collaborative Agency',
  });

  const DIM_ORDER = ['AL', 'PR', 'EC', 'ES', 'CS', 'CD', 'AUI', 'CA'];

  function _normaliseProfile(profile) {
    let source = profile;
    if (typeof source === 'string') {
      try {
        source = JSON.parse(source);
      } catch {
        source = {};
      }
    }
    if (!source || typeof source !== 'object' || Array.isArray(source)) {
      source = {};
    }

    const out = {};
    for (const key of DIM_ORDER) {
      const raw = source[key] || source[key.toLowerCase()] || {};
      const value = Number(raw.value);
      out[key] = {
        ...raw,
        status: String(raw.status || '').toUpperCase(),
        value: Number.isFinite(value) ? Math.max(0, Math.min(1, value)) : null,
      };
    }
    return out;
  }

  function _hasScoreableDimensions(profile) {
    return DIM_ORDER.some((key) => {
      const d = profile?.[key];
      return d?.status === 'OK' && d.value != null;
    });
  }

  function _resetRadarDetail() {
    const container = document.getElementById('radar-container');
    const button = document.getElementById('btn-toggle-radar');
    const svg = document.getElementById('radar-svg');
    const legend = document.getElementById('radar-legend');

    if (container) container.classList.add('hidden');
    if (button) {
      button.setAttribute('aria-expanded', 'false');
      button.textContent = 'Show dimension detail';
    }
    if (svg) {
      while (svg.firstChild) svg.removeChild(svg.firstChild);
    }
    if (legend) legend.innerHTML = '';
  }

  function _setRadarAvailable(available) {
    const row = document.querySelector('.radar-toggle-row');
    const button = document.getElementById('btn-toggle-radar');
    if (row) row.classList.toggle('hidden', !available);
    if (button) button.disabled = !available;
    if (!available) _resetRadarDetail();
  }

  // ── FLAG LABELS ───────────────────────────────────────────────────────────
  const FLAG_LABELS = Object.freeze({
    fluent_incompetence: 'Fluency mismatch noted',
    debt_flag:           'Passive acceptance pattern',
    judge_unavailable:   'Score estimated (judge unavailable)',
    judge_family_conflict: 'Judge conflict — treat with caution',
    ec_low_calibration_confidence: 'EC: low calibration confidence',
  });

  // ── VIEWS ─────────────────────────────────────────────────────────────────
  const VIEWS = [
    'onboarding-welcome',
    'onboarding-setup',
    'pending',
    'main',
    'portfolio',
    'settings',
  ];

  function _showView(name) {
    const active = document.activeElement;

    for (const v of VIEWS) {
      const el = document.getElementById(`view-${v}`);
      if (!el) continue;
      const visible = v === name;

      if (!visible && active instanceof HTMLElement && el.contains(active)) {
        active.blur();
      }

      el.classList.toggle('hidden', !visible);

      if (visible) {
        el.removeAttribute('aria-hidden');
        el.removeAttribute('inert');
        el.inert = false;
      } else {
        el.removeAttribute('aria-hidden');
        el.setAttribute('inert', '');
        el.inert = true;
      }
    }
  }

  // ── MINOR PROTECTION GUARD ────────────────────────────────────────────────
  // Dormant unless backend marks is_minor: true (non-negotiable #15).
  function _checkMinorGuard(data) {
    if (!data || data.is_minor !== true) return false;
    const guard = document.getElementById('minor-guard');
    if (guard) guard.classList.remove('hidden');
    for (const v of VIEWS) {
      document.getElementById(`view-${v}`)?.classList.add('hidden');
    }
    return true;
  }

  // ── HEALTH DOTS ───────────────────────────────────────────────────────────
  function _updateHealthDots(health) {
    for (const id of ['health-dot-main', 'health-dot-pending']) {
      const el = document.getElementById(id);
      if (el) el.dataset.health = health || 'unknown';
    }
  }

  // ── BACKGROUND BRIDGE ─────────────────────────────────────────────────────
  function _sendBg(message) {
    return new Promise((resolve) => {
      chrome.runtime.sendMessage(message, (response) => {
        void chrome.runtime.lastError; // suppress "no listener" console error
        resolve(response || { ok: false, error: 'no_response' });
      });
    });
  }

  // ── STATE ─────────────────────────────────────────────────────────────────
  let _userRef = null;
  let _currentChatId = null;
  let _pendingPollTimer = null;
  let _analysisPollTimer = null;
  let _selectedFeedbackRating = null;

  // ── INIT ──────────────────────────────────────────────────────────────────
  async function init() {
    const res = await _sendBg({ type: 'SAF_PANEL_GET_STATUS' });
    if (!res.ok) {
      _showView('onboarding-welcome');
      return;
    }

    const { onboardingComplete, userRef, health, latestCapture, analysisProgress } = res.data;
    _userRef = userRef;
    _updateHealthDots(health);

    if (!onboardingComplete || !userRef) {
      _showView('onboarding-welcome');
      return;
    }

    if (analysisProgress?.active && analysisProgress.stage !== 'error' && analysisProgress.stage !== 'complete') {
      _showView('pending');
      _renderAnalysisProgress(analysisProgress);
      _startAnalysisProgressPoll();
      if (analysisProgress.chatId) {
        _currentChatId = analysisProgress.chatId;
        _startPendingPoll(userRef);
      }
    } else if (latestCapture?.conversation_id) {
      await _resolveCapture(userRef, latestCapture);
    } else {
      _showView('main');
      _renderBlank();
    }
  }

  // ── CAPTURE RESOLUTION ────────────────────────────────────────────────────
  async function _resolveCapture(userRef, capture) {
    const convId = capture.conversation_id;
    const chatRes = await _sendBg({ type: 'SAF_PANEL_LIST_CHATS', userRef });

    if (!chatRes.ok) {
      _showView('main');
      _renderBlank();
      return;
    }

    const chats = chatRes.data.chats || [];
    const chat = chats.find((c) => c.conversation_id === convId);

    if (!chat) {
      // Not yet ingested (consent OFF or first load)
      _showView('main');
      _renderBlank();
      return;
    }

    _currentChatId = chat.chat_id;

    if (chat.status === 'scored') {
      await _loadAndShowScore(userRef, chat.chat_id);
    } else {
      _showView('pending');
      _startPendingPoll(userRef);
    }
  }

  // ── PENDING POLL ──────────────────────────────────────────────────────────
  function _startPendingPoll(userRef) {
    if (_pendingPollTimer) clearInterval(_pendingPollTimer);
    _startAnalysisProgressPoll();
    let fillPct = 0;

    _pendingPollTimer = setInterval(async () => {
      const statusRes = await _sendBg({ type: 'SAF_PANEL_GET_STATUS' });
      if (statusRes.ok && statusRes.data?.analysisProgress) {
        _renderAnalysisProgress(statusRes.data.analysisProgress);
      } else {
        fillPct = Math.min(fillPct + 5, 90); // synthetic - never reaches 100 until done
        const fill = document.getElementById('progress-fill');
        if (fill) fill.style.width = `${fillPct}%`;
      }

      if (!_currentChatId) return;

      // Read status (not just the score) so we resolve 'scored' AND surface
      // 'failed' instead of spinning forever. (D-008)
      const listRes = await _sendBg({ type: 'SAF_PANEL_LIST_CHATS', userRef });
      const chat = listRes.ok
        ? (listRes.data.chats || []).find((c) => c.chat_id === _currentChatId)
        : null;

      if (chat?.status === 'failed') {
        clearInterval(_pendingPollTimer);
        _pendingPollTimer = null;
        _stopAnalysisProgressPoll();
        _setPendingHint('Scoring failed — press “Analyse now” to retry.');
        return;
      }

      if (chat?.status === 'scored') {
        clearInterval(_pendingPollTimer);
        _pendingPollTimer = null;
        _stopAnalysisProgressPoll();
        const fill2 = document.getElementById('progress-fill');
        if (fill2) fill2.style.width = '100%';
        await _loadAndShowScore(userRef, _currentChatId);
      }
    }, 5000);
  }

  // ── SMALL UI HELPERS ──────────────────────────────────────────────────────
  function _setPendingHint(text) {
    const el = document.querySelector('#view-pending .pending-hint');
    if (el) el.textContent = text;
  }

  function _renderAnalysisProgress(progress, fallbackMessage) {
    const pct = Math.max(0, Math.min(100, Math.round(Number(progress?.percent ?? 0))));
    const stage = String(progress?.stage || 'analysing').replace(/_/g, ' ');
    const message = progress?.message || fallbackMessage || 'Working on this chat...';
    const turns = Number(progress?.capturedTurns || 0);

    const label = document.getElementById('pending-stage-label');
    if (label) label.textContent = stage.charAt(0).toUpperCase() + stage.slice(1);

    const fill = document.getElementById('progress-fill');
    if (fill) fill.style.width = `${pct}%`;

    const track = document.querySelector('#view-pending .progress-track');
    if (track) track.setAttribute('aria-valuenow', String(pct));

    const detail = turns > 0
      ? `${message} Chat captured: ${turns} turn${turns === 1 ? '' : 's'} (${pct}%).`
      : `${message} ${pct}%.`;
    _setPendingHint(detail);
  }

  function _startAnalysisProgressPoll() {
    if (_analysisPollTimer) clearInterval(_analysisPollTimer);
    _analysisPollTimer = setInterval(async () => {
      const res = await _sendBg({ type: 'SAF_PANEL_GET_STATUS' });
      if (res.ok && res.data?.analysisProgress) {
        _renderAnalysisProgress(res.data.analysisProgress);
      }
    }, 700);
  }

  function _stopAnalysisProgressPoll() {
    if (_analysisPollTimer) clearInterval(_analysisPollTimer);
    _analysisPollTimer = null;
  }

  // Briefly show a message on whichever status line is visible (main or settings).
  function _flashStatus(text) {
    const statusEl = document.getElementById('settings-status');
    if (!statusEl) return;
    statusEl.textContent = text;
    statusEl.className = 'settings-status error-text';
    statusEl.classList.remove('hidden');
    setTimeout(() => statusEl.classList.add('hidden'), 3500);
  }

  // ── SCORE LOADING ─────────────────────────────────────────────────────────
  async function _loadAndShowScore(userRef, chatId) {
    const res = await _sendBg({ type: 'SAF_PANEL_GET_SCORE', userRef, chatId });

    if (!res.ok || !res.data) {
      _showView('pending');
      _startPendingPoll(userRef);
      return;
    }

    if (_checkMinorGuard(res.data)) return;

    _renderScore(res.data);
    _showView('main');
  }

  // ── BLANK STATE ───────────────────────────────────────────────────────────
  function _renderBlank() {
    const el = document.getElementById('strengths-list');
    if (el) {
      el.innerHTML = '';
      const li = document.createElement('li');
      li.className = 'trait-item trait-none';
      li.textContent = 'Open a chat on ChatGPT and press "Analyse now".';
      el.appendChild(li);
    }
    const gl = document.getElementById('growth-list');
    if (gl) gl.innerHTML = '';
    document.getElementById('flag-pills-container')?.classList.add('hidden');
    document.getElementById('regime-bar-container')?.classList.add('hidden');
    document.getElementById('sustainability-text')?.classList.add('hidden');
    document.getElementById('feedback-section')?.classList.add('hidden');
    document.getElementById('tier-caveat')?.classList.add('hidden');
    _setRadarAvailable(false);
    const tr = document.getElementById('chat-tier-rung');
    if (tr) tr.textContent = '';
  }

  // ── SCORE RENDERING ───────────────────────────────────────────────────────
  function _renderScore(data) {
    const profile = _normaliseProfile(data.profile);
    const hasDimensions = _hasScoreableDimensions(profile);

    // Tier + rung badge (non-negotiable #14: every claim carries exactly one rung)
    const tierEl = document.getElementById('chat-tier-rung');
    if (tierEl) {
      const tier = data.tier || 1;
      const rung = data.report?.rung || 'MEASURABLE';
      tierEl.textContent = `Tier ${tier} · ${_safeText(rung.toLowerCase())}`;
      tierEl.dataset.tier = tier;
    }

    _renderRegimeBar(data.regime_overlay, data.state_validity);

    // Section 1: strengths — DOM order enforces position; this code never reorders
    _renderStrengths(data.report, profile);

    // Section 2: growth nudge
    _renderGrowthNudge(data.report, profile);

    // Tier caveat
    const caveatEl = document.getElementById('tier-caveat');
    if (caveatEl && data.report?.tier_caveat) {
      caveatEl.textContent = _safeText(data.report.tier_caveat);
      caveatEl.classList.remove('hidden');
    } else if (caveatEl) {
      caveatEl.classList.add('hidden');
    }

    _renderFlagPills(data.flags);
    _setRadarAvailable(hasDimensions);
    if (hasDimensions) {
      _renderRadar(profile);
    }
    _renderSustainability(data.sustainability);

    // Feedback (only when consent on and not already given)
    const fbSection = document.getElementById('feedback-section');
    if (fbSection) {
      fbSection.classList.toggle('hidden', data.feedback_given !== false);
    }
  }

  // ── REGIME BAR ────────────────────────────────────────────────────────────
  function _renderRegimeBar(regimeOverlay, stateValidity) {
    const container = document.getElementById('regime-bar-container');
    const svg = document.getElementById('regime-bar-svg');
    const label = document.getElementById('regime-label');
    if (!container || !svg || !label) return;

    while (svg.firstChild) svg.removeChild(svg.firstChild);

    if (!regimeOverlay || stateValidity?.state_compromised) {
      container.classList.add('hidden');
      return;
    }

    const occupancy = regimeOverlay.occupancy || {};
    if (!Object.keys(occupancy).length) {
      container.classList.add('hidden');
      return;
    }

    container.classList.remove('hidden');

    // Dominant regime (highest occupancy)
    const dominant = Object.entries(occupancy).reduce(
      (best, [k, v]) => (v > best[1] ? [k, v] : best),
      ['', 0],
    );
    const regimeName = dominant[0]
      .toLowerCase()
      .replace(/_/g, ' ');

    // Simple three-zone bar
    const W = 320, H = 28, R = 4;
    const zones = [
      { x: 0,   w: 106, cls: 'regime-zone-low' },
      { x: 107, w: 106, cls: 'regime-zone-mid' },
      { x: 214, w: 106, cls: 'regime-zone-high' },
    ];
    for (const z of zones) {
      const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
      rect.setAttribute('x', z.x); rect.setAttribute('y', 2);
      rect.setAttribute('width', z.w); rect.setAttribute('height', H - 4);
      rect.setAttribute('rx', R);
      rect.setAttribute('class', z.cls);
      svg.appendChild(rect);
    }

    // Position indicator proportional to dominant occupancy
    const dotX = Math.max(8, Math.min(W - 8, dominant[1] * W));
    const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
    circle.setAttribute('cx', dotX); circle.setAttribute('cy', H / 2);
    circle.setAttribute('r', 6);
    circle.setAttribute('class', 'regime-dot');
    svg.appendChild(circle);

    // Non-negotiable #5: "surrender" redacted by _safeText
    label.textContent = regimeName ? `State: ${_safeText(regimeName)}` : '';
  }

  // ── SECTION 1: STRENGTHS (ALWAYS FIRST) ──────────────────────────────────
  function _renderStrengths(report, profile) {
    const list = document.getElementById('strengths-list');
    if (!list) return;
    list.innerHTML = '';

    // Use report.observed for rich text; fall back to top-scoring dims
    const items = report?.observed?.length ? report.observed.slice(0, 3) : null;

    if (items) {
      for (const text of items) {
        _appendTraitItem(list, _safeText(text), 'trait-item');
      }
      return;
    }

    // Fallback: top dims by score
    if (profile) {
      const scored = DIM_ORDER
        .map((k) => ({ k, d: profile[k] }))
        .filter(({ d }) => d?.status === 'OK' && d.value != null)
        .sort((a, b) => b.d.value - a.d.value)
        .slice(0, 3);

      if (scored.length) {
        for (const { k, d } of scored) {
          const ci = d.ci ? ` [${d.ci.low.toFixed(2)}–${d.ci.high.toFixed(2)}]` : '';
          const rung = d.rung ? ` · ${_safeText(d.rung.toLowerCase())}` : '';
          const text = `${DIM_LABELS[k]}: ${d.value.toFixed(2)}${ci}${rung}`;
          _appendTraitItem(list, text, 'trait-item');
        }
        return;
      }
    }

    _appendTraitItem(list, 'More data needed for strength identification.', 'trait-item trait-none');
  }

  // ── SECTION 2: GROWTH NUDGE (ALWAYS SECOND) ───────────────────────────────
  function _renderGrowthNudge(report, profile) {
    const list = document.getElementById('growth-list');
    if (!list) return;
    list.innerHTML = '';

    // Use report.inferred for growth areas; fall back to lowest dims
    const items = report?.inferred?.length ? report.inferred.slice(0, 2) : null;

    if (items) {
      for (const text of items) {
        _appendTraitItem(list, _safeText(text), 'trait-item trait-growth');
      }
      return;
    }

    if (profile) {
      const scored = DIM_ORDER
        .map((k) => ({ k, d: profile[k] }))
        .filter(({ d }) => d?.status === 'OK' && d.value != null)
        .sort((a, b) => a.d.value - b.d.value)
        .slice(0, 2);

      if (scored.length) {
        for (const { k, d } of scored) {
          const rung = d.rung ? ` · ${_safeText(d.rung.toLowerCase())}` : '';
          const text = `${DIM_LABELS[k]}: ${d.value.toFixed(2)}${rung} — room to expand`;
          _appendTraitItem(list, text, 'trait-item trait-growth');
        }
        return;
      }
    }

    _appendTraitItem(list, 'Insufficient data for growth areas.', 'trait-item trait-none');
  }

  function _appendTraitItem(list, text, className) {
    const li = document.createElement('li');
    li.className = className;
    li.textContent = text; // already passed through _safeText by callers
    list.appendChild(li);
  }

  // ── FLAG PILLS ────────────────────────────────────────────────────────────
  function _renderFlagPills(flags) {
    const container = document.getElementById('flag-pills-container');
    if (!container) return;
    container.innerHTML = '';

    if (!flags || typeof flags !== 'object') {
      container.classList.add('hidden');
      return;
    }

    const active = Object.entries(FLAG_LABELS)
      .filter(([k]) => Boolean(flags[k]))
      .map(([, label]) => label);

    if (!active.length) {
      container.classList.add('hidden');
      return;
    }

    container.classList.remove('hidden');
    for (const label of active) {
      const pill = document.createElement('span');
      pill.className = 'flag-pill';
      pill.setAttribute('role', 'listitem');
      pill.textContent = _safeText(label);
      container.appendChild(pill);
    }
  }

  // ── RADAR SVG ─────────────────────────────────────────────────────────────
  function _renderRadar(profile) {
    const svg = document.getElementById('radar-svg');
    const legend = document.getElementById('radar-legend');
    if (!svg || !legend) return;

    while (svg.firstChild) svg.removeChild(svg.firstChild);
    legend.innerHTML = '';

    const N = DIM_ORDER.length; // 8
    const R = 0.68;

    // Background rings
    for (const rf of [0.25, 0.5, 0.75, 1.0]) {
      const ring = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
      ring.setAttribute('cx', 0); ring.setAttribute('cy', 0);
      ring.setAttribute('r', R * rf);
      ring.setAttribute('class', `radar-ring${rf === 1.0 ? ' radar-ring-outer' : ''}`);
      svg.appendChild(ring);
    }

    // Axis lines
    for (let i = 0; i < N; i++) {
      const angle = (2 * Math.PI * i / N) - Math.PI / 2;
      const x = R * Math.cos(angle);
      const y = R * Math.sin(angle);
      const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
      line.setAttribute('x1', 0); line.setAttribute('y1', 0);
      line.setAttribute('x2', x.toFixed(4)); line.setAttribute('y2', y.toFixed(4));
      line.setAttribute('class', 'radar-axis');
      svg.appendChild(line);
    }

    for (let i = 0; i < N; i++) {
      const key = DIM_ORDER[i];
      const angle = (2 * Math.PI * i / N) - Math.PI / 2;
      const labelR = 0.88;
      const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
      text.setAttribute('x', (labelR * Math.cos(angle)).toFixed(4));
      text.setAttribute('y', (labelR * Math.sin(angle)).toFixed(4));
      text.setAttribute('class', 'radar-axis-label');
      text.setAttribute('font-size', '0.12');
      text.setAttribute('text-anchor', 'middle');
      text.setAttribute('dominant-baseline', 'central');
      text.textContent = key;
      svg.appendChild(text);
    }

    // Data polygon
    const points = DIM_ORDER.map((k, i) => {
      const angle = (2 * Math.PI * i / N) - Math.PI / 2;
      const d = profile?.[k];
      const val = (d?.status === 'OK' && d.value != null) ? d.value : 0;
      const r = R * val;
      return [r * Math.cos(angle), r * Math.sin(angle)];
    });

    const poly = document.createElementNS('http://www.w3.org/2000/svg', 'polygon');
    poly.setAttribute('points', points.map(([x, y]) => `${x.toFixed(4)},${y.toFixed(4)}`).join(' '));
    poly.setAttribute('class', 'radar-polygon');
    svg.appendChild(poly);

    points.forEach(([x, y], i) => {
      const d = profile?.[DIM_ORDER[i]];
      const dot = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
      dot.setAttribute('cx', x.toFixed(4));
      dot.setAttribute('cy', y.toFixed(4));
      dot.setAttribute('r', '0.035');
      dot.setAttribute('class', d?.status === 'OK' && d.value != null ? 'radar-dot' : 'radar-dot absent');
      svg.appendChild(dot);
    });

    // Legend
    for (const k of DIM_ORDER) {
      const d = profile?.[k];
      const ok = d?.status === 'OK' && d.value != null;
      const valueText = ok ? d.value.toFixed(2) : 'N/A';
      const rungText = d?.rung ? ` · ${_safeText(d.rung.toLowerCase())}` : '';

      const li = document.createElement('li');
      li.className = 'radar-legend-item';

      const keySpan = document.createElement('span');
      keySpan.className = `radar-dim-key${ok ? '' : ' absent'}`;
      keySpan.textContent = k;

      const labelSpan = document.createElement('span');
      labelSpan.className = 'radar-dim-label';
      labelSpan.textContent = DIM_LABELS[k] || k;

      const scoreSpan = document.createElement('span');
      scoreSpan.className = 'radar-dim-score';
      scoreSpan.textContent = `${valueText}${rungText}`;

      li.appendChild(keySpan);
      li.appendChild(labelSpan);
      li.appendChild(scoreSpan);
      legend.appendChild(li);
    }
  }

  // ── SUSTAINABILITY ────────────────────────────────────────────────────────
  function _renderSustainability(sustainability) {
    const el = document.getElementById('sustainability-text');
    if (!el) return;

    if (!sustainability?.debt_ewma) {
      el.classList.add('hidden');
      return;
    }

    const ewma = sustainability.debt_ewma;
    if (ewma.n_sessions < 2) {
      el.classList.add('hidden');
      return;
    }

    // Show ewma.mode as a soft note; non-negotiable #5: _safeText applied
    const mode = _safeText(String(ewma.mode || '').toLowerCase().replace(/_/g, ' '));
    el.textContent = mode ? `Pattern: ${mode} (${ewma.n_sessions} sessions)` : '';
    el.classList.toggle('hidden', !mode);
  }

  // ── PORTFOLIO ─────────────────────────────────────────────────────────────
  async function _loadPortfolio() {
    _showView('portfolio');
    if (!_userRef) return;

    const res = await _sendBg({ type: 'SAF_PANEL_GET_PORTFOLIO', userRef: _userRef });
    if (!res.ok || !res.data) {
      document.getElementById('portfolio-insufficient')?.classList.remove('hidden');
      return;
    }

    const d = res.data;

    if (d.status === 'INSUFFICIENT_HISTORY') {
      document.getElementById('portfolio-insufficient')?.classList.remove('hidden');
      return;
    }

    // Rung (non-negotiable #14)
    const rungEl = document.getElementById('portfolio-rung');
    if (rungEl) rungEl.textContent = `Rung: ${_safeText((d.rung || 'DESIGNED').toLowerCase())}`;

    // Archetype
    const archetypeEl = document.getElementById('portfolio-archetype');
    if (archetypeEl) archetypeEl.textContent = d.archetype ? `Type: ${_safeText(d.archetype)}` : '';

    const archetypeDescEl = document.getElementById('portfolio-archetype-desc');
    if (archetypeDescEl && d.archetype_description) {
      archetypeDescEl.textContent = _safeText(d.archetype_description);
      archetypeDescEl.classList.remove('hidden');
    }

    // Trajectory
    const trajEl = document.getElementById('portfolio-trajectory');
    if (trajEl) {
      if (!d.trajectory || d.trajectory === 'INSUFFICIENT_HISTORY') {
        trajEl.textContent = 'Trend: more sessions needed';
      } else if (typeof d.trajectory === 'object') {
        const dir = _safeText(d.trajectory.trend_direction || 'stable');
        trajEl.textContent = `Trend: ${dir} (uncertainty: high · DESIGNED)`;
      }
    }

    // Dimension averages from profile_radar
    const dimList = document.getElementById('portfolio-dim-list');
    if (dimList && d.profile_radar) {
      dimList.innerHTML = '';
      for (const k of DIM_ORDER) {
        const val = d.profile_radar[k];
        const li = document.createElement('li');
        li.className = 'portfolio-dim-item';

        const keyEl = document.createElement('span');
        keyEl.className = 'pdim-key';
        keyEl.textContent = k;

        const labelEl = document.createElement('span');
        labelEl.className = 'pdim-label';
        labelEl.textContent = DIM_LABELS[k] || k;

        const scoreEl = document.createElement('span');
        scoreEl.className = 'pdim-score';
        scoreEl.textContent = val != null ? val.toFixed(2) : 'N/A';
        if (val == null) scoreEl.classList.add('absent');

        li.appendChild(keyEl);
        li.appendChild(labelEl);
        li.appendChild(scoreEl);
        dimList.appendChild(li);
      }
    }

    // Growth summary
    const gs = d.growth_summary;
    if (gs) {
      const summaryEl = document.getElementById('portfolio-growth-summary');
      const strongestEl = document.getElementById('portfolio-strongest');
      const watchEl = document.getElementById('portfolio-watch');

      if (gs.strongest_dim && strongestEl) {
        strongestEl.textContent = `Strongest: ${DIM_LABELS[gs.strongest_dim] || gs.strongest_dim}`;
      }
      if (gs.watch_dim && watchEl) {
        watchEl.textContent = `Focus area: ${DIM_LABELS[gs.watch_dim] || gs.watch_dim}`;
      }
      if (summaryEl && (gs.strongest_dim || gs.watch_dim)) {
        summaryEl.classList.remove('hidden');
      }
    }

    // Session count
    const countEl = document.getElementById('portfolio-count');
    if (countEl) {
      countEl.textContent = `Based on ${d.sessions_analysed || 0} session(s)`;
    }
  }

  // ── SETTINGS ──────────────────────────────────────────────────────────────
  async function _loadSettings() {
    const res = await _sendBg({ type: 'SAF_PANEL_GET_STATUS' });
    if (res.ok) {
      const { userRef, apiEndpoint } = res.data;
      _setInputVal('settings-user-ref', userRef || '');
      _setInputVal('settings-api-endpoint', apiEndpoint || '');
      // Keys not echoed back — fields start empty; user types a new value to change
      const consentEl = document.getElementById('settings-consent');
      if (consentEl) consentEl.checked = Boolean(res.data.consent);
    }
    _showView('settings');
  }

  async function _saveSettings() {
    const userRef     = _inputVal('settings-user-ref');
    const apiEndpoint = _inputVal('settings-api-endpoint');
    const apiKey      = _inputVal('settings-api-key');
    const consent     = document.getElementById('settings-consent')?.checked ?? false;

    const msg = {
      type: 'SAF_PANEL_SAVE_SETTINGS',
      userRef,
      apiEndpoint,
      consent,
    };
    if (apiKey)    msg.apiKey    = apiKey;

    const res = await _sendBg(msg);
    if (res.ok && userRef) _userRef = userRef;

    const statusEl = document.getElementById('settings-status');
    if (statusEl) {
      statusEl.textContent = res.ok ? 'Saved.' : 'Save failed — check API endpoint.';
      statusEl.className = `settings-status ${res.ok ? 'ok' : 'error-text'}`;
      statusEl.classList.remove('hidden');
      setTimeout(() => statusEl.classList.add('hidden'), 2500);
    }
  }

  // ── ONBOARDING ────────────────────────────────────────────────────────────
  async function _saveOnboarding() {
    const userRef     = _inputVal('input-user-ref');
    const apiEndpoint = _inputVal('input-api-endpoint') || 'http://localhost:8000';
    const apiKey      = _inputVal('input-api-key');
    const consent     = document.getElementById('toggle-consent')?.checked ?? false;

    const errorEl = document.getElementById('onboarding-error');

    if (!userRef) {
      if (errorEl) {
        errorEl.textContent = 'Please enter your ID.';
        errorEl.classList.remove('hidden');
      }
      return;
    }

    const msg = { type: 'SAF_PANEL_SAVE_SETTINGS', userRef, apiEndpoint, consent };
    if (apiKey)    msg.apiKey    = apiKey;

    await _sendBg(msg);
    await _sendBg({ type: 'SAF_PANEL_ONBOARDING_COMPLETE' });
    _userRef = userRef;

    if (errorEl) errorEl.classList.add('hidden');
    await init();
  }

  // ── FEEDBACK ──────────────────────────────────────────────────────────────
  async function _submitFeedback() {
    if (!_selectedFeedbackRating || !_currentChatId || !_userRef) return;
    const comment = (_inputVal('feedback-comment') || '').slice(0, 280);

    await _sendBg({
      type: 'SAF_PANEL_POST_FEEDBACK',
      userRef: _userRef,
      chatId: _currentChatId,
      body: { match_rating: _selectedFeedbackRating, comment },
    });

    document.getElementById('feedback-section')?.classList.add('hidden');
    _selectedFeedbackRating = null;
  }

  // ── HELPERS ───────────────────────────────────────────────────────────────
  function _inputVal(id) {
    return (document.getElementById(id)?.value || '').trim();
  }

  function _setInputVal(id, val) {
    const el = document.getElementById(id);
    if (el) el.value = val;
  }

  // ── EVENT WIRING ──────────────────────────────────────────────────────────
  function _wire() {
    // Onboarding
    document.getElementById('btn-start-onboarding')
      ?.addEventListener('click', () => _showView('onboarding-setup'));
    document.getElementById('btn-back-welcome')
      ?.addEventListener('click', () => _showView('onboarding-welcome'));
    document.getElementById('btn-save-onboarding')
      ?.addEventListener('click', _saveOnboarding);

    // Main view navigation
    document.getElementById('btn-go-settings')
      ?.addEventListener('click', _loadSettings);
    document.getElementById('btn-go-portfolio')
      ?.addEventListener('click', _loadPortfolio);
    document.getElementById('btn-back-main-from-portfolio')
      ?.addEventListener('click', () => _showView('main'));
    document.getElementById('btn-back-main-from-settings')
      ?.addEventListener('click', () => _showView('main'));

    // Pending
    document.getElementById('btn-pending-settings')
      ?.addEventListener('click', _loadSettings);

    // Analyse now
    document.getElementById('btn-analyse-now')?.addEventListener('click', async () => {
      // Query tab from popup context — currentWindow here correctly refers to the
      // parent browser window (not the extension popup), so this reliably finds the ChatGPT tab.
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      _showView('pending');
      _renderAnalysisProgress({ stage: 'capturing', percent: 1, message: 'Starting capture...' });
      _startAnalysisProgressPoll();
      const res = await _sendBg({ type: 'SAF_PANEL_ANALYSE_NOW', tabId: tab?.id });

      if (!res.ok) {
        // Prefer the background's user-facing message (consent off, no key, etc.)
        _stopAnalysisProgressPoll();
        _showView('main');
        _flashStatus(res.message || res.error || 'Could not start analysis.');
        return;
      }

      // D-008/D-010: the ingest outcome carries the chat_id. Without assigning it,
      // _startPendingPoll bails every tick and the bar freezes at 90%.
      const chatId = res.data?.chatId;
      if (chatId) _currentChatId = chatId;

      if (_userRef && _currentChatId) {
        _showView('pending');
        _renderAnalysisProgress({ stage: 'scoring', percent: 90, message: 'Conversation captured. Results appear here once ready.' });
        _startPendingPoll(_userRef);
      } else {
        _stopAnalysisProgressPoll();
        _showView('main');
        _flashStatus('Could not start analysis — no conversation found.');
      }
    });

    // Radar toggle
    document.getElementById('btn-toggle-radar')?.addEventListener('click', () => {
      const container = document.getElementById('radar-container');
      const btn = document.getElementById('btn-toggle-radar');
      if (!container || !btn) return;
      const nowHidden = container.classList.toggle('hidden');
      btn.setAttribute('aria-expanded', nowHidden ? 'false' : 'true');
      btn.textContent = nowHidden ? 'Show dimension detail' : 'Hide dimension detail';
    });

    // Feedback rating buttons
    document.querySelectorAll('.btn-feedback').forEach((btn) => {
      btn.addEventListener('click', () => {
        _selectedFeedbackRating = btn.dataset.rating;
        document.querySelectorAll('.btn-feedback')
          .forEach((b) => b.classList.remove('selected'));
        btn.classList.add('selected');
      });
    });
    document.getElementById('btn-submit-feedback')
      ?.addEventListener('click', _submitFeedback);

    // Settings
    document.getElementById('btn-save-settings')
      ?.addEventListener('click', _saveSettings);

    // Delete data
    document.getElementById('btn-delete-data')?.addEventListener('click', async () => {
      if (!_userRef) return;
      const confirmed = window.confirm(
        'Delete all your sessions, scores, and feedback? This cannot be undone.',
      );
      if (!confirmed) return;
      const res = await _sendBg({ type: 'SAF_PANEL_DELETE_DATA', userRef: _userRef });
      if (res.ok) {
        _userRef = null;
        _currentChatId = null;
        _showView('onboarding-welcome');
      }
    });
  }

  // ── BOOTSTRAP ─────────────────────────────────────────────────────────────
  document.addEventListener('DOMContentLoaded', () => {
    _wire();
    init().catch(console.warn);
  });
})();
