import json
from pathlib import Path

# Paste your dumped content here as a triple-quoted string
DUMP = """
{
  "id": "task_aceea274",
  "title": "Implement Project Awareness (Phase 2)",
  "description": "Add full project awareness to Cliff AI by parsing goals, code structure, git commit history, and task list to support contextual next-step suggestions.",
  "status": "planned",
  "created_at": "2025-05-07T21:18:40.906447Z",
  "updated_at": "2025-05-07T21:18:40.906459Z",
  "files": [],
  "tags": ["project-awareness", "context", "chat-ui", "git", "tasks"],
  "steps": [
    "Parse README.md, project charter, and goals.json into structured project memory",
    "Index and summarize codebase file tree with basic metadata",
    "Extract and summarize recent Git commits with timestamps and diffs",
    "Track tasks from task_list.json or markdown sources",
    "Add middleware to chat window to inject project summary and next suggestions",
    "Implement next-step recommender based on current goal/task diff"
  ],
  "current_step": 0,
  "notes": "",
  "paused_state": null,
  "blocked_by": [],
  "related_tasks": []
}
"""

DEST_DIR = Path("memory/tasks")
DEST_DIR.mkdir(parents=True, exist_ok=True)

def restore():
    lines = DUMP.strip().splitlines()
    for line in lines:
        try:
            task = json.loads(line.strip())
            task_id = task["id"]
            task_dir = DEST_DIR / task_id
            task_dir.mkdir(parents=True, exist_ok=True)
            with open(task_dir / "task.json", "w") as f:
                json.dump(task, f, indent=2)
            print(f"✔️ Restored {task_id}")
        except Exception as e:
            print(f"❌ Failed on line: {line[:60]}... → {e}")

if __name__ == "__main__":
    restore()
