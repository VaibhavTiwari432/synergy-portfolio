const SHOW_NOTIFICATION_DOT_KEY = 'saf_show_notification_dot';

// Local-testing convenience: the well-known key that start_saf.ps1 serves by
// default (no -Prod). The "Use dev key" button writes this to chrome.storage on
// an explicit click — it is never invented/auto-sent, so the api_client egress
// guarantee (extension never invents a shared key) is untouched.
const LOCAL_DEV_API_KEY = 'dev-local';

export function initSettingsView(shadowRoot) {
  const state = {
    userRef: '',
    settings: {
      auto_analyse: false,
      calibration_opt_in: false,
    },
    apiEndpoint: '',
    consent: false,
    notificationDot: true,
    devKeyApplied: false,
    loading: false,
    saving: false,
    deleting: false,
    disposed: false,
  };

  const els = {
    status: shadowRoot.getElementById('saf-settings-status'),
    retry: shadowRoot.getElementById('saf-settings-retry'),
    userRef: shadowRoot.getElementById('saf-setting-user-ref'),
    apiEndpoint: shadowRoot.getElementById('saf-setting-api-endpoint'),
    apiKey: shadowRoot.getElementById('saf-setting-api-key'),
    useDevKey: shadowRoot.getElementById('saf-settings-use-dev-key'),
    consent: shadowRoot.getElementById('saf-setting-consent'),
    saveConnection: shadowRoot.getElementById('saf-settings-save-connection'),
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
    const message = result?.detail || result?.error || result?.message;
    if (result?.status === 401 || /invalid or missing X-API-Key/i.test(String(message || ''))) {
      return 'API key is missing or invalid for this backend.';
    }
    if (result?.error === 'api_unreachable') {
      return 'Local settings loaded. SAF backend is not reachable at the configured endpoint.';
    }
    if (result?.error === 'user_ref_required') {
      return 'Set your user ID before changing account settings.';
    }
    return message || fallback;
  }

  function healthWarning(health) {
    if (!health?.ok) return '';
    if (health.data?.db === 'unavailable') {
      return 'Backend is reachable, but Postgres is unavailable.';
    }
    if (health.data?.scoring === 'missing_judge_key') {
      return 'Backend is reachable, but scoring needs GEMINI_API_KEY or GOOGLE_API_KEY on the server.';
    }
    return '';
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
    if (els.saveConnection) els.saveConnection.disabled = isBusy;
  }

  function renderSettings() {
    if (els.userRef) els.userRef.value = state.userRef || '';
    if (els.apiEndpoint) els.apiEndpoint.value = state.apiEndpoint || api()?.DEFAULT_ENDPOINT || 'http://localhost:8000';
    if (els.consent) els.consent.checked = Boolean(state.consent);
    if (els.autoAnalyse) els.autoAnalyse.checked = Boolean(state.settings.auto_analyse);
    if (els.calibrationOptIn) els.calibrationOptIn.checked = Boolean(state.settings.calibration_opt_in);
    if (els.notificationDot) els.notificationDot.checked = Boolean(state.notificationDot);
    renderDevKeyButton();
    setRemoteDisabled(!state.userRef || state.loading || state.saving || state.deleting);
  }

  // The dev-key sentinel is a LOCAL-ONLY convenience: it is shown only when the
  // configured endpoint is localhost, and only until it has been applied this
  // session. It is never offered for a remote backend, so the dev key cannot be
  // written against (and later sent to) a non-local server.
  function isLocalEndpoint(value) {
    try {
      const host = new URL(value).hostname;
      return host === 'localhost' || host === '127.0.0.1' || host === '::1' || host === '[::1]';
    } catch (_) {
      return false;
    }
  }

  function renderDevKeyButton() {
    if (!els.useDevKey) return;
    const endpoint = String(els.apiEndpoint?.value || state.apiEndpoint || '').trim();
    els.useDevKey.hidden = !(isLocalEndpoint(endpoint) && !state.devKeyApplied);
  }

  async function ensureUserRef() {
    if (state.userRef) return state.userRef;
    const storageApi = storage();
    if (!storageApi) return '';
    state.userRef = await storageApi.get(storageApi.STORAGE_KEYS.USER_REF, '');
    return state.userRef;
  }

  function isHttpEndpoint(value) {
    try {
      const url = new URL(value);
      return url.protocol === 'http:' || url.protocol === 'https:';
    } catch (_) {
      return false;
    }
  }

  async function loadLocalSetup() {
    const storageApi = storage();
    if (!storageApi) return;
    const keys = storageApi.STORAGE_KEYS;
    const values = await storageApi.getMany([
      keys.USER_REF,
      keys.API_ENDPOINT,
      keys.CONSENT_ENABLED,
    ]);
    state.userRef = values[keys.USER_REF] || '';
    state.apiEndpoint = values[keys.API_ENDPOINT] || api()?.DEFAULT_ENDPOINT || 'http://localhost:8000';
    state.consent = Boolean(values[keys.CONSENT_ENABLED]);
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
      await loadLocalSetup();
      await loadLocalPreference();
      const userRef = state.userRef || await ensureUserRef();
      if (state.disposed) return;
      if (!userRef) {
        state.settings = { auto_analyse: false, calibration_opt_in: false };
        renderSettings();
        setStatus('Save your connection settings to enable capture.');
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

  async function saveConnection() {
    if (state.saving || state.loading) return;
    const storageApi = storage();
    const apiClient = api();
    if (!storageApi) {
      setStatus('Local extension storage is unavailable.', true);
      return;
    }

    const keys = storageApi.STORAGE_KEYS;
    const userRef = String(els.userRef?.value || '').trim();
    const apiEndpoint = String(els.apiEndpoint?.value || apiClient?.DEFAULT_ENDPOINT || 'http://localhost:8000').trim();
    const apiKey = String(els.apiKey?.value || '').trim();
    const consent = Boolean(els.consent?.checked);

    if (!userRef) {
      setStatus('User ID is required before capture can run.', true);
      return;
    }
    if (!apiEndpoint) {
      setStatus('API endpoint is required.', true);
      return;
    }
    if (!isHttpEndpoint(apiEndpoint)) {
      setStatus('API endpoint must start with http:// or https://.', true);
      return;
    }

    setAllBusy(true);
    setStatus('Saving connection...');

    try {
      const updates = {
        [keys.USER_REF]: userRef,
        [keys.API_ENDPOINT]: apiEndpoint,
        [keys.CONSENT_ENABLED]: consent,
        [keys.ONBOARDING_COMPLETE]: true,
      };
      if (apiKey) updates[keys.API_KEY] = apiKey;
      else await storageApi.remove(keys.API_KEY);
      await storageApi.set(updates);

      state.userRef = userRef;
      state.apiEndpoint = apiEndpoint;
      state.consent = consent;
      if (els.apiKey) els.apiKey.value = '';
      renderSettings();

      const health = apiClient?.getHealth ? await apiClient.getHealth() : null;
      const reachable = apiClient?.getHealth ? Boolean(health?.ok) : await apiClient?.checkHealth?.();
      if (!reachable) {
        setStatus('Connection saved. Backend is not reachable yet.', true);
      } else if (apiClient?.getSettings) {
        const authCheck = await apiClient.getSettings(userRef);
        const warning = healthWarning(health);
        setStatus(
          authCheck?.ok
            ? (warning || 'Connection saved. API key accepted.')
            : detailText(authCheck, 'Connection saved, but API key could not be verified.'),
          !authCheck?.ok || Boolean(warning),
        );
      } else {
        setStatus('Connection saved. Backend reachable.');
      }
      shadowRoot.dispatchEvent?.(new CustomEvent('saf-settings-updated', { bubbles: true }));
    } catch (error) {
      setStatus(error.message || 'Could not save connection.', true);
    } finally {
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

  function handleSaveConnection() {
    void saveConnection();
  }

  async function useDevKey() {
    const storageApi = storage();
    if (!storageApi) {
      setStatus('Local extension storage is unavailable.', true);
      return;
    }
    // Two-layer conditional guard. Layer 1 (renderDevKeyButton) hides the button
    // for any non-localhost endpoint so it cannot normally be clicked. Layer 2 is
    // this re-check at click time: even if the endpoint changed between render and
    // click (or the element were forced visible), the dev key is never written for
    // a remote backend.
    const endpoint = String(els.apiEndpoint?.value || state.apiEndpoint || '').trim();
    if (!isLocalEndpoint(endpoint)) return;
    try {
      await storageApi.set({ [storageApi.STORAGE_KEYS.API_KEY]: LOCAL_DEV_API_KEY });
      state.devKeyApplied = true;
      if (els.apiKey) els.apiKey.value = '';
      renderDevKeyButton();
      setStatus('Dev key set.');
    } catch (error) {
      setStatus(error.message || 'Could not set the dev key.', true);
    }
  }

  function handleUseDevKey() {
    void useDevKey();
  }

  function handleEndpointInput() {
    // Re-evaluate dev-key visibility live as the endpoint is edited. Note: this
    // does NOT call renderSettings(), which would overwrite the field the user
    // is typing into; it only toggles the sentinel button.
    renderDevKeyButton();
  }

  function handleDelete() {
    void deleteData();
  }

  els.saveConnection?.addEventListener('click', handleSaveConnection);
  els.useDevKey?.addEventListener('click', handleUseDevKey);
  els.apiEndpoint?.addEventListener('input', handleEndpointInput);
  els.autoAnalyse?.addEventListener('change', handleAutoAnalyseChange);
  els.notificationDot?.addEventListener('change', handleNotificationDotChange);
  els.calibrationOptIn?.addEventListener('change', handleCalibrationChange);
  els.retry?.addEventListener('click', handleRetry);
  els.deleteData?.addEventListener('click', handleDelete);

  void loadSettings();

  return () => {
    state.disposed = true;
    els.saveConnection?.removeEventListener('click', handleSaveConnection);
    els.useDevKey?.removeEventListener('click', handleUseDevKey);
    els.apiEndpoint?.removeEventListener('input', handleEndpointInput);
    els.autoAnalyse?.removeEventListener('change', handleAutoAnalyseChange);
    els.notificationDot?.removeEventListener('change', handleNotificationDotChange);
    els.calibrationOptIn?.removeEventListener('change', handleCalibrationChange);
    els.retry?.removeEventListener('click', handleRetry);
    els.deleteData?.removeEventListener('click', handleDelete);
  };
}
