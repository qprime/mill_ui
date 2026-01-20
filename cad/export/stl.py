
from __future__ import annotations

import numpy as np
import trimesh
from pathlib import Path
from typing import Any

from core.constants import DepthMode

try:
    from shapely.geometry import Polygon, Point, MultiPolygon
    from shapely import affinity
    from shapely.ops import unary_union
except ImportError:
    raise ImportError(
        "shapely is required for STL export. Install with: pip install shapely"
    )


def shape_dict_to_polygon(shape: dict[str, Any]) -> Polygon:
    shape_type = shape["type"]
    geometry = shape["geometry"]
    cx, cy = shape["placement"]["center_xy_mm"]

    if shape_type == "Rect":
        w = geometry["w_mm"]
        h = geometry["h_mm"]

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

        center = Point(cx, cy)
        return center.buffer(radius, resolution=32)

    elif shape_type == "Polyline":
        points = geometry["points"]

        coords = list(points)
        if coords[0] != coords[-1]:
            coords.append(coords[0])
        return Polygon(coords)

    elif shape_type == "Polygon":
        points = geometry.get("points", [])
        holes = geometry.get("holes", [])

        if not points:
            raise ValueError("Polygon shape has no points")

        outer_coords = [(p[0], p[1]) for p in points]
        if outer_coords[0] != outer_coords[-1]:
            outer_coords.append(outer_coords[0])

        hole_coords = []
        for hole in holes:
            hole_ring = [(p[0], p[1]) for p in hole]
            if hole_ring[0] != hole_ring[-1]:
                hole_ring.append(hole_ring[0])
            hole_coords.append(hole_ring)

        return Polygon(outer_coords, holes=hole_coords if hole_coords else None)

    elif shape_type == "RoundedRect":
        w = geometry["w_mm"]
        h = geometry["h_mm"]
        radius_tl = geometry.get("radius_tl_mm", geometry.get("radius_mm", 0))
        radius_tr = geometry.get("radius_tr_mm", geometry.get("radius_mm", 0))
        radius_br = geometry.get("radius_br_mm", geometry.get("radius_mm", 0))
        radius_bl = geometry.get("radius_bl_mm", geometry.get("radius_mm", 0))

        half_w = w / 2
        half_h = h / 2

        coords = []
        arc_resolution = 8

        if radius_bl > 0:
            for i in range(arc_resolution + 1):
                angle = np.pi + (np.pi / 2) * (i / arc_resolution)
                coords.append((
                    -half_w + radius_bl + radius_bl * np.cos(angle),
                    -half_h + radius_bl + radius_bl * np.sin(angle)
                ))
        else:
            coords.append((-half_w, -half_h))

        if radius_br > 0:
            for i in range(arc_resolution + 1):
                angle = 3 * np.pi / 2 + (np.pi / 2) * (i / arc_resolution)
                coords.append((
                    half_w - radius_br + radius_br * np.cos(angle),
                    -half_h + radius_br + radius_br * np.sin(angle)
                ))
        else:
            coords.append((half_w, -half_h))

        if radius_tr > 0:
            for i in range(arc_resolution + 1):
                angle = 0 + (np.pi / 2) * (i / arc_resolution)
                coords.append((
                    half_w - radius_tr + radius_tr * np.cos(angle),
                    half_h - radius_tr + radius_tr * np.sin(angle)
                ))
        else:
            coords.append((half_w, half_h))

        if radius_tl > 0:
            for i in range(arc_resolution + 1):
                angle = np.pi / 2 + (np.pi / 2) * (i / arc_resolution)
                coords.append((
                    -half_w + radius_tl + radius_tl * np.cos(angle),
                    half_h - radius_tl + radius_tl * np.sin(angle)
                ))
        else:
            coords.append((-half_w, half_h))

        poly = Polygon(coords)
        return affinity.translate(poly, xoff=cx, yoff=cy)

    else:
        raise ValueError(f"Unsupported shape type: {shape_type}")


def apply_kerf_offset(poly: Polygon, kerf_mm: float, feature_type: str, side: str | None) -> Polygon:
    if kerf_mm == 0:
        return poly


    if feature_type == "profile":
        if side == "outside":

            return poly.buffer(kerf_mm, resolution=16)
        elif side == "inside":

            return poly.buffer(-kerf_mm, resolution=16)
        else:

            return poly

    elif feature_type in ("pocket", "hole"):

        return poly.buffer(-kerf_mm, resolution=16)

    elif feature_type == "engrave":

        return poly

    else:

        return poly


