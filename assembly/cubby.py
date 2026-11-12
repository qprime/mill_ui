from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from assembly.core import Assembly, Interface, InterfaceType, MemberSpec
from assembly.joinery import Butt, Captured, Finger, HalfLap, JoineryStrategy
from assembly.panel import PanelRole, PanelSpec

_FIT_TOLERANCE_MM = 1e-9


@dataclass(frozen=True)
class _Span:
    start_mm: float
    end_mm: float

    def __post_init__(self) -> None:
        if not math.isfinite(self.start_mm) or not math.isfinite(self.end_mm) or self.end_mm <= self.start_mm:
            raise ValueError(f"Cubby span must be finite and positive, got [{self.start_mm}, {self.end_mm}]mm")

    @property
    def length_mm(self) -> float:
        return self.end_mm - self.start_mm


@dataclass(frozen=True)
class _Design:
    width_mm: float
    depth_mm: float
    height_mm: float
    thickness_mm: float
    rows: int
    cols: int
    perimeter: JoineryStrategy
    shelf: JoineryStrategy
    partition: JoineryStrategy
    internal: JoineryStrategy
    back: JoineryStrategy | None
    back_thickness_mm: float
    back_setback_mm: float
    back_support: bool

    def __post_init__(self) -> None:
        dimensions = (self.width_mm, self.depth_mm, self.height_mm, self.thickness_mm)
        if any(not math.isfinite(d) or d <= 0 for d in dimensions):
            raise ValueError(f"Cubby dimensions must be finite and positive, got {dimensions}")
        if self.rows < 1 or self.cols < 1:
            raise ValueError(f"Cubby grid counts must be positive, got {self.cols} x {self.rows}")
        if not math.isfinite(self.back_setback_mm) or self.back_setback_mm < 0:
            raise ValueError(f"Cubby back setback must be finite and nonnegative, got {self.back_setback_mm}mm")
        if self.back is not None and (not math.isfinite(self.back_thickness_mm) or self.back_thickness_mm <= 0):
            raise ValueError(f"Cubby back thickness must be finite and positive, got {self.back_thickness_mm}mm")


@dataclass(frozen=True)
class _Frame:
    cap_x: _Span
    wall_z: _Span
    inside_x: _Span
    inside_z: _Span


@dataclass(frozen=True)
class _Back:
    x: _Span
    y: _Span
    z: _Span


@dataclass(frozen=True)
class _Layout:
    frame: _Frame
    shelf_x: _Span
    partition_z: _Span
    shelf_depth_mm: float
    partition_depth_mm: float
    shelf_starts_z_mm: tuple[float, ...]
    partition_starts_x_mm: tuple[float, ...]
    back: _Back | None


def _captured_depth(joint: Captured, inserted_thickness: float, receiving_thickness: float) -> float:
    depth = joint.groove_depth_mm(inserted_thickness)
    if not 0 < depth <= receiving_thickness:
        raise ValueError(
            f"Cubby groove depth must be positive and fit {receiving_thickness}mm receiving stock, got {depth}mm"
        )
    return depth


def _engagement(joint: JoineryStrategy, inserted_thickness: float, receiving_thickness: float) -> float:
    if isinstance(joint, Butt):
        return 0.0
    if isinstance(joint, Captured) and joint.receiving == "a":
        return _captured_depth(joint, inserted_thickness, receiving_thickness)
    raise ValueError("Cubby internal/back support fit requires Butt or Captured(receiving='a')")


def _frame(d: _Design) -> _Frame:
    w, h, t = d.width_mm, d.height_mm, d.thickness_mm
    inside_x, inside_z = _Span(t, w - t), _Span(t, h - t)
    wall_z = _Span(0, h)
    if isinstance(d.perimeter, Finger):
        return _Frame(_Span(0, w), wall_z, inside_x, inside_z)
    if isinstance(d.perimeter, Butt):
        return _Frame(inside_x, wall_z, inside_x, inside_z)
    if isinstance(d.perimeter, Captured):
        inset = d.perimeter.inset_mm
        if not math.isfinite(inset) or inset < 0:
            raise ValueError(f"Cubby perimeter inset must be finite and nonnegative, got {inset}mm")
        depth = _captured_depth(d.perimeter, t, t)
        if d.perimeter.receiving == "a":
            return _Frame(_Span(0, w), _Span(t - depth, h - t + depth), _Span(inset + t, w - inset - t), inside_z)
        return _Frame(_Span(t - depth, w - t + depth), wall_z, inside_x, _Span(inset + t, h - inset - t))
    raise ValueError(f"Cubby perimeter fit is unsupported for {type(d.perimeter).__name__}")


