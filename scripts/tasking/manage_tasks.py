import argparse
from development.task_manager import list_tasks, create_task, update_task


def print_task(task):
    print(f"[{task['status'].upper()}] {task['id']} - {task['title']}")
    print(f"  Description: {task['description']}")
    print(f"  Tags: {', '.join(task['tags'])}")
    print(f"  Files: {', '.join(task['files'])}")
    print(f"  Created: {task['created_at']}  Updated: {task['updated_at']}\n")


def handle_list(args):
    tasks = list_tasks(status_filter=args.status)
    if not tasks:
        print("No tasks found.")
        return
    for task in tasks:
        print_task(task)


def handle_create(args):
    task = create_task(
        title=args.title,
        description=args.description,
        files=args.files,
        tags=args.tags,
        steps=args.steps
    )
    print("Task created:")
    print_task(task)


def handle_update(args):
    updated = update_task(args.task_id, {"status": args.new_status})
    if updated:
        print(f"Task {args.task_id} updated to status '{args.new_status}'")
    else:
        print(f"Task {args.task_id} not found.")


def main():
    parser = argparse.ArgumentParser(description="Manage Cliff AI tasks")
    subparsers = parser.add_subparsers(dest="command")

    list_parser = subparsers.add_parser("list", help="List tasks")
    list_parser.add_argument("--status", help="Filter by status")
    list_parser.set_defaults(func=handle_list)

    create_parser = subparsers.add_parser("create", help="Create a new task")
    create_parser.add_argument("--title", required=True)
    create_parser.add_argument("--description", required=True)
    create_parser.add_argument("--files", nargs="*", default=[])
    create_parser.add_argument("--tags", nargs="*", default=[])
    create_parser.add_argument("--steps", nargs="*", default=[])
    create_parser.set_defaults(func=handle_create)

    update_parser = subparsers.add_parser("update", help="Update task status")
    update_parser.add_argument("task_id", required=True)
    update_parser.add_argument("new_status", required=True, choices=["planned", "active", "paused", "complete", "blocked"])
    update_parser.set_defaults(func=handle_update)

    args = parser.parse_args()
    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
