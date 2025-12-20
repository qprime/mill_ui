"""STL export using trimesh for visual validation.

This module exports 2.5D CNC layouts to STL mesh format for visual inspection.
The primary use case is validating pocket depths, profile orientation, and
feature placement before expensive CNC machining.

Architecture:
    1. shape dict → 2D polygon (shapely)
    2. Apply kerf offset if requested (shapely.buffer)
    3. Extrude polygon → 3D mesh (trimesh)
    4. Boolean subtract features from stock (trimesh.boolean)
    5. Write binary STL

Supported shapes: Rect, Circle, Polyline
Supported features: profile (through-cut), pocket, hole, engrave
"""

from __future__ import annotations

import numpy as np
import trimesh
from pathlib import Path
from typing import Any

try:
    from shapely.geometry import Polygon, Point
    from shapely import affinity
except ImportError:
    raise ImportError(
        "shapely is required for STL export. Install with: pip install shapely"
    )


def shape_dict_to_polygon(shape: dict[str, Any]) -> Polygon:
    """Convert shape dict to shapely Polygon.

    Args:
        shape: Shape dict with type, geometry, placement

    Returns:
        Shapely Polygon representing the 2D footprint

    Raises:
        ValueError: If shape type is unsupported
    """
    shape_type = shape["type"]
    geometry = shape["geometry"]
    cx, cy = shape["placement"]["center_xy_mm"]

    if shape_type == "Rect":
        w = geometry["w_mm"]
        h = geometry["h_mm"]
        # Create rect centered at origin, then translate
        half_w = w / 2
        half_h = h / 2
        coords = [
            (-half_w, -half_h),
            (half_w, -half_h),
            (half_w, half_h),
            (-half_w, half_h),
        ]
        poly = Polygon(coords)
        return affinity.translate(poly, xoff=cx, yoff=cy)

    elif shape_type == "Circle":
        diameter = geometry["diameter_mm"]
        radius = diameter / 2
        # Use Point.buffer to create circle
        center = Point(cx, cy)
        return center.buffer(radius, resolution=32)  # 32 segments for circles

    elif shape_type == "Polyline":
        points = geometry["points"]
        # Polyline points are already in absolute coordinates
        # If not closed, close it
        coords = list(points)
        if coords[0] != coords[-1]:
            coords.append(coords[0])
        return Polygon(coords)

    else:
        raise ValueError(f"Unsupported shape type: {shape_type}")


def apply_kerf_offset(poly: Polygon, kerf_mm: float, feature_type: str, side: str | None) -> Polygon:
    """Apply kerf compensation offset to polygon.

    Args:
        poly: Input polygon
        kerf_mm: Kerf amount in mm (tool radius)
        feature_type: Feature type (profile, pocket, hole, engrave)
        side: Profile side (inside, outside, on) or None

    Returns:
        Offset polygon
    """
    if kerf_mm == 0:
        return poly

    # Determine offset direction
    if feature_type == "profile":
        if side == "outside":
            # Outside profile: expand (positive offset)
            return poly.buffer(kerf_mm, resolution=16)
        elif side == "inside":
            # Inside profile: shrink (negative offset)
            return poly.buffer(-kerf_mm, resolution=16)
        else:  # side == "on"
            # No offset for on-line profiles
            return poly

    elif feature_type in ("pocket", "hole"):
        # Pockets and holes: shrink (negative offset to make hole bigger)
        return poly.buffer(-kerf_mm, resolution=16)

    elif feature_type == "engrave":
        # Engraving: no offset (follows path exactly)
        return poly

    else:
        # Unknown feature type: no offset
        return poly


def extrude_polygon_to_mesh(poly: Polygon, height_mm: float) -> trimesh.Trimesh:
    """Extrude 2D polygon to 3D mesh.

    Args:
        poly: Shapely polygon
        height_mm: Extrusion height in mm

    Returns:
        Trimesh object
    """
    # Extrude to 3D
    mesh = trimesh.creation.extrude_polygon(poly, height=height_mm)

    # Ensure mesh is watertight for boolean operations
    if not mesh.is_watertight:
        # Try to fix mesh
        trimesh.repair.fix_normals(mesh)
        trimesh.repair.fill_holes(mesh)

    return mesh


