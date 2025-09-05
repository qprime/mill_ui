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
    ox, oy = origin
    for r in range(rows):
        for c in range(cols):
            yield (ox + c * (cell_w + gap_x), oy + r * (cell_h + gap_y))

def place_parts(parts: List[cq.Workplane], positions: List[Tuple[float, float]]) -> List[cq.Workplane]:
    """Place parts at specified positions, keeping top at Z=0 (flush with sheet top)"""
    placed = []
    for part, (x, y) in zip(parts, positions):
        bb = part.val().BoundingBox()
        # Keep parts with their top at Z=0, just translate in X,Y
        placed.append(part.translate((x - bb.xmin, y - bb.ymin, -bb.zmax)))
    return placed

def export_doors(doors: List[cq.Workplane], out_dir: Path) -> None:
    """Export individual door STL files"""
    out_dir.mkdir(parents=True, exist_ok=True)
    for i, d in enumerate(doors, start=1):
        cq.exporters.export(d.val(), str(out_dir / f"door_{i}.stl"))

def export_sheet_layout(sheet: cq.Workplane, doors: List[cq.Workplane], out_step: Path,
                       tool_diameter: float = 6.35, kerf_visualization_depth: float = None) -> None:
    """
    Export CNC nesting layout with doors embedded in the sheet.
    This represents how the parts would be arranged on a sheet of MDF for CNC cutting.
    
    Args:
        sheet: The sheet workplane
        doors: List of door workplanes positioned on the sheet  
        out_step: Output path for STEP file
        tool_diameter: CNC bit diameter in mm (default 6.35mm = 1/4")
        kerf_visualization_depth: Depth of kerf visualization groove. If None, uses 1/40 of sheet thickness
    
    The output STL shows:
    - The full sheet with doors in their cutting positions
    - Panel recesses visible on the top surface
    - Kerf lines showing where doors will be cut from sheet
    """
    out_dir = out_step.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    print("\n=== CNC Nesting Layout Export ===")
    
    # Debug: Verify all parts are at same Z level
    sheet_bb = sheet.val().BoundingBox()
    print(f"Sheet: Z from {sheet_bb.zmin:.2f} to {sheet_bb.zmax:.2f}")
    print(f"Sheet dimensions: {sheet_bb.xlen:.1f} x {sheet_bb.ylen:.1f} x {abs(sheet_bb.zmin):.1f} mm")
    
    # Export individual doors (for separate processing if needed)
    step_dir = out_dir / "step"
    stl_dir = out_dir / "doors"
    step_dir.mkdir(parents=True, exist_ok=True)
    stl_dir.mkdir(parents=True, exist_ok=True)

    for i, d in enumerate(doors, start=1):
        door_bb = d.val().BoundingBox()
        print(f"Door {i}: Position ({door_bb.xmin:.1f}, {door_bb.ymin:.1f}), "
              f"Size {door_bb.xlen:.1f} x {door_bb.ylen:.1f} mm, "
              f"Z from {door_bb.zmin:.2f} to {door_bb.zmax:.2f}")
        try:
            cq.exporters.export(d.val(), str(step_dir / f"door_{i}.step"))
            cq.exporters.export(d.val(), str(stl_dir / f"door_{i}.stl"))
        except Exception as e:
            print(f"Warning: Could not export door {i}: {e}")

    # === MAIN EXPORT: Nested Layout for CNC ===
    # Create a single solid representing the sheet with doors embedded
    # This is what the CNC will see - a single sheet with all the door features
    
    print("\n=== Creating CNC Layout ===")
    
    # Start with empty sheet volume
    nested_layout = sheet
    
    # First, place all doors into the sheet
    for i, door in enumerate(doors, start=1):
        door_bb = door.val().BoundingBox()
        
        # Cut out a pocket where the door will go
        # Make pocket slightly smaller to ensure clean union
        pocket = (cq.Workplane("XY")
                 .workplane(offset=0)
                 .rect(door_bb.xlen - 0.01, door_bb.ylen - 0.01)
                 .extrude(-abs(door_bb.zmin))
                 .translate((door_bb.xmin + door_bb.xlen/2, 
                           door_bb.ymin + door_bb.ylen/2, 
                           0)))
        
        # Cut pocket from sheet
        nested_layout = nested_layout.cut(pocket)
        
        # Now union the door into that space
        nested_layout = nested_layout.union(door)
        print(f"Embedded door {i} into sheet")
    
    # Now add perimeter grooves to show where doors will be cut out
    # These represent the tool paths for separating doors from the sheet
    sheet_thickness = abs(sheet_bb.zmin)
    
    # Use provided depth or default to shallow visualization groove
    if kerf_visualization_depth is None:
        kerf_visualization_depth = sheet_thickness
    
    # Tool diameter plus small clearance
    kerf_width = tool_diameter + 0.5  # Add 0.5mm clearance
    
    print(f"Adding perimeter cut lines (tool: {tool_diameter}mm, kerf: {kerf_width}mm)...")
    for i, door in enumerate(doors, start=1):
        door_bb = door.val().BoundingBox()
        
        # Create a rectangular groove around each door perimeter
        # This is a thin rectangular ring
        outer_rect = (cq.Workplane("XY")
                     .rect(door_bb.xlen + kerf_width, door_bb.ylen + kerf_width))
        inner_rect = (cq.Workplane("XY")
                     .rect(door_bb.xlen - kerf_width, door_bb.ylen - kerf_width))
        
        # Create the ring by subtracting inner from outer
        groove = (outer_rect.extrude(-kerf_visualization_depth)
                 .cut(inner_rect.extrude(-kerf_visualization_depth))
                 .translate((door_bb.xmin + door_bb.xlen/2,
                           door_bb.ymin + door_bb.ylen/2,
                           0)))
        
        # Cut this groove into the layout
        nested_layout = nested_layout.cut(groove)
        print(f"Added perimeter groove for door {i}")
    
    # Export the nested layout
    nested_stl_path = out_dir / "cnc_nested_layout.stl"
    try:
        cq.exporters.export(nested_layout.val(), str(nested_stl_path))
        print(f"✓ Exported CNC nested layout to: {nested_stl_path}")
    except Exception as e:
        print(f"✗ Error exporting nested STL: {e}")

    # Also export as STEP for CAM software that prefers it
    nested_step_path = out_dir / "cnc_nested_layout.step"
    try:
        cq.exporters.export(nested_layout.val(), str(nested_step_path))
        print(f"✓ Exported CNC nested layout to: {nested_step_path}")
    except Exception as e:
        print(f"✗ Error exporting nested STEP: {e}")

    # === Alternative: Simple Union (may work better with some CAM) ===
    # Just union all parts without cutting pockets first
    simple_union = sheet
    for i, door in enumerate(doors, start=1):
        try:
            simple_union = simple_union.union(door)
        except Exception as e:
            print(f"Warning: Could not union door {i}: {e}")
    
    simple_path = out_dir / "cnc_simple_union.stl"
    try:
        cq.exporters.export(simple_union.val(), str(simple_path))
        print(f"✓ Exported simple union to: {simple_path}")
    except:
        pass

    # Export sheet-only for reference
    try:
        cq.exporters.export(sheet.val(), str(out_dir / "sheet_blank.stl"))
        print(f"✓ Exported blank sheet reference")
    except:
        pass

    # 2D DXF for CAM software (cutting boundaries)
    try:
        import ezdxf
        doc = ezdxf.new("R2010")
        msp = doc.modelspace()

        def rect(x, y, w, h, layer):
            msp.add_lwpolyline(
                [(x, y), (x+w, y), (x+w, y+h), (x, y+h), (x, y)],
                dxfattribs={"layer": layer, "closed": True},
            )

        # Sheet boundary
        rect(sheet_bb.xmin, sheet_bb.ymin, sheet_bb.xlen, sheet_bb.ylen, "SHEET_BOUNDARY")
        
        # Door cut boundaries
        for i, d in enumerate(doors, start=1):
            door_bb = d.val().BoundingBox()
            rect(door_bb.xmin, door_bb.ymin, door_bb.xlen, door_bb.ylen, f"CUT_DOOR_{i}")
            
            # If there's a panel recess, add that as a separate layer
            # This is approximate - actual recess geometry is in the 3D model
            faces = d.faces("<Z").vals()
            if len(faces) > 1:  # Has a recess
                # Estimate panel position (simplified)
                panel_inset = 60  # Based on typical stile/rail width
                rect(door_bb.xmin + panel_inset, 
                     door_bb.ymin + panel_inset,
                     door_bb.xlen - 2*panel_inset,
                     door_bb.ylen - 2*panel_inset,
                     f"POCKET_DOOR_{i}")
        
        doc.saveas(str(out_dir / "cnc_layout.dxf"))
        print(f"✓ Exported CNC DXF to: cnc_layout.dxf")
    except Exception as e:
        print(f"Note: Could not export DXF: {e}")

    print("\n=== CNC Export Complete ===")
    print(f"Main file for CAM: {nested_stl_path}")
    print(f"The nested layout shows doors embedded in the sheet as they would be cut from MDF.\n")

