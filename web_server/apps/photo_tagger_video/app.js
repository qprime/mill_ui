let db;
const request = indexedDB.open("VideoTaggerDB", 1);
request.onupgradeneeded = function(e) {
  db = e.target.result;
  db.createObjectStore("videos", { keyPath: "id", autoIncrement: true });
};
request.onsuccess = function(e) {
  db = e.target.result;
  updateList();
};
request.onerror = function() {
  alert("Failed to open IndexedDB.");
};

document.getElementById('saveBtn').onclick = () => {
  const videoInput = document.getElementById('videoInput');
  const tagsInput = document.getElementById('tagsInput');
  const file = videoInput.files[0];
  if (!file) {
    alert("Please select a video.");
    return;
  }

  const reader = new FileReader();
  reader.onload = function() {
    const tags = tagsInput.value.split(',').map(t => t.trim()).filter(Boolean);
    const dt = new Date();
    const timestamp = dt.toISOString().slice(0,16).replace(/[:T]/g, '-');
    const baseName = (tags[0] || "video") + '_' + timestamp;
    const entry = {
      videoData: reader.result,
      videoName: baseName + ".mp4",
      tags,
      ts: Date.now()
    };
    const tx = db.transaction("videos", "readwrite");
    tx.objectStore("videos").add(entry);
    tx.oncomplete = () => {
      tagsInput.value = '';
      videoInput.value = '';
      updateList();
    };
  };
  reader.readAsDataURL(file);
};

document.getElementById('exportBtn').onclick = () => {
  const tx = db.transaction("videos", "readonly");
  const store = tx.objectStore("videos");
  const request = store.getAll();
  request.onsuccess = () => {
    const exportData = request.result;
    const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "video_entries.json";
    a.click();
  };
};

function updateList() {
  const entryList = document.getElementById('entryList');
  const tagSuggestions = document.getElementById('tagSuggestions');
  const usedTags = new Set();
  const tx = db.transaction("videos", "readonly");
  const store = tx.objectStore("videos");
  const request = store.getAll();
  request.onsuccess = () => {
    entryList.innerHTML = '';
    tagSuggestions.innerHTML = '';
    request.result.sort((a,b) => b.ts - a.ts).forEach(entry => {
      entry.tags.forEach(tag => usedTags.add(tag));
      const li = document.createElement("li");
      li.innerHTML = `
        <strong>${entry.videoName}</strong><br/>
        Tags: ${entry.tags.join(', ')}<br/>
        <video controls src="${entry.videoData}"></video>
      `;
      entryList.appendChild(li);
    });
    [...usedTags].forEach(tag => {
      const opt = document.createElement('option');
      opt.value = tag;
      tagSuggestions.appendChild(opt);
    });
  };
}