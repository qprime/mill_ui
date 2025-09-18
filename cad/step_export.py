from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

try:
    import cadquery as cq
except ImportError:  # pragma: no cover - optional dependency
    cq = None  # type: ignore


@dataclass(frozen=True)
class SheetSpec:
    width_mm: float
    height_mm: float
    thickness_mm: float


@dataclass(frozen=True)
class ResolvedShape:
    type: str
    geometry: Dict[str, Any]
    feature: Dict[str, Any]
    placement: Dict[str, Any]
    id: Optional[str] = None


@dataclass(frozen=True)
class RectProfileInfo:
    """Metadata for rectangular through profiles used to detect shared seams."""

    id: str
    center_x: float
    center_y: float
    width: float
    height: float

    @property
    def left(self) -> float:
        return self.center_x - 0.5 * self.width

    @property
    def right(self) -> float:
        return self.center_x + 0.5 * self.width

    @property
    def bottom(self) -> float:
        return self.center_y - 0.5 * self.height

    @property
    def top(self) -> float:
        return self.center_y + 0.5 * self.height


@dataclass(frozen=True)
class SharedSeam:
    """Represents a coincident edge between two rectangular profiles."""

    orientation: str  # "vertical" or "horizontal"
    coord: float      # x for vertical seams, y for horizontal
    span_start: float
    span_end: float
    negative_id: str  # left (vertical) or bottom (horizontal)
    positive_id: str  # right (vertical) or top (horizontal)


_DEFAULT_KERF_MM = 3.175
_EPSILON = 1.0  # extra depth for through cuts so STEP shows daylight


def _feature_depth_mm(feature: Dict[str, Any], sheet_thickness: float) -> float:
    ftype = str(feature.get("type", "profile")).lower()
    if ftype == "pocket" or ftype == "engrave":
        return float(feature.get("depth_mm", 0.0))
    depth = feature.get("depth")
    if depth in (None, "through"):
        return float(sheet_thickness) + _EPSILON
    return float(depth)


def _center_xy(shape: ResolvedShape) -> Tuple[float, float]:
    plc = shape.placement or {}
    value = plc.get("center_xy_mm")
    if isinstance(value, (tuple, list)) and len(value) == 2:
        return float(value[0]), float(value[1])
    return 0.0, 0.0


def _workplane_for_shape(shape: ResolvedShape) -> Optional[cq.Workplane]:
    cx, cy = _center_xy(shape)
    if shape.type.lower() == "rect":
        w = float(shape.geometry.get("w_mm", 0.0))
        h = float(shape.geometry.get("h_mm", 0.0))
        if w <= 0 or h <= 0:
            return None
        return cq.Workplane("XY").center(cx, cy).rect(w, h)
    if shape.type.lower() == "circle":
        d = float(shape.geometry.get("diameter_mm", 0.0))
        if d <= 0:
            return None
        r = d * 0.5
        return cq.Workplane("XY").center(cx, cy).circle(r)
    return None


def _apply_profile_cut(sheet: cq.Workplane,
                       shape: ResolvedShape,
                       kerf_mm: float,
                       sheet_thickness: float,
                       floating_parts: Optional[Dict[str, cq.Workplane]] = None,
                       part_id: Optional[str] = None) -> cq.Workplane:
    kerf = kerf_mm if kerf_mm > 0 else _DEFAULT_KERF_MM
    feature_type = shape.type.lower()
    cx, cy = _center_xy(shape)

    if feature_type == "rect":
        w = float(shape.geometry.get("w_mm", 0.0))
        h = float(shape.geometry.get("h_mm", 0.0))
        if w > 0.0 and h > 0.0:
            opening = cq.Workplane("XY").center(cx, cy).rect(w + kerf, h + kerf).extrude(-sheet_thickness - _EPSILON)
            sheet = sheet.cut(opening)
            if floating_parts is not None:
                pid = part_id or shape.id or f"part_{len(floating_parts) + 1}"
                floating_parts[pid] = cq.Workplane("XY").center(cx, cy).rect(w, h).extrude(-sheet_thickness)
            return sheet

    if feature_type == "circle":
        d = float(shape.geometry.get("diameter_mm", 0.0))
        if d > 0.0:
            opening = cq.Workplane("XY").center(cx, cy).circle(d * 0.5 + kerf * 0.5).extrude(-sheet_thickness - _EPSILON)
            sheet = sheet.cut(opening)
            if floating_parts is not None:
                pid = part_id or shape.id or f"part_{len(floating_parts) + 1}"
                floating_parts[pid] = cq.Workplane("XY").center(cx, cy).circle(d * 0.5).extrude(-sheet_thickness)
            return sheet

    base = _workplane_for_shape(shape)
    if base is not None:
        sheet = sheet.cut(base.extrude(-sheet_thickness - _EPSILON))
        if floating_parts is not None:
            pid = part_id or shape.id or f"part_{len(floating_parts) + 1}"
            floating_parts[pid] = base.extrude(-sheet_thickness)
    return sheet


