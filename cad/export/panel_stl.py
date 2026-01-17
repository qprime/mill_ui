

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Mapping, Any, Tuple, List, Optional

import numpy as np

from core.constants import DepthMode
from skills.cam_engine.heightfield_solid import triangulate_heightfield
from skills.cam_engine.stl_writer import write_binary_stl

__all__ = ["write_panel_stl"]


def _center_xy(item: Mapping[str, Any]) -> Tuple[float, float]:
    placement = item.get("placement") or {}
    value = placement.get("center_xy_mm")
    if isinstance(value, (tuple, list)) and len(value) == 2:
        return float(value[0]), float(value[1])
    return 0.0, 0.0


def _feature_target_z(feature: Mapping[str, Any] | None, thickness_mm: float) -> float:
    if not feature:
        return float(thickness_mm)

    ftype = str(feature.get("type") or "").lower()

    depth = 0.0
    if DepthMode.is_through(str(feature.get("depth", "")).lower()):
        depth = float(thickness_mm)
    elif "depth_mm" in feature:
        try:
            depth = float(feature["depth_mm"])
        except Exception:
            depth = 0.0
    elif "depth" in feature:
        try:
            depth = float(feature["depth"])
        except Exception:
            depth = 0.0

    depth = max(0.0, min(float(thickness_mm), depth))

    if ftype in {"profile", "pocket", "engrave", "hole"}:
        return float(thickness_mm) - depth
    return float(thickness_mm)


def _apply_rect(height: np.ndarray,
                x_grid: np.ndarray,
                y_grid: np.ndarray,
                center: Tuple[float, float],
                size: Tuple[float, float],
                *,
                mode: str,
                value: float,
                stock_thickness: float,
                profile_mask: Optional[np.ndarray] = None) -> None:
    cx, cy = center
    w, h = size
    if w <= 0.0 or h <= 0.0:
        return
    x0 = cx - 0.5 * w
    x1 = cx + 0.5 * w
    y0 = cy - 0.5 * h
    y1 = cy + 0.5 * h
    mask = (x_grid >= x0) & (x_grid <= x1) & (y_grid >= y0) & (y_grid <= y1)
    if profile_mask is not None and mode == "max":
        profile_mask[mask] = True
    if np.any(mask):
        current = height[mask]
        if mode == "max":
            height[mask] = np.maximum(current, value)
        elif mode == "min":
            height[mask] = np.minimum(current, value)
        elif mode == "set":
            height[mask] = value


def _apply_circle(height: np.ndarray,
                  x_grid: np.ndarray,
                  y_grid: np.ndarray,
                  center: Tuple[float, float],
                  diameter: float,
                  *,
                  mode: str,
                  value: float,
                  stock_thickness: float,
                  profile_mask: Optional[np.ndarray] = None) -> None:
    if diameter <= 0.0:
        return
    cx, cy = center
    r = 0.5 * diameter
    mask = (x_grid - cx) ** 2 + (y_grid - cy) ** 2 <= r * r + 1e-9
    if profile_mask is not None and mode == "max":
        profile_mask[mask] = True
    if np.any(mask):
        current = height[mask]
        if mode == "max":
            height[mask] = np.maximum(current, value)
        elif mode == "min":
            height[mask] = np.minimum(current, value)
        elif mode == "set":
            height[mask] = value


def _polyline_points(item: Mapping[str, Any]) -> List[Tuple[float, float]]:
    geom = item.get("geometry") or {}
    pts = geom.get("points") or []
    cx, cy = _center_xy(item)
    out: List[Tuple[float, float]] = []
    for pt in pts:
        if isinstance(pt, (list, tuple)) and len(pt) == 2:
            out.append((float(pt[0]) + cx, float(pt[1]) + cy))
    return out


def _apply_polyline(height: np.ndarray,
                    x_grid: np.ndarray,
                    y_grid: np.ndarray,
                    points: List[Tuple[float, float]],
                    *,
                    diameter: float,
                    mode: str,
                    value: float,
                    stock_thickness: float) -> None:
    if diameter <= 0.0 or not points:
        return
    samples = list(points)
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        samples.append(((float(x0) + float(x1)) * 0.5, (float(y0) + float(y1)) * 0.5))
    for pt in samples:
        _apply_circle(
            height,
            x_grid,
            y_grid,
            pt,
            diameter,
            mode=mode,
            value=value,
            stock_thickness=stock_thickness,
        )


