# path: continuum/patcher.py
# type: file_patching_utils
# tags: backup, file, io, utils
# owner: cliff
# depends_on: shutil, pathlib
# description: Provides utility functions for backing up and patching files.

import shutil
from pathlib import Path


def backup_file(path: str) -> None:
    path_obj = Path(path)
    backup = path_obj.with_suffix(path_obj.suffix + ".bak")
    shutil.copy(path, backup)


def write_file(path: str, content: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def replace_file_if_changed(path: str, new_content: str) -> bool:
    with open(path, "r", encoding="utf-8") as f:
        old = f.read()
    if old != new_content:
        backup_file(path)
        write_file(path, new_content)
        return True
    return False
