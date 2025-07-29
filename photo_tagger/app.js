let entries = JSON.parse(localStorage.getItem('entries') || '[]');
const photoInput = document.getElementById('photoInput');
const recordBtn = document.getElementById('recordBtn');
const tagsInput = document.getElementById('tagsInput');
const saveBtn = document.getElementById('saveBtn');
const gallery = document.getElementById('gallery');
const tagSuggestions = document.getElementById('tagSuggestions');

let currentImage = null;
let currentTranscript = '';
let recognition;

if ('webkitSpeechRecognition' in window) {
  recognition = new webkitSpeechRecognition();
  recognition.lang = 'en-US';
  recognition.continuous = false;
  recognition.interimResults = false;

  recognition.onresult = (event) => {
    currentTranscript = event.results[0][0].transcript;
    alert("Heard: " + currentTranscript);
  };
}

recordBtn.onclick = () => {
  if (recognition) recognition.start();
};

photoInput.onchange = async () => {
  const file = photoInput.files[0];
  const reader = new FileReader();
  reader.onload = () => {
    currentImage = reader.result;
    alert("Image loaded and ready to save.");
  };
  reader.readAsDataURL(file);
};

saveBtn.onclick = () => {
  if (!currentImage) return alert("Add a photo");
  const tags = tagsInput.value.split(',').map(tag => tag.trim()).filter(Boolean);
  entries.unshift({ image: currentImage, tags, transcript: currentTranscript, ts: Date.now() });
  localStorage.setItem('entries', JSON.stringify(entries));
  tagsInput.value = '';
  currentTranscript = '';
  currentImage = null;
  updateGallery();
};

function updateGallery() {
  gallery.innerHTML = '';
  const usedTags = new Set();
  entries.forEach(entry => {
    entry.tags.forEach(tag => usedTags.add(tag));
    const div = document.createElement('div');
    div.className = 'entry';
    div.innerHTML = `
      <img src="${entry.image}" />
      <p><b>Tags:</b> ${entry.tags.join(', ')}</p>
      <p><b>Note:</b> ${entry.transcript}</p>
    `;
    gallery.appendChild(div);
  });

  tagSuggestions.innerHTML = '';
  [...usedTags].forEach(tag => {
    const opt = document.createElement('option');
    opt.value = tag;
    tagSuggestions.appendChild(opt);
  });
}

updateGallery();
