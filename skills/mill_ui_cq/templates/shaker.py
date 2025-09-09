from __future__ import annotations
from typing import List
from skills.mill_ui_cq.shapes.base import ShapeSpec
from . import register_template
from .base import TemplateBase

@register_template("Shaker")
class Shaker(TemplateBase):
    """
    Emits shapes for a Shaker cabinet door:
      - Outer Rect as profile cut (door perimeter)
      - Panel pocket Rect (if panel_recess > 0)
      - Anchor recess circles (if enabled)
    All shapes centered at (0,0); engine applies template placement/rotation.
    """
    def expand(self, p, t_mm) -> List[ShapeSpec]:
        ow = float(p["outer_w"])
        oh = float(p["outer_h"])
        sw = float(p["stile_w"])
        rh = float(p["rail_h"])
        recess = float(p.get("panel_recess", 0.0))

        out: List[ShapeSpec] = []

        # Outer perimeter - just a profile cut through
        # CAM will decide if it's inside/outside based on context
        out.append(ShapeSpec(
            type="Rect",
            geometry={"w_mm": ow, "h_mm": oh},
            placement={"center_xy_mm": [0.0, 0.0]},
            feature={"type": "profile", "depth": "through"},
            id="perimeter"
        ))

        # Panel recess (pocket)
        if recess > 0:
            panel_w = ow - 2*sw
            panel_h = oh - 2*rh
            
            out.append(ShapeSpec(
                type="Rect",
                geometry={"w_mm": panel_w, "h_mm": panel_h},
                placement={"center_xy_mm": [0.0, 0.0]},
                feature={"type": "pocket", "depth_mm": recess},
                id="panel"
            ))

            # Anchor recesses (if enabled)
            anchor = p.get("anchor_recess", {})
            if anchor.get("enabled", False):
                diameter = float(anchor["diameter_mm"])
                total_depth = recess + float(anchor["extra_depth_mm"])
                offsets = anchor["offsets_mm"]
                
                # Calculate positions relative to panel recess corners
                panel_x0 = -panel_w / 2.0
                panel_y0 = -panel_h / 2.0
                panel_x1 = panel_w / 2.0
                panel_y1 = panel_h / 2.0
                
                left_offset = float(offsets["left"])
                right_offset = float(offsets["right"])
                top_offset = float(offsets["top"])
                bottom_offset = float(offsets["bottom"])
                
                # Four corner anchor holes
                anchors = [
                    ("anchor_tl", panel_x0 + left_offset, panel_y1 - top_offset),
                    ("anchor_tr", panel_x1 - right_offset, panel_y1 - top_offset),
                    ("anchor_br", panel_x1 - right_offset, panel_y0 + bottom_offset),
                    ("anchor_bl", panel_x0 + left_offset, panel_y0 + bottom_offset)
                ]
                
                for anchor_id, x, y in anchors:
                    out.append(ShapeSpec(
                        type="Circle",
                        geometry={"diameter_mm": diameter},
                        placement={"center_xy_mm": [x, y]},
                        feature={"type": "pocket", "depth_mm": total_depth},
                        id=anchor_id
                    ))

        return out