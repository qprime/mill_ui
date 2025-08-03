# path: continuum/diff_tools.py
# type: diff utilities
# tags: diff, utilities, text comparison
# owner: cliff
# depends_on: difflib
# description: Provides utilities for generating and comparing text diffs.

import difflib
from typing import List


def get_unified_diff(a: str, b: str, filename: str = "file") -> str:
    a_lines = a.splitlines()
    b_lines = b.splitlines()
    diff = difflib.unified_diff(
        a_lines, b_lines, fromfile=f"{filename }.old", tofile=f"{filename }.new"
    )
    return "\n".join(diff)


def side_by_side_diff(a: str, b: str, width: int = 80) -> List[str]:
    a_lines, b_lines = a.splitlines(), b.splitlines()
    diff = []
    maxlen = max(len(a_lines), len(b_lines))
    for i in range(maxlen):
        left = a_lines[i] if i < len(a_lines) else ""
        right = b_lines[i] if i < len(b_lines) else ""
        diff.append(f"{left :<{width }} | {right }")
    return diff


def has_changes(a: str, b: str) -> bool:
    return a != b
