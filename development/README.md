readme_content = """
# 📋 Cliff AI — Development & Task Manager

This module provides programmatic access to task management for Cliff AI. It operates on a structured task memory (`task_state.jsonl`) and allows for task creation, updates, and querying through code, CLI, or UI.

---

## 🧠 Purpose

The development module powers Cliff's ability to:
- Track tasks and subtasks with metadata
- Resume paused work sessions
- Generate and manage goals across memory domains

---

## 📁 Key File

| File                | Description                                 |
|---------------------|---------------------------------------------|
| `task_manager.py`   | Core logic to create, load, update tasks    |
| → Backed by:        | `memory/development/task_state.jsonl`       |

---

## 🧩 Task Schema

Each task object includes:
- `id`, `title`, `description`
- `status`: planned, active, complete, paused, blocked
- `steps`: substeps with progress tracking
- `files`, `tags`, `related_tasks`, `paused_state`
- Timestamps: `created_at`, `updated_at`

---

## ⚙️ Example Usage

```python
from development.task_manager import create_task

create_task(
    title=\"Implement CLI Archive Summary\",
    description=\"Add semantic analysis to CLI history and surface common patterns\",
    tags=[\"cli\", \"summary\"],
    steps=[\"Extract sessions\", \"Tokenize commands\", \"Generate embeddings\"]
)
