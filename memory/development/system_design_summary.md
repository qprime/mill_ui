## 🧠 CLIFF AI — Conversational Project Manager & Second Brain

**Goal:** Build a system that understands your codebase, remembers past work, tracks progress, and helps you design + implement features through natural dialogue — across voice, CLI, and web.

---

### 🗉 Core Components

✅ Task Management System (Web + CLI)

Cliff AI now includes a unified task manager accessible via both the command line and web interface.
📌 Features:

    Backed by: memory/development/task_state.jsonl

    Web UI:

        /tasks: View task backlog grouped by status

        /tasks/create: Submit new tasks via Bootstrap-styled form

        Inline status updates via dropdown (planned, active, paused, complete, blocked)

    CLI Support:

        scripts/manage_tasks.py supports listing, creating, and updating tasks

    Schema-aware: All tasks include title, description, files, tags, steps, timestamps, and status

    Ready for future integration:

        Task creation via voice input (Whisper → LLM → task_state)

        Flagging conversation bubbles as tasks (/conversations pending)

        Embedding or suggesting tasks using LLM agents
#### 2. **Codebase Awareness**

* Format: `code_index.json`, tokenized chunks (via `code_memory/`)
* Captures: file paths, content, edit times, code roles
* Enables: smart suggestions, file-based reminders, AI-driven scaffolding

#### 3. **Knowledge Embeds**

* Folder: `knowledge_base/`
* Stores: schemas, config formats, APIs, solved problems, and reusable patterns
* Enables: Cliff to suggest “known good” solutions and avoid repeat errors

#### 4. **Web + Voice UI**

* Interfaces: `web_server/`, voice → Whisper → Mistral/GPT
* Functionality:

  * View tasks, resume/complete them
  * Add or reprioritize items by voice
  * Ask Cliff “what’s next?” or “what’s blocked?”

#### 5. **Context Management + Task Switching**

* Cliff can:

  * Pause any task with snapshot of current files + notes
  * Resume with prior state (“You were editing `cli_archiver/query.py` on step 3 of 5.”)
  * Switch threads fluidly (e.g. from debugging to feature work)

---

### 💠 How We’ll Build It (Phase by Phase)

| Phase                    | Milestone                             | Outcome                                              |
| ------------------------ | ------------------------------------- | ---------------------------------------------------- |
| 1. Project Memory        | `tasks.jsonl` + query tool            | Track and display active, paused, planned tasks      |
| 2. Code Awareness        | `code_memory/` with metadata + chunks | Cliff knows what files exist and their purpose       |
| 3. Conversational Design | Scaffold features from voice/text     | Cliff helps define + plan features from conversation |
| 4. Interrupt Tracking    | Save/resume task state fluidly        | Cliff remembers what you were doing and why          |
| 5. Web UI                | View/edit task state + backlog        | You can manage tasks from your browser or phone      |
| 6. Schema Knowledge      | Store reusable formats + solutions    | Cliff recalls patterns and known fixes on demand     |

---

### 📌 Example Use

> **You:** “Cliff, let’s build a search function for the CLI logs.”
> **Cliff:** “Logged as new task. Would touch `cli_archiver/query.py`. Want me to stub it out?”
> **Later…** “Cliff, pause this and show me our Whisper startup bug.”
> **Cliff:** “Paused task with 2 files modified. Opening Whisper debug thread…”

---

### ✅ Why It Will Work

* Modular, versioned task memory
* Continuous code context awareness
* Incremental build strategy (always useful, never waiting for perfection)
* Local + API model support
* You are actively using it every day = natural feedback loop
