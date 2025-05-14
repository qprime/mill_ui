import os
import shutil
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
GIT_HOOKS_DIR = REPO_ROOT / ".git" / "hooks"
SOURCE_HOOK = REPO_ROOT / "scripts" / "git_hooks" / "post-commit"
TARGET_HOOK = GIT_HOOKS_DIR / "post-commit"

def install_hook():
    if not SOURCE_HOOK.exists():
        print("❌ Source post-commit hook missing.")
        return

    if TARGET_HOOK.exists():
        with open(TARGET_HOOK, "r") as f:
            if "CLIFF" in f.read():
                print("✅ CLIFF post-commit hook already installed.")
                return
            else:
                print("⚠️ Another post-commit hook already exists. Skipping overwrite.")
                return

    shutil.copy2(SOURCE_HOOK, TARGET_HOOK)
    os.chmod(TARGET_HOOK, 0o755)
    print(f"✅ Installed CLIFF post-commit hook → {TARGET_HOOK}")

if __name__ == "__main__":
    install_hook()
