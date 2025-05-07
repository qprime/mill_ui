# 🧠 Cliff AI

Cliff AI is a modular, voice-driven personal assistant framework built for system automation, memory, and contextual intelligence. Inspired by tools like Jarvis, it's designed to grow with your workflow and evolve into a full command and research copilot.

---

## 🚀 Project Vision

- **Daily Force Multiplier**: Remember what you say and do.
- **Modular Intelligence**: Per-domain memory and expert reasoning modules.
- **Voice + CLI + Web UI**: Multiple interaction modes for maximum flexibility.

---

## 🧱 Key Components

| Folder           | Description                                                                 |
|------------------|-----------------------------------------------------------------------------|
| `cli_archiver/`  | Captures shell command history with timestamps and stores to JSONL         |
| `scripts/`       | Utilities for cleaning, embedding, querying, and managing memory            |
| `lab_manager/`   | Tracks devices, IPs, and state across your workshop or network              |
| `llm_server/`    | Local LLM inference wrapper for models like Mistral                         |
| `memory/`        | Structured per-domain memory (e.g., lab, personal, production, etc.)        |
| `web_server/`    | Flask UI to chat, manage memory, view logs, and interact with tasks         |
| `voice_input/`   | Placeholder for real-time voice capture pipelines (e.g. Whisper streaming)  |
| `whisper/`       | Self-hosted Whisper transcription server with certs and runner              |

---

## 🧠 Memory Domains

Memory is organized in ChromaDB-backed folders under `memory/`, including:

- `cli_logs.jsonl`: Shell history
- `task_state.jsonl`: Task manager state
- `device_inventory.json`: Lab devices
- `chat_cleaned.jsonl`: ChatGPT logs for long-term memory

Schemas are documented in `memory/schemas/`.

---

## 🛠️ Development Tools

- **Git commit summaries** are auto-logged to `CHANGELOG.md` and `git_commit_summary.jsonl`
- Run `scripts/update_project_docs.py` manually, or let the `post-commit` hook automate it
- See `docs/system_design_summary.md` for architectural overview

---

## 🗂️ Getting Started

```bash
# clone the project
git clone <repo-url> && cd cliff_ai

# install deps (if applicable)
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt  # if used

# run the web server
python3 web_server/app.py
