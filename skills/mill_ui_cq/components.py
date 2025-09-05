from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Optional, Any
import cadquery as cq

# --------------------------- Specs ---------------------------

@dataclass
class ShakerSpec:
    outer_w: float       # mm
    outer_h: float       # mm
    thickness: float     # mm
    stile_w: float       # mm
    rail_h: float        # mm
    panel_recess: float  # mm (depth into top; 0 disables)
    # NEW: optional, flat JSON block passed straight through from layout.json
    anchor_recess: Optional[Dict[str, Any]] = None

    def validate(self) -> None:
        assert self.stile_w * 2 < self.outer_w, "stile_w too large"
        assert self.rail_h  * 2 < self.outer_h, "rail_h too large"
        assert 0 <= self.panel_recess < self.thickness, "panel_recess out of range"


# --------------------------- Builders ---------------------------

def build_shaker(spec: ShakerSpec) -> cq.Workplane:
    """
    Shaker door with:
      - lower-left at (0,0)
      - top surface at Z = 0
      - thickness extending into -Z (i.e., occupies [-T, 0])
    """
    spec.validate()
    W, H, T = spec.outer_w, spec.outer_h, spec.thickness
    stile, rail, recess = spec.stile_w, spec.rail_h, spec.panel_recess

    # Base door blank extruded +Z
    door = cq.Workplane("XY").rect(W, H).extrude(T)

    # Recess pocket: cut from the door's TOP face workplane
    pocket_w = W - 2 * stile
    pocket_h = H - 2 * rail
    if pocket_w > 0 and pocket_h > 0 and recess > 0:
        door = (door
                .faces(">Z").workplane(centerOption="CenterOfMass")
                .rect(pocket_w, pocket_h)
                .cutBlind(-recess))  # negative goes into the solid

    # Normalize pose:
    #   - move XY so lower-left is at (0,0)
    #   - drop entire part so top is Z=0 (solid occupies [-T, 0])
    bb = door.val().BoundingBox()
    door = door.translate((-bb.xmin, -bb.ymin, 0.0))
    door = door.translate((0.0, 0.0, -T))

    # Optional: round anchor pockets inside the panel recess
    door = cut_round_anchor_recesses(door, spec)

    return door


# ------------------ Recess Feature: Round Anchors ------------------

@dataclass
class _RoundAnchorsCfg:
    diameter_mm: float
    extra_depth_mm: float
    offsets_mm: Dict[str, float]          # keys: left,right,top,bottom
    corners: Optional[Dict[str, Dict[str, float]]] = None

    @classmethod
    def from_json(cls, obj: dict) -> "_RoundAnchorsCfg":
        return cls(
            diameter_mm=float(obj["diameter_mm"]),
            extra_depth_mm=float(obj["extra_depth_mm"]),
            offsets_mm={
                k: float(obj["offsets_mm"][k]) for k in ("left", "right", "top", "bottom")
            },
            corners=obj.get("corners"),
        )

def _get_flat_anchor_cfg(spec: ShakerSpec) -> Optional[_RoundAnchorsCfg]:
    """
    Read component.props.anchor_recess from the flat Shaker spec.
    """
    anchors = getattr(spec, "anchor_recess", None)
    if not anchors or not anchors.get("enabled", False):
        return None
    return _RoundAnchorsCfg.from_json(anchors)

def _recess_rect_from_shaker(spec: ShakerSpec) -> tuple[float, float, float, float]:
    """
    Return (x0,y0,x1,y1) for the panel recess rectangle in door-local XY.
    Derived from stile/rail and outer dims (matches current behavior).
    """
    x0 = float(spec.stile_w)
    y0 = float(spec.rail_h)
    x1 = float(spec.outer_w) - float(spec.stile_w)
    y1 = float(spec.outer_h) - float(spec.rail_h)
    return x0, y0, x1, y1

def cut_round_anchor_recesses(door: cq.Workplane, spec: ShakerSpec) -> cq.Workplane:
    """
    Cut four circular pockets inside the panel recess.
    - Uses flat JSON block: component.props.anchor_recess
    - Cuts from top face (Z=0) downward by (panel_recess + extra_depth_mm)
    - No-ops if disabled or if panel_recess <= 0
    """
    cfg = _get_flat_anchor_cfg(spec)
    if not cfg:
        return door

    recess_depth = float(spec.panel_recess or 0.0)
    if recess_depth <= 0:
        return door

    x0, y0, x1, y1 = _recess_rect_from_shaker(spec)

    # Corner centers (relative to DOOR LOWER-LEFT origin (0,0))
    if cfg.corners:
        tl = (x0 + cfg.corners["tl"]["dx"], y1 - cfg.corners["tl"]["dy"])
        tr = (x1 - cfg.corners["tr"]["dx"], y1 - cfg.corners["tr"]["dy"])
        br = (x1 - cfg.corners["br"]["dx"], y0 + cfg.corners["br"]["dy"])
        bl = (x0 + cfg.corners["bl"]["dx"], y0 + cfg.corners["bl"]["dy"])
    else:
        L = cfg.offsets_mm["left"]; R = cfg.offsets_mm["right"]
        T = cfg.offsets_mm["top"];  B = cfg.offsets_mm["bottom"]
        tl = (x0 + L, y1 - T); tr = (x1 - R, y1 - T)
        br = (x1 - R, y0 + B); bl = (x0 + L, y0 + B)

    r = cfg.diameter_mm / 2.0
    total_depth = -(recess_depth + cfg.extra_depth_mm)  # negative into the solid

    # IMPORTANT: anchor the workplane origin at the TOP FACE, LOWER-LEFT vertex
    # so (cx,cy) are absolute in door-local coordinates.
    wp = door.faces(">Z").vertices("<XY").workplane()

    for (cx, cy) in (tl, tr, br, bl):
        wp = wp.center(cx, cy).circle(r).cutBlind(total_depth).center(-cx, -cy)

    # Return the mutated door solid
    return door
