from __future__ import annotations
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent.parent
PROJECTS_ROOT = BASE / "memories" / "cam_projects" / "sheet_layouts"

PROJECT_NAME = "4x4"
MEM_ROOT = PROJECTS_ROOT / PROJECT_NAME
INPUT_DIR = MEM_ROOT / "input"
OUTPUT_DIR = MEM_ROOT / "output"
DOORS_DIR = OUTPUT_DIR / "doors"  # kept for legacy callers; not created by default

def set_project(name: str) -> None:
    global PROJECT_NAME, MEM_ROOT, INPUT_DIR, OUTPUT_DIR, DOORS_DIR
    PROJECT_NAME = name
    MEM_ROOT = PROJECTS_ROOT / name
    INPUT_DIR = MEM_ROOT / "input"
    OUTPUT_DIR = MEM_ROOT / "output"
    DOORS_DIR = OUTPUT_DIR / "doors"

def ensure_dirs() -> None:
    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    # DO NOT auto-create doors/
