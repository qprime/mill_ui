from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable, List, Tuple, Dict, Any
from pathlib import Path
import json
import cadquery as cq

@dataclass
class SheetSpec:
    width: float
    height: float
    thickness: float

def build_sheet(sheet: SheetSpec) -> cq.Workplane:
    """Return a rectangular sheet with:
    - lower-left corner at (0, 0)
    - top surface at Z = 0
    - thickness extending in -Z (i.e., occupies [-T, 0])
    """
    W, H, T = sheet.width, sheet.height, sheet.thickness
    slab = cq.Workplane("XY").rect(W, H).extrude(-T)
    bb = slab.val().BoundingBox()
    slab = slab.translate((-bb.xmin, -bb.ymin, 0.0))
    return slab

def grid_positions(cols: int, rows: int, cell_w: float, cell_h: float,
                   origin: Tuple[float, float]=(0, 0),
                   gap_x: float=0.0, gap_y: float=0.0) -> Iterable[Tuple[float, float]]:
    """Generate grid positions for arranging items.
    
    Args:
        cols: Number of columns
        rows: Number of rows
        cell_w: Width of each cell
        cell_h: Height of each cell
        origin: Starting position (x, y)
        gap_x: Horizontal gap between cells
        gap_y: Vertical gap between cells
        
    Yields:
        (x, y) positions for each grid cell
    """
    ox, oy = origin
    for r in range(rows):
        for c in range(cols):
            yield (ox + c * (cell_w + gap_x), oy + r * (cell_h + gap_y))

def apply_grid_layout(items: List[Dict[str, Any]], layout_cfg: Dict[str, Any], 
                      sheet_width: float, sheet_height: float) -> None:
    """
    Apply grid layout positions to items in-place.
    Modifies items by adding 'placement' field with calculated positions.
    
    Args:
        items: List of item dictionaries to position
        layout_cfg: Layout configuration with cols, rows, gaps, border
        sheet_width: Sheet width in mm
        sheet_height: Sheet height in mm
    """
    if not layout_cfg or layout_cfg.get("type") != "grid":
        return
    
    # Get grid parameters
    cols = layout_cfg.get("cols", 2)
    rows = layout_cfg.get("rows", 2)
    gap_x = layout_cfg.get("gap_x_mm", 10)
    gap_y = layout_cfg.get("gap_y_mm", 10)
    border = layout_cfg.get("border_mm", 20)
    
    # Find max dimensions among items to determine cell size
    max_w = 0
    max_h = 0
    
    for item in items:
        if item.get("kind") == "template" and item.get("type") == "Shaker":
            params = item.get("params", {})
            max_w = max(max_w, float(params.get("outer_w", 0)))
            max_h = max(max_h, float(params.get("outer_h", 0)))
        elif item.get("kind") == "shape":
            geom = item.get("geometry", {})
            if item.get("type") == "Rect":
                max_w = max(max_w, float(geom.get("w_mm", 0)))
                max_h = max(max_h, float(geom.get("h_mm", 0)))
            elif item.get("type") == "Circle":
                d = float(geom.get("diameter_mm", 0))
                max_w = max(max_w, d)
                max_h = max(max_h, d)
    
    # Calculate cell size
    if max_w > 0 and max_h > 0:
        cell_w = max_w
        cell_h = max_h
    else:
        # Calculate from available space
        cell_w = (sheet_width - 2*border - (cols-1)*gap_x) / cols
        cell_h = (sheet_height - 2*border - (rows-1)*gap_y) / rows
    
    # Generate grid positions
    positions = list(grid_positions(
        cols=cols, rows=rows,
        cell_w=cell_w, cell_h=cell_h,
        origin=(border, border),
        gap_x=gap_x, gap_y=gap_y
    ))
    
    # Apply positions to items that don't already have placement
    for idx, item in enumerate(items):
        if not item.get("placement") and idx < len(positions):
            x, y = positions[idx]
            # Position at center of cell
            item["placement"] = {
                "center_xy_mm": [x + cell_w/2, y + cell_h/2]
            }

def export_final(sheet: cq.Workplane,
                 out_dir: Path,
                 make_step: bool = True,
                 make_stl: bool = True,
                 make_dxf: bool = False,
                 basename: str = "final") -> Dict[str, Path]:
    """
    Write a single final solid as STEP/STL, and optional DXF (top-face wires).
    Returns dict of written paths.
    
    Args:
        sheet: The workplane to export
        out_dir: Output directory
        make_step: Export as STEP file
        make_stl: Export as STL file
        make_dxf: Export as DXF file (2D wireframe)
        basename: Base filename for exports
        
    Returns:
        Dictionary mapping format to Path of exported file
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    written: Dict[str, Path] = {}

    if make_step:
        p = out_dir / f"{basename}.step"
        cq.exporters.export(sheet.val(), str(p))
        written["step"] = p

    if make_stl:
        p = out_dir / f"{basename}.stl"
        cq.exporters.export(sheet.val(), str(p))
        written["stl"] = p

    if make_dxf:
        # Export the top-face wireframe as 2D DXF (outline + holes if present)
        try:
            wires_wp = sheet.faces(">Z").wires()
            p = out_dir / f"{basename}.dxf"
            cq.exporters.export(wires_wp, str(p))
            written["dxf"] = p
        except Exception as e:
            print(f"[export_final] DXF skipped: {e}")

    return written