def _apply_partial_cut(sheet: cq.Workplane,
                        shape: ResolvedShape,
                        depth_mm: float) -> cq.Workplane:
    base = _workplane_for_shape(shape)
    if base is None or depth_mm <= 0:
        return sheet
    cut = base.extrude(-depth_mm)
    return sheet.cut(cut)


def _find_shared_rect_seams(rects: Dict[str, RectProfileInfo],
                            *,
                            tolerance_mm: float = 0.05,
                            min_overlap_mm: float = 1.0) -> List[SharedSeam]:
    """Identify seams where rectangular profiles touch with no explicit gap."""

    if len(rects) < 2:
        return []

    seams: List[SharedSeam] = []
    rect_items = list(rects.items())

    for i in range(len(rect_items)):
        _, rect_a = rect_items[i]
        for j in range(i + 1, len(rect_items)):
            _, rect_b = rect_items[j]

            # Vertical seam: right edge of one meets left edge of the other
            if abs(rect_a.right - rect_b.left) <= tolerance_mm or abs(rect_b.right - rect_a.left) <= tolerance_mm:
                if abs(rect_a.right - rect_b.left) <= tolerance_mm:
                    left_rect, right_rect = rect_a, rect_b
                else:
                    left_rect, right_rect = rect_b, rect_a

                overlap_start = max(left_rect.bottom, right_rect.bottom)
                overlap_end = min(left_rect.top, right_rect.top)
                if overlap_end - overlap_start >= min_overlap_mm:
                    seam_x = 0.5 * (left_rect.right + right_rect.left)
                    seams.append(
                        SharedSeam(
                            orientation="vertical",
                            coord=seam_x,
                            span_start=overlap_start,
                            span_end=overlap_end,
                            negative_id=left_rect.id,
                            positive_id=right_rect.id,
                        )
                    )
                    continue

            # Horizontal seam: top of one meets bottom of the other
            if abs(rect_a.top - rect_b.bottom) <= tolerance_mm or abs(rect_b.top - rect_a.bottom) <= tolerance_mm:
                if abs(rect_a.top - rect_b.bottom) <= tolerance_mm:
                    bottom_rect, top_rect = rect_a, rect_b
                else:
                    bottom_rect, top_rect = rect_b, rect_a

                overlap_start = max(bottom_rect.left, top_rect.left)
                overlap_end = min(bottom_rect.right, top_rect.right)
                if overlap_end - overlap_start >= min_overlap_mm:
                    seam_y = 0.5 * (bottom_rect.top + top_rect.bottom)
                    seams.append(
                        SharedSeam(
                            orientation="horizontal",
                            coord=seam_y,
                            span_start=overlap_start,
                            span_end=overlap_end,
                            negative_id=bottom_rect.id,
                            positive_id=top_rect.id,
                        )
                    )

    return seams


def _trim_parts_for_shared_seams(parts: Dict[str, cq.Workplane],
                                 seams: List[SharedSeam],
                                 *,
                                 kerf_mm: float,
                                 sheet_thickness_mm: float) -> None:
    """Slice away kerf/2 from each part that participates in a shared seam."""

    if cq is None or not seams:
        return

    half_kerf = 0.5 * float(kerf_mm)
    if half_kerf <= 0.0:
        return

    for seam in seams:
        span = float(seam.span_end) - float(seam.span_start)
        if span <= 0.0:
            continue

        neg_part = parts.get(seam.negative_id)
        pos_part = parts.get(seam.positive_id)
        if neg_part is None and pos_part is None:
            continue

        if seam.orientation == "vertical":
            center_y = 0.5 * (float(seam.span_start) + float(seam.span_end))
            length = span
            if neg_part is not None:
                strip = cq.Workplane("XY").center(seam.coord - 0.5 * half_kerf, center_y)
                strip = strip.rect(half_kerf, length).extrude(-sheet_thickness_mm)
                parts[seam.negative_id] = neg_part.cut(strip)
            if pos_part is not None:
                strip = cq.Workplane("XY").center(seam.coord + 0.5 * half_kerf, center_y)
                strip = strip.rect(half_kerf, length).extrude(-sheet_thickness_mm)
                parts[seam.positive_id] = pos_part.cut(strip)
        else:  # horizontal seam
            center_x = 0.5 * (float(seam.span_start) + float(seam.span_end))
            length = span
            if neg_part is not None:
                strip = cq.Workplane("XY").center(center_x, seam.coord - 0.5 * half_kerf)
                strip = strip.rect(length, half_kerf).extrude(-sheet_thickness_mm)
                parts[seam.negative_id] = neg_part.cut(strip)
            if pos_part is not None:
                strip = cq.Workplane("XY").center(center_x, seam.coord + 0.5 * half_kerf)
                strip = strip.rect(length, half_kerf).extrude(-sheet_thickness_mm)
                parts[seam.positive_id] = pos_part.cut(strip)


