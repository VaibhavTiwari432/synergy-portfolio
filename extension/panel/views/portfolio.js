const DIMENSIONS = ['AL', 'PR', 'EC', 'ES', 'CS', 'CD', 'AUI', 'CA'];
const SVG_NS = 'http://www.w3.org/2000/svg';
const RADAR_CENTER = 120;
const RADAR_RADIUS = 78;
const LABEL_RADIUS = 100;

export function initPortfolioView(shadowRoot) {
  const state = {
    loading: false,
    disposed: false,
  };

  const els = {
    status: shadowRoot.getElementById('saf-portfolio-status'),
    retry: shadowRoot.getElementById('saf-portfolio-retry'),
    history: shadowRoot.getElementById('saf-portfolio-history'),
    content: shadowRoot.getElementById('saf-portfolio-content'),
    sessions: shadowRoot.getElementById('saf-portfolio-sessions'),
    archetype: shadowRoot.getElementById('saf-portfolio-archetype'),
    archetypeDesc: shadowRoot.getElementById('saf-portfolio-archetype-desc'),
    radar: shadowRoot.getElementById('saf-portfolio-radar'),
    trajectory: shadowRoot.getElementById('saf-portfolio-trajectory'),
    growth: shadowRoot.getElementById('saf-portfolio-growth'),
    since: shadowRoot.getElementById('saf-portfolio-since'),
    rung: shadowRoot.getElementById('saf-portfolio-rung'),
  };

  function api() {
    return globalThis.SAFApiClient;
  }

  function storage() {
    return globalThis.SAFStorage;
  }

  function setStatus(message, isError = false) {
    if (!els.status) return;
    els.status.textContent = message;
    els.status.classList.toggle('is-error', isError);
  }

  function friendlyError(result, fallback = 'Could not load portfolio.') {
    const message = result?.message || result?.detail || result?.error;
    if (result?.status === 401 || /invalid or missing X-API-Key/i.test(String(message || ''))) {
      return 'API key is missing or invalid. Open Settings and save the API key for this backend.';
    }
    if (message === 'api_unreachable') {
      return 'SAF backend is not reachable. Start the backend or update the API endpoint in Settings.';
    }
    if (message === 'user_ref_required') {
      return 'Set your user ID in Settings before loading portfolio.';
    }
    return message || fallback;
  }

  function setVisible(node, visible) {
    if (node) node.hidden = !visible;
  }

  function clearRadar() {
    els.radar?.replaceChildren();
  }

  function numeric(value) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }

  function clampUnit(value) {
    if (value == null) return null;
    return Math.min(1, Math.max(0, value));
  }

  function presentRadarValues(profileRadar) {
    return DIMENSIONS
      .map((dim) => ({ dim, value: clampUnit(numeric(profileRadar?.[dim])) }))
      .filter((item) => item.value != null);
  }

  function pointFor(index, total, radius) {
    const angle = -Math.PI / 2 + (index / total) * Math.PI * 2;
    return {
      x: RADAR_CENTER + Math.cos(angle) * radius,
      y: RADAR_CENTER + Math.sin(angle) * radius,
    };
  }

  function createSvgElement(name, attributes = {}) {
    const node = document.createElementNS(SVG_NS, name);
    Object.entries(attributes).forEach(([key, value]) => {
      node.setAttribute(key, String(value));
    });
    return node;
  }

  function pointsAttribute(points) {
    return points.map((point) => `${point.x.toFixed(1)},${point.y.toFixed(1)}`).join(' ');
  }

  function renderRadar(values) {
    clearRadar();
    if (!els.radar || !values.length) return;

    const total = values.length;
    [0.33, 0.66, 1].forEach((scale) => {
      const ringPoints = values.map((_, index) => pointFor(index, total, RADAR_RADIUS * scale));
      els.radar.appendChild(createSvgElement('polygon', {
        class: 'saf-radar-grid',
        points: pointsAttribute(ringPoints),
      }));
    });

    values.forEach((item, index) => {
      const axisEnd = pointFor(index, total, RADAR_RADIUS);
      const labelPoint = pointFor(index, total, LABEL_RADIUS);
      els.radar.appendChild(createSvgElement('line', {
        class: 'saf-radar-axis',
        x1: RADAR_CENTER,
        y1: RADAR_CENTER,
        x2: axisEnd.x.toFixed(1),
        y2: axisEnd.y.toFixed(1),
      }));

      const label = createSvgElement('text', {
        class: 'saf-radar-label',
        x: labelPoint.x.toFixed(1),
        y: labelPoint.y.toFixed(1),
      });
      label.textContent = item.dim;
      els.radar.appendChild(label);
    });

    const shapePoints = values.map((item, index) => pointFor(index, total, RADAR_RADIUS * item.value));
    els.radar.appendChild(createSvgElement('polygon', {
      class: 'saf-radar-shape',
      points: pointsAttribute(shapePoints),
    }));

    shapePoints.forEach((point) => {
      els.radar.appendChild(createSvgElement('circle', {
        class: 'saf-radar-point',
        cx: point.x.toFixed(1),
        cy: point.y.toFixed(1),
        r: 3,
      }));
    });
  }

  function renderInsufficient() {
    setVisible(els.content, false);
    setVisible(els.history, true);
    clearRadar();
  }

  const TREND_LABEL = {
    improving: 'Improving',
    declining: 'Declining',
    stable: 'Stable',
    baseline: 'Baseline',
  };

  function formatSince(iso) {
    if (!iso) return '';
    const date = new Date(iso);
    if (Number.isNaN(date.getTime())) return '';
    return `Since ${date.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })}`;
  }

  // Surface the descriptive fields the route already returns (archetype blurb,
  // trajectory direction, growth focus, first-analysed, rung). Trajectory shows
  // the DIRECTION only — never a composite/overall number (#6).
  function renderDetail(data) {
    if (els.archetypeDesc) {
      const desc = data?.archetype_description || '';
      els.archetypeDesc.textContent = desc;
      els.archetypeDesc.hidden = !desc;
    }

    if (els.trajectory) {
      const traj = data?.trajectory;
      if (traj && typeof traj === 'object') {
        const label = TREND_LABEL[traj.trend_direction] || 'Baseline';
        const band = traj.uncertainty_band ? ` · uncertainty ${traj.uncertainty_band}` : '';
        els.trajectory.textContent = `${label}${band}`;
      } else {
        els.trajectory.textContent = 'Not enough sessions yet';
      }
    }

    if (els.growth) {
      const g = data?.growth_summary || {};
      const parts = [];
      if (g.strongest_dim) parts.push(`Strongest ${g.strongest_dim}`);
      if (g.growing_dim) parts.push(`Growing ${g.growing_dim}`);
      if (g.watch_dim) parts.push(`Watch ${g.watch_dim}`);
      els.growth.textContent = parts.length ? parts.join('  ·  ') : '—';
    }

    if (els.since) els.since.textContent = formatSince(data?.first_analysed_at);

    if (els.rung) {
      const rung = data?.rung;
      els.rung.textContent = rung || '';
      els.rung.title = 'Designed — portfolio aggregation is research-grade, not yet validated.';
      els.rung.hidden = !rung;
    }
  }

  function renderPortfolio(data) {
    const sessions = Number(data?.sessions_analysed || 0);
    const insufficient = data?.status === 'INSUFFICIENT_HISTORY' || sessions < 3;
    if (els.sessions) els.sessions.textContent = String(sessions);
    if (els.archetype) els.archetype.textContent = data?.archetype || 'Baseline';

    if (insufficient) {
      renderInsufficient();
      setStatus('');
      return;
    }

    const values = presentRadarValues(data?.profile_radar || {});
    setVisible(els.history, false);
    setVisible(els.content, true);
    renderRadar(values);
    renderDetail(data);
    setStatus(values.length ? '' : 'No profile dimensions available yet.');
  }

  async function acknowledgeIfNeeded(userRef, data) {
    if (data?.ack?.acked || !data?.snapshot_hash) return;
    const apiClient = api();
    if (!apiClient?.acknowledgePortfolio) return;
    const result = await apiClient.acknowledgePortfolio(userRef, data.snapshot_hash);
    if (result?.ok && data.ack) {
      data.ack.acked = true;
    }
  }

  async function loadPortfolio() {
    if (state.loading) return;
    const storageApi = storage();
    const apiClient = api();

    if (!storageApi || !apiClient?.getPortfolio) {
      setStatus('SAF API client is unavailable.', true);
      return;
    }

    state.loading = true;
    if (els.retry) els.retry.hidden = true;
    setVisible(els.content, false);
    setVisible(els.history, false);
    setStatus('Loading portfolio...');

    try {
      const userRef = await storageApi.get(storageApi.STORAGE_KEYS.USER_REF, '');
      if (state.disposed) return;
      if (!userRef) {
        setStatus('Save your connection settings before loading portfolio.', true);
        return;
      }

      const result = await apiClient.getPortfolio(userRef);
      if (state.disposed) return;
      if (!result?.ok) {
        throw new Error(friendlyError(result, 'Could not load portfolio.'));
      }

      const data = result.data || {};
      await acknowledgeIfNeeded(userRef, data);
      if (state.disposed) return;
      renderPortfolio(data);
    } catch (error) {
      if (els.retry) els.retry.hidden = false;
      setVisible(els.content, false);
      setVisible(els.history, false);
      setStatus(friendlyError(error, 'Could not load portfolio.'), true);
    } finally {
      state.loading = false;
    }
  }

  function handleRetry() {
    void loadPortfolio();
  }

  els.retry?.addEventListener('click', handleRetry);
  void loadPortfolio();

  return () => {
    state.disposed = true;
    els.retry?.removeEventListener('click', handleRetry);
  };
}
