#!/usr/bin/env python3
"""
Remove local artifacts from the legacy chat prototype.

Targets (if present):
  - memories/chat_logs/
  - memories/chatting/chat_logs/
  - web_server/memories/chat_logs/

Sidecar and ledger data are left intact because the new chat uses them.
"""

from __future__ import annotations
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TO_DELETE = [
    ROOT / "memories" / "chat_logs",
    ROOT / "memories" / "chatting" / "chat_logs",
    ROOT / "web_server" / "memories" / "chat_logs",
]

def rm_rf(p: Path) -> None:
    if p.exists():
        print(f"[delete] {p}")
        shutil.rmtree(p)
    else:
        print(f"[skip]   {p} (not found)")

def main() -> None:
    for path in TO_DELETE:
        rm_rf(path)
    print("Done.")

if __name__ == "__main__":
    main()

