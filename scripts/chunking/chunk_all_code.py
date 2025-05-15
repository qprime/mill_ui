# scripts/chunking/chunk_all_code.py

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR))  # Make project root importable

import os
import json
from scripts.chunking.chunk_functions import extract_chunks_from_file

OUTPUT_DIR = ROOT_DIR / "memory/development/code_chunks"
EXCLUDE_DIRS = {"venv", ".venv", ".git", "node_modules", "__pycache__", "models", "memory"}

def should_include(file: Path) -> bool:
    parts = file.parts
    return not any(part in EXCLUDE_DIRS for part in parts)

def chunk_all_code():
    print("🔍 Scanning for Python files...")
    py_files = [f for f in ROOT_DIR.rglob("*.py") if should_include(f)]
    print(f"📁 Found {len(py_files)} Python files.")

    for file_path in py_files:
        try:
            chunks = extract_chunks_from_file(file_path)
            if not chunks:
                continue

            rel_path = file_path.relative_to(ROOT_DIR)
            output_path = OUTPUT_DIR / rel_path.with_suffix(".json")
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(chunks, f, indent=2)
            print(f"✅ Chunked {rel_path} -> {output_path.relative_to(ROOT_DIR)}")
        except Exception as e:
            print(f"❌ Failed to chunk {file_path}: {e}")

if __name__ == "__main__":
    chunk_all_code()

