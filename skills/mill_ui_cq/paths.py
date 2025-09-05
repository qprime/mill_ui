from __future__ import annotations
from pathlib import Path

# Resolve project root by walking up from this file
BASE = Path(__file__).resolve().parent.parent.parent

# Canonical I/O per your convention
MEM_ROOT = BASE / "memories" / "cam_projects" / "sheet_layouts" / "4x4"
INPUT_DIR = MEM_ROOT / "input"
OUTPUT_DIR = MEM_ROOT / "output"
DOORS_DIR = OUTPUT_DIR / "doors"

def ensure_dirs() -> None:
    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    DOORS_DIR.mkdir(parents=True, exist_ok=True)
