# 📁 Project Structure Overview: Cliff AI

This document summarizes the purpose and layout of the major directories and files in the Cliff AI project. It supports reasoning about where to place new modules, logs, memory, or UI components.

---

## 🔧 Top-Level Folders

### `/scripts/`

* Python logic that supports both CLI and Flask interfaces.
* Contains modules like `rag_loader.py`, embedding utils, and batch operations.
* Preferred home for backend processing or callable tools not tied to UI.

### `/scripts/utils/`

* Shared support code (e.g. `ai_router.py`) that abstracts external services or system logic.
* Use this for wrappers, adapters, or shared helpers.

### `/web_server/`

* Flask web interface and routes.
* Templates live in `/web_server/templates/`
* This is the user-facing entry point for browser-based interaction with Cliff.

### `/memory/`

* Long-term memory store organized by function:

  * `/memory/development/` → dev-focused logs, RAG source files, summaries
  * `/memory/personal/`, `/lab/`, `/production/` → for other roles as Cliff expands

### `/memory/development/module_summaries/`

* Auto-generated summaries of code folders or key components
* Used for embedding into ChromaDB for RAG

### `/chroma_store/`

* Persistent vector database used by ChromaDB
* All RAG input embeddings are stored here and shared by both CLI and web components

---

## 🆕 Where to Add New Files

| Task                                                 | Put it in                             |
| ---------------------------------------------------- | ------------------------------------- |
| Add new utility module for embeddings, hardware, etc | `scripts/utils/`                      |
| Add a new chat route or JSON API                     | `web_server/app.py` or `/web_server/` |
| Log system-level CLI tasks                           | `memory/development/cli_logs.jsonl`   |
| New RAG data source                                  | `memory/development/*.md`             |
| CLI scripts or non-UI tools                          | `scripts/`                            |

---

## 🧠 Guidance

* Favor modularity: if a component can be used outside of Flask, put it in `scripts/`
* Avoid duplicating logic in both CLI and UI — call shared tools from `scripts/`
* Document new modules with a `.md` summary in `memory/development/` to keep RAG up to date

---

*Last updated: May 2025*