def extrude_polygon_to_mesh(poly: Polygon | MultiPolygon, height_mm: float) -> trimesh.Trimesh:

    if isinstance(poly, MultiPolygon):
        meshes = []
        for geom in poly.geoms:
            mesh = trimesh.creation.extrude_polygon(geom, height=height_mm)
            if not mesh.is_watertight:
                trimesh.repair.fix_normals(mesh)
                trimesh.repair.fill_holes(mesh)
            meshes.append(mesh)
        if len(meshes) == 1:
            return meshes[0]
        return trimesh.util.concatenate(meshes)


    mesh = trimesh.creation.extrude_polygon(poly, height=height_mm)


    if not mesh.is_watertight:

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
    output_path = Path(output_path)


    quality_map = {"low": 16, "medium": 32, "high": 64}
    circle_resolution = quality_map.get(quality, 32)


    profile_outside_shapes = []
    subtractive_shapes = []

    for shape in shapes:
        feature = shape["feature"]
        feature_type = feature["type"]
        side = feature.get("side")
        shape_type = shape.get("type", "")

        if shape_type == "Polyline" and feature_type == "engrave":
            continue

        if feature_type == "profile" and side == "outside":
            profile_outside_shapes.append(shape)
        else:
            subtractive_shapes.append(shape)


    all_x = []
    all_y = []
    all_shapes = profile_outside_shapes + subtractive_shapes
    for shape in all_shapes:
        poly = shape_dict_to_polygon(shape)
        bounds = poly.bounds
        all_x.extend([bounds[0], bounds[2]])
        all_y.extend([bounds[1], bounds[3]])

    if not all_x:
        raise ValueError("No shapes to export")

    min_x, max_x = min(all_x), max(all_x)
    min_y, max_y = min(all_y), max(all_y)


    margin = 10.0
    stock_min_x = min_x - margin
    stock_min_y = min_y - margin
    stock_max_x = max_x + margin
    stock_max_y = max_y + margin

    width = stock_max_x - stock_min_x
    height = stock_max_y - stock_min_y


    stock = trimesh.creation.box(extents=[width, height, sheet_thickness_mm])
    stock.apply_translation([stock_min_x + width/2, stock_min_y + height/2, sheet_thickness_mm/2])


    floating_parts = []


    if profile_outside_shapes:

        part_polygons = []
        profile_depth_mm = sheet_thickness_mm

        for shape in profile_outside_shapes:
            feature = shape["feature"]


            poly = shape_dict_to_polygon(shape)
            side = feature.get("side")
            poly_kerf = apply_kerf_offset(poly, kerf_mm, "profile", side)
            part_polygons.append(poly_kerf)


            depth_value = feature["depth"]
            if DepthMode.is_through(depth_value):
                depth_mm = sheet_thickness_mm
            else:
                depth_mm = feature.get("depth_mm", depth_value)
            profile_depth_mm = min(profile_depth_mm, depth_mm)


        combined_poly = unary_union(part_polygons)


        part_mesh = extrude_polygon_to_mesh(combined_poly, profile_depth_mm)
        part_mesh.apply_translation([0, 0, 0])


        try:
            if not stock.is_watertight:
                trimesh.repair.fix_normals(stock)
                trimesh.repair.fill_holes(stock)

            if not part_mesh.is_watertight:
                trimesh.repair.fix_normals(part_mesh)
                trimesh.repair.fill_holes(part_mesh)

            result = None
            last_error = None
            for engine in ["manifold", "blender"]:
                try:

                    result = stock.intersection(part_mesh, engine=engine)
                    break
                except Exception as e:
                    last_error = e
                    continue

            if result is None:
                print(f"Warning: Boolean intersection failed for profile outside shapes: {last_error}")
            elif isinstance(result, list):
                if len(result) > 0:

                    stock = trimesh.util.concatenate(result)
            else:
                stock = result

        except Exception as e:
            print(f"Warning: Boolean intersection failed for profile outside shapes: {e}")


    for shape in subtractive_shapes:
        feature = shape["feature"]
        feature_type = feature["type"]


        poly = shape_dict_to_polygon(shape)
        side = feature.get("side")
        poly_kerf = apply_kerf_offset(poly, kerf_mm, feature_type, side)


        depth_value = feature["depth"]
        if DepthMode.is_through(depth_value):
            depth_mm = sheet_thickness_mm
        else:
            depth_mm = feature.get("depth_mm", depth_value)


        feature_mesh = extrude_polygon_to_mesh(poly_kerf, depth_mm)


        if feature_type == "profile":

            feature_mesh.apply_translation([0, 0, 0])
        elif feature_type == "pocket":

            feature_mesh.apply_translation([0, 0, sheet_thickness_mm - depth_mm])
        elif feature_type == "hole":

            feature_mesh.apply_translation([0, 0, 0])
        elif feature_type == "engrave":

            feature_mesh.apply_translation([0, 0, sheet_thickness_mm - depth_mm])


        try:

            if not stock.is_watertight:
                trimesh.repair.fix_normals(stock)
                trimesh.repair.fill_holes(stock)

            if not feature_mesh.is_watertight:
                trimesh.repair.fix_normals(feature_mesh)
                trimesh.repair.fill_holes(feature_mesh)


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

                print(f"Warning: Boolean operation failed for shape {shape.get('id', 'unknown')}: {last_error}")
                continue


            if isinstance(result, list):

                if len(result) > 0:

                    volumes = [m.volume for m in result]
                    main_idx = volumes.index(max(volumes))
                    stock = result[main_idx]


                    for i, part in enumerate(result):
                        if i != main_idx and include_floating_parts:
                            floating_parts.append(part)
            else:
                stock = result

        except Exception as e:
            print(f"Warning: Boolean operation failed for shape {shape.get('id', 'unknown')}: {e}")
            continue


    stock.export(str(output_path), file_type="stl")


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
