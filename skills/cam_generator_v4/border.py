# path: skills/cam_generator_v4/border.py
# desc: Generate rectangular border toolpaths around carving area
# api: generate_rect_border_moves
# tags: border,toolpath,cam

from __future__ import annotations
from typing import Dict, List, Tuple

__all__ = ["generate_rect_border_moves"]

_Move = Dict[str, float]
Bounds = Tuple[float, float, float, float]

def _rect_path(xmin: float, xmax: float, ymin: float, ymax: float, z: float, feed: float, ccw: bool) -> List[_Move]:
    """Generate moves for a single rectangular path."""
    pts = [(xmin, ymin), (xmax, ymin), (xmax, ymax), (xmin, ymax)]
    if not ccw:
        pts = pts[::-1]
    moves: List[_Move] = []
    for (x, y) in pts + [pts[0]]:  # close the loop
        moves.append({"mode": 1, "x": float(x), "y": float(y), "z": float(z), "f": float(feed)})
    return moves

def generate_rect_border_moves(bounds_mm: Bounds,
                               inset_mm: float,
                               width_mm: float,
                               target_depth_mm: float,
                               stepover_mm: float,
                               feed_mm_min: float,
                               climb_ccw: bool = True) -> List[_Move]:
    """
    Generate concentric rectangular border toolpaths.
    
    Args:
        bounds_mm: (xmin, xmax, ymin, ymax) of the carving area
        inset_mm: Distance from carving edge to start of border (positive = outside carving)
        width_mm: Total width of border ring
        target_depth_mm: Depth to cut border (positive value)
        stepover_mm: Distance between concentric border passes
        feed_mm_min: Feed rate for cutting moves
        climb_ccw: True for climb milling (CCW), False for conventional (CW)
    
    Returns:
        List of move dictionaries for the border toolpath
    """
    xmin, xmax, ymin, ymax = bounds_mm
    
    if stepover_mm <= 0.0 or width_mm <= 0.0:
        return []

    # For outside border: start at inset_mm outside the carving area
    # and extend width_mm further out
    inner_border_offset = inset_mm  # distance outside carving area to start border
    outer_border_offset = inset_mm + width_mm  # distance outside carving area to end border
    
    z = -abs(float(target_depth_mm))  # Ensure depth is negative

    moves: List[_Move] = []
    current_offset = inner_border_offset
    toggle = False
    
    # Generate concentric rectangles from inner to outer
    while current_offset <= outer_border_offset + 1e-9:
        # Calculate rectangle bounds for this pass
        # Expand the carving bounds by current_offset in all directions
        x0 = xmin - current_offset
        x1 = xmax + current_offset  
        y0 = ymin - current_offset
        y1 = ymax + current_offset
        
        # Ensure valid rectangle (should always be valid when expanding outward)
        if x1 <= x0 or y1 <= y0:
            break
            
        # Alternate direction for each pass to minimize tool travel
        ccw = climb_ccw ^ toggle
        moves.extend(_rect_path(x0, x1, y0, y1, z, feed_mm_min, ccw))
        
        # Move to next pass
        current_offset += stepover_mm
        toggle = not toggle
        
        # Stop if we've reached the outer boundary
        if current_offset > outer_border_offset:
            break

    return moves