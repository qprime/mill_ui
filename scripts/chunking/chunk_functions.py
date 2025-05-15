# scripts/chunking/chunk_functions.py

import ast
from pathlib import Path
from typing import List, Dict, Union

def extract_chunks_from_file(file_path: Path) -> List[Dict[str, Union[str, int, List[str]]]]:
    source = file_path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    chunks = []
    lines = source.splitlines()
    module_path = str(file_path)

    def get_code_segment(start: int, end: int) -> str:
        return "\n".join(lines[start - 1:end])

    last_end = 0

    # Handle preamble (everything before the first class or function)
    if tree.body:
        first_node = tree.body[0]
        if hasattr(first_node, 'lineno') and first_node.lineno > 1:
            chunks.append({
                "file": module_path,
                "name": "preamble",
                "type": "preamble",
                "start_line": 1,
                "end_line": first_node.lineno - 1,
                "code": get_code_segment(1, first_node.lineno - 1)
            })

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            start = node.lineno
            end = getattr(node, 'end_lineno', start + 1)
            chunks.append({
                "file": module_path,
                "name": node.name,
                "type": type(node).__name__,
                "start_line": start,
                "end_line": end,
                "code": get_code_segment(start, end),
                "docstring": ast.get_docstring(node) or ""
            })

    return sorted(chunks, key=lambda c: c["start_line"])



