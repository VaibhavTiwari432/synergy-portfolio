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
        SAF Analysis
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
      ${caveat ? `<div class="saf-caveat">${safe(caveat)}</div>` : ''}
      <button class="saf-analyse-btn" id="saf-m-analyse">Analyse again</button>
    `);
    document.getElementById('saf-m-analyse')?.addEventListener('click', triggerAnalyse);
  }

  function renderPending(msg) {
    renderBody(`
      <div class="saf-status-line">
        <span class="saf-spinner"></span>${msg || 'Analysing…'}
      </div>
      <div class="saf-caveat" style="text-align:center;padding-bottom:4px">
        This usually takes 15–30 seconds.
      </div>
    `);
  }

  function renderBlank() {
    renderBody(`
      <div class="saf-status-line">No analysis yet.</div>
      <button class="saf-analyse-btn" id="saf-m-analyse">Analyse now</button>
    `);
    document.getElementById('saf-m-analyse')?.addEventListener('click', triggerAnalyse);
  }

  function renderError(msg) {
    renderBody(`
      <div class="saf-status-line" style="color:#f04438">${safe(msg)}</div>
      <button class="saf-analyse-btn" id="saf-m-analyse">Try again</button>
    `);
    document.getElementById('saf-m-analyse')?.addEventListener('click', triggerAnalyse);
  }

  // ── trigger analysis ────────────────────────────────────────────────────────
  async function triggerAnalyse() {
    renderPending('Capturing conversation…');
    const res = await sendBg({ type: 'SAF_PANEL_ANALYSE_NOW' });
    if (!res?.ok) {
      renderError(res?.message || 'Nothing captured — have a conversation first');
      return;
    }
    renderPending('Sent for scoring…');
    // Poll for score
    let attempts = 0;
    const poll = setInterval(async () => {
      attempts++;
      if (attempts > 24) { // 2 min max
        clearInterval(poll);
        renderError('Scoring timed out — try again');
        return;
      }
      await refresh(true /* silent */);
      // If body no longer shows spinner, we're done
      if (!document.querySelector('#saf-m-body .saf-spinner')) clearInterval(poll);
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

      const { userRef, health, latestCapture, onboardingComplete } = statusRes.data;
      setHealth(health);

      if (health === 'error') {
        if (!silent) renderError('SAF server offline — run start_saf.ps1');
        return;
      }

      if (!onboardingComplete || !userRef) {
        if (!silent) renderBlank();
        return;
      }

      if (!latestCapture?.conversation_id) {
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
      const chat = chats.find((c) => c.conversation_id === latestCapture.conversation_id);

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
