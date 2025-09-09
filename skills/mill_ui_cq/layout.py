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

def apply_grid_layout(items, layout_cfg, sheet_width: float, sheet_height: float) -> None:
    """
    Grid placement with symmetric sheet border, precise gaps, offcut bias,
    and selectable fit mode:
      fit = "tight"  -> cells sized from item outer dims (max W/H)
      fit = "fill"   -> cells derived from available interior (current behavior)
    """
    if not layout_cfg or layout_cfg.get("type") != "grid":
        return

    cols = int(layout_cfg.get("cols", 1))
    rows = int(layout_cfg.get("rows", 1))
    gap_x = float(layout_cfg.get("gap_x_mm", 0.0))
    gap_y = float(layout_cfg.get("gap_y_mm", 0.0))
    border = float(layout_cfg.get("border_mm", 0.0))
    bias = (layout_cfg.get("cutoff_bias") or "bottom-left").lower()
    fit  = (layout_cfg.get("fit") or "fill").lower()  # "tight" or "fill"

    assert cols > 0 and rows > 0, "rows/cols must be positive"

    # --- item outer size helper
    def item_size_mm(it):
        if it.get("kind") == "template" and it.get("type") == "Shaker":
            p = it.get("params", {})
            return float(p.get("outer_w", 0)), float(p.get("outer_h", 0))
        if it.get("kind") == "shape":
            t = it.get("type"); g = it.get("geometry", {})
            if t == "Rect":
                return float(g.get("w_mm", 0)), float(g.get("h_mm", 0))
            if t == "Circle":
                d = float(g.get("diameter_mm", 0)); return d, d
        return 0.0, 0.0

    # --- available interior after sheet border and gaps
    avail_w = sheet_width  - 2 * border - (cols - 1) * gap_x
    avail_h = sheet_height - 2 * border - (rows - 1) * gap_y
    if avail_w <= 0 or avail_h <= 0:
        raise ValueError("Grid + borders/gaps exceed sheet size")

    if fit == "tight":
        # cells from actual parts (tight packing)
        max_w = max((item_size_mm(it)[0] for it in items), default=0.0)
        max_h = max((item_size_mm(it)[1] for it in items), default=0.0)
        cell_w, cell_h = max_w, max_h

        block_w = cols * cell_w + (cols - 1) * gap_x
        block_h = rows * cell_h + (rows - 1) * gap_y

        if block_w > avail_w + 1e-6 or block_h > avail_h + 1e-6:
            raise ValueError(
                f"Tight pack does not fit: block {block_w:.2f}×{block_h:.2f} > "
                f"avail {avail_w:.2f}×{avail_h:.2f} (reduce borders/gaps or size)"
            )
    else:
        # fill interior evenly (legacy behavior)
        cell_w = avail_w / cols
        cell_h = avail_h / rows
        block_w = cols * cell_w + (cols - 1) * gap_x
        block_h = rows * cell_h + (rows - 1) * gap_y
        # validate items fit these cells
        too_big = []
        for it in items:
            w, h = item_size_mm(it)
            if (w and w > cell_w + 1e-6) or (h and h > cell_h + 1e-6):
                ident = it.get("id") or f"{it.get('kind','?')}/{it.get('type','?')}"
                too_big.append(f"{ident}: {w:.2f}×{h:.2f} > cell {cell_w:.2f}×{cell_h:.2f}")
        if too_big:
            raise ValueError("Item(s) too large for grid cells -> " + "; ".join(too_big))

    # --- choose origin per offcut bias
    ox = border; oy = border  # bottom-left
    if bias == "bottom-right":
        ox = sheet_width - border - block_w
    elif bias == "top-left":
        oy = sheet_height - border - block_h
    elif bias == "top-right":
        ox = sheet_width  - border - block_w
        oy = sheet_height - border - block_h

    # --- place centers
    positions = []
    for r in range(rows):
        for c in range(cols):
            x = ox + c * (cell_w + gap_x) + 0.5 * cell_w
            y = oy + r * (cell_h + gap_y) + 0.5 * cell_h
            positions.append((x, y))

    i = 0
    for it in items:
        if it.get("placement"):  # leave manual placements untouched
            continue
        if i >= len(positions):
            break
        cx, cy = positions[i]
        it["placement"] = {"center_xy_mm": [cx, cy]}
        i += 1

    # --- debug: report offcuts (helps target a 12" right strip)
    right_offcut  = sheet_width  - (ox + block_w) - border
    top_offcut    = sheet_height - (oy + block_h) - border
    left_offcut   = ox - border
    bottom_offcut = oy - border
    print(
        f"[layout] offcuts mm (L,R,T,B) = "
        f"{left_offcut:.2f}, {right_offcut:.2f}, {top_offcut:.2f}, {bottom_offcut:.2f}"
    )




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