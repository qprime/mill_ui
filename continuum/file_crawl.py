# path: continuum/file_crawl.py
# type: file crawler
# tags: filesystem, crawler, utils, file management
# owner: cliff
# depends_on: os, pathlib, typing
# description: Recursively searches and filters project files based on extensions and other criteria.

import os
from pathlib import Path
from typing import List, Callable, Dict, Optional

# Exclusion list: edit as project evolves
EXCLUDE_DIRS = {'.git', '__pycache__', '.venv', 'venv', 'output', '.mypy_cache', '.pytest_cache', 'dist', 'build'}

def is_excluded(path: Path) -> bool:
    """Return True if any part of the path matches an excluded directory."""
    return any(part in EXCLUDE_DIRS for part in path.parts)

def find_files(
    root: Path = Path("."), 
    pattern: str = "*", 
    allowed_ext: Optional[List[str]] = None, 
    filter_func: Optional[Callable[[Path], bool]] = None,
    return_metadata: bool = False
) -> List[Path]:
   
    files = []
    for p in root.rglob(pattern):
        if not p.is_file() or is_excluded(p):
            continue
        if allowed_ext and p.suffix not in allowed_ext:
            continue
        if filter_func and not filter_func(p):
            continue
        if return_metadata:
            files.append({
                'path': str(p),
                'size': p.stat().st_size,
                'mtime': p.stat().st_mtime,
            })
        else:
            files.append(p)
    return files

def find_project_files(ext: str) -> List[Path]:
    
    return find_files(Path('.'), allowed_ext=[ext])

def find_relative_files(root: Path = Path('.'), **kwargs) -> List[str]:
    
    root = root.resolve()
    files = find_files(root, **kwargs)
    return [str(f.relative_to(root)) for f in files]

if __name__ == "__main__":
    # CLI quick test: list all Python files, relative to repo root
    for rel_path in find_relative_files(Path('.'), allowed_ext=['.py']):
        print(rel_path)
