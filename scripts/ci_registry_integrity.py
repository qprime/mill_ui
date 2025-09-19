from __future__ import annotations

from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from skills.memory_framework.registry import MemoryRegistry


def main() -> int:
    registry = MemoryRegistry()
    registry.validate_chain()
    staged = registry.staged()
    if staged:
        print("Found staged memories:")
        for memory in staged:
            print(f"- {memory.id} {memory.title}")
        return 1
    print("registry ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
