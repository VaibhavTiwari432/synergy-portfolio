const SHOW_NOTIFICATION_DOT_KEY = 'saf_show_notification_dot';

export function initSettingsView(shadowRoot) {
  const state = {
    userRef: '',
    settings: {
      auto_analyse: false,
      calibration_opt_in: false,
    },
    notificationDot: true,
    loading: false,
    saving: false,
    deleting: false,
    disposed: false,
  };

  const els = {
    status: shadowRoot.getElementById('saf-settings-status'),
    retry: shadowRoot.getElementById('saf-settings-retry'),
    autoAnalyse: shadowRoot.getElementById('saf-setting-auto-analyse'),
    notificationDot: shadowRoot.getElementById('saf-setting-notification-dot'),
    calibrationOptIn: shadowRoot.getElementById('saf-setting-calibration-opt-in'),
    deleteData: shadowRoot.getElementById('saf-settings-delete-data'),
  };

  function api() {
    return globalThis.SAFApiClient;
  }

  function storage() {
    return globalThis.SAFStorage;
  }

  function detailText(result, fallback) {
    return result?.detail || result?.error || fallback;
  }

  function setStatus(message = '', isError = false) {
    if (!els.status) return;
    els.status.textContent = message;
    els.status.classList.toggle('is-error', isError);
  }

  function setRemoteDisabled(disabled) {
    if (els.autoAnalyse) els.autoAnalyse.disabled = disabled;
    if (els.calibrationOptIn) els.calibrationOptIn.disabled = disabled;
    if (els.deleteData) els.deleteData.disabled = disabled;
  }

  function setAllBusy(isBusy) {
    state.saving = isBusy;
    if (els.retry) els.retry.disabled = isBusy;
    setRemoteDisabled(isBusy || !state.userRef);
    if (els.notificationDot) els.notificationDot.disabled = isBusy;
  }

  function renderSettings() {
    if (els.autoAnalyse) els.autoAnalyse.checked = Boolean(state.settings.auto_analyse);
    if (els.calibrationOptIn) els.calibrationOptIn.checked = Boolean(state.settings.calibration_opt_in);
    if (els.notificationDot) els.notificationDot.checked = Boolean(state.notificationDot);
    setRemoteDisabled(!state.userRef || state.loading || state.saving || state.deleting);
  }

  async function ensureUserRef() {
    if (state.userRef) return state.userRef;
    const storageApi = storage();
    if (!storageApi) return '';
    state.userRef = await storageApi.get(storageApi.STORAGE_KEYS.USER_REF, '');
    return state.userRef;
  }

  async function loadLocalPreference() {
    const storageApi = storage();
    if (!storageApi) return;
    state.notificationDot = await storageApi.get(SHOW_NOTIFICATION_DOT_KEY, true);
  }

  async function saveLocalPreference(value) {
    const storageApi = storage();
    if (!storageApi) throw new Error('Local settings are unavailable.');
    state.notificationDot = Boolean(value);
    await storageApi.set(SHOW_NOTIFICATION_DOT_KEY, state.notificationDot);
    renderSettings();
    setStatus('Notification setting saved.');
  }

  async function loadSettings() {
    if (state.loading) return;
    const storageApi = storage();
    const apiClient = api();

    if (!storageApi || !apiClient?.getSettings) {
      setStatus('SAF API client is unavailable.', true);
      return;
    }

    state.loading = true;
    if (els.retry) els.retry.hidden = true;
    setAllBusy(true);
    setStatus('Loading settings...');

    try {
      await loadLocalPreference();
      const userRef = await ensureUserRef();
      if (state.disposed) return;
      if (!userRef) {
        state.settings = { auto_analyse: false, calibration_opt_in: false };
        renderSettings();
        setStatus('Set your user ID before changing account settings.', true);
        return;
      }

      const result = await apiClient.getSettings(userRef);
      if (state.disposed) return;
      if (!result?.ok) {
        throw new Error(detailText(result, 'Could not load settings.'));
      }

      state.settings = {
        auto_analyse: Boolean(result.data?.auto_analyse),
        calibration_opt_in: Boolean(result.data?.calibration_opt_in),
      };
      renderSettings();
      setStatus('');
    } catch (error) {
      if (els.retry) els.retry.hidden = false;
      setStatus(error.message || 'Could not load settings.', true);
    } finally {
      state.loading = false;
      setAllBusy(false);
      renderSettings();
    }
  }

  async function updateRemoteSetting(key, value) {
    if (state.saving || state.loading) return;
    const apiClient = api();
    if (!apiClient?.updateSettings) {
      setStatus('Settings updates are unavailable.', true);
      renderSettings();
      return;
    }

    const previous = Boolean(state.settings[key]);
    state.settings = { ...state.settings, [key]: Boolean(value) };
    renderSettings();
    setAllBusy(true);
    setStatus('Saving settings...');

    try {
      const userRef = await ensureUserRef();
      if (!userRef) throw new Error('Set your user ID before changing account settings.');
      const result = await apiClient.updateSettings(userRef, { [key]: Boolean(value) });
      if (!result?.ok) {
        throw new Error(detailText(result, 'Could not save setting.'));
      }
      state.settings = {
        auto_analyse: Boolean(result.data?.auto_analyse),
        calibration_opt_in: Boolean(result.data?.calibration_opt_in),
      };
      setStatus('Settings saved.');
    } catch (error) {
      state.settings = { ...state.settings, [key]: previous };
      setStatus(error.message || 'Could not save setting.', true);
    } finally {
      setAllBusy(false);
      renderSettings();
    }
  }

  async function deleteData() {
    if (state.deleting || state.loading || state.saving) return;
    const apiClient = api();
    const storageApi = storage();
    if (!apiClient?.deleteUser || !storageApi) {
      setStatus('Data deletion is unavailable.', true);
      return;
    }

    const userRef = await ensureUserRef();
    if (!userRef) {
      setStatus('No user ID is set.', true);
      return;
    }
    if (!globalThis.confirm('Delete your SAF data for this user? This cannot be undone.')) {
      return;
    }

    state.deleting = true;
    setAllBusy(true);
    setStatus('Deleting data...');

    try {
      const result = await apiClient.deleteUser(userRef);
      if (!result?.ok) {
        throw new Error(detailText(result, 'Could not delete data.'));
      }
      await storageApi.remove([
        storageApi.STORAGE_KEYS.USER_REF,
        storageApi.STORAGE_KEYS.ONBOARDING_COMPLETE,
      ]);
      state.userRef = '';
      state.settings = { auto_analyse: false, calibration_opt_in: false };
      renderSettings();
      setStatus('Data deleted.');
    } catch (error) {
      setStatus(error.message || 'Could not delete data.', true);
    } finally {
      state.deleting = false;
      setAllBusy(false);
      renderSettings();
    }
  }

  function handleAutoAnalyseChange(event) {
    void updateRemoteSetting('auto_analyse', event.target.checked);
  }

  function handleNotificationDotChange(event) {
    void saveLocalPreference(event.target.checked).catch((error) => {
      state.notificationDot = !event.target.checked;
      renderSettings();
      setStatus(error.message || 'Could not save notification setting.', true);
    });
  }

  function handleCalibrationChange(event) {
    void updateRemoteSetting('calibration_opt_in', event.target.checked);
  }

  function handleRetry() {
    void loadSettings();
  }

  function handleDelete() {
    void deleteData();
  }

  els.autoAnalyse?.addEventListener('change', handleAutoAnalyseChange);
  els.notificationDot?.addEventListener('change', handleNotificationDotChange);
  els.calibrationOptIn?.addEventListener('change', handleCalibrationChange);
  els.retry?.addEventListener('click', handleRetry);
  els.deleteData?.addEventListener('click', handleDelete);

  void loadSettings();

  return () => {
    state.disposed = true;
    els.autoAnalyse?.removeEventListener('change', handleAutoAnalyseChange);
    els.notificationDot?.removeEventListener('change', handleNotificationDotChange);
    els.calibrationOptIn?.removeEventListener('change', handleCalibrationChange);
    els.retry?.removeEventListener('click', handleRetry);
    els.deleteData?.removeEventListener('click', handleDelete);
  };
}
