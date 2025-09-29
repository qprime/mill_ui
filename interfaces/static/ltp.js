(() => {
  const app = document.getElementById('ltp-app');
  if (!app) return;

  const state = {
    slug: app.dataset.slug || '',
    mode: app.dataset.mode || 'draft',
    projects: [],
    templates: [],
    tonePresets: [],
    quickChecks: [],
    selectedTone: null,
    sections: [],
    prompts: [],
    summary: {},
    actionItems: [],
    suggestions: [],
    preview: null,
    previewRequest: null,
    recording: null,
    coauthorSuggestion: null,
    pendingBrief: null,
    pendingBriefContext: null,
    whisperStatus: { ok: null, reason: '', status: null },
    ledgerStatus: { needs_compaction: false, size_mb: 0, threshold_mb: 0 },
  };

  const refs = {
    slugInput: document.getElementById('ltp-slug'),
    loadBtn: document.getElementById('ltp-load'),
    projectSelect: document.getElementById('ltp-project-select'),
    projectNew: document.getElementById('ltp-project-new'),
    templateModal: document.getElementById('ltp-template-modal'),
    templateForm: document.getElementById('ltp-template-form'),
    templateClose: document.getElementById('ltp-template-close'),
    templateOptions: document.getElementById('ltp-template-options'),
    modeButtons: Array.from(document.querySelectorAll('.ltp-mode-buttons button')),
    recordBtn: document.getElementById('ltp-record'),
    stopBtn: document.getElementById('ltp-stop'),
    uploadBtn: document.getElementById('ltp-upload'),
    fileInput: document.getElementById('ltp-file'),
    tidyBtn: document.getElementById('ltp-tidy'),
    reviseBtn: document.getElementById('ltp-revise'),
    exportPdf: document.getElementById('ltp-export-pdf'),
    exportDocx: document.getElementById('ltp-export-docx'),
    prompts: document.getElementById('ltp-prompts'),
    tones: document.getElementById('ltp-tones'),
    quickChecks: document.getElementById('ltp-quick-checks'),
    suggestions: document.getElementById('ltp-suggestions'),
    actionList: document.getElementById('ltp-actions-list'),
    actionInput: document.getElementById('ltp-action-input'),
    actionAdd: document.getElementById('ltp-action-add'),
    sections: document.getElementById('ltp-sections'),
    previewBefore: document.getElementById('ltp-preview-before'),
    previewAfter: document.getElementById('ltp-preview-after'),
    previewDiff: document.getElementById('ltp-preview-diff'),
    applyBtn: document.getElementById('ltp-apply'),
    cancelBtn: document.getElementById('ltp-cancel'),
    briefBtn: document.getElementById('ltp-brief'),
    summary: document.getElementById('ltp-summary'),
    coauthorInput: document.getElementById('ltp-coauthor-input'),
    coauthorSection: document.getElementById('ltp-coauthor-section'),
    coauthorSend: document.getElementById('ltp-coauthor-send'),
    coauthorOutput: document.getElementById('ltp-coauthor-output'),
    briefModal: document.getElementById('ltp-brief-modal'),
    briefText: document.getElementById('ltp-brief-text'),
    briefSend: document.getElementById('ltp-brief-send'),
    briefClose: document.getElementById('ltp-brief-close'),
    whisperStatus: document.getElementById('ltp-whisper-status'),
    ledgerBanner: document.getElementById('ltp-ledger-banner'),
    ledgerText: document.querySelector('.ltp-ledger-text'),
    ledgerLink: document.querySelector('.ltp-ledger-link'),
  };

  const fetchJSON = async (url, options = {}) => {
    const res = await fetch(url, options);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  };

  const snapshotUrl = () => `/api/ltp/projects/${state.slug}/snapshot`;

  const setMode = (mode) => {
    state.mode = mode;
    app.dataset.mode = mode;
    refs.modeButtons.forEach((btn) => {
      btn.classList.toggle('active', btn.dataset.mode === mode);
    });
  };

  const renderProjects = () => {
    if (!refs.projectSelect) return;
    refs.projectSelect.innerHTML = '';
    const placeholder = document.createElement('option');
    placeholder.value = '';
    placeholder.textContent = 'Select project…';
    placeholder.disabled = true;
    placeholder.selected = !state.slug;
    refs.projectSelect.appendChild(placeholder);
    state.projects.forEach((project) => {
      const option = document.createElement('option');
      option.value = project.slug;
      option.textContent = `${project.title} (${project.slug})`;
      if (project.slug === state.slug) option.selected = true;
      refs.projectSelect.appendChild(option);
    });
  };

  const renderTemplates = () => {
    if (!refs.templateOptions) return;
    refs.templateOptions.innerHTML = '';
    if (!state.templates.length) {
      const empty = document.createElement('p');
      empty.textContent = 'No templates found. A blank shell will be created.';
      refs.templateOptions.appendChild(empty);
      return;
    }
    state.templates.forEach((template, idx) => {
      const wrapper = document.createElement('div');
      wrapper.className = 'ltp-template-option';
      const label = document.createElement('label');
      const input = document.createElement('input');
      input.type = 'radio';
      input.name = 'template';
      input.value = template.id;
      if (idx === 0) input.checked = true;
      const span = document.createElement('span');
      span.textContent = template.title;
      label.appendChild(input);
      label.appendChild(span);
      wrapper.appendChild(label);
      const p = document.createElement('p');
      p.textContent = template.description;
      wrapper.appendChild(p);
      refs.templateOptions.appendChild(wrapper);
    });
  };

  const renderToneChips = () => {
    if (!refs.tones) return;
    refs.tones.innerHTML = '';
    state.tonePresets.forEach((tone) => {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.textContent = tone.label;
      btn.classList.toggle('active', state.selectedTone && state.selectedTone.id === tone.id);
      btn.addEventListener('click', () => {
        if (state.selectedTone && state.selectedTone.id === tone.id) {
          state.selectedTone = null;
        } else {
          state.selectedTone = tone;
        }
        renderToneChips();
      });
      refs.tones.appendChild(btn);
    });
  };

  const renderQuickChecks = () => {
    if (!refs.quickChecks) return;
    refs.quickChecks.innerHTML = '';
    state.quickChecks.forEach((item) => {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.textContent = item.label;
      btn.addEventListener('click', () => runQuickCheck(item));
      refs.quickChecks.appendChild(btn);
    });
  };

  const renderPrompts = () => {
    if (!refs.prompts) return;
    refs.prompts.innerHTML = '';
    state.prompts.forEach((prompt) => {
      const li = document.createElement('li');
      li.textContent = prompt;
      refs.prompts.appendChild(li);
    });
  };

  const renderSuggestions = () => {
    refs.suggestions.innerHTML = '';
    state.suggestions.forEach((suggestion) => {
      const box = document.createElement('div');
      box.className = 'ltp-suggestion';
      const title = document.createElement('div');
      title.textContent = `${suggestion.title}: ${suggestion.reason}`;
      box.appendChild(title);
      const btn = document.createElement('button');
      btn.textContent = 'Preview';
      btn.addEventListener('click', () => previewSection(suggestion.section_id, suggestion.intent, suggestion.constraints || []));
      box.appendChild(btn);
      refs.suggestions.appendChild(box);
    });
  };

  const renderActionItems = () => {
    refs.actionList.innerHTML = '';
    state.actionItems.forEach((item, idx) => {
      const li = document.createElement('li');
      const label = document.createElement('label');
      const checkbox = document.createElement('input');
      checkbox.type = 'checkbox';
      checkbox.checked = !!item.done;
      checkbox.addEventListener('change', () => updateActionItem(idx, checkbox.checked));
      label.appendChild(checkbox);
      const span = document.createElement('span');
      span.textContent = item.title || '';
      label.appendChild(span);
      li.appendChild(label);
      refs.actionList.appendChild(li);
    });
  };

  const renderSections = () => {
    refs.sections.innerHTML = '';
    state.sections.forEach((section) => {
      const box = document.createElement('div');
      box.className = 'ltp-section';
      const header = document.createElement('header');
      const h3 = document.createElement('h3');
      h3.textContent = section.title;
      header.appendChild(h3);
      const count = document.createElement('span');
      count.textContent = `${section.word_count} words`;
      header.appendChild(count);
      box.appendChild(header);
      if (section.snippet) {
        const snippet = document.createElement('p');
        snippet.textContent = section.snippet;
        box.appendChild(snippet);
      }
      section.issues.forEach((issue) => {
        const issueEl = document.createElement('div');
        issueEl.className = 'ltp-issue';
        issueEl.textContent = issue.message;
        box.appendChild(issueEl);
      });
      const footer = document.createElement('footer');
      section.quick_actions.forEach((action) => {
        const chip = document.createElement('button');
        chip.className = 'ltp-chip';
        chip.textContent = action.label;
        chip.addEventListener('click', () => previewSection(section.id, action.intent, action.constraints || []));
        footer.appendChild(chip);
      });
      box.appendChild(footer);
      refs.sections.appendChild(box);
    });
    renderCoauthorSections();
  };

  const renderSummary = () => {
    refs.summary.textContent = JSON.stringify(state.summary, null, 2);
  };

  const renderWhisperStatus = () => {
    if (!refs.whisperStatus) return;
    const status = state.whisperStatus || {};
    let statusAttr = 'unknown';
    if (status.ok === true) statusAttr = 'ok';
    else if (status.ok === false) statusAttr = 'error';
    refs.whisperStatus.dataset.status = statusAttr;
    refs.whisperStatus.title = status.reason || '';
    const label = refs.whisperStatus.querySelector('.ltp-status-label');
    if (label) {
      label.textContent = statusAttr === 'error' ? 'Whisper offline' : 'Whisper';
    }
    const disableAudio = statusAttr !== 'ok';
    if (refs.recordBtn) refs.recordBtn.disabled = disableAudio;
    if (refs.uploadBtn) refs.uploadBtn.disabled = disableAudio;
  };

  const renderLedgerStatus = () => {
    if (!refs.ledgerBanner) return;
    const status = state.ledgerStatus || {};
    if (!status.needs_compaction) {
      refs.ledgerBanner.hidden = true;
      return;
    }
    const size = status.size_mb ?? 0;
    const threshold = status.threshold_mb ?? 0;
    if (refs.ledgerText) {
      refs.ledgerText.textContent = `Size ${size} MB of ${threshold} MB`;
    }
    if (refs.ledgerLink) {
      refs.ledgerLink.href = '/chat';
    }
    refs.ledgerBanner.hidden = false;
  };

  const renderPreview = () => {
    if (!state.preview) {
      refs.previewBefore.textContent = '';
      refs.previewAfter.textContent = '';
      refs.previewDiff.textContent = '';
      refs.applyBtn.disabled = true;
      refs.cancelBtn.disabled = true;
      refs.briefBtn.disabled = true;
      return;
    }
    refs.previewBefore.textContent = state.preview.before || '';
    refs.previewAfter.textContent = state.preview.after || '';
    refs.previewDiff.textContent = state.preview.diff || '';
    refs.applyBtn.disabled = false;
    refs.cancelBtn.disabled = false;
    refs.briefBtn.disabled = false;
  };

  const renderCoauthorSections = () => {
    if (!refs.coauthorSection) return;
    const current = refs.coauthorSection.value;
    refs.coauthorSection.innerHTML = '';
    const anyOption = document.createElement('option');
    anyOption.value = '';
    anyOption.textContent = 'Whole document';
    refs.coauthorSection.appendChild(anyOption);
    state.sections.forEach((section) => {
      const option = document.createElement('option');
      option.value = section.id;
      option.textContent = section.title;
      refs.coauthorSection.appendChild(option);
    });
    if (current) {
      refs.coauthorSection.value = current;
    }
  };

  const renderCoauthorSuggestion = () => {
    const output = refs.coauthorOutput;
    output.innerHTML = '';
    if (!state.coauthorSuggestion) {
      output.textContent = 'Ask for guidance or a first draft.';
      return;
    }
    const { intent, constraints, draft } = state.coauthorSuggestion;
    const intentEl = document.createElement('p');
    intentEl.innerHTML = `<strong>Intent:</strong> ${intent}`;
    output.appendChild(intentEl);
    if (constraints?.length) {
      const list = document.createElement('ul');
      constraints.forEach((c) => {
        const li = document.createElement('li');
        li.textContent = c;
        list.appendChild(li);
      });
      output.appendChild(list);
    }
    if (draft) {
      const pre = document.createElement('pre');
      pre.textContent = draft;
      output.appendChild(pre);
    }
    const actions = document.createElement('div');
    actions.style.marginTop = '0.6rem';
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.textContent = 'Preview suggestion';
    btn.addEventListener('click', () => {
      const sectionId = refs.coauthorSection.value || (state.sections[0]?.id || '');
      previewSection(sectionId, intent, constraints || []);
    });
    actions.appendChild(btn);
    output.appendChild(actions);
  };

  const render = () => {
    renderPrompts();
    renderSuggestions();
    renderActionItems();
    renderSections();
    renderSummary();
    renderPreview();
    renderCoauthorSuggestion();
    renderWhisperStatus();
    renderLedgerStatus();
  };

  const loadSnapshot = async () => {
    if (!state.slug) return;
    const data = await fetchJSON(snapshotUrl());
    state.prompts = data.prompts || [];
    state.actionItems = data.action_items || [];
    state.sections = data.sections || [];
    state.summary = data.summary || {};
    render();
  };

  const loadWhisperStatus = async () => {
    try {
      const data = await fetchJSON('/api/ltp/status/whisper');
      state.whisperStatus = data;
      renderWhisperStatus();
    } catch (err) {
      console.warn('Whisper status unavailable', err);
      state.whisperStatus = { ok: false, reason: 'status_unavailable' };
      renderWhisperStatus();
    }
  };

  const loadLedgerStatus = async () => {
    try {
      const data = await fetchJSON('/api/system/ledger/status');
      state.ledgerStatus = data;
      renderLedgerStatus();
    } catch (err) {
      console.warn('Ledger status check failed', err);
    }
  };

  const tidyNow = async () => {
    if (!state.slug) return;
    const data = await fetchJSON(`/api/ltp/projects/${state.slug}/tidy`, { method: 'POST' });
    state.prompts = data.prompts || [];
    state.actionItems = data.action_items || [];
    state.sections = data.sections || [];
    state.summary = data.summary || state.summary;
    render();
  };

  const updateActionItem = async (index, done) => {
    if (!state.slug) return;
    const data = await fetchJSON(`/api/ltp/projects/${state.slug}/action-items`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ index, done }),
    });
    state.actionItems = data.action_items || [];
    renderActionItems();
  };

  const addActionItem = async () => {
    if (!state.slug) return;
    const title = refs.actionInput.value.trim();
    if (!title) return;
    refs.actionInput.value = '';
    const data = await fetchJSON(`/api/ltp/projects/${state.slug}/action-items`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ add: title }),
    });
    state.actionItems = data.action_items || [];
    renderActionItems();
  };

  const mergeToneConstraints = (constraints = []) => {
    const list = [...constraints];
    if (state.selectedTone) {
      list.push(state.selectedTone.instructions);
    }
    return list;
  };

  const previewSection = async (sectionId, intent, constraints) => {
    if (!state.slug || !sectionId) return;
    const mergedConstraints = mergeToneConstraints(constraints || []);
    state.previewRequest = { sectionId, intent, constraints: mergedConstraints };
    const data = await fetchJSON(`/api/ltp/projects/${state.slug}/sections/${sectionId}/preview`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ intent, constraints: mergedConstraints }),
    });
    state.preview = data;
    renderPreview();
  };

  const applyPreview = async () => {
    if (!state.previewRequest) return;
    const req = state.previewRequest;
    await fetchJSON(`/api/ltp/projects/${state.slug}/sections/${req.sectionId}/apply`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ intent: req.intent, constraints: req.constraints }),
    });
    state.preview = null;
    state.previewRequest = null;
    await loadSnapshot();
  };

  const cancelPreview = () => {
    state.preview = null;
    state.previewRequest = null;
    renderPreview();
  };

  const loadRevision = async () => {
    if (!state.slug) return;
    const data = await fetchJSON(`/api/ltp/projects/${state.slug}/revise`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sections: [] }),
    });
    state.suggestions = data.suggestions || [];
    renderSuggestions();
  };

  const exportDoc = async (kind) => {
    if (!state.slug) return;
    const data = await fetchJSON(`/api/ltp/projects/${state.slug}/export`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ kind }),
    });
    alert(`Exported to ${data.output}`);
  };

  const sendAudioBlob = async (blob) => {
    if (!state.slug) return;
    const form = new FormData();
    form.append('file', blob, `${state.slug}.webm`);
    const res = await fetch(`/api/ltp/projects/${state.slug}/voice`, { method: 'POST', body: form });
    if (!res.ok) throw new Error('transcription failed');
    const data = await res.json();
    state.prompts = data.prompts || [];
    state.actionItems = data.action_items || [];
    state.sections = data.sections || [];
    state.summary = data.summary || state.summary;
    render();
  };

  const startRecording = async () => {
    try {
      if (!navigator.mediaDevices) {
        alert('Microphone not available');
        return;
      }
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      const chunks = [];
      recorder.ondataavailable = (e) => chunks.push(e.data);
      recorder.onstop = async () => {
        stream.getTracks().forEach((track) => track.stop());
        const blob = new Blob(chunks, { type: 'audio/webm' });
        await sendAudioBlob(blob);
        refs.recordBtn.disabled = false;
        refs.stopBtn.disabled = true;
      };
      recorder.start();
      state.recording = recorder;
      refs.recordBtn.disabled = true;
      refs.stopBtn.disabled = false;
    } catch (err) {
      alert('Unable to start recording');
    }
  };

  const stopRecording = () => {
    if (!state.recording) return;
    state.recording.stop();
    state.recording = null;
  };

  const uploadAudio = () => refs.fileInput.click();

  const handleFileChange = async (event) => {
    const file = event.target.files[0];
    if (!file) return;
    event.target.value = '';
    try {
      await sendAudioBlob(file);
    } catch (err) {
      alert('Upload failed');
    }
  };

  const runQuickCheck = (item) => {
    if (!state.sections.length) return;
    let sectionId = item.section_hint && state.sections.find((section) => section.id === item.section_hint)?.id;
    if (!sectionId) {
      sectionId = state.sections[0].id;
    }
    previewSection(sectionId, item.intent, item.constraints || []);
  };

 const openTemplateModal = () => {
    refs.templateForm.reset();
    renderTemplates();
    refs.templateModal.hidden = false;
  };

  const closeTemplateModal = () => {
    refs.templateModal.hidden = true;
  };

  const handleCreateProject = async (event) => {
    event.preventDefault();
    const formData = new FormData(refs.templateForm);
    const title = (formData.get('title') || '').toString().trim();
    if (!title) {
      alert('Title is required');
      return;
    }
    const slug = (formData.get('slug') || '').toString().trim();
    const owners = (formData.get('owners') || '')
      .toString()
      .split(',')
      .map((item) => item.trim())
      .filter(Boolean);
    const tags = (formData.get('tags') || '')
      .toString()
      .split(',')
      .map((item) => item.trim())
      .filter(Boolean);
    const template = formData.get('template')?.toString() || null;
    const payload = {
      title,
      slug,
      owners,
      tags,
    };
    if (template) payload.template = template;
    const data = await fetchJSON('/api/ltp/projects', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    closeTemplateModal();
    await loadProjects();
    loadProject(data.slug);
  };

  const loadProject = (slug) => {
    state.slug = slug;
    app.dataset.slug = slug;
    refs.slugInput.value = slug;
    if (refs.projectSelect && slug) {
      refs.projectSelect.value = slug;
    }
    loadSnapshot();
  };

  const loadProjects = async () => {
    const data = await fetchJSON('/api/ltp/projects');
    state.projects = data.projects || [];
    renderProjects();
  };

  const loadMeta = async () => {
    const data = await fetchJSON('/api/ltp/templates');
    state.templates = data.templates || [];
    state.tonePresets = data.tones || [];
    state.quickChecks = data.quick_checks || [];
    renderToneChips();
    renderQuickChecks();
  };

  const composeBrief = async () => {
    if (!state.slug || !state.previewRequest) return;
    try {
      const payload = {
        intent: state.previewRequest.intent,
        constraints: state.previewRequest.constraints,
        sections: [state.previewRequest.sectionId],
        notes: state.selectedTone ? `Tone: ${state.selectedTone.instructions}` : undefined,
        request_plan: true,
      };
      const data = await fetchJSON(`/api/ltp/projects/${state.slug}/compose-brief`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      state.pendingBrief = data.brief;
      state.pendingBriefContext = data.context;
      refs.briefText.textContent = data.brief.text;
      refs.briefModal.hidden = false;
    } catch (err) {
      alert('Unable to compose brief');
    }
  };

  const closeBriefModal = () => {
    refs.briefModal.hidden = true;
  };

  const sendBriefToAce = async () => {
    // ACE interface has been removed. This action is disabled.
    alert('ACE is disabled in this build. Briefs are not sent to ACE.');
    return;
  };

  const runCoauthor = async () => {
    if (!state.slug) return;
    const prompt = refs.coauthorInput.value.trim();
    if (!prompt) {
      alert('Enter a prompt for the co-author.');
      return;
    }
    try {
      const payload = {
        prompt,
        section_id: refs.coauthorSection.value || undefined,
      };
      const data = await fetchJSON(`/api/ltp/projects/${state.slug}/coauthor`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      state.coauthorSuggestion = data.suggestion;
      renderCoauthorSuggestion();
    } catch (err) {
      alert('Co-author request failed');
    }
  };

  const attachEvents = () => {
    refs.loadBtn.addEventListener('click', () => {
      const slug = refs.slugInput.value.trim();
      if (!slug) return;
      if (!state.projects.find((p) => p.slug === slug)) {
        state.projects.unshift({ slug, title: slug, updated_at: '', owners: [], tags: [] });
        renderProjects();
      }
      loadProject(slug);
    });
    if (refs.projectSelect) {
      refs.projectSelect.addEventListener('change', (event) => {
        const value = event.target.value;
        if (value) loadProject(value);
      });
    }
    if (refs.projectNew) refs.projectNew.addEventListener('click', openTemplateModal);
    if (refs.templateClose) refs.templateClose.addEventListener('click', closeTemplateModal);
    if (refs.templateForm) refs.templateForm.addEventListener('submit', handleCreateProject);
    refs.tidyBtn.addEventListener('click', tidyNow);
    refs.reviseBtn.addEventListener('click', loadRevision);
    refs.exportPdf.addEventListener('click', () => exportDoc('pdf'));
    refs.exportDocx.addEventListener('click', () => exportDoc('docx'));
    refs.applyBtn.addEventListener('click', applyPreview);
    refs.cancelBtn.addEventListener('click', cancelPreview);
    refs.briefBtn.addEventListener('click', composeBrief);
    refs.briefClose.addEventListener('click', closeBriefModal);
    refs.briefSend.addEventListener('click', sendBriefToAce);
    refs.recordBtn.addEventListener('click', startRecording);
    refs.stopBtn.addEventListener('click', stopRecording);
    refs.uploadBtn.addEventListener('click', uploadAudio);
    refs.fileInput.addEventListener('change', handleFileChange);
    refs.actionAdd.addEventListener('click', addActionItem);
    refs.coauthorSend.addEventListener('click', runCoauthor);
    refs.modeButtons.forEach((btn) => {
      btn.addEventListener('click', () => setMode(btn.dataset.mode));
    });
  };

  const init = async () => {
    setMode(state.mode || 'draft');
    await Promise.all([loadMeta(), loadProjects()]);
    attachEvents();
    loadWhisperStatus();
    loadLedgerStatus();
    setInterval(loadWhisperStatus, 30000);
    setInterval(loadLedgerStatus, 60000);
    if (state.slug) {
      if (!state.projects.find((p) => p.slug === state.slug)) {
        state.projects.unshift({ slug: state.slug, title: state.slug, updated_at: '', owners: [], tags: [] });
        renderProjects();
      }
      loadSnapshot();
    } else {
      render();
    }
  };

  init().catch((err) => {
    console.error('Failed to initialize LTP UI', err);
  });
})();