def export_stl(
    shapes: list[dict[str, Any]],
    sheet_thickness_mm: float,
    output_path: str | Path,
    kerf_mm: float = 0.0,
    quality: str = "medium",
    include_floating_parts: bool = True,
) -> None:
    """Export shapes to STL file for visual validation.

    Args:
        shapes: List of shape dicts from ast_to_cad.items_to_shape_dicts()
        sheet_thickness_mm: Stock thickness in mm
        output_path: Path to output .stl file
        kerf_mm: Kerf compensation in mm (default: 0.0)
        quality: Mesh quality - low/medium/high (default: medium)
        include_floating_parts: Export floating parts as separate files (default: True)

    Raises:
        ValueError: If shapes are invalid or export fails
    """
    output_path = Path(output_path)

    # Map quality to circle resolution
    quality_map = {"low": 16, "medium": 32, "high": 64}
    circle_resolution = quality_map.get(quality, 32)

    # Create stock material (starting box)
    # Determine bounding box from all shapes
    all_x = []
    all_y = []
    for shape in shapes:
        poly = shape_dict_to_polygon(shape)
        bounds = poly.bounds  # (minx, miny, maxx, maxy)
        all_x.extend([bounds[0], bounds[2]])
        all_y.extend([bounds[1], bounds[3]])

    if not all_x:
        raise ValueError("No shapes to export")

    min_x, max_x = min(all_x), max(all_x)
    min_y, max_y = min(all_y), max(all_y)

    # Add margin for visualization
    margin = 10.0  # mm
    min_x -= margin
    min_y -= margin
    max_x += margin
    max_y += margin

    width = max_x - min_x
    height = max_y - min_y

    # Create stock box (translate to origin for trimesh)
    stock = trimesh.creation.box(extents=[width, height, sheet_thickness_mm])
    stock.apply_translation([min_x + width/2, min_y + height/2, sheet_thickness_mm/2])

    # Process features
    floating_parts = []

    for shape in shapes:
        feature = shape["feature"]
        feature_type = feature["type"]

        # Convert to polygon and apply kerf
        poly = shape_dict_to_polygon(shape)
        side = feature.get("side")
        poly_kerf = apply_kerf_offset(poly, kerf_mm, feature_type, side)

        # Determine depth
        depth_value = feature["depth"]
        if depth_value == "through":
            depth_mm = sheet_thickness_mm
        else:
            depth_mm = feature.get("depth_mm", depth_value)

        # Extrude feature
        feature_mesh = extrude_polygon_to_mesh(poly_kerf, depth_mm)

        # Position feature mesh at correct Z level
        if feature_type == "profile" and depth_value == "through":
            # Through profile: cuts all the way through
            feature_mesh.apply_translation([0, 0, 0])
        elif feature_type == "pocket":
            # Pocket: cuts from top surface down
            feature_mesh.apply_translation([0, 0, sheet_thickness_mm - depth_mm])
        elif feature_type == "hole":
            # Hole: cuts all the way through
            feature_mesh.apply_translation([0, 0, 0])
        elif feature_type == "engrave":
            # Engrave: shallow cut from top
            feature_mesh.apply_translation([0, 0, sheet_thickness_mm - depth_mm])

        # Perform boolean subtraction
        try:
            # Ensure both meshes are watertight before boolean op
            if not stock.is_watertight:
                trimesh.repair.fix_normals(stock)
                trimesh.repair.fill_holes(stock)

            if not feature_mesh.is_watertight:
                trimesh.repair.fix_normals(feature_mesh)
                trimesh.repair.fill_holes(feature_mesh)

            # Try multiple boolean engines in order of preference
            result = None
            last_error = None
            for engine in ["manifold", "blender"]:
                try:
                    result = stock.difference(feature_mesh, engine=engine)
                    break
                except Exception as e:
                    last_error = e
                    continue

            if result is None:
                # Fallback: skip this operation
                print(f"Warning: Boolean operation failed for shape {shape.get('id', 'unknown')}: {last_error}")
                continue

            # Check if result is a single mesh or multiple parts
            if isinstance(result, list):
                # Multiple parts after cut (floating parts created)
                if len(result) > 0:
                    # Largest part is the main stock
                    volumes = [m.volume for m in result]
                    main_idx = volumes.index(max(volumes))
                    stock = result[main_idx]

                    # Smaller parts are floating pieces
                    for i, part in enumerate(result):
                        if i != main_idx and include_floating_parts:
                            floating_parts.append(part)
            else:
                stock = result

        except Exception as e:
            print(f"Warning: Boolean operation failed for shape {shape.get('id', 'unknown')}: {e}")
            continue

    # Export main part
    stock.export(str(output_path), file_type="stl")

    # Export floating parts
    if floating_parts:
        base_name = output_path.stem
        output_dir = output_path.parent
        for i, part in enumerate(floating_parts):
            floating_path = output_dir / f"{base_name}_part_{i+1}.stl"
            part.export(str(floating_path), file_type="stl")

    print(f"✓ Exported STL: {output_path}")
    if floating_parts:
        print(f"  + {len(floating_parts)} floating part(s)")


__all__ = ["export_stl", "shape_dict_to_polygon", "apply_kerf_offset", "extrude_polygon_to_mesh"]