def rect_bbox(part: cq.Workplane) -> Dict[str, float]:
    bb = part.val().BoundingBox()
    return {"x": bb.xmin, "y": bb.ymin, "w": bb.xlen, "h": bb.ylen}

def write_design_intent(doors_bbox: List[Dict[str, float]], cfg: Dict[str, Any], out_json: Path) -> None:
    """Write CNC-specific metadata including tool paths and operations"""
    intents = []
    for i, bb in enumerate(doors_bbox, start=1):
        # Perimeter cut (through-cut to separate door from sheet)
        intents.append({
            "part_id": f"door_{i}",
            "operation": "profile_cut",
            "edge_ref": "outer_perimeter",
            "depth": "through",
            "tool": "1/4_inch_endmill",
            "priority": 100  # Do profile cuts last
        })
        
        comp = cfg.get("component", {})
        props = comp.get("props", {})
        if float(props.get("panel_recess", 0)) > 0:
            # Panel pocket (partial depth)
            intents.append({
                "part_id": f"door_{i}",
                "operation": "pocket",
                "edge_ref": "panel_recess",
                "depth_mm": props.get("panel_recess"),
                "tool": "1/4_inch_endmill",
                "priority": 20  # Do pockets first
            })
    
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps({"cnc_operations": intents}, indent=2), encoding="utf-8")