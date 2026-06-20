const PAGE_SIZE = 20;
const DIMENSIONS = ['AL', 'PR', 'EC', 'ES', 'CS', 'CD', 'AUI', 'CA'];

export function initProjectsView(shadowRoot) {
  const state = {
    userRef: '',
    projects: [],
    nextCursor: null,
    selectedProjectId: null,
    selectedProject: null,
    chatOptions: [],
    loading: false,
    loadingChats: false,
    creating: false,
    updating: false,
    deleting: false,
    assigningChats: false,
    conflict: null,
    disposed: false,
  };

  const els = {
    status: shadowRoot.getElementById('saf-projects-status'),
    retry: shadowRoot.getElementById('saf-projects-retry'),
    name: shadowRoot.getElementById('saf-project-name'),
    description: shadowRoot.getElementById('saf-project-description'),
    create: shadowRoot.getElementById('saf-project-create'),
    list: shadowRoot.getElementById('saf-project-list'),
    loadMore: shadowRoot.getElementById('saf-project-load-more'),
    detailEmpty: shadowRoot.getElementById('saf-project-detail-empty'),
    detail: shadowRoot.getElementById('saf-project-detail'),
    detailTitle: shadowRoot.getElementById('saf-project-detail-heading'),
    detailMeta: shadowRoot.getElementById('saf-project-detail-meta'),
    editName: shadowRoot.getElementById('saf-project-edit-name'),
    editDescription: shadowRoot.getElementById('saf-project-edit-description'),
    save: shadowRoot.getElementById('saf-project-save'),
    delete: shadowRoot.getElementById('saf-project-delete'),
    conflictRetry: shadowRoot.getElementById('saf-project-conflict-retry'),
    refreshChats: shadowRoot.getElementById('saf-project-refresh-chats'),
    chatSelect: shadowRoot.getElementById('saf-project-chat-select'),
    addChats: shadowRoot.getElementById('saf-project-add-chats'),
    assignStatus: shadowRoot.getElementById('saf-project-assign-status'),
    profileList: shadowRoot.getElementById('saf-project-profile-list'),
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

  function clear(node) {
    node?.replaceChildren();
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

  function colorForValue(value) {
    if (value >= 0.66) return 'var(--saf-green)';
    if (value >= 0.38) return 'var(--saf-amber)';
    return 'var(--saf-red)';
  }

  function detailText(result, fallback) {
    return result?.detail || result?.error || fallback;
  }

  function shortId(value) {
    const text = String(value || 'unknown');
    if (text.length <= 12) return text;
    return `${text.slice(0, 6)}...${text.slice(-4)}`;
  }

  function chatLabel(chat) {
    return `Conversation ${shortId(chat?.conversation_id || chat?.chat_id)}`;
  }

  function setAssignStatus(message = '', isError = false) {
    if (!els.assignStatus) return;
    els.assignStatus.textContent = message;
    els.assignStatus.classList.toggle('is-error', isError);
  }

  function versionConflict(result) {
    if (result?.status !== 409) return null;
    if (result?.detailData?.error !== 'version_conflict') return null;
    const currentVersion = Number(result.detailData.current_version);
    return Number.isFinite(currentVersion) ? currentVersion : null;
  }

  function ensureApi() {
    const storageApi = storage();
    const apiClient = api();
    if (!storageApi || !apiClient?.listProjects || !apiClient?.getProject) {
      setStatus('SAF API client is unavailable.', true);
      return null;
    }
    return { storageApi, apiClient };
  }

  async function ensureUserRef() {
    if (state.userRef) return state.userRef;
    const storageApi = storage();
    if (!storageApi) return '';
    state.userRef = await storageApi.get(storageApi.STORAGE_KEYS.USER_REF, '');
    return state.userRef;
  }

  function setCreateBusy(isBusy) {
    state.creating = isBusy;
    if (els.create) els.create.disabled = isBusy;
  }

  function setDetailBusy(isBusy) {
    if (els.save) els.save.disabled = isBusy;
    if (els.delete) els.delete.disabled = isBusy;
    if (els.conflictRetry) els.conflictRetry.disabled = isBusy;
  }

  function setAssignBusy(isBusy) {
    state.assigningChats = isBusy;
    if (els.addChats) els.addChats.disabled = isBusy;
    if (els.refreshChats) els.refreshChats.disabled = isBusy;
    if (els.chatSelect) els.chatSelect.disabled = isBusy;
  }

  function renderEmptyList(message) {
    clear(els.list);
    const row = document.createElement('div');
    row.className = 'saf-project-empty-row';
    row.textContent = message;
    els.list?.appendChild(row);
  }

  function projectMeta(project) {
    const count = Number(project?.session_count || 0);
    return `${count} ${count === 1 ? 'session' : 'sessions'}`;
  }

  function renderProjectRow(project) {
    const row = document.createElement('button');
    row.className = 'saf-project-row';
    row.type = 'button';
    row.dataset.projectId = project.project_id || '';
    row.classList.toggle('is-selected', project.project_id === state.selectedProjectId);

    const text = document.createElement('span');
    text.className = 'saf-project-row-text';

    const title = document.createElement('span');
    title.className = 'saf-project-row-title';
    title.textContent = project.name || 'Untitled project';
    text.appendChild(title);

    const meta = document.createElement('span');
    meta.className = 'saf-project-row-meta';
    meta.textContent = projectMeta(project);
    text.appendChild(meta);
    row.appendChild(text);

    return row;
  }

  function renderList() {
    clear(els.list);
    if (!state.projects.length) {
      renderEmptyList('No projects yet.');
    } else {
      const fragment = document.createDocumentFragment();
      state.projects.forEach((project) => {
        fragment.appendChild(renderProjectRow(project));
      });
      els.list?.appendChild(fragment);
    }
    if (els.loadMore) els.loadMore.hidden = !state.nextCursor;
  }

  function renderChatOptions() {
    clear(els.chatSelect);
    if (!els.chatSelect) return;

    if (!state.chatOptions.length) {
      const option = document.createElement('option');
      option.disabled = true;
      option.textContent = 'No chats available';
      els.chatSelect.appendChild(option);
      return;
    }

    const fragment = document.createDocumentFragment();
    state.chatOptions.forEach((chat) => {
      const option = document.createElement('option');
      option.value = chat.chat_id || '';
      option.textContent = chatLabel(chat);
      fragment.appendChild(option);
    });
    els.chatSelect.appendChild(fragment);
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

  function renderProfileDimension(dim, entry) {
    const stateName = entry?.state || 'STRUCTURAL_NA';
    const { row, fill, value, ci } = makeDimensionRow(dim, stateName);

    if (stateName === 'scored') {
      const scoreValue = clampUnit(numeric(entry?.value)) ?? 0;
      fill.style.setProperty('--saf-dim-fill', `${Math.round(scoreValue * 100)}%`);
      fill.style.setProperty('--saf-dim-color', colorForValue(scoreValue));
      value.textContent = formatValue(scoreValue);
      const low = numeric(entry?.ci?.[0]);
      const high = numeric(entry?.ci?.[1]);
      ci.textContent = low != null && high != null ? `±${((high - low) / 2).toFixed(2).replace(/^0/, '')}` : '±?';
      return row;
    }

    fill.style.setProperty('--saf-dim-fill', '100%');
    if (stateName === 'MEASUREMENT_SATURATED') fill.classList.add('is-saturated');
    value.textContent = {
      STRUCTURAL_NA: 'N/A',
      INSUFFICIENT_SAMPLE: 'Low n',
      MEASUREMENT_SATURATED: 'Saturated',
    }[stateName] || stateName;
    ci.textContent = entry?.n ? `n=${entry.n}` : '';
    return row;
  }

  function renderProjectProfile(profileRadar) {
    clear(els.profileList);
    const fragment = document.createDocumentFragment();
    DIMENSIONS.forEach((dim) => {
      fragment.appendChild(renderProfileDimension(dim, profileRadar?.[dim]));
    });
    els.profileList?.appendChild(fragment);
  }

  function renderDetail() {
    const project = state.selectedProject;
    setVisible(els.detailEmpty, !project);
    setVisible(els.detail, Boolean(project));
    if (!project) return;

    if (els.detailTitle) els.detailTitle.textContent = project.name || 'Untitled project';
    if (els.detailMeta) {
      els.detailMeta.textContent = `Version ${project.version} / ${projectMeta(project)}`;
    }
    if (els.editName) els.editName.value = project.name || '';
    if (els.editDescription) els.editDescription.value = project.description || '';
    if (els.conflictRetry) els.conflictRetry.hidden = !state.conflict;
    renderChatOptions();
    renderProjectProfile(project.profile_radar || {});
  }

  async function refreshProject(projectId) {
    const apiClient = api();
    if (!apiClient?.getProject || !state.userRef) return null;
    const result = await apiClient.getProject(state.userRef, projectId);
    if (!result?.ok) {
      throw new Error(detailText(result, 'Could not refresh project.'));
    }
    state.selectedProject = result.data || null;
    state.selectedProjectId = state.selectedProject?.project_id || projectId;
    state.projects = state.projects.map((project) => (
      project.project_id === projectId
        ? {
          ...project,
          name: state.selectedProject?.name || project.name,
          session_count: state.selectedProject?.session_count ?? project.session_count,
        }
        : project
    ));
    renderList();
    renderDetail();
    return state.selectedProject;
  }

  async function loadChatOptions() {
    if (state.loadingChats) return;
    const apiClient = api();
    if (!apiClient?.getChatList) {
      setAssignStatus('Chat list is unavailable.', true);
      return;
    }

    state.loadingChats = true;
    setAssignBusy(true);
    setAssignStatus('Loading chats...');

    try {
      const userRef = await ensureUserRef();
      if (!userRef) throw new Error('Set your user ID in Settings first.');
      const result = await apiClient.getChatList(userRef);
      if (!result?.ok) {
        throw new Error(detailText(result, 'Could not load chats.'));
      }

      const chats = Array.isArray(result.data?.chats) ? result.data.chats : [];
      state.chatOptions = chats.filter((chat) => chat?.chat_id);
      renderChatOptions();
      setAssignStatus(state.chatOptions.length ? '' : 'No chats available to add.');
    } catch (error) {
      setAssignStatus(error.message || 'Could not load chats.', true);
    } finally {
      state.loadingChats = false;
      setAssignBusy(false);
    }
  }

  async function handleConflict(action, projectId, patch, result) {
    const currentVersion = versionConflict(result);
    if (currentVersion == null) {
      throw new Error(detailText(result, 'Project change failed.'));
    }
    state.conflict = { action, projectId, patch };
    await refreshProject(projectId);
    if (els.conflictRetry) els.conflictRetry.hidden = false;
    setStatus(`Project changed elsewhere. Refreshed to version ${currentVersion}. Review and retry.`, true);
  }

  async function loadProjects({ append = false } = {}) {
    if (state.loading) return;
    const deps = ensureApi();
    if (!deps) return;

    state.loading = true;
    if (els.retry) els.retry.hidden = true;
    setStatus('Loading projects...');

    try {
      const userRef = await ensureUserRef();
      if (state.disposed) return;
      if (!userRef) {
        setStatus('Set your user ID in Settings first.', true);
        return;
      }

      const result = await deps.apiClient.listProjects(userRef, {
        limit: PAGE_SIZE,
        cursor: append ? state.nextCursor : null,
      });
      if (state.disposed) return;
      if (!result?.ok) {
        throw new Error(detailText(result, 'Could not load projects.'));
      }

      const data = result.data || {};
      const items = Array.isArray(data.items) ? data.items : [];
      state.projects = append ? [...state.projects, ...items] : items;
      state.nextCursor = data.next_cursor || null;
      renderList();
      setStatus('');
    } catch (error) {
      if (els.retry) els.retry.hidden = false;
      setStatus(error.message || 'Could not load projects.', true);
    } finally {
      state.loading = false;
    }
  }

  async function selectProject(projectId) {
    if (!projectId) return;
    state.selectedProjectId = projectId;
    state.conflict = null;
    renderList();
    setStatus('Loading project...');
    try {
      await refreshProject(projectId);
      void loadChatOptions();
      setStatus('');
    } catch (error) {
      setStatus(error.message || 'Could not load project.', true);
    }
  }

  function selectedChatIds() {
    if (!els.chatSelect) return [];
    return Array.from(els.chatSelect.selectedOptions)
      .map((option) => option.value)
      .filter(Boolean);
  }

  function assignmentMessage(data) {
    const added = Number(data?.added || 0);
    const skipped = Number(data?.skipped_already_present || 0);
    const unknown = Array.isArray(data?.unknown) ? data.unknown : [];
    const parts = [`${added} added`, `${skipped} already present`];
    if (unknown.length) parts.push(`${unknown.length} unknown: ${unknown.map(shortId).join(', ')}`);
    return parts.join(' / ');
  }

  async function addSelectedChats() {
    if (state.assigningChats || !state.selectedProject) return;
    const apiClient = api();
    if (!apiClient?.addProjectSessions) {
      setAssignStatus('Adding chats is unavailable.', true);
      return;
    }

    const chatIds = selectedChatIds();
    if (!chatIds.length) {
      setAssignStatus('Select at least one chat to add.', true);
      return;
    }

    setAssignBusy(true);
    setAssignStatus('Adding chats...');
    const projectId = state.selectedProject.project_id;

    try {
      const userRef = await ensureUserRef();
      if (!userRef) throw new Error('Set your user ID in Settings first.');
      const result = await apiClient.addProjectSessions(userRef, projectId, chatIds);
      if (!result?.ok) {
        if (result?.status === 404) {
          setAssignStatus('Project not found. Refreshing projects...', true);
          await loadProjects();
          return;
        }
        throw new Error(detailText(result, 'Could not add chats.'));
      }

      setAssignStatus(assignmentMessage(result.data || {}));
      await refreshProject(projectId);
    } catch (error) {
      setAssignStatus(error.message || 'Could not add chats.', true);
    } finally {
      setAssignBusy(false);
    }
  }

  async function createProject() {
    if (state.creating) return;
    const deps = ensureApi();
    if (!deps?.apiClient?.createProject) {
      setStatus('Project creation is unavailable.', true);
      return;
    }

    const name = String(els.name?.value || '').trim();
    const description = String(els.description?.value || '').trim();
    if (!name) {
      setStatus('Project name is required.', true);
      return;
    }

    setCreateBusy(true);
    setStatus('Creating project...');
    try {
      const userRef = await ensureUserRef();
      if (!userRef) throw new Error('Set your user ID in Settings first.');
      const result = await deps.apiClient.createProject(userRef, {
        name,
        description: description || null,
      });
      if (!result?.ok) {
        throw new Error(detailText(result, 'Could not create project.'));
      }
      if (els.name) els.name.value = '';
      if (els.description) els.description.value = '';
      await loadProjects();
      const projectId = result.data?.project_id;
      if (projectId) await selectProject(projectId);
      setStatus('Project created.');
    } catch (error) {
      setStatus(error.message || 'Could not create project.', true);
    } finally {
      setCreateBusy(false);
    }
  }

  function currentPatch() {
    return {
      name: String(els.editName?.value || '').trim(),
      description: String(els.editDescription?.value || '').trim() || null,
    };
  }

  async function updateSelectedProject(patch = currentPatch()) {
    if (state.updating || !state.selectedProject) return;
    const apiClient = api();
    if (!apiClient?.updateProject) {
      setStatus('Project update is unavailable.', true);
      return;
    }
    if (!patch.name) {
      setStatus('Project name is required.', true);
      return;
    }

    state.updating = true;
    setDetailBusy(true);
    state.conflict = null;
    setStatus('Saving project...');
    const projectId = state.selectedProject.project_id;
    try {
      const result = await apiClient.updateProject(state.userRef, projectId, patch, state.selectedProject.version);
      if (!result?.ok) {
        await handleConflict('update', projectId, patch, result);
        return;
      }
      await refreshProject(projectId);
      state.conflict = null;
      setStatus('Project saved.');
    } catch (error) {
      setStatus(error.message || 'Could not save project.', true);
    } finally {
      state.updating = false;
      setDetailBusy(false);
      renderDetail();
    }
  }

  async function deleteSelectedProject() {
    if (state.deleting || !state.selectedProject) return;
    const apiClient = api();
    if (!apiClient?.deleteProject) {
      setStatus('Project deletion is unavailable.', true);
      return;
    }

    state.deleting = true;
    setDetailBusy(true);
    state.conflict = null;
    setStatus('Deleting project...');
    const projectId = state.selectedProject.project_id;
    try {
      const result = await apiClient.deleteProject(state.userRef, projectId, state.selectedProject.version);
      if (!result?.ok) {
        await handleConflict('delete', projectId, null, result);
        return;
      }
      state.projects = state.projects.filter((project) => project.project_id !== projectId);
      state.selectedProject = null;
      state.selectedProjectId = null;
      state.conflict = null;
      renderList();
      renderDetail();
      setStatus('Project deleted.');
    } catch (error) {
      setStatus(error.message || 'Could not delete project.', true);
    } finally {
      state.deleting = false;
      setDetailBusy(false);
    }
  }

  function retryConflict() {
    const conflict = state.conflict;
    if (!conflict) return;
    if (conflict.action === 'update') {
      void updateSelectedProject(conflict.patch);
    } else if (conflict.action === 'delete') {
      void deleteSelectedProject();
    }
  }

  function handleRetryClick() {
    void loadProjects();
  }

  function handleLoadMoreClick() {
    void loadProjects({ append: true });
  }

  function handleCreateClick() {
    void createProject();
  }

  function handleSaveClick() {
    void updateSelectedProject();
  }

  function handleDeleteClick() {
    void deleteSelectedProject();
  }

  function handleRefreshChatsClick() {
    void loadChatOptions();
  }

  function handleAddChatsClick() {
    void addSelectedChats();
  }

  function handleListClick(event) {
    const target = event.target;
    if (!(target instanceof Element)) return;
    const row = target.closest('.saf-project-row[data-project-id]');
    if (!row || !els.list?.contains(row)) return;
    void selectProject(row.getAttribute('data-project-id'));
  }

  els.retry?.addEventListener('click', handleRetryClick);
  els.loadMore?.addEventListener('click', handleLoadMoreClick);
  els.create?.addEventListener('click', handleCreateClick);
  els.list?.addEventListener('click', handleListClick);
  els.save?.addEventListener('click', handleSaveClick);
  els.delete?.addEventListener('click', handleDeleteClick);
  els.refreshChats?.addEventListener('click', handleRefreshChatsClick);
  els.addChats?.addEventListener('click', handleAddChatsClick);
  els.conflictRetry?.addEventListener('click', retryConflict);

  void loadProjects();

  return () => {
    state.disposed = true;
    els.retry?.removeEventListener('click', handleRetryClick);
    els.loadMore?.removeEventListener('click', handleLoadMoreClick);
    els.create?.removeEventListener('click', handleCreateClick);
    els.list?.removeEventListener('click', handleListClick);
    els.save?.removeEventListener('click', handleSaveClick);
    els.delete?.removeEventListener('click', handleDeleteClick);
    els.refreshChats?.removeEventListener('click', handleRefreshChatsClick);
    els.addChats?.removeEventListener('click', handleAddChatsClick);
    els.conflictRetry?.removeEventListener('click', retryConflict);
  };
}
