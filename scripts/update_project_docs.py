# update_project_docs.py
import os
import subprocess
import datetime
import json
import ast
from pathlib import Path

DOC_ROOT = Path(".")
CHANGELOG_PATH = DOC_ROOT / "CHANGELOG.md"
COMMIT_LOG_JSONL = Path("memory/development/git_commit_summary.jsonl")
SUMMARY_OUTPUT_DIR = Path("memory/development/module_summaries")
SUMMARY_LIMIT = 50


def get_recent_commits(limit=SUMMARY_LIMIT):
    result = subprocess.run(
        ["git", "log", f"-n{limit}", "--pretty=format:%h|%ad|%s", "--name-only", "--date=short"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    log_lines = result.stdout.strip().split("\n")
    commits = []
    current = None
    for line in log_lines:
        if "|" in line:
            if current:
                commits.append(current)
            parts = line.split("|", 2)
            current = {"hash": parts[0], "date": parts[1], "message": parts[2], "files": []}
        elif line.strip():
            if current:
                current["files"].append(line.strip())
    if current:
        commits.append(current)
    return commits


def get_last_logged_hash():
    if not COMMIT_LOG_JSONL.exists():
        return None
    try:
        with open(COMMIT_LOG_JSONL, "rb") as f:
            f.seek(-2048, os.SEEK_END)
            lines = f.readlines()
            for line in reversed(lines):
                try:
                    entry = json.loads(line.decode("utf-8"))
                    if entry.get("type") == "commit" and "hash" in entry.get("data", {}):
                        return entry["data"]["hash"]
                except json.JSONDecodeError:
                    continue
    except Exception:
        return None


def filter_new_commits(commits, last_hash):
    if not last_hash:
        return commits
    new_commits = []
    for commit in commits:
        if commit["hash"] == last_hash:
            break
        new_commits.append(commit)
    return list(reversed(new_commits))


def update_changelog(commits):
    if not commits:
        return
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    header = f"\n## Auto-update: {timestamp}\n"
    body = "".join([f"- [{c['hash']}] {c['message']} ({c['date']})\n" for c in commits])
    with open(CHANGELOG_PATH, "a") as f:
        f.write(header + body)


def update_jsonl_log(commits):
    if not commits:
        return
    COMMIT_LOG_JSONL.parent.mkdir(parents=True, exist_ok=True)
    with open(COMMIT_LOG_JSONL, "a") as f:
        for commit in commits:
            entry = {
                "type": "commit",
                "timestamp": datetime.datetime.now().isoformat(),
                "data": commit
            }
            f.write(json.dumps(entry) + "\n")


def generate_module_summary(directory: str):
    dir_path = Path(directory)
    py_files = list(dir_path.glob("*.py"))
    sh_files = list(dir_path.glob("*.sh"))
    json_files = list(dir_path.glob("*.json"))
    md_files = list(dir_path.glob("*.md"))

    lines = [f"# 📁 {directory}\n\nAuto-generated summary of the `{directory}` module in the Cliff AI system.\n"]

    if py_files:
        lines.append("\n## Python Files and Contents\n")
        for py_file in py_files:
            lines.append(f"### {py_file.name}")
            try:
                with open(py_file, "r") as f:
                    tree = ast.parse(f.read(), filename=str(py_file))
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef):
                        lines.append(f"- Function: `{node.name}()`")
                    elif isinstance(node, ast.ClassDef):
                        lines.append(f"- Class: `{node.name}`")
            except Exception as e:
                lines.append(f"(Could not parse {py_file.name}: {e})")

    if sh_files:
        lines.append("\n## Shell Scripts\n")
        for file in sh_files:
            lines.append(f"- `{file.name}`")

    if json_files:
        lines.append("\n## JSON Files\n")
        for file in json_files:
            lines.append(f"- `{file.name}`")

    if md_files:
        lines.append("\n## Markdown Documents\n")
        for file in md_files:
            lines.append(f"- `{file.name}`")

    out_path = SUMMARY_OUTPUT_DIR / f"{directory}.md"
    SUMMARY_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines))
    print(f"📄 Wrote module summary for {directory}")



def update_module_summaries():
    for item in os.listdir():
        if os.path.isdir(item) and not item.startswith(".") and item != "memory":
            generate_module_summary(item)


def main():
    all_commits = get_recent_commits()
    last_hash = get_last_logged_hash()
    new_commits = filter_new_commits(all_commits, last_hash)

    if not new_commits:
        print("No new commits to log.")
    else:
        update_changelog(new_commits)
        update_jsonl_log(new_commits)
        print(f"Logged {len(new_commits)} new commits.")

    update_module_summaries()
    print("Updated module summaries for all folders.")


if __name__ == "__main__":
    main()
