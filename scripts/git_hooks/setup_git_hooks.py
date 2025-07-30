#!/usr/bin/env python3

import os
import shutil
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
GIT_HOOKS_DIR = REPO_ROOT / ".git" / "hooks"

def install_hook(hook_name: str, source_path: Path):
    target_path = GIT_HOOKS_DIR / hook_name

    if not source_path.exists():
        print(f"❌ Hook source not found: {source_path}")
        return

    if target_path.exists():
        print(f"⚠️ {hook_name} already exists at {target_path}.")
        answer = input("❓ Overwrite with CLIFF hook? [Y/n]: ").strip().lower()
        if answer not in {"y", "yes", ""}:
            print("🚫 Skipped installation.")
            return

    shutil.copy2(source_path, target_path)
    os.chmod(target_path, 0o755)
    print(f"✅ Installed CLIFF {hook_name} → {target_path.relative_to(REPO_ROOT)}")

if __name__ == "__main__":
    install_hook("post-commit", REPO_ROOT / "scripts" / "git_hooks" / "post-commit.sh")