def write_panel_stl(path: Path,
                    *,
                    width_mm: float,
                    height_mm: float,
                    thickness_mm: float,
                    items: Iterable[Mapping[str, Any]],
                    resolution_mm: float = 1.5) -> Path:

    width = max(float(width_mm), 1.0)
    height = max(float(height_mm), 1.0)
    thickness = max(float(thickness_mm), 0.0)
    pitch = max(0.1, float(resolution_mm))

    nx = max(2, int(round(width / pitch)) + 1)
    ny = max(2, int(round(height / pitch)) + 1)

    xs = np.linspace(0.0, width, nx, dtype=np.float32)
    ys = np.linspace(0.0, height, ny, dtype=np.float32)
    x_grid = xs[np.newaxis, :]
    y_grid = ys[:, np.newaxis]

    heightmap = np.full((ny, nx), thickness, dtype=np.float32)
    profile_mask = np.zeros((ny, nx), dtype=bool)

    for item in items:
        shape_type = str(item.get("type") or "").lower()
        feature = item.get("feature") if isinstance(item.get("feature"), Mapping) else None
        ftype = str((feature or {}).get("type", "")).lower()
        target_z = _feature_target_z(feature, thickness)

        center = _center_xy(item)

        depth_mm = max(0.0, min(thickness, thickness - float(target_z)))
        is_through_profile = False
        if feature:
            depth_flag = str(feature.get("depth", "")).lower()
            is_through_profile = DepthMode.is_through(depth_flag) or depth_mm >= thickness - 1e-6

        if shape_type == "rect":
            geom = item.get("geometry") or {}
            size = (
                float(geom.get("w_mm", 0.0)),
                float(geom.get("h_mm", 0.0)),
            )
            if ftype == "profile":
                if not is_through_profile and depth_mm > 1e-6:
                    _apply_rect(heightmap, x_grid, y_grid, center, size,
                                mode="min", value=target_z, stock_thickness=thickness)
                else:
                    _apply_rect(heightmap, x_grid, y_grid, center, size,
                                mode="max", value=thickness, stock_thickness=thickness,
                                profile_mask=profile_mask)
            else:
                if target_z >= thickness:
                    continue
                _apply_rect(heightmap, x_grid, y_grid, center, size,
                            mode="min", value=target_z, stock_thickness=thickness)
        elif shape_type == "circle":
            geom = item.get("geometry") or {}
            diameter = float(geom.get("diameter_mm", 0.0))
            if ftype == "profile":
                if not is_through_profile and depth_mm > 1e-6:
                    _apply_circle(heightmap, x_grid, y_grid, center, diameter,
                                  mode="min", value=target_z, stock_thickness=thickness)
                else:
                    _apply_circle(heightmap, x_grid, y_grid, center, diameter,
                                  mode="max", value=thickness, stock_thickness=thickness,
                                  profile_mask=profile_mask)
            else:
                if target_z >= thickness:
                    continue
                _apply_circle(heightmap, x_grid, y_grid, center, diameter,
                              mode="min", value=target_z, stock_thickness=thickness)
        elif shape_type == "polyline":
            points = _polyline_points(item)
            if not points:
                continue
            line_width = float((feature or {}).get("line_width_mm", 1.0))
            line_width = max(0.5, line_width)
            mode = "min" if target_z < thickness else "set"
            _apply_polyline(heightmap, x_grid, y_grid, points,
                            diameter=line_width,
                            mode=mode,
                            value=target_z,
                            stock_thickness=thickness)
        else:
            continue

    if np.any(profile_mask):
        heightmap = np.where(profile_mask, heightmap, 0.0)
    heightmap = np.clip(heightmap, 0.0, thickness)
    pitch_out = float(width / max(1, nx - 1))

    tris = triangulate_heightfield(
        heightmap,
        pitch_out,
        base_plane_z_mm=0.0,
        add_base_and_walls=True,
        top_z_mm=thickness,
        z_exaggeration=1.0,
    )
    write_binary_stl(Path(path), tris)
    return Path(path)
