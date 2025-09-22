(() => {
  const LOG_THRESHOLD = 60000;
  const DIFF_THRESHOLD = 40000;
  const ARTIFACT_THRESHOLD = 20000;

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
    eventSource: null,
    sseActive: false,
    policy: {
      map: {},
      known: [],
      values: ['accept', 'verify', 'escalate'],
    },
    ledgerStatus: { needs_compaction: false, size_mb: 0, threshold_mb: 0 },
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
    commitBtn: document.querySelector('[data-action="commit-run"]'),
    rerunBtn: document.querySelector('[data-action="rerun"]'),
    ignoreBtn: document.querySelector('[data-action="ignore-run"]'),
    operateQuick: document.querySelector('[data-action="operate-quick"]'),
    policyCard: document.getElementById('policy-card'),
    policyList: document.querySelector('[data-role="policy-list"]'),
    policyEmpty: document.querySelector('[data-role="policy-empty"]'),
    policyAddForm: document.getElementById('policy-add-form'),
    policyRefresh: document.querySelector('[data-action="refresh-policy"]'),
    ledgerAlert: document.getElementById('ace-ledger-alert'),
  };

  const api = (path, options = {}) => fetch(`/ace${path}`, {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  });

  function toJSON(res) {
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  }

  function renderExpandable(preEl, text, threshold = 50000) {
    if (!preEl) return;
    const toggleId = preEl.dataset.toggleId;
    let toggle = toggleId ? document.getElementById(toggleId) : null;
    const content = text || '';
    if (!content || content.length <= threshold) {
      preEl.textContent = content;
      preEl.dataset.expanded = 'true';
      if (toggle) {
        toggle.remove();
        delete preEl.dataset.toggleId;
      }
      return;
    }
    if (!toggle) {
      toggle = document.createElement('button');
      const id = `expander-${Math.random().toString(36).slice(2)}`;
      toggle.id = id;
      toggle.type = 'button';
      toggle.className = 'ace-expander';
      preEl.dataset.toggleId = id;
      preEl.after(toggle);
    }
    if (!preEl.dataset.expanded) {
      preEl.dataset.expanded = 'false';
    }
    const apply = () => {
      const expanded = preEl.dataset.expanded === 'true';
      if (expanded) {
        preEl.textContent = content;
        toggle.textContent = 'Show less';
      } else {
        preEl.textContent = `${content.slice(0, threshold)}\n…`;
        toggle.textContent = 'Show more';
      }
    };
    toggle.onclick = () => {
      preEl.dataset.expanded = preEl.dataset.expanded === 'true' ? 'false' : 'true';
      apply();
    };
    apply();
  }

  function disconnectLogStream() {
    if (state.eventSource) {
      state.eventSource.close();
      state.eventSource = null;
    }
    state.sseActive = false;
  }

  function connectLogStream(runId) {
    if (!('EventSource' in window)) return false;
    disconnectLogStream();
    try {
      const es = new EventSource(`/ace/runs/${runId}/sse`);
      state.eventSource = es;
      state.sseActive = false;
      es.addEventListener('log', (evt) => {
        try {
          const payload = JSON.parse(evt.data || '{}');
          renderExpandable(els.runLog, payload.text || '', LOG_THRESHOLD);
          state.sseActive = true;
        } catch (err) {
          console.error(err);
        }
      });
      es.addEventListener('heartbeat', () => {});
      es.onerror = () => {
        es.close();
        state.eventSource = null;
        state.sseActive = false;
        if (!state.logTimer) {
          state.logTimer = setInterval(fetchLog, 2500);
          fetchLog().catch(() => {});
        }
      };
      return true;
    } catch (err) {
      console.warn('SSE connection failed', err);
      return false;
    }
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

  async function loadPolicy() {
    try {
      const data = await api('/operate/policy').then(toJSON);
      state.policy.map = data.policy || {};
      state.policy.known = Array.isArray(data.known_types) ? data.known_types : [];
      state.policy.values = Array.isArray(data.values) ? data.values : state.policy.values;
      renderPolicy();
    } catch (err) {
      console.error('Failed to load operate policy', err);
    }
  }

  async function loadLedgerStatus() {
    try {
      const res = await fetch('/api/system/ledger/status');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      state.ledgerStatus = await res.json();
      renderLedgerStatus();
    } catch (err) {
      console.warn('Ledger status unavailable', err);
    }
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

  function renderPolicy() {
    if (!els.policyList) return;
    const known = state.policy.known || [];
    els.policyList.innerHTML = '';
    if (els.policyEmpty) {
      els.policyEmpty.hidden = known.length > 0;
    }
    known.sort().forEach((type) => {
      const row = document.createElement('div');
      row.className = 'ace-policy-row';
      const label = document.createElement('span');
      label.textContent = type;
      const select = document.createElement('select');
      const current = (state.policy.map && state.policy.map[type]) || 'accept';
      (state.policy.values || ['accept', 'verify', 'escalate']).forEach((value) => {
        const opt = document.createElement('option');
        opt.value = value;
        opt.textContent = value;
        if (current === value) {
          opt.selected = true;
        }
        select.appendChild(opt);
      });
      select.addEventListener('change', async () => {
        try {
          await api('/operate/policy', {
            method: 'PATCH',
            body: JSON.stringify({ [type]: select.value }),
          }).then(toJSON);
          state.policy.map[type] = select.value;
        } catch (err) {
          console.error('Failed to update operate policy', err);
        }
      });
      row.appendChild(label);
      row.appendChild(select);
      els.policyList.appendChild(row);
    });
  }

  function renderLedgerStatus() {
    if (!els.ledgerAlert) return;
    const status = state.ledgerStatus || {};
    if (!status.needs_compaction) {
      els.ledgerAlert.hidden = true;
      els.ledgerAlert.textContent = '';
      return;
    }
    const size = status.size_mb ?? 0;
    const threshold = status.threshold_mb ?? 0;
    els.ledgerAlert.hidden = false;
    els.ledgerAlert.textContent = `Ledger at ${size} MB of ${threshold} MB – consider compaction.`;
    const link = document.createElement('a');
    link.href = '/chat';
    link.textContent = 'Open chat';
    link.style.marginLeft = 'auto';
    link.target = '_blank';
    els.ledgerAlert.appendChild(link);
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
    renderExpandable(els.runDiff, '', DIFF_THRESHOLD);
    renderExpandable(els.runLog, '', LOG_THRESHOLD);
    renderArtifacts(run.artifacts || []);
    const running = run.status === 'running' || run.status === 'pending';
    els.pushBtn.disabled = run.mode !== 'build' || running;
    if (els.commitBtn) {
      els.commitBtn.disabled = run.mode !== 'build' || running;
    }
    els.rerunBtn.disabled = running;
    els.ignoreBtn.disabled = running;
    state.activeTab = running ? 'system' : 'summary';
    activateTab(state.activeTab);
    if (!running) {
      stopPolling();
      fetchLog().catch(() => {});
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
      fetchLog().catch(() => {});
    }
    if (tab === 'plan') {
      maybeFetchPlan();
    }
  }

  async function fetchDiff(path) {
    if (!state.currentRun) return;
    try {
      const res = await api(`/runs/${state.currentRun.id}/file?path=${encodeURIComponent(path)}`);
      if (!res.ok) throw new Error('diff load failed');
      const text = await res.text();
      renderExpandable(els.runDiff, text, DIFF_THRESHOLD);
    } catch (err) {
      console.error(err);
    }
  }

  async function maybeFetchPlan() {
    if (!state.currentRun) return;
    if (state.currentRun.plan_summary) return;
    const candidate = (state.currentRun.artifacts || []).find((p) => /plan\.txt$/.test(p));
    if (!candidate) return;
    try {
      const res = await api(`/runs/${state.currentRun.id}/file?path=${encodeURIComponent(candidate)}`);
      if (res.ok) {
        const text = await res.text();
        els.runPlan.textContent = text;
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
      renderExpandable(pre, text, ARTIFACT_THRESHOLD);
    } catch (err) {
      console.error(err);
    }
  }

  function scheduleRunPolling(runId) {
    stopPolling();
    const usingSSE = connectLogStream(runId);
    if (!usingSSE) {
      if (!state.logTimer) {
        state.logTimer = setInterval(fetchLog, 2500);
      }
    }
    fetchLog().catch(() => {});
    state.refreshTimer = setInterval(async () => {
      try {
        const data = await api(`/runs/${runId}/summary`).then(toJSON);
        if (!state.currentRun || state.currentRun.id !== runId) return;
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
    if (state.logTimer) {
      clearInterval(state.logTimer);
      state.logTimer = null;
    }
    if (state.refreshTimer) {
      clearInterval(state.refreshTimer);
      state.refreshTimer = null;
    }
    disconnectLogStream();
  }

  async function fetchLog() {
    if (!state.currentRun) return;
    try {
      const res = await api(`/runs/${state.currentRun.id}/stream`);
      if (!res.ok) return;
      const text = await res.text();
      renderExpandable(els.runLog, text, LOG_THRESHOLD);
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
      const data = await res.json();
      state.pendingBrief = null;
      hidePlan();
      if (data.run) {
        loadHistory();
        selectRun(data.run.id);
      }
    } catch (err) {
      console.error(err);
    }
  }

  function showPlan(items) {
    const numbered = (items || []).map((line, idx) => `${idx + 1}. ${line}`);
    els.planOutline.textContent = numbered.join('\n');
    els.planCard.hidden = false;
    els.composeCard.classList.add('blurred');
  }

  function hidePlan() {
    els.planCard.hidden = true;
    els.composeCard.classList.remove('blurred');
    els.planOutline.textContent = '';
  }

  function focusTextarea() {
    els.textarea.focus();
  }

  function setupEvents() {
    if (els.form) {
      els.form.addEventListener('submit', (event) => {
        event.preventDefault();
        const wantsPlan = els.planSelect.value === 'show';
        submitBrief(!wantsPlan).catch(console.error);
      });
    }

    if (els.planConfirm) {
      els.planConfirm.addEventListener('click', () => {
        if (!state.pendingBrief) return;
        submitBrief(true).catch(console.error);
      });
    }

    if (els.planCancel) {
      els.planCancel.addEventListener('click', () => {
        hidePlan();
        state.pendingBrief = null;
      });
    }

    if (els.refreshBtn) {
      els.refreshBtn.addEventListener('click', () => {
        loadHistory().catch(console.error);
      });
    }

    if (els.tabs) {
      els.tabs.addEventListener('click', (event) => {
        const target = event.target.closest('button[data-tab]');
        if (!target) return;
        activateTab(target.dataset.tab);
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

    if (els.commitBtn) {
      els.commitBtn.addEventListener('click', () => {
        if (!state.currentRun) return;
        const messageInput = prompt('Commit message', `Ace run ${state.currentRun.id}`);
        if (messageInput === null) {
          return;
        }
        const message = messageInput.trim() || `Ace run ${state.currentRun.id}`;
        els.commitBtn.disabled = true;
        api(`/runs/${state.currentRun.id}/commit`, { method: 'POST', body: JSON.stringify({ message }) })
          .then((res) => res.json().catch(() => ({})))
          .then((result) => {
            els.commitBtn.disabled = false;
            if (!result.ok) {
              alert(result.stderr || result.error || 'Commit failed');
            } else {
              alert('Commit created');
              loadHistory().catch(console.error);
              if (state.currentRun) {
                api(`/runs/${state.currentRun.id}/summary`)
                  .then(toJSON)
                  .then((data) => {
                    state.currentRun = data.run;
                    renderRun(data.run);
                  })
                  .catch(console.error);
              }
            }
            if (result.log_path) {
              fetchLog().catch(() => {});
            }
          })
          .catch((err) => {
            els.commitBtn.disabled = false;
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

    if (els.policyRefresh) {
      els.policyRefresh.addEventListener('click', () => {
        loadPolicy();
      });
    }

    if (els.policyAddForm) {
      els.policyAddForm.addEventListener('submit', (event) => {
        event.preventDefault();
        const formData = new FormData(els.policyAddForm);
        const commandType = (formData.get('command_type') || '').toString().trim();
        const value = (formData.get('value') || '').toString();
        if (!commandType || !value) return;
        api('/operate/policy', {
          method: 'PATCH',
          body: JSON.stringify({ [commandType]: value }),
        })
          .then(toJSON)
          .then((data) => {
            state.policy.map = data.policy || state.policy.map;
            if (!state.policy.known.includes(commandType)) {
              state.policy.known.push(commandType);
            }
            renderPolicy();
            els.policyAddForm.reset();
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
    Promise.all([
      loadMachines(),
      loadCommands(),
      loadHistory(),
      loadPolicy(),
      loadLedgerStatus(),
    ]).catch(console.error);
    setInterval(loadLedgerStatus, 60000);
  }

  init();
})();
