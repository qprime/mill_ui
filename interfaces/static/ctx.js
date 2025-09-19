async function loadTimeline() {
  const params = new URLSearchParams(window.location.search);
  const handle = params.get('handle') || 'revolutionary-context-engine';
  const res = await fetch(`/ctx/api/threads/${handle}/timeline`);
  const data = await res.json();
  const timelineList = document.getElementById('timeline-list');
  const escalationList = document.getElementById('escalation-list');
  timelineList.innerHTML = '';
  escalationList.innerHTML = '';

  (data.events || []).forEach((event) => {
    const li = document.createElement('li');
    li.className = `event-${event.type}`;
    li.textContent = `${event.created_at} • [${event.type}] ${event.title}`;
    if (event.type === 'action') {
      li.textContent += ` • status: ${event.status}`;
      if (event.status === 'needs_human') {
        const esc = document.createElement('li');
        esc.textContent = `${event.title} (${event.intent}) requires review`;
        escalationList.appendChild(esc);
      }
    }
    timelineList.appendChild(li);
  });
}

document.addEventListener('DOMContentLoaded', loadTimeline);
