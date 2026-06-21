'use strict';

/**
 * injected_icon.js - SAF FAB, modal host, and overlay lifecycle only.
 * OWNER: Codex.
 */

(function initSafModalShell() {
  const SAF_BUILD = '0.5.1-toolbar-open';
  const FAB_ID = 'saf-fab';
  const HOST_ID = 'saf-modal-host';
  const ROOT_STYLESHEET_ID = 'saf-panel-stylesheet';
  const PANEL_CSS_PATH = 'panel/panel.css';
  const PANEL_HTML_PATH = 'panel/panel.html';
  const CLOSE_TRANSITION_MS = 240;

  let modalHost = null;
  let modalShadow = null;
  let modalOverlay = null;
  let isOpen = false;
  let isOpening = false;
  let closeTimer = null;
  let sidebarCleanup = null;

  console.info(`[SAF] injected_icon build ${SAF_BUILD} loaded`);

  function extensionUrl(path) {
    return chrome.runtime.getURL(path);
  }

  function logoUrl() {
    return chrome.runtime.getURL('icons/icon.png');
  }

  function setLogoSources(root) {
    root.querySelectorAll('img[data-saf-logo]').forEach((logo) => {
      logo.src = logoUrl();
    });
  }

  function installRootStylesheet() {
    if (document.getElementById(ROOT_STYLESHEET_ID)) return;
    const link = document.createElement('link');
    link.id = ROOT_STYLESHEET_ID;
    link.rel = 'stylesheet';
    link.href = extensionUrl(PANEL_CSS_PATH);
    document.head.appendChild(link);
  }

  function setFabExpanded(expanded) {
    const fab = document.getElementById(FAB_ID);
    if (!fab) return;
    fab.setAttribute('aria-expanded', expanded ? 'true' : 'false');
  }

  function setFabNotification(visible) {
    const fab = document.getElementById(FAB_ID);
    if (!fab) return;
    fab.dataset.hasWork = visible ? 'true' : 'false';
  }

  function installFab() {
    const existing = document.getElementById(FAB_ID);
    if (existing) existing.remove();

    const fab = document.createElement('button');
    fab.id = FAB_ID;
    fab.type = 'button';
    fab.setAttribute('aria-label', 'Open SAF');
    fab.setAttribute('aria-expanded', 'false');
    fab.dataset.hasWork = 'false';

    const logo = document.createElement('img');
    logo.className = 'saf-fab-logo';
    logo.alt = '';
    logo.setAttribute('aria-hidden', 'true');
    logo.dataset.safLogo = 'true';
    fab.appendChild(logo);

    const dot = document.createElement('span');
    dot.className = 'saf-fab-dot';
    dot.setAttribute('aria-hidden', 'true');
    fab.appendChild(dot);

    fab.addEventListener('click', () => {
      if (isOpen || isOpening) closeModal();
      else void openModal();
    });

    document.body.appendChild(fab);
    setLogoSources(fab);
  }

  async function loadModalFragment() {
    const response = await fetch(extensionUrl(PANEL_HTML_PATH));
    if (!response.ok) {
      throw new Error(`Unable to load modal shell: ${response.status}`);
    }

    const source = await response.text();
    const parsed = new DOMParser().parseFromString(source, 'text/html');
    const template = parsed.getElementById('saf-modal-template');
    if (!(template instanceof HTMLTemplateElement)) {
      throw new Error('Modal shell template missing from panel.html');
    }

    return document.importNode(template.content, true);
  }

  function bindModalEvents() {
    const closeButton = modalShadow.getElementById('saf-modal-close');
    const modal = modalShadow.getElementById('saf-modal');
    modalOverlay = modalShadow.getElementById('saf-modal-overlay');

    modalOverlay.addEventListener('mousedown', (event) => {
      if (event.target === modalOverlay) closeModal();
    });

    closeButton?.addEventListener('click', closeModal);
    modal?.focus({ preventScroll: true });
  }

  async function openModal() {
    if (isOpen || isOpening) return;
    isOpening = true;

    try {
      closeTimer = null;
      modalHost = document.createElement('div');
      modalHost.id = HOST_ID;
      document.body.appendChild(modalHost);

      modalShadow = modalHost.attachShadow({ mode: 'closed' });

      const stylesheet = document.createElement('link');
      stylesheet.rel = 'stylesheet';
      stylesheet.href = extensionUrl(PANEL_CSS_PATH);
      modalShadow.appendChild(stylesheet);
      modalShadow.appendChild(await loadModalFragment());
      setLogoSources(modalShadow);
      const { initSidebar } = await import(chrome.runtime.getURL('panel/sidebar.js'));
      sidebarCleanup = initSidebar(modalShadow);

      bindModalEvents();
      document.addEventListener('keydown', handleKeydown);
      setFabExpanded(true);
      isOpen = true;

      requestAnimationFrame(() => {
        modalOverlay?.classList.add('saf-open');
      });
    } catch (error) {
      console.error('[SAF] Failed to open modal shell', error);
      teardownModal();
    } finally {
      isOpening = false;
    }
  }

  function closeModal() {
    if (!isOpen && !isOpening) return;
    isOpening = false;
    isOpen = false;
    setFabExpanded(false);
    document.removeEventListener('keydown', handleKeydown);

    if (!modalOverlay) {
      teardownModal();
      return;
    }

    modalOverlay.classList.remove('saf-open');
    modalOverlay.addEventListener('transitionend', handleCloseTransitionEnd, { once: true });
    closeTimer = window.setTimeout(teardownModal, CLOSE_TRANSITION_MS);
  }

  function handleCloseTransitionEnd(event) {
    if (event.target === modalOverlay) teardownModal();
  }

  function handleKeydown(event) {
    if (event.key === 'Escape') closeModal();
  }

  function handleRuntimeMessage(message) {
    if (message?.type === 'SAF_FAB_NOTIFICATION_DOT') {
      setFabNotification(Boolean(message.visible));
    } else if (message?.type === 'SAF_OPEN_MODAL') {
      // toolbar icon click relayed from background — toggle the modal open.
      if (isOpen || isOpening) closeModal();
      else void openModal();
    }
  }

  function teardownModal() {
    if (closeTimer) {
      window.clearTimeout(closeTimer);
      closeTimer = null;
    }

    sidebarCleanup?.();
    sidebarCleanup = null;
    modalHost?.remove();
    modalHost = null;
    modalShadow = null;
    modalOverlay = null;
    setFabExpanded(false);
  }

  installRootStylesheet();
  installFab();
  chrome.runtime.onMessage.addListener(handleRuntimeMessage);
})();