def _grid_starts(span: _Span, count: int, thickness: float) -> tuple[float, ...]:
    opening = (span.length_mm - (count - 1) * thickness) / count
    if opening <= 0:
        raise ValueError(f"Cubby grid must leave positive clear openings, got {opening}mm")
    return tuple(span.start_mm + (i + 1) * opening + i * thickness for i in range(count - 1))


def _inserted_span(span: _Span, joint: JoineryStrategy, thickness: float) -> _Span:
    depth = _engagement(joint, thickness, thickness)
    return _Span(span.start_mm - depth, span.end_mm + depth)


def _back(d: _Design, frame: _Frame) -> _Back | None:
    if d.back is None:
        return None
    if (
        isinstance(d.back, Captured)
        and not math.isclose(d.back.inset_mm, 0, abs_tol=_FIT_TOLERANCE_MM)
        and not math.isclose(d.back.inset_mm, d.back_setback_mm, abs_tol=_FIT_TOLERANCE_MM)
    ):
        raise ValueError("Cubby back joint inset conflicts with back_inset rear-face setback")
    depth = _engagement(d.back, d.back_thickness_mm, d.thickness_mm)
    rear = d.depth_mm - d.back_setback_mm
    front = rear - d.back_thickness_mm
    if front <= 0:
        raise ValueError("Cubby back inset and thickness must leave positive interior depth")
    return _Back(
        _Span(frame.inside_x.start_mm - depth, frame.inside_x.end_mm + depth),
        _Span(front, rear),
        _Span(frame.inside_z.start_mm - depth, frame.inside_z.end_mm + depth),
    )


def _layout(d: _Design) -> _Layout:
    frame = _frame(d)
    shelf_starts = _grid_starts(frame.inside_z, d.rows, d.thickness_mm)
    partition_starts = _grid_starts(frame.inside_x, d.cols, d.thickness_mm)
    shelf_x = _inserted_span(frame.inside_x, d.shelf if shelf_starts else Butt(), d.thickness_mm)
    partition_z = _inserted_span(frame.inside_z, d.partition if partition_starts else Butt(), d.thickness_mm)
    back = _back(d, frame)
    shelf_depth = partition_depth = d.depth_mm
    if back is not None:
        shelf_depth = partition_depth = back.y.start_mm
        if d.back_support:
            if shelf_starts:
                shelf_depth += _engagement(d.shelf, d.thickness_mm, d.back_thickness_mm)
            if partition_starts:
                partition_depth += _engagement(d.partition, d.thickness_mm, d.back_thickness_mm)
    if shelf_starts and partition_starts:
        if not isinstance(d.internal, HalfLap):
            raise ValueError(
                "Cubby continuous shelf/partition crossings require HalfLap or an explicit segmented layout"
            )
        if not math.isclose(shelf_depth, partition_depth, rel_tol=0, abs_tol=_FIT_TOLERANCE_MM):
            raise ValueError(
                "Cubby HalfLap crossings require shelves and partitions with the same front and rear extents"
            )
    return _Layout(frame, shelf_x, partition_z, shelf_depth, partition_depth, shelf_starts, partition_starts, back)


def _panels(d: _Design, layout: _Layout) -> dict[str, MemberSpec]:
    f = layout.frame
    panels: dict[str, MemberSpec] = {
        "top": PanelSpec("top", f.cap_x.length_mm, d.depth_mm, d.thickness_mm, role=PanelRole.TOP),
        "bottom": PanelSpec("bottom", f.cap_x.length_mm, d.depth_mm, d.thickness_mm, role=PanelRole.BOTTOM),
        "left_side": PanelSpec("left_side", d.depth_mm, f.wall_z.length_mm, d.thickness_mm, role=PanelRole.LEFT),
        "right_side": PanelSpec("right_side", d.depth_mm, f.wall_z.length_mm, d.thickness_mm, role=PanelRole.RIGHT),
    }
    for i in range(len(layout.shelf_starts_z_mm)):
        name = f"shelf_{i + 1}"
        panels[name] = PanelSpec(
            name, layout.shelf_x.length_mm, layout.shelf_depth_mm, d.thickness_mm, role=PanelRole.SHELF
        )
    for j in range(len(layout.partition_starts_x_mm)):
        name = f"partition_{j + 1}"
        panels[name] = PanelSpec(
            name, layout.partition_depth_mm, layout.partition_z.length_mm, d.thickness_mm, role=PanelRole.PARTITION
        )
    if layout.back is not None:
        panels["back"] = PanelSpec(
            "back", layout.back.x.length_mm, layout.back.z.length_mm, d.back_thickness_mm, role=PanelRole.BACK
        )
    return panels


