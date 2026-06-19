'use strict';

/**
 * injected_icon.js — floating SAF button + inline mini-panel on ChatGPT page.
 * OWNER: Chief Engineer.
 *
 * Injects a circular logo button (bottom-right). Clicking it toggles a
 * compact score window that shows health, tier, Section 1 (strengths) and
 * Section 2 (growth) without opening the browser popup.
 *
 * Non-negotiables enforced here:
 *  #4  "synergy" never in output
 *  #5  "surrender" never in output
 *  #14 every claim carries exactly one rung
 */

(function initInjectedIcon() {
  const SAF_BUILD = '0.2.0';
  console.info(`[SAF] injected_icon build ${SAF_BUILD} loaded in this tab`);
  if (document.getElementById('saf-fab')) return; // no double-inject

  // ── forbidden-word guard (mirrors panel.js) ─────────────────────────────────
  const FORBIDDEN = ['synergy', 'surrender', 'dependent', 'decline'];
  function safe(text) {
    if (!text) return '';
    let s = String(text);
    FORBIDDEN.forEach((w) => { s = s.replace(new RegExp(w, 'gi'), '···'); });
    return s;
  }

  // ── chrome message bridge ───────────────────────────────────────────────────
  function sendBg(msg) {
    return new Promise((resolve) => {
      chrome.runtime.sendMessage(msg, (res) => {
        void chrome.runtime.lastError;
        resolve(res || { ok: false, error: 'no_response' });
      });
    });
  }

  // ── styles ──────────────────────────────────────────────────────────────────
  const style = document.createElement('style');
  style.textContent = `
    #saf-fab {
      position: fixed;
      bottom: 80px;
      right: 20px;
      z-index: 2147483640;
      width: 52px;
      height: 52px;
      border-radius: 50%;
      border: none;
      background: #fff;
      box-shadow: 0 2px 10px rgba(0,0,0,0.22);
      cursor: pointer;
      padding: 0;
      display: flex;
      align-items: center;
      justify-content: center;
      transition: box-shadow .15s, transform .12s;
    }
    #saf-fab:hover { box-shadow: 0 4px 18px rgba(0,0,0,0.28); transform: scale(1.07); }
    #saf-fab:active { transform: scale(0.95); }
    #saf-fab img { width: 38px; height: 38px; border-radius: 50%; object-fit: cover; }
    #saf-fab .saf-fallback {
      font-size: 13px; font-weight: 700; color: #1a6fa0;
      font-family: system-ui, sans-serif; pointer-events: none;
    }

    /* mini window */
    #saf-mini {
      position: fixed;
      bottom: 142px;
      right: 20px;
      z-index: 2147483641;
      width: 300px;
      background: #fff;
      border-radius: 14px;
      box-shadow: 0 8px 32px rgba(0,0,0,0.18);
      font-family: system-ui, -apple-system, sans-serif;
      font-size: 13px;
      color: #1a1a2e;
      overflow: hidden;
      display: none;
    }
    #saf-mini.open { display: block; }

    .saf-mini-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 10px 14px 8px;
      background: #f0f4fb;
      border-bottom: 1px solid #e4e7ec;
    }
    .saf-mini-title {
      font-weight: 700;
      font-size: 13px;
      color: #1a1a2e;
      display: flex;
      align-items: center;
      gap: 7px;
    }
    .saf-hdot {
      width: 9px; height: 9px; border-radius: 50%; background: #98a2b3;
    }
    .saf-hdot[data-h="ok"]    { background: #12b76a; }
    .saf-hdot[data-h="error"] { background: #f04438; }
    .saf-mini-close {
      background: none; border: none; cursor: pointer;
      color: #667085; font-size: 18px; line-height: 1; padding: 0 2px;
    }
    .saf-mini-close:hover { color: #1a1a2e; }

    .saf-mini-body { padding: 12px 14px; }

    .saf-tier-badge {
      display: inline-block;
      font-size: 11px;
      font-weight: 600;
      color: #1a6fa0;
      background: #e8f0fb;
      border-radius: 20px;
      padding: 2px 10px;
      margin-bottom: 10px;
    }

    .saf-section-label {
      font-size: 11px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: .05em;
      color: #667085;
      margin: 8px 0 4px;
    }
    .saf-section-1 { background: #f0f9f4; border-radius: 8px; padding: 8px 10px; margin-bottom: 6px; }
    .saf-section-2 { background: #f0f4fb; border-radius: 8px; padding: 8px 10px; }
    .saf-item { font-size: 12px; color: #1a1a2e; line-height: 1.5; margin-bottom: 3px; }
    .saf-item:last-child { margin-bottom: 0; }

    .saf-caveat {
      font-size: 10px; color: #98a2b3; margin-top: 8px; line-height: 1.4;
    }

    .saf-analyse-btn {
      display: block;
      width: 100%;
      margin-top: 10px;
      padding: 8px 0;
      background: #1a6fa0;
      color: #fff;
      border: none;
      border-radius: 8px;
      font-size: 13px;
      font-weight: 600;
      cursor: pointer;
      transition: background .12s;
    }
    .saf-analyse-btn:hover { background: #145d8a; }
    .saf-analyse-btn:disabled { background: #98a2b3; cursor: default; }

    .saf-mini-actions {
      display: flex;
      gap: 6px;
      margin-top: 10px;
    }
    .saf-mini-actions .saf-analyse-btn {
      margin-top: 0;
      flex: 1;
      padding: 7px 0;
      font-size: 12px;
    }
    .saf-mini-secondary {
      background: #fff;
      color: #344054;
      border: 1px solid #d0d5dd;
    }
    .saf-mini-secondary:hover { background: #f7f8fa; }

    .saf-progress-track {
      height: 6px;
      background: #e4e7ec;
      border-radius: 999px;
      overflow: hidden;
      margin: 10px 0 8px;
    }
    .saf-progress-fill {
      height: 100%;
      width: 0%;
      background: #1a6fa0;
      border-radius: 999px;
      transition: width .25s ease;
    }
    .saf-progress-meta {
      font-size: 11px;
      color: #667085;
      line-height: 1.4;
      text-align: center;
    }

    .saf-radar-mini {
      width: 130px;
      height: 130px;
      display: block;
      margin: 4px auto 8px;
      overflow: visible;
    }
    .saf-radar-mini .ring, .saf-radar-mini .axis {
      stroke: #d0d5dd;
      stroke-width: .012;
      fill: none;
    }
    .saf-radar-mini .poly {
      fill: rgba(26,111,160,.18);
      stroke: #1a6fa0;
      stroke-width: .035;
    }
    .saf-radar-mini .dot {
      fill: #1a6fa0;
      stroke: #fff;
      stroke-width: .015;
    }

    .saf-status-line {
      font-size: 12px; color: #667085; text-align: center;
      padding: 12px 0 4px;
    }
    .saf-spinner {
      display: inline-block;
      width: 14px; height: 14px;
      border: 2px solid #e4e7ec;
      border-top-color: #1a6fa0;
      border-radius: 50%;
      animation: saf-spin .7s linear infinite;
      vertical-align: middle;
      margin-right: 5px;
    }
    @keyframes saf-spin { to { transform: rotate(360deg); } }

    #saf-fab {
      border: 1px solid rgba(23,107,145,.16);
      box-shadow: 0 10px 26px rgba(15,23,42,.22);
    }
    #saf-fab:hover {
      box-shadow: 0 14px 34px rgba(15,23,42,.28);
      transform: translateY(-1px) scale(1.04);
    }
    #saf-fab:focus-visible,
    .saf-mini-close:focus-visible,
    .saf-analyse-btn:focus-visible {
      outline: 2px solid #176b91;
      outline-offset: 3px;
    }

    #saf-mini {
      width: 320px;
      color: #111827;
      border: 1px solid rgba(198,210,223,.9);
      border-radius: 8px;
      box-shadow: 0 18px 42px rgba(15,23,42,.22);
    }

    .saf-mini-header {
      padding: 12px 14px;
      background: #f7f9fc;
    }

    .saf-mini-title {
      color: #111827;
      letter-spacing: 0;
    }

    .saf-hdot {
      box-shadow: 0 0 0 3px rgba(100,116,139,.12);
    }
    .saf-hdot[data-h="ok"] {
      box-shadow: 0 0 0 3px rgba(18,183,106,.14);
    }
    .saf-hdot[data-h="error"] {
      box-shadow: 0 0 0 3px rgba(240,68,56,.14);
    }

    .saf-mini-close {
      width: 28px;
      height: 28px;
      border-radius: 7px;
    }
    .saf-mini-close:hover {
      background: #eef4f8;
    }

    .saf-mini-body {
      padding: 14px;
      background: #fff;
    }

    .saf-tier-badge {
      color: #2f465e;
      background: #f8fafc;
      border: 1px solid #d9e2ec;
      border-radius: 999px;
      margin-bottom: 12px;
    }

    .saf-section-1,
    .saf-section-2 {
      border: 1px solid #d9e2ec;
      border-radius: 8px;
      margin-bottom: 8px;
    }
    .saf-section-1 {
      background: linear-gradient(180deg,#f4fbf6 0%,#fff 100%);
      border-color: #cbe9d5;
    }
    .saf-section-2 {
      background: linear-gradient(180deg,#f1f6fb 0%,#fff 100%);
      border-color: #cbdceb;
    }

    .saf-section-label {
      color: #53677d;
      margin-top: 0;
      margin-bottom: 7px;
    }

    .saf-item {
      color: #111827;
    }

    .saf-analyse-btn {
      min-height: 34px;
      background: #176b91;
      border-radius: 7px;
      box-shadow: 0 1px 2px rgba(17,87,119,.24);
    }
    .saf-analyse-btn:hover {
      background: #115777;
    }
    .saf-mini-secondary {
      background: #fff;
      box-shadow: none;
      color: #27364a;
      border-color: #c6d2df;
    }
    .saf-mini-secondary:hover {
      background: #eef4f8;
    }

    .saf-progress-track {
      height: 8px;
      background: #e5ebf1;
    }
    .saf-progress-fill {
      background: linear-gradient(90deg,#176b91,#2f8f8a);
    }

    .saf-radar-mini {
      width: 140px;
      height: 140px;
      margin-top: 8px;
    }
    .saf-radar-mini .poly {
      fill: rgba(23,107,145,.16);
      stroke: #176b91;
    }
    .saf-radar-mini .dot {
      fill: #176b91;
    }
  `;
  document.head.appendChild(style);

  // ── FAB button ──────────────────────────────────────────────────────────────
  const fab = document.createElement('button');
  fab.id = 'saf-fab';
  fab.title = 'SAF — Analyse collaboration';
  fab.setAttribute('aria-label', 'SAF — Analyse collaboration');

  const img = document.createElement('img');
  img.src = chrome.runtime.getURL('icons/icon.png');
  img.alt = 'SAF';
  img.onerror = () => {
    img.remove();
    const span = document.createElement('span');
    span.className = 'saf-fallback';
    span.textContent = 'SAF';
    fab.appendChild(span);
  };
  fab.appendChild(img);
  document.body.appendChild(fab);

  // ── mini window ─────────────────────────────────────────────────────────────
  const mini = document.createElement('div');
  mini.id = 'saf-mini';
  mini.setAttribute('role', 'dialog');
  mini.setAttribute('aria-label', 'SAF analysis panel');
  mini.innerHTML = `
    <div class="saf-mini-header">
      <div class="saf-mini-title">
        <span class="saf-hdot" id="saf-m-hdot"></span>
        SAF Analysis <span style="font-weight:400;color:#98a2b3;font-size:11px">v${SAF_BUILD}</span>
      </div>
      <button class="saf-mini-close" id="saf-m-close" aria-label="Close">×</button>
    </div>
    <div class="saf-mini-body" id="saf-m-body">
      <div class="saf-status-line">Loading…</div>
    </div>
  `;
  document.body.appendChild(mini);

  // ── toggle ──────────────────────────────────────────────────────────────────
  let isOpen = false;
  let miniPollTimer = null;
  function openMini() { mini.classList.add('open'); isOpen = true; refresh(); }
  function closeMini() { mini.classList.remove('open'); isOpen = false; }

  fab.addEventListener('click', () => isOpen ? closeMini() : openMini());
  document.getElementById('saf-m-close').addEventListener('click', closeMini);

  // ── render helpers ──────────────────────────────────────────────────────────
  function setHealth(h) {
    const dot = document.getElementById('saf-m-hdot');
    if (dot) dot.dataset.h = h || 'unknown';
  }

  function renderBody(html) {
    document.getElementById('saf-m-body').innerHTML = html;
  }

  const DIM_ORDER = ['AL', 'PR', 'EC', 'ES', 'CS', 'CD', 'AUI', 'CA'];

  function normaliseProfile(profile) {
    let source = profile;
    if (typeof source === 'string') {
      try { source = JSON.parse(source); } catch { source = {}; }
    }
    if (!source || typeof source !== 'object' || Array.isArray(source)) source = {};
    const out = {};
    for (const key of DIM_ORDER) {
      const raw = source[key] || source[key.toLowerCase()] || {};
      const value = Number(raw.value);
      out[key] = {
        status: String(raw.status || '').toUpperCase(),
        value: Number.isFinite(value) ? Math.max(0, Math.min(1, value)) : null,
      };
    }
    return out;
  }

  function radarSvg(profile) {
    const p = normaliseProfile(profile);
    const r = 0.68;
    const axes = DIM_ORDER.map((key, i) => {
      const angle = (2 * Math.PI * i / DIM_ORDER.length) - Math.PI / 2;
      const x = r * Math.cos(angle);
      const y = r * Math.sin(angle);
      return `<line class="axis" x1="0" y1="0" x2="${x.toFixed(4)}" y2="${y.toFixed(4)}"></line>`;
    }).join('');
    const points = DIM_ORDER.map((key, i) => {
      const angle = (2 * Math.PI * i / DIM_ORDER.length) - Math.PI / 2;
      const d = p[key];
      const value = d?.status === 'OK' && d.value != null ? d.value : 0;
      return `${(r * value * Math.cos(angle)).toFixed(4)},${(r * value * Math.sin(angle)).toFixed(4)}`;
    }).join(' ');
    const dots = points.split(' ').map((point) => {
      const [x, y] = point.split(',');
      return `<circle class="dot" cx="${x}" cy="${y}" r="0.035"></circle>`;
    }).join('');
    return `
      <svg class="saf-radar-mini" viewBox="-1 -1 2 2" aria-label="Expected radar">
        <circle class="ring" cx="0" cy="0" r="${(r * 0.33).toFixed(4)}"></circle>
        <circle class="ring" cx="0" cy="0" r="${(r * 0.66).toFixed(4)}"></circle>
        <circle class="ring" cx="0" cy="0" r="${r}"></circle>
        ${axes}
        <polygon class="poly" points="${points}"></polygon>
        ${dots}
      </svg>
    `;
  }

  function actionButtons(primaryLabel = 'Analyse', includePortfolio = true) {
    return `
      <div class="saf-mini-actions">
        <button class="saf-analyse-btn" id="saf-m-analyse">${primaryLabel}</button>
        ${includePortfolio ? '<button class="saf-analyse-btn saf-mini-secondary" id="saf-m-portfolio">Portfolio</button>' : ''}
        <button class="saf-analyse-btn saf-mini-secondary" id="saf-m-settings">Settings</button>
      </div>
    `;
  }

  function wireMiniNav() {
    document.getElementById('saf-m-analyse')?.addEventListener('click', triggerAnalyse);
    document.getElementById('saf-m-portfolio')?.addEventListener('click', renderPortfolio);
    document.getElementById('saf-m-settings')?.addEventListener('click', renderSettingsHint);
  }

  function renderScore(data) {
    const tier  = data.tier || 1;
    const rung  = safe((data.report?.rung || 'measurable').toLowerCase());
    const obs   = (data.report?.observed || []).slice(0, 3);
    const inf   = (data.report?.inferred || []).slice(0, 2);
    const caveat = data.report?.tier_caveat || '';

    const s1items = obs.length
      ? obs.map((t) => `<div class="saf-item">• ${safe(t)}</div>`).join('')
      : '<div class="saf-item" style="color:#98a2b3">More data needed.</div>';

    const s2items = inf.length
      ? inf.map((t) => `<div class="saf-item">• ${safe(t)}</div>`).join('')
      : '<div class="saf-item" style="color:#98a2b3">Insufficient data.</div>';

    renderBody(`
      <div class="saf-tier-badge">Tier ${tier} · ${rung}</div>
      <div class="saf-section-1">
        <div class="saf-section-label">Strengths observed</div>
        ${s1items}
      </div>
      <div class="saf-section-2">
        <div class="saf-section-label">Growth area</div>
        ${s2items}
      </div>
      ${radarSvg(data.profile)}
      ${caveat ? `<div class="saf-caveat">${safe(caveat)}</div>` : ''}
      ${actionButtons('Analyse again')}
    `);
    wireMiniNav();
  }

  function renderPending(msg) {
    renderProgress({ stage: 'analysing', percent: 50, message: msg || 'Analysing...' });
  }

  function renderProgress(progress) {
    const pct = Math.max(0, Math.min(100, Math.round(Number(progress?.percent ?? 0))));
    const turns = Number(progress?.capturedTurns || 0);
    const stage = safe(String(progress?.stage || 'analysing').replace(/_/g, ' '));
    const msg = safe(progress?.message || 'Working on this chat...');
    renderBody(`
      <div class="saf-status-line">
        <span class="saf-spinner"></span>${stage.charAt(0).toUpperCase() + stage.slice(1)}
      </div>
      <div class="saf-progress-track" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${pct}">
        <div class="saf-progress-fill" style="width:${pct}%"></div>
      </div>
      <div class="saf-progress-meta">
        ${msg}<br>
        ${turns > 0 ? `Chat captured: ${turns} turn${turns === 1 ? '' : 's'} (${pct}%).` : `${pct}%.`}
      </div>
    `);
  }

  function renderBlank() {
    renderBody(`
      <div class="saf-status-line">Ready to analyse this chat.</div>
      ${radarSvg({})}
      <div class="saf-caveat" style="text-align:center">Radar appears after analysis.</div>
      ${actionButtons('Analyse')}
    `);
    wireMiniNav();
  }

  function renderError(msg) {
    renderBody(`
      <div class="saf-status-line" style="color:#f04438">${safe(msg)}</div>
      ${actionButtons('Try again')}
    `);
    wireMiniNav();
  }

  // ── trigger analysis ────────────────────────────────────────────────────────
  async function renderPortfolio() {
    const statusRes = await sendBg({ type: 'SAF_PANEL_GET_STATUS' });
    const userRef = statusRes?.data?.userRef;
    if (!userRef) {
      renderError('Set your user ID in Settings first.');
      return;
    }
    renderProgress({ stage: 'portfolio', percent: 30, message: 'Loading portfolio...' });
    const res = await sendBg({ type: 'SAF_PANEL_GET_PORTFOLIO', userRef });
    if (!res?.ok || !res.data || res.data.status === 'INSUFFICIENT_HISTORY') {
      renderBody(`
        <div class="saf-status-line">More sessions needed for portfolio.</div>
        ${actionButtons('Analyse')}
      `);
      wireMiniNav();
      return;
    }
    const d = res.data;
    const summary = d.growth_summary || {};
    const radarProfile = Object.fromEntries(DIM_ORDER.map((k) => [
      k,
      { status: d.profile_radar?.[k] == null ? 'NA' : 'OK', value: d.profile_radar?.[k] },
    ]));
    renderBody(`
      <div class="saf-tier-badge">Portfolio</div>
      ${radarSvg(radarProfile)}
      <div class="saf-section-1">
        <div class="saf-section-label">Strength</div>
        <div class="saf-item">${safe(summary.strongest_dim || 'More history needed')}</div>
      </div>
      <div class="saf-section-2">
        <div class="saf-section-label">Focus</div>
        <div class="saf-item">${safe(summary.watch_dim || 'More history needed')}</div>
      </div>
      ${actionButtons('Analyse')}
    `);
    wireMiniNav();
  }

  function renderSettingsHint() {
    renderBody(`
      <div class="saf-status-line">Settings live in the extension popup.</div>
      <div class="saf-caveat" style="text-align:center">
        Open the toolbar extension icon to edit endpoint, user ID, API key, and consent.
      </div>
      ${actionButtons('Analyse')}
    `);
    wireMiniNav();
  }

  function startMiniProgressPoll() {
    if (miniPollTimer) clearInterval(miniPollTimer);
    miniPollTimer = setInterval(async () => {
      const statusRes = await sendBg({ type: 'SAF_PANEL_GET_STATUS' });
      const progress = statusRes?.data?.analysisProgress;
      if (progress?.active !== false && progress?.stage && progress.stage !== 'complete') {
        renderProgress(progress);
      }
    }, 700);
  }

  function stopMiniProgressPoll() {
    if (miniPollTimer) clearInterval(miniPollTimer);
    miniPollTimer = null;
  }

  async function triggerAnalyse() {
    renderProgress({ stage: 'capturing', percent: 1, message: 'Starting capture...' });
    startMiniProgressPoll();
    const res = await sendBg({ type: 'SAF_PANEL_ANALYSE_NOW' });
    if (!res?.ok) {
      stopMiniProgressPoll();
      renderError(res?.message || 'Nothing captured — have a conversation first');
      return;
    }
    renderProgress({ stage: 'scoring', percent: 90, message: 'Sent for scoring...' });
    // Poll for score
    let attempts = 0;
    const poll = setInterval(async () => {
      attempts++;
      if (attempts > 48) { // 4 min max
        clearInterval(poll);
        stopMiniProgressPoll();
        // The score is computed server-side and persists — it is not lost. Reopening
        // the widget runs refresh() and shows it once the worker finishes.
        renderError('Still scoring — reopen in a moment to see the result.');
        return;
      }
      await refresh(true /* silent */);
      // If body no longer shows spinner, we're done
      if (!document.querySelector('#saf-m-body .saf-spinner')) {
        clearInterval(poll);
        stopMiniProgressPoll();
      }
    }, 5000);
  }

  // ── refresh mini window from background ─────────────────────────────────────
  let _refreshing = false;
  async function refresh(silent = false) {
    if (_refreshing) return;
    _refreshing = true;
    try {
      const statusRes = await sendBg({ type: 'SAF_PANEL_GET_STATUS' });
      if (!statusRes.ok) {
        setHealth('error');
        if (!silent) renderError('Extension not responding — reload page');
        return;
      }

      const { userRef, health, latestCapture, onboardingComplete, analysisProgress } = statusRes.data;
      setHealth(health);

      if (health === 'error') {
        if (!silent) renderError('SAF server offline — run start_saf.ps1');
        return;
      }

      if (!onboardingComplete || !userRef) {
        if (!silent) renderBlank();
        return;
      }

      // Show live progress for the CAPTURE/ingest phase only. The 'scoring' stage
      // means the chat is ingested and the async worker is scoring it — nothing
      // updates this flag when the worker finishes, so we must NOT short-circuit on
      // it. Fall through to the live chat-status check below, which detects the
      // score the moment it lands (and otherwise renders a pending spinner).
      if (
        analysisProgress?.active &&
        analysisProgress.stage !== 'error' &&
        analysisProgress.stage !== 'complete' &&
        analysisProgress.stage !== 'scoring'
      ) {
        renderProgress(analysisProgress);
        return;
      }

      if (analysisProgress?.stage === 'error') {
        if (!silent) renderError(analysisProgress.message || 'Capture failed');
        return;
      }

      // Resolve the chat to display. Prefer the id the chat was actually INGESTED
      // under (carried on analysisProgress) over the page's current conversation
      // id: a chat captured before its URL settled is stored under a draft id, and
      // matching latestCapture (which may have since changed) would miss the score.
      const targetChatId = analysisProgress?.chatId || null;
      const targetConvId =
        analysisProgress?.conversationId || latestCapture?.conversation_id || null;
      if (!targetChatId && !targetConvId) {
        if (!silent) renderBlank();
        return;
      }

      // Check if this conversation is scored
      const chatsRes = await sendBg({ type: 'SAF_PANEL_LIST_CHATS', userRef });
      if (!chatsRes.ok) {
        if (!silent) renderError('Could not load chats');
        return;
      }

      const chats = chatsRes.data?.chats || [];
      const chat = chats.find(
        (c) =>
          (targetChatId && c.chat_id === targetChatId) ||
          c.conversation_id === targetConvId,
      );

      if (!chat) {
        if (!silent) renderBlank();
        return;
      }

      if (chat.status === 'scored') {
        const scoreRes = await sendBg({
          type: 'SAF_PANEL_GET_SCORE',
          userRef,
          chatId: chat.chat_id,
        });
        if (scoreRes.ok && scoreRes.data) {
          renderScore(scoreRes.data);
        } else {
          if (!silent) renderError('Score unavailable');
        }
      } else if (chat.status === 'failed') {
        if (!silent) renderError('Scoring failed — try again');
      } else {
        renderPending('Score in progress…');
      }
    } finally {
      _refreshing = false;
    }
  }
})();
