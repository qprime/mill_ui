from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import json
import cadquery as cq

import skills.mill_ui_cq.paths as P
from skills.mill_ui_cq.layout import (
    SheetSpec, 
    build_sheet, 
    export_final,
    apply_grid_layout  # New function
)
from skills.mill_ui_cq.shapes import ShapeSpec, resolve_profile
from skills.mill_ui_cq.templates import expand_template

_EPS = 1.0  # small overcut for "through" features
_DEFAULT_KERF = 3.175  # Default kerf width (1/8" bit) in mm

def _load_json(p: Path) -> Dict[str, Any]:
    return json.loads(p.read_text(encoding="utf-8"))

def _feature_depth_mm(feature: Dict[str, Any], sheet_thickness: float) -> float:
    """Get actual depth from feature."""
    ftype = feature.get("type", "profile").lower()
    if ftype == "pocket":
        return float(feature["depth_mm"])
    elif ftype == "engrave":
        return float(feature.get("depth_mm", 0.5))
    else:  # profile
        depth = feature.get("depth")
        if depth == "through" or depth is None:
            return float(sheet_thickness) + _EPS
        return float(depth)

def _create_kerf_cut(shape_type: str, geometry: Dict, placement: Optional[Dict], 
                     kerf_width: float, sheet_thickness: float) -> Tuple[Optional[cq.Workplane], Optional[cq.Workplane]]:
    """
    Create a kerf ring (cut) and the floating interior part.
    Returns (kerf_solid, floating_part) or (None, None) if failed.
    """
    cx, cy = 0, 0
    if placement and "center_xy_mm" in placement:
        cx, cy = placement["center_xy_mm"]
    
    try:
        if shape_type == "Rect":
            w = float(geometry.get("w_mm", 0))
            h = float(geometry.get("h_mm", 0))
            
            if w > kerf_width * 2 and h > kerf_width * 2:
                # Create kerf ring
                outer = (cq.Workplane("XY").center(cx, cy)
                        .rect(w + kerf_width, h + kerf_width)
                        .extrude(-sheet_thickness - _EPS))
                inner = (cq.Workplane("XY").center(cx, cy)
                        .rect(w - kerf_width, h - kerf_width)
                        .extrude(-sheet_thickness - _EPS))
                kerf = outer.cut(inner)
                
                # Create floating part
                floating = (cq.Workplane("XY").center(cx, cy)
                           .rect(w - kerf_width, h - kerf_width)
                           .extrude(-sheet_thickness))
                
                return kerf, floating
                
        elif shape_type == "Circle":
            d = float(geometry.get("diameter_mm", 0))
            r = d / 2.0
            
            if r > kerf_width:
                # Create kerf ring
                outer = (cq.Workplane("XY").center(cx, cy)
                        .circle(r + kerf_width/2)
                        .extrude(-sheet_thickness - _EPS))
                inner = (cq.Workplane("XY").center(cx, cy)
                        .circle(r - kerf_width/2)
                        .extrude(-sheet_thickness - _EPS))
                kerf = outer.cut(inner)
                
                # Create floating part
                floating = (cq.Workplane("XY").center(cx, cy)
                           .circle(r - kerf_width/2)
                           .extrude(-sheet_thickness))
                
                return kerf, floating
    except Exception as e:
        print(f"Kerf creation failed for {shape_type}: {e}")
    
    return None, None

def _process_shapes_on_sheet(sheet: cq.Workplane, specs: List[ShapeSpec], 
                            sheet_thickness: float, kerf_width: float) -> Tuple[cq.Workplane, List[cq.Workplane], List[Dict]]:
    """
    Process shapes: cut pockets/engraves into sheet, create kerf cuts for profiles.
    Returns (modified_sheet, floating_parts, metadata)
    """
    floating_parts = []
    metadata = []
    
    for spec in specs:
        prof2d = resolve_profile(spec)
        wire = prof2d.val()
        
        if isinstance(wire, cq.Wire):
            feat = spec.feature or {"type": "profile", "depth": "through"}
            ftype = feat.get("type", "profile").lower()
            actual_depth = _feature_depth_mm(feat, sheet_thickness)
            
            # Handle profile cuts (through cuts with kerf)
            if ftype == "profile" and actual_depth >= sheet_thickness:
                kerf_solid, floating_part = _create_kerf_cut(
                    spec.type, spec.geometry, spec.placement, 
                    kerf_width, sheet_thickness
                )
                
                if kerf_solid:
                    sheet = sheet.cut(kerf_solid)
                    if floating_part:
                        floating_parts.append(floating_part)
                else:
                    # Fallback: just cut the shape
                    face = cq.Face.makeFromWires(wire)
                    if spec.placement and "center_xy_mm" in spec.placement:
                        cx, cy = spec.placement["center_xy_mm"]
                        face = face.translate((cx, cy, 0))
                    cut = cq.Workplane("XY").add(face).extrude(-sheet_thickness - _EPS)
                    sheet = sheet.cut(cut)
                    
            # Handle pockets and engraves (partial depth cuts)
            elif ftype in ("pocket", "engrave") or (ftype == "profile" and actual_depth < sheet_thickness):
                face = cq.Face.makeFromWires(wire)
                width = feat.get("width_mm")
                
                if width:
                    # Ring cut with specified width
                    bb = wire.BoundingBox()
                    if abs(bb.xlen - bb.ylen) < 0.1:  # Circle
                        radius = bb.xlen / 2.0
                        outer = cq.Workplane("XY").circle(radius + width/2.0).extrude(-actual_depth)
                        inner = cq.Workplane("XY").circle(radius - width/2.0).extrude(-actual_depth)
                        cut = outer.cut(inner)
                    else:
                        cut = cq.Workplane("XY").add(face).extrude(-actual_depth)
                else:
                    cut = cq.Workplane("XY").add(face).extrude(-actual_depth)
                
                # Apply placement
                if spec.placement and "center_xy_mm" in spec.placement:
                    cx, cy = spec.placement["center_xy_mm"]
                    cut = cut.translate((cx, cy, 0))
                
                sheet = sheet.cut(cut)
        
        # Store metadata
        metadata.append({
            "id": spec.id,
            "type": spec.type,
            "geometry": spec.geometry,
            "placement": spec.placement,
            "feature": spec.feature,
        })
    
    return sheet, floating_parts, metadata

