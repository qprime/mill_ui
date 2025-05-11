# CLIFF Voice Agent Prompt & Setup Summary

This document outlines the architecture, implementation details, service setup, and integration goals for the Whisper + Tortoise TTS pipeline, designed to be integrated into CLIFF AI as a modular voice assistant component.

---

## 👤 Developer Profile (Include in Prompt Context)

* Senior Software Engineer
* Extensive experience in ubuntu 20.04+, TTS, STT, Web development, LLM usage, javascript, https, python, venv and/or uv, command line.
* Primary development platform: Ubuntu 24.04
* GPU hardware: NVIDIA RTX 4070
* Project: CLIFF AI — a multimodal assistant framework for fabrication, automation, and system ops

---

## ✅ What’s Already Working

### 🧠 Whisper (STT)

* Running `faster-whisper` in service mode
* \*HTTPS endpoint: \*`https://192.168.0.179:8001/transcribe`
* Whisper service runs on SkyTech machine
* Accepts `multipart/form-data` (e.g., from Voice Terminal web UI)
* Service definition includes CUDA-visible GPU use and proper LD\_LIBRARY\_PATH
* CORS is enabled via FastAPI middleware
* Mic input tested via browser and file upload
* Service logs show \~4s transcription time for 130-word input

### 🌐 Web Server

* \*Runs on \*Beelink
* HTTPS-enabled with valid self-signed cert trusted locally
* `app.py`\* (FastAPI) + \*`voice_terminal.html`
* Web UI supports:

  * 🎤 Record via mic (MediaRecorder API)
  * 📤 Upload `.wav` file
  * 📄 Display transcription text
  * 📏 Show response duration and word count
  * ✅ All tested and functional

---

## 🗂️ Files to Include with This Prompt

* `voice_terminal.html`\* – working web UI with mic and upload\*
* `app.py`\* – web server routes and logic\*
* `whisper_server.py`\* – current Whisper FastAPI logic\*
* `whisper.service`\* – systemd user service config for Whisper\*

---

## 🧩 Next Goal: Add Tortoise TTS as a Service

### 🗺️ Architecture

* Tortoise will run on the same SkyTech machine as Whisper
* \*Service will expose HTTPS POST endpoint \*`/speak`
* \*Accepts JSON: \*`{ "text": "..." }`
* Outputs audio (`.wav`) and streams or plays it back

### 🛠 Service Plan

* `tts_server.py`\*\*\*\*: FastAPI server that:

  * Loads Tortoise models once on startup (high VRAM use, \~5–7GB)
  * Accepts incoming text via REST
  * Generates and plays back `.wav` using selected voice (e.g., `william` or `pat`)
  * Supports `--preset fast` or `standard` for tuning quality/speed

* `tts.service`\*\*\*\*: systemd user service for persistent background use

### 📦 Notes:

* Startup latency doesn’t matter since it’s long-running
* Sentence-level playback may later be added using buffer pipelines
* Whisper + Tortoise co-running is feasible on 4070

---

## 📈 Web UI Extensions for Testing & Metrics

To use Voice Terminal as a diagnostic and performance test bench:

### 🔧 Additions:

* Show real-time timestamps for:

  * STT transcription duration
  * TTS synthesis duration
* Play back TTS results in-browser (HTML5 `<audio>`)
* \*Add toggle: `Enable LLM` vs. \*`Direct TTS`
* Add field: `Injected Text Response` to simulate LLM output
* Add logs for:

  * Chunked STT timing
  * TTS stream start/finish

### 🧠 Future Enhancements:

* Stream Whisper chunks as they arrive
* Use Whisper+VAD to detect natural pauses
* Start LLM + TTS processing mid-paragraph
* TTS sentence-level streaming (when switching from Tortoise to Coqui/Bark/etc.)

---

## 🧠 Memory for Future Prompts

* Whisper is stable and streaming-capable
* Tortoise TTS is preferred for quality; not streamable
* CLIFF will integrate transcription + TTS in loop
* Dev platform is 2-machine LAN setup (Beelink + SkyTech)
* HTTPS is enforced due to iPad + Mac browser strictness
* LLM output will eventually be inserted between STT and TTS

---

## 📌 Summary Prompt for Future Session

> You are a senior software engineer working on a modular, voice-enabled AI assistant named CLIFF. You’ve implemented Whisper (STT) and are integrating Tortoise (TTS). The system includes a web interface, performance metrics, HTTPS endpoints, and plans for LLM-driven responses. You’re now ready to:
>
> 1. Deploy Tortoise as a systemd service
> 2. Build an endpoint to receive JSON and speak it
> 3. Integrate TTS response into your web UI or CLIFF orchestration layer
>
> Developer files include `voice_terminal.html`, `app.py`, `whisper_server.py`, and systemd configs. Continue from this working state.

---

Let me know when you're ready to start the Tortoise service setup. This doc can be saved as `README.md` in \*\*`cliff_ai`*`/voice`****`_pipeline/`**\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\* or similar.*
