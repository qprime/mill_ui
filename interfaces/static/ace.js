(() => {
  const state = {
    machines: [],
    commands: [],
    history: [],
    currentRun: null,
    logTimer: null,
    refreshTimer: null,
    pendingBrief: null,
    activeTab: 'summary',
    artifactCache: new Map(),
  };

  const els = {
    form: document.getElementById('brief-form'),
    textarea: document.getElementById('brief-text'),
    mode: document.getElementById('brief-mode'),
    planSelect: document.getElementById('brief-plan'),
    machinesSelect: document.getElementById('brief-machines'),
    tags: document.getElementById('brief-tags'),
    model: document.getElementById('brief-model'),
    reasoning: document.getElementById('brief-reasoning'),
    notes: document.getElementById('brief-notes'),
    quickBar: document.querySelector('[data-role="quick-picks"]'),
    planCard: document.getElementById('plan-card'),
    planOutline: document.querySelector('[data-role="plan-outline"]'),
    composeCard: document.getElementById('compose-card'),
    runTitle: document.querySelector('[data-role="run-title"]'),
    runStatus: document.querySelector('[data-role="run-status"]'),
    runHeadline: document.querySelector('[data-role="run-headline"]'),
    runResult: document.querySelector('[data-role="run-result"]'),
    runPlan: document.querySelector('[data-role="run-plan"]'),
    runDiff: document.querySelector('[data-role="run-diff"]'),
    runArtifacts: document.querySelector('[data-role="run-artifacts"]'),
    runLog: document.querySelector('[data-role="run-log"]'),
    tabs: document.querySelector('[data-role="run-tabs"]'),
    historyList: document.querySelector('[data-role="history-list"]'),
    historyCount: document.querySelector('[data-role="history-count"]'),
    planConfirm: document.querySelector('[data-action="confirm-plan"]'),
    planCancel: document.querySelector('[data-action="cancel-plan"]'),
    micToggle: document.querySelector('[data-action="toggle-mic"]'),
    micIndicator: document.querySelector('[data-role="mic-indicator"]'),
    refreshBtn: document.querySelector('[data-action="refresh-history"]'),
    machinesBtn: document.querySelector('[data-action="open-machines"]'),
    machinesCard: document.getElementById('machines-card'),
    machineList: document.querySelector('[data-role="machine-list"]'),
    machineForm: document.getElementById('machine-form'),
    closeMachines: document.querySelector('[data-action="close-machines"]'),
    runCard: document.getElementById('run-card'),
    pushBtn: document.querySelector('[data-action="push-run"]'),
    rerunBtn: document.querySelector('[data-action="rerun"]'),
    ignoreBtn: document.querySelector('[data-action="ignore-run"]'),
    operateQuick: document.querySelector('[data-action="operate-quick"]'),
  };

  const api = (path, options = {}) => fetch(`/ace${path}`, {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  });

  function toJSON(res) {
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  }

  async function loadMachines() {
    const data = await api('/machines').then(toJSON);
    state.machines = data.machines || [];
    renderMachinesSelect();
    renderMachineList();
  }

  async function loadCommands() {
    const data = await api('/operate/commands').then(toJSON);
    state.commands = data.commands || [];
    renderQuickPicks();
  }

  async function loadHistory() {
    const data = await api('/history?limit=20').then(toJSON);
    state.history = data.runs || [];
    renderHistory();
  }

  function renderMachinesSelect() {
    els.machinesSelect.innerHTML = '';
    state.machines.forEach((machine) => {
      const opt = document.createElement('option');
      opt.value = machine.name;
      opt.textContent = machine.name;
      if (machine.name === 'skylink') opt.selected = true;
      els.machinesSelect.appendChild(opt);
    });
  }

  function renderQuickPicks() {
    els.quickBar.innerHTML = '';
    state.commands.forEach((cmd) => {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'ace-chip';
      btn.textContent = cmd.title;
      btn.title = cmd.description;
      btn.addEventListener('click', () => {
        els.mode.value = 'operate';
        els.textarea.value = cmd.id;
        els.planSelect.value = 'skip';
        focusTextarea();
      });
      els.quickBar.appendChild(btn);
    });
  }

  function renderHistory() {
    els.historyList.innerHTML = '';
    els.historyCount.textContent = state.history.length ? `${state.history.length} runs` : 'empty';
    state.history.forEach((run) => {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.innerHTML = `<strong>${run.brief?.text || 'Untitled'}</strong><span class="muted">${run.mode} · ${run.status} · ${run.updated_at}</span>`;
      btn.addEventListener('click', () => selectRun(run.id));
      els.historyList.appendChild(btn);
    });
  }

  function selectRun(runId) {
    loadRun(runId).catch(console.error);
  }

  async function loadRun(runId) {
    const data = await api(`/runs/${runId}/summary`).then(toJSON);
    const run = data.run;
    state.currentRun = run;
    renderRun(run);
    scheduleRunPolling(run.id);
  }

  function renderRun(run) {
    state.artifactCache.clear();
    els.runTitle.textContent = run.brief?.text || 'Ace run';
    els.runStatus.textContent = `${run.status} · ${run.updated_at}`;
    els.runHeadline.textContent = run.headline || '';
    els.runResult.textContent = run.result_summary || '';
    els.runPlan.textContent = run.plan_summary || '—';
    els.runDiff.textContent = '';
    els.runLog.textContent = '';
    renderArtifacts(run.artifacts || []);
    const running = run.status === 'running' || run.status === 'pending';
    els.pushBtn.disabled = run.mode !== 'build' || running;
    els.rerunBtn.disabled = running;
    els.ignoreBtn.disabled = running;
    state.activeTab = running ? 'system' : 'summary';
    activateTab(state.activeTab);
    if (!running) {
      stopPolling();
      fetchLog();
      if (run.diff_path) fetchDiff(run.diff_path).catch(() => {});
    }
  }

  function renderArtifacts(paths) {
    els.runArtifacts.innerHTML = '';
    if (!paths.length) {
      const li = document.createElement('li');
      li.textContent = 'No artifacts yet.';
      li.style.justifyContent = 'flex-start';
      els.runArtifacts.appendChild(li);
      return;
    }
    paths.forEach((path) => {
      const li = document.createElement('li');
      const span = document.createElement('span');
      span.textContent = path;
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.textContent = 'View';
      btn.addEventListener('click', () => loadArtifact(path, li));
      li.appendChild(span);
      li.appendChild(btn);
      els.runArtifacts.appendChild(li);
    });
  }

  function activateTab(tab) {
    state.activeTab = tab;
    els.tabs.querySelectorAll('button').forEach((btn) => {
      const active = btn.dataset.tab === tab;
      btn.classList.toggle('active', active);
    });
    document.querySelectorAll('.ace-tab-content').forEach((panel) => {
      panel.hidden = panel.dataset.tabContent !== tab;
    });
    if (tab === 'diff' && state.currentRun?.diff_path) {
      fetchDiff(state.currentRun.diff_path).catch(() => {});
    }
    if (tab === 'system') {
      fetchLog();
    }
    if (tab === 'plan') {
      maybeFetchPlan();
    }
  }

  async function fetchDiff(path) {
    if (!state.currentRun) return;
    const res = await api(`/runs/${state.currentRun.id}/file?path=${encodeURIComponent(path)}`);
    if (!res.ok) throw new Error('diff load failed');
    const text = await res.text();
    els.runDiff.textContent = text;
  }

  async function maybeFetchPlan() {
    if (!state.currentRun) return;
    if (state.currentRun.plan_summary) return; // already present
    const candidate = (state.currentRun.artifacts || []).find((p) => /plan\.txt$/.test(p));
    if (!candidate) return;
    try {
      const res = await api(`/runs/${state.currentRun.id}/file?path=${encodeURIComponent(candidate)}`);
      if (res.ok) {
        const text = await res.text();
        els.runPlan.textContent = text;
        state.currentRun.plan_summary = text;
      }
    } catch (err) {
      console.warn(err);
    }
  }

  async function loadArtifact(path, li) {
    if (!state.currentRun) return;
    try {
      let text = state.artifactCache.get(path);
      if (!text) {
        const res = await api(`/runs/${state.currentRun.id}/file?path=${encodeURIComponent(path)}`);
        if (!res.ok) throw new Error('artifact fetch failed');
        text = await res.text();
        state.artifactCache.set(path, text);
      }
      let pre = li.querySelector('pre');
      if (!pre) {
        pre = document.createElement('pre');
        pre.className = 'ace-pre';
        li.appendChild(pre);
      }
      pre.textContent = text;
    } catch (err) {
      console.error(err);
    }
  }

  function scheduleRunPolling(runId) {
    stopPolling();
    state.logTimer = setInterval(fetchLog, 2500);
    state.refreshTimer = setInterval(async () => {
      try {
        const data = await api(`/runs/${runId}/summary`).then(toJSON);
        state.currentRun = data.run;
        renderRun(data.run);
        if (data.run.status !== 'running' && data.run.status !== 'pending') {
          stopPolling();
        }
      } catch (err) {
        console.error(err);
      }
    }, 3000);
  }

  function stopPolling() {
    if (state.logTimer) clearInterval(state.logTimer);
    if (state.refreshTimer) clearInterval(state.refreshTimer);
    state.logTimer = state.refreshTimer = null;
  }

  async function fetchLog() {
    if (!state.currentRun) return;
    try {
      const res = await api(`/runs/${state.currentRun.id}/stream`);
      if (!res.ok) return;
      els.runLog.textContent = await res.text();
    } catch (err) {
      console.error(err);
    }
  }

  function formToPayload(execute = true) {
    const machines = Array.from(els.machinesSelect.selectedOptions).map((opt) => opt.value);
    const tags = (els.tags.value || '')
      .split(/[,\s]+/)
      .map((t) => t.trim())
      .filter(Boolean);
    const brief = {
      mode: els.mode.value,
      text: els.textarea.value.trim(),
      machines: machines.length ? machines : ['skylink'],
      tags,
      plan_preview: els.planSelect.value,
    };
    if (els.model.value) brief.model = els.model.value.trim();
    if (els.reasoning.value) brief.reasoning = els.reasoning.value;
    if (els.notes.value.trim()) brief.notes = els.notes.value.trim();
    return {
      brief,
      execute,
    };
  }

  async function submitBrief(execute) {
    if (!els.textarea.value.trim()) return;
    const payload = formToPayload(execute);
    state.pendingBrief = payload;
    try {
      const res = await api('/runs', {
        method: 'POST',
        body: JSON.stringify(payload),
      });
      if (res.status === 202) {
        const data = await res.json();
        showPlan(data.plan_outline || []);
        return;
      }
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      hidePlan();
      state.pendingBrief = null;
      await loadHistory();
      selectRun(data.run.id);
    } catch (err) {
      console.error(err);
    }
  }

  function showPlan(items) {
    els.planOutline.textContent = (items || []).map((line, idx) => `${idx + 1}. ${line}`).join('\n');
    els.planCard.hidden = false;
    els.composeCard.classList.add('blurred');
  }

  function hidePlan() {
    els.planCard.hidden = true;
    els.composeCard.classList.remove('blurred');
  }

  function focusTextarea() {
    els.textarea.focus({ preventScroll: false });
  }

  function setupEvents() {
    els.form.addEventListener('submit', (event) => {
      event.preventDefault();
      const wantsPlan = els.planSelect.value === 'show';
      submitBrief(!wantsPlan).catch(console.error);
    });

    els.planConfirm.addEventListener('click', () => {
      if (!state.pendingBrief) return;
      submitBrief(true).catch(console.error);
    });

    els.planCancel.addEventListener('click', () => {
      hidePlan();
      state.pendingBrief = null;
    });

    if (els.refreshBtn) {
      els.refreshBtn.addEventListener('click', () => loadHistory().catch(console.error));
    }

    if (els.tabs) {
      els.tabs.addEventListener('click', (event) => {
        const button = event.target.closest('button[data-tab]');
        if (!button) return;
        activateTab(button.dataset.tab);
      });
    }

    if (els.pushBtn) {
      els.pushBtn.addEventListener('click', () => {
        if (!state.currentRun) return;
        els.pushBtn.disabled = true;
        api(`/runs/${state.currentRun.id}/push`, { method: 'POST', body: JSON.stringify({}) })
          .then((res) => res.json().catch(() => ({})))
          .then((result) => {
            els.pushBtn.disabled = false;
            if (result.ok) {
              fetchLog();
            } else {
              alert(`Push failed: ${result.error || result.stderr || 'unknown error'}`);
            }
          })
          .catch((err) => {
            els.pushBtn.disabled = false;
            console.error(err);
          });
      });
    }

    if (els.rerunBtn) {
      els.rerunBtn.addEventListener('click', () => {
        if (!state.currentRun) return;
        api(`/runs/${state.currentRun.id}/rerun`, { method: 'POST', body: JSON.stringify({}) })
          .then(toJSON)
          .then((data) => {
            loadHistory();
            selectRun(data.run.id);
          })
          .catch(console.error);
      });
    }

    if (els.ignoreBtn) {
      els.ignoreBtn.addEventListener('click', () => {
        if (!state.currentRun) return;
        api(`/runs/${state.currentRun.id}/ignore`, { method: 'POST', body: JSON.stringify({}) })
          .then(toJSON)
          .then((data) => {
            state.currentRun = data.run;
            renderRun(data.run);
            loadHistory();
          })
          .catch(console.error);
      });
    }

    if (els.machinesBtn) {
      els.machinesBtn.addEventListener('click', () => {
        els.machinesCard.hidden = false;
      });
    }

    if (els.closeMachines) {
      els.closeMachines.addEventListener('click', () => {
        els.machinesCard.hidden = true;
      });
    }

    if (els.machineForm) {
      els.machineForm.addEventListener('submit', (event) => {
        event.preventDefault();
        const formData = new FormData(els.machineForm);
        const payload = Object.fromEntries(formData.entries());
        if (!payload.name || !payload.workspace) return;
        api('/machines', { method: 'POST', body: JSON.stringify(payload) })
          .then(toJSON)
          .then(() => {
            els.machineForm.reset();
            loadMachines();
          })
          .catch(console.error);
      });
    }

    if (els.operateQuick) {
      els.operateQuick.addEventListener('click', () => {
        els.mode.value = 'operate';
        els.planSelect.value = 'skip';
        focusTextarea();
      });
    }

    setupMicrophone();
  }

  function renderMachineList() {
    if (!els.machineList) return;
    els.machineList.innerHTML = '';
    state.machines.forEach((m) => {
      const li = document.createElement('li');
      li.innerHTML = `<div><strong>${m.name}</strong><div class="muted">${m.type} · ${m.workspace}</div></div>`;
      const del = document.createElement('button');
      del.type = 'button';
      del.className = 'ghost';
      del.textContent = 'Delete';
      del.addEventListener('click', () => {
        api(`/machines/${encodeURIComponent(m.name)}`, { method: 'DELETE' })
          .then(() => loadMachines())
          .catch(console.error);
      });
      li.appendChild(del);
      els.machineList.appendChild(li);
    });
  }

  function setupMicrophone() {
    if (!('webkitSpeechRecognition' in window || 'SpeechRecognition' in window)) {
      els.micIndicator.textContent = 'Voice unavailable';
      els.micToggle.disabled = true;
      return;
    }
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    const recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = true;
    let active = false;

    recognition.onresult = (event) => {
      const transcript = Array.from(event.results)
        .map((result) => result[0]?.transcript || '')
        .join(' ');
      els.textarea.value = `${els.textarea.value} ${transcript}`.trim();
    };
    recognition.onstart = () => {
      active = true;
      els.micToggle.textContent = '🛑 Stop';
      els.micToggle.setAttribute('aria-pressed', 'true');
      els.micIndicator.textContent = 'Listening…';
    };
    recognition.onend = () => {
      active = false;
      els.micToggle.textContent = '🎙 Start';
      els.micToggle.setAttribute('aria-pressed', 'false');
      els.micIndicator.textContent = 'Mic off';
    };

    els.micToggle.addEventListener('click', () => {
      if (active) {
        recognition.stop();
      } else {
        try {
          recognition.start();
        } catch (err) {
          console.error(err);
        }
      }
    });
  }

  function init() {
    setupEvents();
    Promise.all([loadMachines(), loadCommands(), loadHistory()]).catch(console.error);
  }

  init();
})();
