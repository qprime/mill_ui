# Voice Harvester

## Concept

The Voice Harvester module is designed to extract a single, consistent voice style or character tone from multi-voice audio sources such as audiobooks, narrated YouTube videos, or long-form podcasts.

This enables the creation of clean, high-quality datasets for:

- Voice cloning (e.g., creating a custom Cliff TTS voice)
- Speaker-specific RAG indexing
- Training datasets for future AI models
- Filtering and assembling coherent narrations from noisy or mixed-content sources

---

## Motivation

Many narrated sources include multiple character voices, affectations, or tonal shifts. This module would allow Cliff to:

- Identify and isolate a consistent speaker or narrator
- Build reusable embeddings of specific voices (e.g., Stephen Fry-style, Jeremy Fielding narration)
- Reduce noise and improve retrieval clarity from long-form sources

---

## Proposed Pipeline

### 1. **Audio Ingestion**
- Download or stream audio from local file, YouTube, podcast, etc.
- Segment into sentence-level or time-based chunks

### 2. **Transcription + Timing**
- Use Whisper (or WhisperX) to produce:
  - Full transcript
  - Word-level timestamps

### 3. **Voice Embedding Extraction**
- Use `resemblyzer`, `pyannote-audio`, or ECAPA-TDNN
- Generate per-segment voice embeddings

### 4. **Speaker Clustering**
- Cluster embeddings using KMeans, DBSCAN, or UMAP + manual selection
- Identify the narrator voice or desired character tone

### 5. **Segment Filtering**
- Retain only segments from the desired voice cluster
- Optionally:
  - Save cleaned audio
  - Save filtered transcript
  - Train a TTS model (e.g., XTTS, Bark)
  - Index into RAG system

---

## Future Extensions

- Emotion classification (calm, urgent, sarcastic)
- Speaker diarization with label retention
- Integration with video for timestamp-linked retrieval
- Automated voiceprint labeling and persistent identity tracking

---

## Status

**Idea stage.** No code yet—this document represents the design intent.

---

## Notes

Use case examples:
- Extracting Jeremy Fielding’s instructional voice from his videos
- Pulling narrator-only segments from character-heavy audiobooks
- Training Cliff to speak like a favorite voice without manual cleaning
