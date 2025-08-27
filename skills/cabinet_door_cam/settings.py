# path: cliff_ai/skills/cabinet_door_cam/settings.py
# desc: Central knobs for post header, default paths, and pack filenames. One place to tweak shop prefs.
# api: (module constants only)
# tags: config, grbl, paths, constants

from __future__ import annotations
from pathlib import Path

# === Where artifacts will be written (you can change this) ===
OUTPUT_ROOT = (Path(__file__).parents[2] / "memories" / "cam_projects" / "cabinet_doors").resolve()

# === Where orders are looked up by default (you can change this) ===
DEFAULT_ORDER_DIR = (Path(__file__).parent / "orders").resolve()

# === Where machine/material/style/tools packs live by default (you can change this) ===
DEFAULT_PACKS_DIR = (Path(__file__).parent / "packs").resolve()

# === Best-guess GRBL modal header (safe to edit for your shop standard) ===
# G17=XY plane, G21=mm, G90=absolute axes, G94=feed/min, G90.1=absolute IJK, G54=work offset 1
GRBL_HEADER = "G17 G21 G90 G94 G90.1 G54"  # <- tweak here if needed (e.g., add G49/G40/G80 per your post)

# === Default pack filenames (relative to DEFAULT_PACKS_DIR unless you pass explicit paths) ===
MACHINE_PACK_FILE = "machine/altmill.v1.json"
MATERIAL_PACK_FILE = "material/mdf_19.v1.json"
STYLE_FILE = "styles/mdf_faux_shaker_recessed.v1.json"

TOOL_FILES = {
    "rough": "tool/half_flat_12p7.v1.json",
    "finish": "tool/quarter_flat_6p35.v1.json",
    "hinge": "tool/boring_35mm_v1.json",
}

# Deterministic rounding
GEOM_MM_PLACES = 2        # 0.01 mm geometry
FEED_MM_MIN_PLACES = 1    # 0.1 mm/min feeds
JSON_INDENT = None        # canonical dump (minified) for hashing
JSON_SORT_KEYS = True
