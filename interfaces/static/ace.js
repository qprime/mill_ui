(() => {
  const STATUS_PENDING = new Set(['pending', 'running']);

  const state = {
    machines: [],
    history: [],
    messages: [],
    policy: [],
    streams: new Map(),
    cache: new Map(),
    pendingPlan: null,
    currentRunId: null,
    threadId: null,
    conversation: [],
  };

  const els = {
    chatLog: document.querySelector('[data-role="chat-log"]'),
    form: document.getElementById('chat-form'),
    input: document.getElementById('chat-input'),
    includeContext: document.getElementById('include-context'),
    includeCode: document.getElementById('include-code'),
    contextScope: document.getElementById('context-scope'),
    contextPersona: document.getElementById('context-persona'),
    machineSelect: document.getElementById('machine-select'),
    modelInput: document.getElementById('model-input'),
    reasoningSelect: document.getElementById('reasoning-select'),
    tagsInput: document.getElementById('tags-input'),
    history: document.querySelector('[data-role="history"]'),
    machineList: document.querySelector('[data-role="machine-list"]'),
    policyList: document.querySelector('[data-role="policy"]'),
  };

  const api = (path, options = {}) => fetch(`/ace${path}`, {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  });

  function escapeHtml(str = '') {
    return str.replace(/[&<>"']/g, (ch) => ({
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      '"': '&quot;',
      "'": '&#39;',
    }[ch] || ch));
  }

  function parseTags(raw) {
    return (raw || '')
      .split(/[,\s]+/)
      .map((t) => t.replace(/^#+/, '').trim())
      .filter(Boolean);
  }

  function badge(status) {
    if (!status) return null;
    const span = document.createElement('span');
    span.className = 'badge';
    span.textContent = status;
    if (status === 'succeeded') span.classList.add('success');
    else if (status === 'failed' || status === 'cancelled') span.classList.add('error');
    else span.classList.add('pending');
    return span;
  }

  function toJSON(res) {
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  }

  function notify(text, variant = 'system') {
    state.messages.push({
      id: `system-${Date.now()}`,
      role: 'system',
      text,
      variant,
      createdAt: new Date().toISOString(),
    });
    renderMessages();
  }

  function addUserMessage(content) {
    const msg = {
      id: `user-${Date.now()}`,
      role: 'user',
      type: 'chat',
      text: content,
      createdAt: new Date().toISOString(),
    };
    state.messages.push(msg);
    renderMessages(true);
    state.conversation.push({ role: 'user', content });
    return msg;
  }

  function ensureRunMessage(run) {
    let message = state.messages.find((m) => m.runId === run.id);
    if (!message) {
      message = {
        id: `run-${run.id}`,
        role: 'assistant',
        runId: run.id,
        createdAt: run.created_at,
      };
      state.messages.push(message);
    }
    return message;
  }

  function updateMessageFromRun(run) {
    if (run.mode === 'ideate') {
      let assistantMessage = state.messages.find((m) => m.runId === run.id && m.type === 'chat' && m.role === 'assistant');
      if (!assistantMessage) {
        assistantMessage = {
          id: `assistant-${run.id}`,
          role: 'assistant',
          type: 'chat',
          runId: run.id,
          createdAt: run.updated_at,
          status: run.status,
          text: '',
        };
        state.messages.push(assistantMessage);
      }
      const responseText = run.result_summary || '';
      assistantMessage.text = responseText;
      assistantMessage.status = run.status;
      const lastEntry = state.conversation[state.conversation.length - 1];
      if (!lastEntry || lastEntry.role !== 'assistant' || lastEntry.content !== responseText) {
        state.conversation.push({ role: 'assistant', content: responseText });
      }
      state.currentRunId = run.id;
      renderMessages(true);
      updateHistoryEntry(run);
      return;
    }
    const msg = ensureRunMessage(run);
    msg.run = run;
    msg.status = run.status;
    msg.headline = run.headline || '';
    msg.result = run.result_summary || '';
    msg.planSummary = run.plan_summary || '';
    msg.diffPath = run.diff_path || null;
    msg.promptPath = run.prompt_path || null;
    msg.logPath = run.log_path || null;
    msg.artifacts = Array.isArray(run.artifacts) ? run.artifacts.slice() : [];
    msg.tags = Array.isArray(run.tags) ? run.tags.slice() : [];
    msg.commands = Array.isArray(run.commands) ? run.commands.slice() : [];
    msg.tests = Array.isArray(run.tests) ? run.tests.slice() : [];
    msg.notes = run.notes || '';
    msg.contextRequests = Array.isArray(run.context_requests) ? run.context_requests.slice() : [];
    msg.updatedAt = run.updated_at;
    state.currentRunId = run.id;
    renderMessages();
  }

  function renderMessages(scroll = false) {
    if (!els.chatLog) return;
    els.chatLog.innerHTML = '';
    const frag = document.createDocumentFragment();
    for (const message of state.messages) {
      frag.appendChild(renderMessage(message));
    }
    els.chatLog.appendChild(frag);
    if (scroll) {
      requestAnimationFrame(() => {
        els.chatLog.scrollTop = els.chatLog.scrollHeight;
      });
    }
    renderHistory();
  }

  function renderMessage(message) {
    const article = document.createElement('article');
    article.className = 'msg';
    article.dataset.messageId = message.id;
    if (message.role === 'user') article.classList.add('msg-user');
    if (message.role === 'system') {
      article.classList.add('msg-system');
      if (message.variant === 'error') {
        article.classList.add('msg-error');
      } else if (message.variant === 'success') {
        article.classList.add('msg-success');
      }
    }
    if (message.runId) article.dataset.runId = message.runId;

    const header = document.createElement('div');
    header.className = 'msg-header';
    const who = document.createElement('strong');
    who.textContent = message.role === 'user' ? 'You' : (message.role === 'assistant' ? 'ACE' : 'System');
    header.appendChild(who);
    if (message.status) {
      const b = badge(message.status);
      if (b) header.appendChild(b);
    }
    if (message.createdAt) {
      const meta = document.createElement('span');
      meta.textContent = new Date(message.createdAt).toLocaleTimeString();
      header.appendChild(meta);
    }
    article.appendChild(header);

    const body = document.createElement('div');
    body.className = 'msg-body';

    if (message.role === 'user' || message.role === 'system') {
      const p = document.createElement('p');
      p.innerHTML = escapeHtml(message.text);
      body.appendChild(p);
    } else if (message.type === 'chat') {
      const bubble = document.createElement('div');
      bubble.className = 'chat-bubble';
      bubble.innerHTML = escapeHtml(message.text);
      body.appendChild(bubble);
    } else if (message.type === 'plan') {
      const section = document.createElement('div');
      section.className = 'msg-section';
      const title = document.createElement('h3');
      title.textContent = 'Plan Preview';
      section.appendChild(title);
      const outline = document.createElement('pre');
      outline.textContent = (message.planOutline || []).join('\n');
      section.appendChild(outline);
      body.appendChild(section);
      const actions = document.createElement('div');
      actions.className = 'msg-actions';
      const approve = document.createElement('button');
      approve.dataset.action = 'approve-plan';
      approve.textContent = 'Approve & Run';
      actions.appendChild(approve);
      const cancel = document.createElement('button');
      cancel.dataset.action = 'cancel-plan';
      cancel.className = 'neutral';
      cancel.textContent = 'Cancel';
      actions.appendChild(cancel);
      body.appendChild(actions);
    } else {
      const summary = document.createElement('div');
      summary.className = 'msg-section';
      const title = document.createElement('h3');
      title.textContent = `Run ${message.runId}`;
      summary.appendChild(title);
      if (message.headline) {
        const headline = document.createElement('p');
        headline.textContent = message.headline;
        summary.appendChild(headline);
      }
      if (message.result) {
        const result = document.createElement('p');
        result.textContent = message.result;
        summary.appendChild(result);
      }
      if (message.tags && message.tags.length) {
        const tagsWrap = document.createElement('p');
        message.tags.forEach((tag) => {
          const span = document.createElement('span');
          span.className = 'tag-chip';
          span.textContent = tag.startsWith('#') ? tag : `#${tag}`;
          tagsWrap.appendChild(span);
        });
        summary.appendChild(tagsWrap);
      }
      if (message.providerPlan && message.providerPlan.length) {
        const prov = document.createElement('p');
        prov.className = 'muted';
        const providers = message.providerPlan.map((plan) => plan.name || plan.provider || '?');
        prov.textContent = `Routing: ${providers.join(' → ')}`;
        summary.appendChild(prov);
      }
      body.appendChild(summary);

      if (message.planSummary) {
        const plan = document.createElement('div');
        plan.className = 'msg-section';
        const titlePlan = document.createElement('h3');
        titlePlan.textContent = 'Plan';
        plan.appendChild(titlePlan);
        const pre = document.createElement('pre');
        pre.textContent = message.planSummary;
        plan.appendChild(pre);
        if (message.planText) {
          const full = document.createElement('pre');
          full.textContent = message.planText;
          plan.appendChild(full);
        }
        const btn = document.createElement('button');
        btn.dataset.action = 'open-plan';
        btn.className = 'neutral';
        btn.textContent = message.planText ? 'Hide full plan' : 'View full plan';
        plan.appendChild(btn);
        body.appendChild(plan);
      }

      if (message.diffPath) {
        const diff = document.createElement('div');
        diff.className = 'msg-section';
        const titleDiff = document.createElement('h3');
        titleDiff.textContent = 'Patch';
        diff.appendChild(titleDiff);
        if (message.diffText) {
          const pre = document.createElement('pre');
          pre.textContent = message.diffText;
          diff.appendChild(pre);
        }
        const view = document.createElement('button');
        view.dataset.action = 'open-diff';
        view.className = 'neutral';
        view.textContent = message.diffText ? 'Hide diff' : 'View diff';
        diff.appendChild(view);
        body.appendChild(diff);
      }

      if (message.commands && message.commands.length) {
        const commands = document.createElement('div');
        commands.className = 'msg-section';
        const titleCmd = document.createElement('h3');
        titleCmd.textContent = 'Commands';
        commands.appendChild(titleCmd);
        const list = document.createElement('ul');
        list.className = 'artifact-list';
        message.commands.forEach((cmd) => {
          const li = document.createElement('li');
          li.textContent = cmd;
          list.appendChild(li);
        });
        commands.appendChild(list);
        body.appendChild(commands);
      }

      if (message.tests && message.tests.length) {
        const tests = document.createElement('div');
        tests.className = 'msg-section';
        const titleTests = document.createElement('h3');
        titleTests.textContent = 'Tests';
        tests.appendChild(titleTests);
        const list = document.createElement('ul');
        list.className = 'artifact-list';
        message.tests.forEach((cmd) => {
          const li = document.createElement('li');
          li.textContent = cmd;
          list.appendChild(li);
        });
        tests.appendChild(list);
        body.appendChild(tests);
      }

      if (message.notes && message.notes !== message.result) {
        const notes = document.createElement('div');
        notes.className = 'msg-section';
        const titleNotes = document.createElement('h3');
        titleNotes.textContent = 'Notes';
        notes.appendChild(titleNotes);
        const pre = document.createElement('pre');
        pre.textContent = message.notes;
        notes.appendChild(pre);
        body.appendChild(notes);
      }

      if (message.contextRequests && message.contextRequests.length) {
        const ctx = document.createElement('div');
        ctx.className = 'msg-section';
        const titleCtx = document.createElement('h3');
        titleCtx.textContent = 'Context';
        ctx.appendChild(titleCtx);
        const list = document.createElement('ul');
        list.className = 'artifact-list';
        message.contextRequests.forEach((req) => {
          const li = document.createElement('li');
          const status = req.status || 'unknown';
          li.textContent = `${status.toUpperCase()} • ${req.path}`;
          list.appendChild(li);
        });
        ctx.appendChild(list);
        body.appendChild(ctx);
      }

      if (message.prompt && !Array.isArray(message.prompt)) {
        const prompt = document.createElement('div');
        prompt.className = 'msg-section';
        const titlePrompt = document.createElement('h3');
        titlePrompt.textContent = 'Prompt Manifest';
        prompt.appendChild(titlePrompt);
        const pre = document.createElement('pre');
        pre.textContent = JSON.stringify(message.prompt, null, 2);
        prompt.appendChild(pre);
        body.appendChild(prompt);
      }

      if (message.artifacts && message.artifacts.length) {
        const artifacts = document.createElement('div');
        artifacts.className = 'msg-section';
        const titleArt = document.createElement('h3');
        titleArt.textContent = 'Artifacts';
        artifacts.appendChild(titleArt);
        const list = document.createElement('ul');
        list.className = 'artifact-list';
        message.artifacts.forEach((path) => {
          const btn = document.createElement('button');
          btn.dataset.action = 'open-artifact';
          btn.dataset.path = path;
          btn.textContent = path;
          list.appendChild(btn);
        });
        artifacts.appendChild(list);
        body.appendChild(artifacts);
      }

      if (message.log) {
        const log = document.createElement('div');
        log.className = 'msg-section';
        const titleLog = document.createElement('h3');
        titleLog.textContent = 'Log';
        log.appendChild(titleLog);
        const pre = document.createElement('pre');
        pre.className = 'ace-log';
        pre.textContent = message.log;
        log.appendChild(pre);
        body.appendChild(log);
      }

      if (message.extraSections && message.extraSections.length) {
        message.extraSections.forEach((section) => {
          body.appendChild(section.node.cloneNode(true));
        });
      }

      const actions = document.createElement('div');
      actions.className = 'msg-actions';
      if (message.diffPath) {
        const check = document.createElement('button');
        check.dataset.action = 'stage-check';
        check.textContent = 'Check Patch';
        const stage = document.createElement('button');
        stage.dataset.action = 'stage-apply';
        stage.textContent = 'Stage Patch';
        actions.appendChild(check);
        actions.appendChild(stage);
      }
      if (message.commands && message.commands.length) {
        const dry = document.createElement('button');
        dry.dataset.action = 'commands-dry';
        dry.textContent = 'Dry-run Commands';
        const run = document.createElement('button');
        run.dataset.action = 'commands-run';
        run.textContent = 'Run Commands';
        actions.appendChild(dry);
        actions.appendChild(run);
      }
      if (message.tests && message.tests.length) {
        const dry = document.createElement('button');
        dry.dataset.action = 'tests-dry';
        dry.textContent = 'Dry-run Tests';
        const run = document.createElement('button');
        run.dataset.action = 'tests-run';
        run.textContent = 'Run Tests';
        actions.appendChild(dry);
        actions.appendChild(run);
      }
      if (message.diffPath) {
        const commit = document.createElement('button');
        commit.dataset.action = 'commit';
        commit.textContent = 'Commit';
        actions.appendChild(commit);
      }
      const push = document.createElement('button');
      push.dataset.action = 'push';
      push.textContent = 'Push';
      push.className = 'danger';
      push.disabled = message.status !== 'succeeded';
      actions.appendChild(push);
      const rerun = document.createElement('button');
      rerun.dataset.action = 'rerun';
      rerun.textContent = 'Re-run';
      rerun.className = 'neutral';
      actions.appendChild(rerun);
      if (message.promptPath) {
        const prompt = document.createElement('button');
        prompt.dataset.action = 'open-prompt';
        prompt.textContent = message.prompt ? 'Hide prompt' : 'View prompt';
        prompt.className = 'neutral';
        actions.appendChild(prompt);
      }
      const logBtn = document.createElement('button');
      logBtn.dataset.action = 'refresh-run';
      logBtn.className = 'neutral';
      logBtn.textContent = 'Refresh';
      actions.appendChild(logBtn);
      body.appendChild(actions);
    }

    article.appendChild(body);
    return article;
  }

  function renderHistory() {
    if (!els.history) return;
    els.history.innerHTML = '';
    const frag = document.createDocumentFragment();
    state.history.forEach((run) => {
      const btn = document.createElement('button');
      btn.dataset.runId = run.id;
      btn.textContent = `${run.id.slice(0, 8)} • ${run.status}`;
      if (state.currentRunId === run.id) btn.classList.add('active');
      const detail = document.createElement('span');
      detail.className = 'muted';
      detail.textContent = new Date(run.updated_at || run.created_at).toLocaleString();
      btn.appendChild(detail);
      frag.appendChild(btn);
    });
    els.history.appendChild(frag);
  }

  function renderMachines() {
    if (!els.machineList || !els.machineSelect) return;
    els.machineList.innerHTML = '';
    const fragList = document.createDocumentFragment();
    state.machines.forEach((machine) => {
      const span = document.createElement('span');
      span.textContent = `${machine.name} • ${machine.workspace}`;
      fragList.appendChild(span);
    });
    if (!state.machines.length) {
      const empty = document.createElement('span');
      empty.textContent = 'No machines registered';
      fragList.appendChild(empty);
    }
    els.machineList.appendChild(fragList);

    const current = els.machineSelect.value;
    els.machineSelect.innerHTML = '';
    state.machines.forEach((machine) => {
      const opt = document.createElement('option');
      opt.value = machine.name;
      opt.textContent = machine.name;
      els.machineSelect.appendChild(opt);
    });
    if (!state.machines.length) {
      const opt = document.createElement('option');
      opt.value = 'skylink';
      opt.textContent = 'skylink';
      els.machineSelect.appendChild(opt);
    }
    if (current && Array.from(els.machineSelect.options).some((o) => o.value === current)) {
      els.machineSelect.value = current;
    }
  }

  function renderPolicy() {
    if (!els.policyList) return;
    els.policyList.innerHTML = '';
    state.policy.forEach(({ type, value }) => {
      const span = document.createElement('span');
      span.textContent = `${type} → ${value}`;
      els.policyList.appendChild(span);
    });
    if (!state.policy.length) {
      const span = document.createElement('span');
      span.textContent = 'No command types observed yet';
      els.policyList.appendChild(span);
    }
  }

  async function loadMachines() {
    try {
      const data = await api('/machines').then(toJSON);
      state.machines = data.machines || [];
      renderMachines();
    } catch (err) {
      notify(`Failed to load machines: ${err.message}`, 'error');
    }
  }

  async function loadHistory() {
    try {
      const data = await api('/history').then(toJSON);
      state.history = data.runs || [];
      renderHistory();
    } catch (err) {
      notify(`Failed to load history: ${err.message}`, 'error');
    }
  }

  async function loadPolicy() {
    try {
      const data = await api('/operate/policy').then(toJSON);
      const effective = data.effective || {};
      state.policy = Object.keys(effective).map((key) => ({ type: key, value: effective[key] }));
      renderPolicy();
    } catch (err) {
      notify(`Failed to load policy: ${err.message}`, 'error');
    }
  }

  function startStream(runId) {
    if (!('EventSource' in window) || state.streams.has(runId)) return;
    try {
      const source = new EventSource(`/ace/runs/${runId}/sse`);
      source.addEventListener('log', (evt) => {
        try {
          const payload = JSON.parse(evt.data || '{}');
          const msg = state.messages.find((m) => m.runId === runId);
          if (msg) {
            msg.log = payload.text || '';
            renderMessages();
          }
        } catch (err) {
          console.error(err);
        }
      });
      source.addEventListener('heartbeat', (evt) => {
        if ((evt.data || '').includes('complete')) {
          source.close();
          state.streams.delete(runId);
        }
      });
      source.onerror = () => {
        source.close();
        state.streams.delete(runId);
      };
      state.streams.set(runId, source);
    } catch (err) {
      console.warn('SSE not available', err);
    }
  }

  function stopStream(runId) {
    const source = state.streams.get(runId);
    if (source) {
      source.close();
      state.streams.delete(runId);
    }
  }

  async function pollRun(runId) {
    try {
      const data = await api(`/runs/${runId}/summary`).then(toJSON);
      if (!data.run) return;
      updateMessageFromRun(data.run);
      updateHistoryEntry(data.run);
      if (STATUS_PENDING.has(data.run.status)) {
        setTimeout(() => pollRun(runId), 2000);
      } else {
        await hydratePrompt(data.run);
        stopStream(runId);
      }
    } catch (err) {
      console.error(err);
    }
  }

  function updateHistoryEntry(run) {
    const idx = state.history.findIndex((item) => item.id === run.id);
    if (idx >= 0) {
      state.history[idx] = run;
    } else {
      state.history.unshift(run);
      state.history = state.history.slice(0, 50);
    }
    renderHistory();
  }

  async function hydratePrompt(run) {
    const message = state.messages.find((m) => m.runId === run.id);
    if (!message || !run.prompt_path || message.prompt) return;
    try {
      const text = await loadRunFile(run.id, run.prompt_path);
      const data = JSON.parse(text);
      message.prompt = data;
      message.providerPlan = data.provider_plan || [];
      renderMessages();
    } catch (err) {
      console.warn('Failed to hydrate prompt', err);
    }
  }

  async function loadRunFile(runId, path) {
    const key = `${runId}|${path}`;
    if (state.cache.has(key)) return state.cache.get(key);
    const res = await fetch(`/ace/runs/${runId}/file?path=${encodeURIComponent(path)}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const text = await res.text();
    state.cache.set(key, text);
    return text;
  }

  async function hydrateConversation(run) {
    if (!run || run.mode !== 'ideate') return;
    const convoPath = (run.artifacts || []).find((p) => p.endsWith('conversation.json'));
    if (!convoPath) return;
    try {
      const text = await loadRunFile(run.id, convoPath);
      const conversation = JSON.parse(text);
      if (!Array.isArray(conversation)) return;
      state.conversation = conversation.map((entry) => ({
        role: entry.role,
        content: entry.content,
      }));
      const threadTag = (run.tags || []).find((tag) => tag.startsWith('thread:'));
      if (threadTag) {
        state.threadId = threadTag.split(':', 2)[1] || state.threadId;
      }
      state.messages = state.messages.filter((msg) => msg.type !== 'chat');
      conversation.forEach((entry, index) => {
        state.messages.push({
          id: `chat-${run.id}-${index}`,
          role: entry.role,
          type: 'chat',
          text: entry.content,
          runId: run.id,
          createdAt: run.updated_at,
        });
      });
      renderMessages();
    } catch (err) {
      console.warn('Failed to hydrate conversation', err);
    }
  }

  function parseBriefForm(text) {
    let mode = 'auto';
    let planPreference = 'auto';
    let payloadText = text.trim();
    if (payloadText.toLowerCase().startsWith('command:')) {
      mode = 'operate';
      planPreference = 'skip';
      payloadText = payloadText.slice(8).trim();
    }
    const includeContext = els.includeContext ? els.includeContext.checked : true;
    const includeCode = els.includeCode ? els.includeCode.checked : false;
    const scope = els.contextScope ? els.contextScope.value : 'auto';
    const persona = els.contextPersona ? els.contextPersona.value.trim() : '';
    const context = includeContext ? {
      include: true,
      include_code: includeCode,
      include_persona: true,
      scope,
      persona: persona || null,
    } : { include: false };
    const machine = els.machineSelect && els.machineSelect.value
      ? els.machineSelect.value
      : (state.machines[0]?.name) || 'skylink';
    const tagsValue = els.tagsInput ? els.tagsInput.value : '';
    const modelValue = els.modelInput ? els.modelInput.value.trim() : '';
    const reasoningValue = els.reasoningSelect ? els.reasoningSelect.value : '';
    const tags = parseTags(tagsValue);

    if (mode !== 'operate') {
      mode = 'ideate';
      planPreference = 'skip';
      if (!tags.includes('chat')) {
        tags.push('chat');
      }
    }

    if (state.threadId) {
      const threadTag = `thread:${state.threadId}`;
      if (!tags.includes(threadTag)) {
        tags.push(threadTag);
      }
    }

    const brief = {
      mode,
      text: payloadText,
      plan_preview: planPreference,
      machines: [machine],
      tags,
      context,
    };
    if (modelValue) brief.model = modelValue;
    if (reasoningValue) brief.reasoning = reasoningValue;
    return brief;
  }

  async function submitChat(evt) {
    evt.preventDefault();
    const text = els.input.value.trim();
    if (!text) return;
    if (!state.threadId) {
      const uuid = (globalThis.crypto && crypto.randomUUID) ? crypto.randomUUID() : Math.random().toString(36).slice(2);
      state.threadId = uuid;
      state.conversation = [];
    }
    addUserMessage(text);
    const brief = parseBriefForm(text);
    els.input.value = '';
    els.input.focus();
    try {
      await createRun({
        brief,
        conversation: state.conversation.map((entry) => ({
          role: entry.role,
          content: entry.content,
        })),
      });
    } catch (err) {
      notify(`Run failed to start: ${err.message}`, 'error');
    }
  }

  async function createRun(body) {
    const res = await api('/runs', {
      method: 'POST',
      body: JSON.stringify(body),
    });
    if (res.status === 202) {
      const data = await res.json();
      showPlanPreview(body.brief, data.plan_outline || []);
      return;
    }
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    if (!data.run) throw new Error('Missing run data');
    const run = data.run;
    updateHistoryEntry(run);
    updateMessageFromRun(run);
    startStream(run.id);
    pollRun(run.id);
  }

  function showPlanPreview(brief, outline) {
    const message = {
      id: `plan-${Date.now()}`,
      role: 'assistant',
      type: 'plan',
      planOutline: outline,
      brief,
      createdAt: new Date().toISOString(),
    };
    state.pendingPlan = message;
    state.messages.push(message);
    renderMessages(true);
  }

  async function approvePlan(message) {
    if (!message) return;
    try {
      await createRun({ brief: message.brief, execute: true });
      removeMessage(message.id);
      state.pendingPlan = null;
    } catch (err) {
      notify(`Failed to launch run: ${err.message}`, 'error');
    }
  }

  function cancelPlan(message) {
    removeMessage(message.id);
    state.pendingPlan = null;
  }

  function removeMessage(id) {
    const idx = state.messages.findIndex((m) => m.id === id);
    if (idx >= 0) {
      state.messages.splice(idx, 1);
      renderMessages();
    }
  }

  async function handleActionClick(evt) {
    const btn = evt.target.closest('button[data-action]');
    if (!btn) return;
    const action = btn.dataset.action;
    const article = btn.closest('[data-message-id]');
    if (!article) return;
    const messageId = article.dataset.messageId;
    const message = state.messages.find((m) => m.id === messageId);
    if (!message) return;

    switch (action) {
      case 'approve-plan':
        await approvePlan(message);
        break;
      case 'cancel-plan':
        cancelPlan(message);
        break;
      case 'open-plan':
        await togglePlan(message);
        break;
      case 'open-diff':
        await toggleDiff(message);
        break;
      case 'open-prompt':
        await togglePrompt(message);
        break;
      case 'open-artifact':
        await openArtifact(message, btn.dataset.path);
        break;
      case 'stage-check':
        await stagePatch(message.runId, true);
        break;
      case 'stage-apply':
        await stagePatch(message.runId, false);
        break;
      case 'commands-dry':
        await runCommands(message.runId, true);
        break;
      case 'commands-run':
        await runCommands(message.runId, false);
        break;
      case 'tests-dry':
        await runTests(message.runId, true);
        break;
      case 'tests-run':
        await runTests(message.runId, false);
        break;
      case 'commit':
        await commitRun(message.runId);
        break;
      case 'push':
        await pushRun(message.runId);
        break;
      case 'rerun':
        await rerun(message.runId);
        break;
      case 'refresh-run':
        await pollRun(message.runId);
        break;
      default:
        break;
    }
  }

  async function togglePlan(message) {
    if (!message.run || !message.run.plan_summary) return;
    if (message.planText) {
      delete message.planText;
      renderMessages();
      return;
    }
    const planPath = message.artifacts?.find((p) => p.endsWith('plan.txt'));
    if (!planPath) return;
    try {
      message.planText = await loadRunFile(message.runId, planPath);
      renderMessages();
    } catch (err) {
      notify(`Failed to load plan: ${err.message}`, 'error');
    }
  }

  async function toggleDiff(message) {
    if (!message.diffPath) return;
    if (message.diffText) {
      delete message.diffText;
      renderMessages();
      return;
    }
    try {
      message.diffText = await loadRunFile(message.runId, message.diffPath);
      renderMessages();
    } catch (err) {
      notify(`Failed to load diff: ${err.message}`, 'error');
    }
  }

  async function togglePrompt(message) {
    if (!message.promptPath) return;
    if (message.prompt) {
      delete message.prompt;
      message.providerPlan = null;
      renderMessages();
      return;
    }
    try {
      const text = await loadRunFile(message.runId, message.promptPath);
      message.prompt = JSON.parse(text);
      message.providerPlan = message.prompt.provider_plan || [];
      renderMessages();
    } catch (err) {
      notify(`Failed to load prompt: ${err.message}`, 'error');
    }
  }

  async function openArtifact(message, path) {
    if (!path) return;
    message.extraSections = message.extraSections || [];
    const existingIndex = message.extraSections.findIndex((sec) => sec.path === path);
    if (existingIndex >= 0) {
      message.extraSections.splice(existingIndex, 1);
      renderMessages();
      return;
    }
    try {
      const text = await loadRunFile(message.runId, path);
      const section = document.createElement('div');
      section.className = 'msg-section';
      const title = document.createElement('h3');
      title.textContent = path;
      section.appendChild(title);
      const pre = document.createElement('pre');
      let printable = text;
      try {
        const parsed = JSON.parse(text);
        printable = JSON.stringify(parsed, null, 2);
      } catch (_) {
        /* ignore */
      }
      pre.textContent = printable;
      section.appendChild(pre);
      message.extraSections.push({ path, node: section });
      renderMessages();
    } catch (err) {
      notify(`Failed to open artifact: ${err.message}`, 'error');
    }
  }

  async function stagePatch(runId, checkOnly) {
    try {
      const res = await api(`/runs/${runId}/stage`, {
        method: 'POST',
        body: JSON.stringify({ check_only: checkOnly }),
      }).then(toJSON);
      notify(checkOnly ? 'Patch check complete' : 'Patch staged', 'system');
      await pollRun(runId);
    } catch (err) {
      notify(`Stage failed: ${err.message}`, 'error');
    }
  }

  async function runCommands(runId, dryRun) {
    try {
      await api(`/runs/${runId}/commands`, {
        method: 'POST',
        body: JSON.stringify({ dry_run: dryRun }),
      }).then(toJSON);
      notify(dryRun ? 'Command dry-run complete' : 'Commands executed', 'system');
      await pollRun(runId);
    } catch (err) {
      notify(`Command execution failed: ${err.message}`, 'error');
    }
  }

  async function runTests(runId, dryRun) {
    try {
      await api(`/runs/${runId}/tests`, {
        method: 'POST',
        body: JSON.stringify({ dry_run: dryRun }),
      }).then(toJSON);
      notify(dryRun ? 'Test dry-run complete' : 'Tests executed', 'system');
      await pollRun(runId);
    } catch (err) {
      notify(`Test execution failed: ${err.message}`, 'error');
    }
  }

  async function commitRun(runId) {
    const message = window.prompt('Commit message', `Ace run ${runId}`);
    if (!message) return;
    try {
      await api(`/runs/${runId}/commit`, {
        method: 'POST',
        body: JSON.stringify({ message }),
      }).then(toJSON);
      notify('Commit attempted — check logs for details', 'system');
      await pollRun(runId);
    } catch (err) {
      notify(`Commit failed: ${err.message}`, 'error');
    }
  }

  async function pushRun(runId) {
    if (!window.confirm('Push to origin?')) return;
    try {
      await api(`/runs/${runId}/push`, { method: 'POST', body: JSON.stringify({}) }).then(toJSON);
      notify('Push attempted — check logs for details', 'system');
    } catch (err) {
      notify(`Push failed: ${err.message}`, 'error');
    }
  }

  async function rerun(runId) {
    try {
      const data = await api(`/runs/${runId}/rerun`, { method: 'POST', body: JSON.stringify({}) }).then(toJSON);
      if (data.run) {
        updateHistoryEntry(data.run);
        updateMessageFromRun(data.run);
        startStream(data.run.id);
        pollRun(data.run.id);
      }
    } catch (err) {
      notify(`Failed to rerun: ${err.message}`, 'error');
    }
  }

  async function handleHistoryClick(evt) {
    const btn = evt.target.closest('button[data-run-id]');
    if (!btn) return;
    const runId = btn.dataset.runId;
    if (!runId) return;
    await pollRun(runId);
    startStream(runId);
    const run = state.history.find((item) => item.id === runId);
    await hydrateConversation(run);
  }

  function handleRefreshMachines() {
    loadMachines();
  }

  function handleRefreshPolicy() {
    loadPolicy();
  }

  function setupEvents() {
    els.form?.addEventListener('submit', submitChat);
    els.chatLog?.addEventListener('click', handleActionClick);
    els.history?.addEventListener('click', handleHistoryClick);
    document.querySelector('[data-action="refresh-machines"]')?.addEventListener('click', handleRefreshMachines);
    document.querySelector('[data-action="refresh-policy"]')?.addEventListener('click', handleRefreshPolicy);
    document.querySelector('[data-action="promote-chat"]')?.addEventListener('click', () => {
      notify('Promotion tools coming soon. Use run actions when ready to convert this chat into a build.', 'system');
    });
    els.input?.addEventListener('keydown', (evt) => {
      if ((evt.metaKey || evt.ctrlKey) && evt.key === 'Enter') {
        submitChat(evt);
      }
    });
  }

  async function bootstrap() {
    setupEvents();
    if (els.contextPersona && !els.contextPersona.value) {
      els.contextPersona.value = 'cliff_main/context';
    }
    await Promise.all([loadMachines(), loadHistory(), loadPolicy()]);
  }

  bootstrap();
})();
