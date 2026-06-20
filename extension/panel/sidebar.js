const PROJECTS_READY_MESSAGE = 'SAF_PROJECTS_API_READY';

export function initSidebar(shadowRoot) {
  const navItems = Array.from(shadowRoot.querySelectorAll('.saf-nav-item[data-view]'));
  const panels = Array.from(shadowRoot.querySelectorAll('[data-view-panel]'));
  const projectsNav = shadowRoot.querySelector('.saf-nav-item[data-view="projects"]');

  function panelFor(view) {
    return panels.find((panel) => panel.dataset.viewPanel === view);
  }

  function unlockProjectsNav() {
    if (!projectsNav) return;
    projectsNav.classList.remove('is-disabled');
    projectsNav.removeAttribute('aria-disabled');
    projectsNav.removeAttribute('title');
  }

  function setActiveView(view) {
    const targetPanel = panelFor(view);
    const targetNav = navItems.find((item) => item.dataset.view === view);
    if (!targetPanel || !targetNav || targetNav.getAttribute('aria-disabled') === 'true') return;

    navItems.forEach((item) => {
      const isActive = item === targetNav;
      item.classList.toggle('is-active', isActive);
      if (isActive) item.setAttribute('aria-current', 'page');
      else item.removeAttribute('aria-current');
    });

    panels.forEach((panel) => {
      const isActive = panel === targetPanel;
      panel.hidden = !isActive;
      panel.classList.toggle('is-active', isActive);
    });
  }

  function handleSidebarClick(event) {
    const target = event.target;
    if (!(target instanceof Element)) return;

    const navItem = target.closest('.saf-nav-item[data-view]');
    if (!navItem || !shadowRoot.contains(navItem)) return;
    if (navItem.getAttribute('aria-disabled') === 'true') return;

    setActiveView(navItem.dataset.view);
  }

  function handleRuntimeMessage(message) {
    if (message?.type === PROJECTS_READY_MESSAGE) {
      unlockProjectsNav();
    }
  }

  shadowRoot.addEventListener('click', handleSidebarClick);
  chrome.runtime.onMessage.addListener(handleRuntimeMessage);

  return () => {
    shadowRoot.removeEventListener('click', handleSidebarClick);
    chrome.runtime.onMessage.removeListener(handleRuntimeMessage);
  };
}
