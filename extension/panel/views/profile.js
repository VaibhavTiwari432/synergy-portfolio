export function initProfileView(shadowRoot) {
  const state = {
    loading: false,
    disposed: false,
  };

  const els = {
    status: shadowRoot.getElementById('saf-profile-status'),
    retry: shadowRoot.getElementById('saf-profile-retry'),
    content: shadowRoot.getElementById('saf-profile-content'),
    username: shadowRoot.getElementById('saf-profile-username'),
    joinDate: shadowRoot.getElementById('saf-profile-join-date'),
    scoredCount: shadowRoot.getElementById('saf-profile-scored-count'),
    streak: shadowRoot.getElementById('saf-profile-streak'),
    manage: shadowRoot.getElementById('saf-profile-manage'),
  };

  function api() {
    return globalThis.SAFApiClient;
  }

  function storage() {
    return globalThis.SAFStorage;
  }

  function setStatus(message = '', isError = false) {
    if (!els.status) return;
    els.status.textContent = message;
    els.status.classList.toggle('is-error', isError);
  }

  function setVisible(node, visible) {
    if (node) node.hidden = !visible;
  }

  function detailText(result, fallback) {
    return result?.detail || result?.error || fallback;
  }

  function dateFrom(value) {
    if (!value) return null;
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? null : date;
  }

  function formatDate(value) {
    const date = dateFrom(value);
    if (!date) return 'Not available';
    return date.toLocaleDateString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  }

  function localDayKey(date) {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
  }

  function addDays(date, offset) {
    const next = new Date(date);
    next.setDate(next.getDate() + offset);
    return next;
  }

  function currentStreak(chats) {
    const scoredDates = chats
      .filter((chat) => String(chat?.status || '').toLowerCase() === 'scored')
      .map((chat) => dateFrom(chat?.captured_at))
      .filter(Boolean);
    if (!scoredDates.length) return 0;

    const days = new Set(scoredDates.map(localDayKey));
    const latest = scoredDates.reduce((max, date) => (date > max ? date : max), scoredDates[0]);
    let count = 0;
    let cursor = latest;
    while (days.has(localDayKey(cursor))) {
      count += 1;
      cursor = addDays(cursor, -1);
    }
    return count;
  }

  function renderProfile(userRef, data) {
    const chats = Array.isArray(data?.chats) ? data.chats : [];
    const capturedDates = chats
      .map((chat) => dateFrom(chat?.captured_at))
      .filter(Boolean);
    const firstCapture = capturedDates.length
      ? capturedDates.reduce((min, date) => (date < min ? date : min), capturedDates[0])
      : null;
    const scored = Number(data?.summary?.scored || 0);
    const streak = currentStreak(chats);

    if (els.username) els.username.textContent = userRef || 'Not set';
    if (els.joinDate) els.joinDate.textContent = firstCapture ? formatDate(firstCapture) : 'Not available';
    if (els.scoredCount) els.scoredCount.textContent = String(scored);
    if (els.streak) els.streak.textContent = `${streak} ${streak === 1 ? 'day' : 'days'}`;
    setVisible(els.content, true);
  }

  async function loadProfile() {
    if (state.loading) return;
    const storageApi = storage();
    const apiClient = api();

    if (!storageApi || !apiClient?.getChatList) {
      setStatus('SAF API client is unavailable.', true);
      return;
    }

    state.loading = true;
    if (els.retry) els.retry.hidden = true;
    setVisible(els.content, false);
    setStatus('Loading profile...');

    try {
      const userRef = await storageApi.get(storageApi.STORAGE_KEYS.USER_REF, '');
      if (state.disposed) return;
      if (!userRef) {
        renderProfile('', { chats: [], summary: { scored: 0 } });
        setStatus('Set your user ID in Settings first.', true);
        return;
      }

      const result = await apiClient.getChatList(userRef);
      if (state.disposed) return;
      if (!result?.ok) {
        throw new Error(detailText(result, 'Could not load profile.'));
      }

      renderProfile(userRef, result.data || {});
      setStatus('');
    } catch (error) {
      if (els.retry) els.retry.hidden = false;
      setVisible(els.content, false);
      setStatus(error.message || 'Could not load profile.', true);
    } finally {
      state.loading = false;
    }
  }

  function handleRetry() {
    void loadProfile();
  }

  function handleManageClick(event) {
    // TODO: replace # with web-app account URL when live.
    event.preventDefault();
  }

  els.retry?.addEventListener('click', handleRetry);
  els.manage?.addEventListener('click', handleManageClick);

  void loadProfile();

  return () => {
    state.disposed = true;
    els.retry?.removeEventListener('click', handleRetry);
    els.manage?.removeEventListener('click', handleManageClick);
  };
}