def _apply_pockets_to_floating_parts(floating_parts: List[cq.Workplane], 
                                     specs: List[ShapeSpec], sheet_thickness: float) -> List[cq.Workplane]:
    """Apply pocket cuts to the appropriate floating parts based on position."""
    final_parts = []
    
    for part in floating_parts:
        part_bb = part.val().BoundingBox()
        modified_part = part
        
        for spec in specs:
            feat = spec.feature or {}
            ftype = feat.get("type", "profile").lower()
            
            if ftype in ("pocket", "engrave"):
                prof2d = resolve_profile(spec)
                wire = prof2d.val()
                
                if isinstance(wire, cq.Wire) and spec.placement and "center_xy_mm" in spec.placement:
                    cx, cy = spec.placement["center_xy_mm"]
                    
                    # Check if this pocket is within the part bounds
                    if (part_bb.xmin <= cx <= part_bb.xmax and 
                        part_bb.ymin <= cy <= part_bb.ymax):
                        
                        face = cq.Face.makeFromWires(wire)
                        pocket_depth = _feature_depth_mm(feat, sheet_thickness)
                        pocket = cq.Workplane("XY").add(face).extrude(-pocket_depth)
                        pocket = pocket.translate((cx, cy, 0))
                        
                        try:
                            modified_part = modified_part.cut(pocket)
                        except:
                            pass
        
        final_parts.append(modified_part)
    
    return final_parts

def build_from_layout(layout_path: Path) -> Path:
    """Build using proper layout module for arrangement."""
    P.ensure_dirs()
    cfg = _load_json(layout_path)
    
    # Sheet setup
    s = cfg["sheet"]
    sheet_spec = SheetSpec(
        width=float(s["width_mm"]),
        height=float(s["height_mm"]),
        thickness=float(s["thickness_mm"]),
    )
    sheet = build_sheet(sheet_spec)
    
    # Get configuration values
    kerf_width = float(cfg.get("kerf_width_mm", _DEFAULT_KERF))
    layout_cfg = cfg.get("layout", {})
    items = cfg.get("items") or cfg.get("shapes") or []
    
    # DELEGATE TO LAYOUT MODULE: Apply grid layout if configured
    apply_grid_layout(items, layout_cfg, sheet_spec.width, sheet_spec.height)
    
    # Expand all items to specs (now with positions already applied)
    all_specs = []
    for it in items:
        kind = (it.get("kind") or "shape").lower()
        if kind == "shape":
            all_specs.append(ShapeSpec(
                type=it["type"],
                geometry=it.get("geometry", {}),
                placement=it.get("placement"),
                feature=it.get("feature", {}),
                id=it.get("id"),
            ))
        elif kind == "template":
            specs = expand_template(
                name=it["type"],
                params=it.get("params", {}),
                stock_thickness_mm=sheet_spec.thickness,
                template_placement=it.get("placement"),
                template_id=it.get("id"),
            )
            all_specs.extend(specs)
    
    # Process shapes on sheet
    sheet, floating_parts, metadata = _process_shapes_on_sheet(
        sheet, all_specs, sheet_spec.thickness, kerf_width
    )
    
    # Apply pockets to floating parts
    final_floating_parts = _apply_pockets_to_floating_parts(
        floating_parts, all_specs, sheet_spec.thickness
    )
    
    # Combine sheet with floating parts
    result = sheet
    for part in final_floating_parts:
        result = result.union(part)
    
    # Export using layout module
    export_final(sheet=result, out_dir=P.OUTPUT_DIR, make_step=True, make_stl=True, make_dxf=True)
    
    # Save metadata
    cam_hints = {
        "sheet": s,
        "kerf_width_mm": kerf_width,
        "layout": layout_cfg,
        "items_resolved": metadata,
        "cam_notes": {
            "description": "3D model shows sheet with kerf cuts and floating parts in position",
            "floating_parts": len(final_floating_parts)
        }
    }
    
    (P.OUTPUT_DIR / "layout_hints.json").write_text(
        json.dumps(cam_hints, indent=2),
        encoding="utf-8",
    )
    
    return P.OUTPUT_DIR