def _internal_interfaces(d: _Design, layout: _Layout) -> list[Interface]:
    result: list[Interface] = []
    for i, z in enumerate(layout.shelf_starts_z_mm):
        name = f"shelf_{i + 1}"
        position = z - layout.frame.wall_z.start_mm
        result.extend(
            [
                Interface(
                    InterfaceType.INTERNAL,
                    "left_side",
                    "bottom",
                    name,
                    "left",
                    d.shelf,
                    position_along_edge_a_mm=position,
                ),
                Interface(
                    InterfaceType.INTERNAL,
                    "right_side",
                    "bottom",
                    name,
                    "right",
                    d.shelf,
                    position_along_edge_a_mm=position,
                ),
            ]
        )
    for j, x in enumerate(layout.partition_starts_x_mm):
        name = f"partition_{j + 1}"
        position = x - layout.frame.cap_x.start_mm
        result.extend(
            [
                Interface(
                    InterfaceType.INTERNAL, "top", "left", name, "top", d.partition, position_along_edge_a_mm=position
                ),
                Interface(
                    InterfaceType.INTERNAL,
                    "bottom",
                    "left",
                    name,
                    "bottom",
                    d.partition,
                    position_along_edge_a_mm=position,
                ),
            ]
        )
    for i, z in enumerate(layout.shelf_starts_z_mm):
        for j, x in enumerate(layout.partition_starts_x_mm):
            result.append(
                Interface(
                    InterfaceType.INTERNAL,
                    f"shelf_{i + 1}",
                    "bottom",
                    f"partition_{j + 1}",
                    "right",
                    d.internal,
                    position_along_edge_a_mm=x - layout.shelf_x.start_mm,
                    position_along_edge_b_mm=z - layout.partition_z.start_mm,
                )
            )
    return result


def _back_interfaces(d: _Design, layout: _Layout) -> list[Interface]:
    if d.back is None or layout.back is None:
        return []
    result = [
        Interface(
            InterfaceType.SIDE_TO_SIDE,
            "left_side",
            "right",
            "back",
            "left",
            d.back,
            position_along_edge_a_mm=d.back_setback_mm,
        ),
        Interface(
            InterfaceType.SIDE_TO_SIDE,
            "right_side",
            "left",
            "back",
            "right",
            d.back,
            position_along_edge_a_mm=d.back_setback_mm,
        ),
        Interface(
            InterfaceType.TOP, "top", "bottom", "back", "top", d.back, position_along_edge_a_mm=d.back_setback_mm
        ),
        Interface(
            InterfaceType.BOTTOM, "bottom", "top", "back", "bottom", d.back, position_along_edge_a_mm=d.back_setback_mm
        ),
    ]
    if d.back_support:
        for i, z in enumerate(layout.shelf_starts_z_mm):
            result.append(
                Interface(
                    InterfaceType.INTERNAL,
                    "back",
                    "bottom",
                    f"shelf_{i + 1}",
                    "top",
                    d.shelf,
                    position_along_edge_a_mm=z - layout.back.z.start_mm,
                )
            )
        for j, x in enumerate(layout.partition_starts_x_mm):
            result.append(
                Interface(
                    InterfaceType.INTERNAL,
                    "back",
                    "left",
                    f"partition_{j + 1}",
                    "right",
                    d.partition,
                    position_along_edge_a_mm=x - layout.back.x.start_mm,
                )
            )
    return result


def cubby(
    width: float,
    length: float,
    height: float,
    thickness: float,
    rows: int,
    cols: int,
    perimeter_joinery: JoineryStrategy | None = None,
    shelf_joinery: JoineryStrategy | None = None,
    partition_joinery: JoineryStrategy | None = None,
    internal_joinery: JoineryStrategy | None = None,
    back: JoineryStrategy | Literal["none"] | None = None,
    back_thickness: float | None = None,
    back_inset: float = 0.0,
    back_internal_support: bool = True,
) -> Assembly:
    design = _Design(
        width,
        length,
        height,
        thickness,
        rows,
        cols,
        Finger() if perimeter_joinery is None else perimeter_joinery,
        Captured() if shelf_joinery is None else shelf_joinery,
        Captured() if partition_joinery is None else partition_joinery,
        HalfLap() if internal_joinery is None else internal_joinery,
        None if back is None or back == "none" else back,
        thickness / 3 if back_thickness is None else back_thickness,
        back_inset,
        back_internal_support,
    )
    layout = _layout(design)
    interfaces = [
        Interface(InterfaceType.TOP, "top", "left", "left_side", "top", design.perimeter),
        Interface(InterfaceType.TOP, "top", "right", "right_side", "top", design.perimeter),
        Interface(InterfaceType.BOTTOM, "bottom", "left", "left_side", "bottom", design.perimeter),
        Interface(InterfaceType.BOTTOM, "bottom", "right", "right_side", "bottom", design.perimeter),
        *_internal_interfaces(design, layout),
        *_back_interfaces(design, layout),
    ]
    return Assembly(members=_panels(design, layout), interfaces=tuple(interfaces))
