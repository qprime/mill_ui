(() => {
    const app = document.getElementById('ltp-app');
    if (!app) return;

    const state = {
        slug: app.dataset.slug || '',
        sections: [],
        prompts: [],
        summary: {},
        actionItems: [],
        suggestions: [],
        preview: null,
        previewRequest: null,
        recording: null
    };

    const refs = {
        slugInput: document.getElementById('ltp-slug'),
        loadBtn: document.getElementById('ltp-load'),
        recordBtn: document.getElementById('ltp-record'),
        stopBtn: document.getElementById('ltp-stop'),
        uploadBtn: document.getElementById('ltp-upload'),
        fileInput: document.getElementById('ltp-file'),
        tidyBtn: document.getElementById('ltp-tidy'),
        reviseBtn: document.getElementById('ltp-revise'),
        exportPdf: document.getElementById('ltp-export-pdf'),
        exportDocx: document.getElementById('ltp-export-docx'),
        prompts: document.getElementById('ltp-prompts'),
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
        summary: document.getElementById('ltp-summary')
    };

    const fetchJSON = async (url, options = {}) => {
        const res = await fetch(url, options);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return await res.json();
    };

    const snapshotUrl = () => `/api/ltp/projects/${state.slug}/snapshot`;

    const renderPrompts = () => {
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
            btn.addEventListener('click', () => previewSection(suggestion.section_id, suggestion.intent, suggestion.constraints));
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
    };

    const renderSummary = () => {
        refs.summary.textContent = JSON.stringify(state.summary, null, 2);
    };

    const renderPreview = () => {
        if (!state.preview) {
            refs.previewBefore.textContent = '';
            refs.previewAfter.textContent = '';
            refs.previewDiff.textContent = '';
            refs.applyBtn.disabled = true;
            refs.cancelBtn.disabled = true;
            return;
        }
        refs.previewBefore.textContent = state.preview.before || '';
        refs.previewAfter.textContent = state.preview.after || '';
        refs.previewDiff.textContent = state.preview.diff || '';
        refs.applyBtn.disabled = false;
        refs.cancelBtn.disabled = false;
    };

    const render = () => {
        renderPrompts();
        renderSuggestions();
        renderActionItems();
        renderSections();
        renderSummary();
        renderPreview();
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
            body: JSON.stringify({ index, done })
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
            body: JSON.stringify({ add: title })
        });
        state.actionItems = data.action_items || [];
        renderActionItems();
    };

    const previewSection = async (sectionId, intent, constraints) => {
        if (!state.slug || !sectionId) return;
        state.previewRequest = { sectionId, intent, constraints: constraints || [] };
        const data = await fetchJSON(`/api/ltp/projects/${state.slug}/sections/${sectionId}/preview`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ intent, constraints })
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
            body: JSON.stringify({ intent: req.intent, constraints: req.constraints })
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
            body: JSON.stringify({ sections: [] })
        });
        state.suggestions = data.suggestions || [];
        renderSuggestions();
    };

    const exportDoc = async (kind) => {
        if (!state.slug) return;
        const data = await fetchJSON(`/api/ltp/projects/${state.slug}/export`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ kind })
        });
        alert(`Exported to ${data.output}`);
    };

    const sendAudioBlob = async (blob) => {
        if (!state.slug) return;
        const form = new FormData();
        form.append('file', blob, `${state.slug}.webm`);
        const res = await fetch(`/api/ltp/projects/${state.slug}/voice`, {
            method: 'POST',
            body: form
        });
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

    const uploadAudio = () => {
        refs.fileInput.click();
    };

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

    refs.loadBtn.addEventListener('click', () => {
        state.slug = refs.slugInput.value.trim();
        loadSnapshot();
    });
    refs.tidyBtn.addEventListener('click', tidyNow);
    refs.reviseBtn.addEventListener('click', loadRevision);
    refs.exportPdf.addEventListener('click', () => exportDoc('pdf'));
    refs.exportDocx.addEventListener('click', () => exportDoc('docx'));
    refs.applyBtn.addEventListener('click', applyPreview);
    refs.cancelBtn.addEventListener('click', cancelPreview);
    refs.recordBtn.addEventListener('click', startRecording);
    refs.stopBtn.addEventListener('click', stopRecording);
    refs.uploadBtn.addEventListener('click', uploadAudio);
    refs.fileInput.addEventListener('change', handleFileChange);
    refs.actionAdd.addEventListener('click', addActionItem);

    if (state.slug) {
        loadSnapshot();
    }
})();