def build_step_solids(sheet: SheetSpec,
                      shapes: Iterable[Dict[str, Any]],
                      *,
                      kerf_mm: float | None = None,
                      include_floating_parts: bool = True) -> Tuple[cq.Workplane, List[cq.Workplane]]:
    if cq is None:  # pragma: no cover - handled by caller
        raise ImportError("cadquery is required for STEP export")

    kerf = float(kerf_mm) if kerf_mm and kerf_mm > 0 else _DEFAULT_KERF_MM
    base = cq.Workplane("XY").rect(sheet.width_mm, sheet.height_mm).extrude(-sheet.thickness_mm)

    floating_parts: Dict[str, cq.Workplane] = {}
    rect_profiles: Dict[str, RectProfileInfo] = {}
    offset_x = -sheet.width_mm * 0.5
    offset_y = -sheet.height_mm * 0.5

    resolved: List[ResolvedShape] = []
    for it in shapes:
        placement = dict(it.get("placement") or {})
        cx, cy = 0.0, 0.0
        value = placement.get("center_xy_mm")
        if isinstance(value, (tuple, list)) and len(value) == 2:
            cx = float(value[0]) + offset_x
            cy = float(value[1]) + offset_y
        else:
            cx = offset_x
            cy = offset_y
        placement["center_xy_mm"] = [cx, cy]

        resolved.append(ResolvedShape(
            type=str(it.get("type", "")),
            geometry=it.get("geometry") or {},
            feature=it.get("feature") or {},
            placement=placement,
            id=it.get("id")
        ))

    for shape in resolved:
        feature_type = str(shape.feature.get("type", "profile")).lower()
        depth = _feature_depth_mm(shape.feature, sheet.thickness_mm)
        part_id = shape.id or f"part_{len(floating_parts) + 1}"
        if feature_type == "profile" and depth >= sheet.thickness_mm:
            base = _apply_profile_cut(
                base,
                shape,
                kerf,
                sheet.thickness_mm,
                floating_parts if include_floating_parts else None,
                part_id=part_id if include_floating_parts else None,
            )
            if include_floating_parts and shape.type.lower() == "rect" and part_id:
                cx, cy = _center_xy(shape)
                rect_profiles[part_id] = RectProfileInfo(
                    id=part_id,
                    center_x=cx,
                    center_y=cy,
                    width=float(shape.geometry.get("w_mm", 0.0)),
                    height=float(shape.geometry.get("h_mm", 0.0)),
                )
        else:
            # partial cuts apply to the remaining sheet (and floating parts later)
            base = _apply_partial_cut(base, shape, min(depth, sheet.thickness_mm))

    if include_floating_parts and floating_parts:
        seams = _find_shared_rect_seams(rect_profiles)
        _trim_parts_for_shared_seams(floating_parts, seams, kerf_mm=kerf, sheet_thickness_mm=sheet.thickness_mm)

        # apply pockets to floating parts
        for shape in resolved:
            feature_type = str(shape.feature.get("type", "profile")).lower()
            depth = _feature_depth_mm(shape.feature, sheet.thickness_mm)
            if feature_type in ("pocket", "engrave") and depth > 0:
                pocket_profile = _workplane_for_shape(shape)
                if pocket_profile is None:
                    continue
                cut = pocket_profile.extrude(-min(depth, sheet.thickness_mm))
                cx, cy = _center_xy(shape)
                for pid, part in list(floating_parts.items()):
                    bb = part.val().BoundingBox()
                    if bb.xmin - 1e-6 <= cx <= bb.xmax + 1e-6 and bb.ymin - 1e-6 <= cy <= bb.ymax + 1e-6:
                        floating_parts[pid] = part.cut(cut)

    parts_out: List[cq.Workplane] = list(floating_parts.values()) if include_floating_parts else []
    return base, parts_out


def export_step(sheet: SheetSpec,
                shapes: Iterable[Dict[str, Any]],
                output_path: Path,
                *,
                kerf_mm: float | None = None,
                include_floating_parts: bool = True) -> None:
    if cq is None:  # pragma: no cover
        raise ImportError("cadquery is required for STEP export")

    solid, parts = build_step_solids(sheet, shapes, kerf_mm=kerf_mm, include_floating_parts=include_floating_parts)

    compound_shapes = [solid.val()]
    if include_floating_parts:
        compound_shapes.extend(part.val() for part in parts)
    try:
        compound = cq.Compound.makeCompound(compound_shapes) if len(compound_shapes) > 1 else compound_shapes[0]
    except Exception:
        compound = solid.val()
    cq.exporters.export(compound, str(output_path))

    if include_floating_parts:
        for idx, part in enumerate(parts):
            part_path = output_path.with_name(output_path.stem + f"_part{idx+1}" + output_path.suffix)
            cq.exporters.export(part.val(), str(part_path))
