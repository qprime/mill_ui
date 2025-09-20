(() => {
  const qs = (sel) => document.querySelector(sel);
  const qsa = (sel) => Array.from(document.querySelectorAll(sel));
  const state = {
    handle: '',
    events: [],
    recent: [],
  };

  function toast(msg, ok=true) {
    const t = qs('#toast');
    t.textContent = msg;
    t.classList.remove('hidden');
    t.classList.add('show');
    setTimeout(() => t.classList.remove('show'), 1800);
  }

  function setHandle(h) {
    state.handle = h;
    localStorage.setItem('ctx.handle', h);
    const recent = new Set((JSON.parse(localStorage.getItem('ctx.recent')||'[]')));
    if (h) recent.add(h);
    state.recent = Array.from(recent).slice(-8);
    localStorage.setItem('ctx.recent', JSON.stringify(state.recent));
    renderRecent();
  }

  function renderRecent() {
    const sel = qs('#recent-select');
    sel.innerHTML = '<option value="">Recent…</option>' + state.recent.map(h => `<option value="${h}">${h}</option>`).join('');
  }

  function rowActions(ev) {
    const wrap = document.createElement('div');
    wrap.className = 'row-actions';
    if (ev.type === 'action') {
      const run = document.createElement('button');
      run.textContent = 'Run';
      run.onclick = () => runAction(ev.id);
      wrap.appendChild(run);

      if (ev.status === 'needs_human') {
        const reason = document.createElement('input'); reason.placeholder = 'reason'; reason.style.maxWidth='200px';
        const approve = document.createElement('button'); approve.textContent = 'Approve';
        approve.onclick = () => approveAction(ev.id, reason.value||'UI approve');
        wrap.appendChild(reason); wrap.appendChild(approve);
      }

      const apply = document.createElement('button'); apply.textContent = 'Apply';
      apply.onclick = () => applyAction(ev.id);
      wrap.appendChild(apply);

      const brief = document.createElement('button'); brief.textContent = 'Brief';
      brief.onclick = () => previewBrief(ev.id);
      wrap.appendChild(brief);

      const artifacts = document.createElement('button'); artifacts.textContent = 'Artifacts';
      artifacts.onclick = () => showArtifacts(ev.id);
      wrap.appendChild(artifacts);
    }
    return wrap;
  }

  function badge(text, cls='') { return `<span class="badge ${cls}">${text}</span>`; }

  function renderTimeline() {
    const list = qs('#timeline-list');
    const esc = qs('#escalation-list');
    list.innerHTML=''; esc.innerHTML='';
    state.events.forEach(ev => {
      const li = document.createElement('li');
      const tags = [];
      if (ev.type === 'action') {
        if (ev.status === 'ready') tags.push(badge('ready','ok'));
        if (ev.status === 'needs_human') tags.push(badge('needs_human','human'));
        if (ev.status === 'failed') tags.push(badge('failed','fail'));
      }
      li.innerHTML = `<div class="muted">${ev.created_at}</div> <div>[${ev.type}] ${ev.title}</div> ${tags.join('')}`;
      li.appendChild(rowActions(ev));
      list.appendChild(li);
      if (ev.type === 'action' && ev.status === 'needs_human') {
        const ei = document.createElement('li');
        ei.textContent = `${ev.title} (${ev.intent||''}) requires review`;
        esc.appendChild(ei);
      }
    });
  }

  async function fetchTimeline() {
    if (!state.handle) return;
    const res = await fetch(`/ctx/api/threads/${encodeURIComponent(state.handle)}/timeline`);
    const data = await res.json();
    state.events = data.events || [];
    renderTimeline();
  }

  async function createAction(payload) {
    const res = await fetch('/ctx/api/actions', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload) });
    if (!res.ok) throw new Error('create failed');
    return res.json();
  }

  async function runAction(id) {
    const res = await fetch(`/ctx/api/actions/${id}/run`, { method:'POST' });
    const data = await res.json();
    toast('Run executed');
    await fetchTimeline();
    return data;
  }

  async function approveAction(id, reason, approver='steve') {
    const res = await fetch(`/ctx/api/actions/${id}/approve`, { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ reason, approver })});
    if (!res.ok) { toast('Approve failed', false); return; }
    toast('Approved');
    await fetchTimeline();
  }

  async function applyAction(id) {
    const res = await fetch(`/ctx/api/actions/${id}/apply`, { method:'POST' });
    if (!res.ok) { const t = await res.text(); toast('Apply failed', false); return; }
    toast('Applied');
    await fetchTimeline();
  }

  async function previewBrief(id) {
    const res = await fetch(`/ctx/api/actions/${id}/brief`);
    const data = await res.json();
    const br = data.brief;
    if (!br) { toast('No brief'); return; }
    openViewer(`Brief ${br.id}`, br.prompt_text || '(empty)');
  }

  async function showArtifacts(id) {
    const res = await fetch(`/ctx/api/actions/${id}/artifacts`);
    const data = await res.json();
    const items = (data.artifacts||[]).map(a => `• ${a.title} (${a.purpose})\n${a.path || ''}`).join('\n\n');
    openViewer('Artifacts', items || '(none)');
  }

  function openViewer(title, body) {
    qs('#viewer-title').textContent = title;
    qs('#viewer-body').textContent = body || '';
    qs('#viewer').classList.remove('hidden');
  }
  function closeViewer() { qs('#viewer').classList.add('hidden'); }

  async function validateRegistry() {
    const res = await fetch('/ctx/api/registry/validate');
    toast(res.ok ? 'Registry ok' : 'Registry error', res.ok);
  }

  function wire() {
    // handle init
    const paramHandle = new URLSearchParams(location.search).get('handle');
    const saved = localStorage.getItem('ctx.handle') || '';
    setHandle(paramHandle || saved || 'revolutionary-context-engine');
    qs('#handle-input').value = state.handle;
    fetchTimeline();

    qs('#load-btn').onclick = () => { setHandle(qs('#handle-input').value.trim()); fetchTimeline(); };
    qs('#recent-select').onchange = (e) => { if (e.target.value){ setHandle(e.target.value); qs('#handle-input').value = state.handle; fetchTimeline(); }};
    qs('#validate-btn').onclick = validateRegistry;
    qs('#viewer-close').onclick = closeViewer;

    qs('#action-form').onsubmit = async (e) => {
      e.preventDefault();
      const f = e.target;
      const title = f.title.value.trim();
      const intent = f.intent.value;
      const executorName = f.executor.value;
      const visibility = f.visibility.value;
      const reqs = f.requirements.value.split('\n').map(s => s.trim()).filter(Boolean);
      const include = f.include.value.split(',').map(s => s.trim()).filter(Boolean);
      const payload = {
        title,
        intent,
        thread: state.handle,
        requirements: reqs,
        constraints: { visibility },
        context_scope: { include },
        executor: { name: executorName, args: {}},
      };
      try {
        await createAction(payload);
        toast('Action created');
        await fetchTimeline();
        f.reset();
      } catch (err) {
        toast('Create failed', false);
      }
    };
  }

  window.ctxInit = wire;
})();
