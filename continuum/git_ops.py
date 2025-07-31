"""
Git helpers for Cliff Continuum: status, diff, restore, commit, etc.
"""

import subprocess
from typing import List, Optional

def git_status() -> str:
    return subprocess.check_output(["git", "status", "--short"], encoding="utf-8")

def git_diff(file: str = None) -> str:
    args = ["git", "diff"]
    if file:
        args.append(file)
    return subprocess.check_output(args, encoding="utf-8")

def git_restore(file: str) -> None:
    subprocess.check_call(["git", "restore", file])

def git_commit(files: List[str], message: str) -> None:
    subprocess.check_call(["git", "add"] + files)
    subprocess.check_call(["git", "commit", "-m", message])

def git_show(file: str, rev: str = "HEAD") -> str:
    return subprocess.check_output(["git", "show", f"{rev}:{file}"], encoding="utf-8")

def git_clean_untracked() -> None:
    subprocess.check_call(["git", "clean", "-fd"])
