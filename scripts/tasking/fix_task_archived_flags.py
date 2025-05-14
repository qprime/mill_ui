import json
from pathlib import Path

TASKS_DIR = Path("memory/tasks")

def patch_archived_flag():
    for task_dir in TASKS_DIR.iterdir():
        task_path = task_dir / "task.json"
        if not task_path.exists():
            continue

        with open(task_path, "r") as f:
            task = json.load(f)

        if "archived" not in task or isinstance(task["archived"], str):
            task["archived"] = False
            with open(task_path, "w") as f:
                json.dump(task, f, indent=2)
            print(f"✅ Patched: {task['id']}")

if __name__ == "__main__":
    patch_archived_flag()
