# update_project_docs.py
import os
import subprocess
import datetime
import json
from pathlib import Path

DOC_ROOT = Path(".")
CHANGELOG_PATH = DOC_ROOT / "CHANGELOG.md"
COMMIT_LOG_JSONL = Path("memory/development/git_commit_summary.jsonl")
SUMMARY_LIMIT = 50  # Fetch more so we can filter

def get_recent_commits(limit=SUMMARY_LIMIT):
    result = subprocess.run(
        ["git", "log", f"-n{limit}", "--pretty=format:%h|%ad|%s", "--date=short"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    lines = result.stdout.strip().split("\n")
    commits = []
    for line in lines:
        parts = line.split("|", 2)
        if len(parts) == 3:
            commits.append({
                "hash": parts[0],
                "date": parts[1],
                "message": parts[2],
            })
    return commits

def get_last_logged_hash():
    if not COMMIT_LOG_JSONL.exists():
        return None
    try:
        with open(COMMIT_LOG_JSONL, "rb") as f:
            f.seek(-1024, os.SEEK_END)  # Read last ~1KB
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
        return commits  # first run, return all
    new_commits = []
    for commit in commits:
        if commit["hash"] == last_hash:
            break
        new_commits.append(commit)
    return list(reversed(new_commits))  # Oldest first

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

def main():
    all_commits = get_recent_commits()
    last_hash = get_last_logged_hash()
    new_commits = filter_new_commits(all_commits, last_hash)

    if not new_commits:
        print("No new commits to log.")
        return

    update_changelog(new_commits)
    update_jsonl_log(new_commits)
    print(f"Logged {len(new_commits)} new commits.")

if __name__ == "__main__":
    main()
