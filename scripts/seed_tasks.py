from cliff_ai.development.task_manager import create_task

# Seed Task 1
create_task(
    title="Implement task manager module",
    description="Create task_manager.py to handle task creation, updates, and listing from task_state.jsonl.",
    files=["development/task_manager.py", "memory/development/task_state.jsonl"],
    tags=["core", "project-mgmt"],
    steps=[
        "Design JSONL task schema",
        "Implement create/list/update functions",
        "Set default path to task_state.jsonl"
    ]
)

# Seed Task 2
create_task(
    title="Build CLI interface to task manager",
    description="Create a script in scripts/ to allow listing, adding, or updating tasks from the command line.",
    files=["scripts/manage_tasks.py"],
    tags=["cli", "tooling"],
    steps=[
        "Add argparse parser",
        "Implement list and add commands",
        "Support status filtering and pretty print"
    ]
)

# Seed Task 3
create_task(
    title="Display task backlog in Cliff web interface",
    description="Create a web route and template to show active/paused/planned tasks from memory/development/task_state.jsonl.",
    files=["web_server/app.py", "web_server/templates/task_backlog.html"],
    tags=["web", "project-mgmt"],
    steps=[
        "Load tasks from JSONL",
        "Create route /tasks",
        "Render tasks by status in HTML"
    ]
)  
