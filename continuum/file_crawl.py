"""
[pipeline]
TODO: describe module functionality.
"""

import os
from typing import List, Callable


def crawl_py_files(root: str = ".", exclude: List[str] = None) -> List[str]:
    """
    Walk the tree and find all .py files, skipping excluded directories.
    """
    exclude = set(
        exclude
        or [
            ".git",
            "__pycache__",
            "venv",
            ".venv",
            "memory",
            ".mypy_cache",
            "node_modules",
        ]
    )
    py_files = []
    for dirpath, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in exclude]
        for f in files:
            if f.endswith(".py"):
                py_files.append(os.path.relpath(os.path.join(dirpath, f), root))
    return py_files


def filter_files(files: List[str], predicate: Callable[[str], bool]) -> List[str]:
    return [f for f in files if predicate(f)]
