# path: skills/mill_ui/api/cam.py
from skills.mill_ui.cam.model.tool import Tool, ToolKind
from skills.mill_ui.cam.model.material import Material
from skills.mill_ui.cam.model.machine import Machine
from skills.mill_ui.cam.model.stock import Stock
from skills.mill_ui.cam.model.setup import Setup
from skills.mill_ui.cam.model.hints import build_cam_hints

from skills.mill_ui.cam.ops.profile import profile_outline
from skills.mill_ui.cam.ops.pocket import pocket_raster
from skills.mill_ui.cam.ops.drill import drill_peck
from skills.mill_ui.cam.ops.face import face_zigzag
from skills.mill_ui.cam.ops.engrave import engrave_lines
from skills.mill_ui.cam.ops.bore import bore_helical, pocket_circle_concentric

from skills.mill_ui.cam.post.gcode import write_gcode

# Ensure template registration when api.cam is imported
try:
    from skills.mill_ui.compositions.cabinets import shaker  # noqa: F401
    from skills.mill_ui.compositions.panels import circle_mount  # noqa: F401
except Exception:
    pass

__all__ = [
    "Tool", "ToolKind", "Material", "Machine", "Stock", "Setup",
    "build_cam_hints",
    "profile_outline", "pocket_raster", "drill_peck", "face_zigzag", "engrave_lines",
    "bore_helical", "pocket_circle_concentric",
    "write_gcode",
]
