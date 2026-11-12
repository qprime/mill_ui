from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations, pairwise
from typing import Any

import pytest
from shapely.affinity import translate
from shapely.geometry import LineString, Polygon, box
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from assembly.core import Assembly, InterfaceType
from assembly.joinery import Butt, Captured, Finger, HalfLap
from assembly.notches import build_notched_polygon
from assembly.panel import PanelSpec
from assembly.primitives import cubby


def _organizer(*, setback: float = 12, support: bool = True) -> Assembly:
    return cubby(
        width=900,
        length=300,
        height=600,
        thickness=18,
        rows=2,
        cols=3,
        perimeter_joinery=Finger(width_mm=15, clearance_mm=0.12),
        shelf_joinery=Captured(fitment_mm=0.12),
        partition_joinery=Captured(fitment_mm=0.12),
        internal_joinery=HalfLap(fitment_mm=0.12),
        back=Captured(dado_depth_mm=9, fitment_mm=0.12),
        back_thickness=18,
        back_inset=setback,
        back_internal_support=support,
    )


def test_finger_cubby_preserves_its_full_outer_frame_dimensions():
    panels = _organizer().panels
    assert (panels["top"].width_mm, panels["top"].height_mm) == (900, 300)
    assert (panels["bottom"].width_mm, panels["bottom"].height_mm) == (900, 300)
    assert (panels["left_side"].width_mm, panels["left_side"].height_mm) == (300, 600)
    assert (panels["right_side"].width_mm, panels["right_side"].height_mm) == (300, 600)


@pytest.mark.parametrize(
    "setback, supported, depth", [(0, True, 291), (12, True, 279), (30, True, 261), (12, False, 270)]
)
def test_dividers_reach_side_cap_and_back_grooves(setback, supported, depth):
    panels = _organizer(setback=setback, support=supported).panels
    assert (panels["shelf_1"].width_mm, panels["shelf_1"].height_mm) == (882, depth)
    assert (panels["partition_1"].width_mm, panels["partition_1"].height_mm) == (depth, 582)
    assert (panels["partition_2"].width_mm, panels["partition_2"].height_mm) == (depth, 582)
    assert (panels["back"].width_mm, panels["back"].height_mm) == (882, 582)


def test_equal_clear_openings_include_the_divider_thickness():
    assembly = _organizer()
    shelves = [i for i in assembly.interfaces if i.panel_a == "left_side" and i.type == InterfaceType.INTERNAL]
    partitions = [i for i in assembly.interfaces if i.panel_a == "top" and i.type == InterfaceType.INTERNAL]
    assert [i.position_along_edge_a_mm for i in shelves] == [291]
    assert [i.position_along_edge_a_mm for i in partitions] == [294, 588]
    x_starts = [18, 294 + 18, 588 + 18]
    x_ends = [294, 588, 882]
    assert [end - start for start, end in zip(x_starts, x_ends, strict=True)] == [276, 276, 276]
    assert 291 - 18 == 582 - (291 + 18) == 273


def test_grid_half_laps_share_world_positions_and_open_from_opposite_depth_ends():
    crossings = [i for i in _organizer().interfaces if isinstance(i.joinery, HalfLap)]
    assert [(i.edge_a, i.edge_b) for i in crossings] == [("bottom", "right"), ("bottom", "right")]
    assert [i.position_along_edge_a_mm for i in crossings] == [285, 579]
    assert [i.position_along_edge_b_mm for i in crossings] == [282, 282]
    resolved = {p.name: p for p in _organizer().resolve()}
    for p in (resolved["shelf_1"], resolved["partition_1"], resolved["partition_2"]):
        assert all(n.depth_mm == 139.5 for n in p.notches)


def test_back_support_grooves_align_with_the_same_shelf_and_partitions():
    support = [i for i in _organizer().interfaces if i.panel_a == "back"]
    assert [(i.panel_b, i.edge_b, i.position_along_edge_a_mm) for i in support] == [
        ("shelf_1", "top", 282),
        ("partition_1", "right", 285),
        ("partition_2", "right", 579),
    ]


def test_all_four_back_grooves_cut_the_rear_of_the_machined_inside_faces():
    assembly = _organizer()
    back_edges = {i.panel_a: (i.edge_a, i.position_along_edge_a_mm) for i in assembly.interfaces if i.panel_b == "back"}
    assert back_edges == {
        "left_side": ("right", 12),
        "right_side": ("left", 12),
        "top": ("bottom", 12),
        "bottom": ("top", 12),
    }
    panels = {p.name: p for p in assembly.resolve()}
    for name, axis, reverse in [
        ("left_side", "vertical", False),
        ("right_side", "vertical", True),
        ("top", "horizontal", True),
        ("bottom", "horizontal", False),
    ]:
        groove = next(d for d in panels[name].dados if d.orientation == axis)
        if groove.edge in ("right", "top"):
            local = (300 - groove.position_from_edge_mm - groove.width_mm, 300 - groove.position_from_edge_mm)
        else:
            local = (groove.position_from_edge_mm, groove.position_from_edge_mm + groove.width_mm)
        physical = (300 - local[1], 300 - local[0]) if reverse else local
        assert physical == pytest.approx((269.88, 288))
        assert groove.depth_mm == 9


def test_an_unsupported_inset_cannot_silently_move_the_back_plane():
    with pytest.raises(ValueError, match=r"back.*inset"):
        cubby(
            width=900,
            length=300,
            height=600,
            thickness=18,
            rows=2,
            cols=3,
            back=Captured(inset_mm=6),
            back_thickness=18,
            back_inset=12,
        )


@pytest.mark.parametrize("rows, cols", [(0, 3), (2, 0), (40, 3), (2, 60)])
def test_grid_rejects_nonpositive_clear_openings(rows, cols):
    with pytest.raises(ValueError, match=r"Cubby.*(grid|opening)"):
        cubby(width=900, length=300, height=600, thickness=18, rows=rows, cols=cols)


@dataclass(frozen=True)
class _Placement:
    kind: str
    origin: tuple[float, float, float]
    reverse: bool = False
    normal: int = 1


def _line_intervals(geometry):
    parts = list(geometry.geoms) if hasattr(geometry, "geoms") else [geometry]
    return [p for p in parts if p.geom_type == "LineString" and p.length > 0]


@dataclass(frozen=True)
class _SectionPanel:
    panel: PanelSpec
    placement: _Placement
    region: BaseGeometry
    cuts: tuple[tuple[BaseGeometry, float], ...]

    @classmethod
    def from_spec(cls, panel: PanelSpec, placement: _Placement) -> _SectionPanel:
        points = build_notched_polygon(panel.width_mm, panel.height_mm, (0, 0), panel.notches)
        region = translate(Polygon(points), xoff=panel.width_mm / 2, yoff=panel.height_mm / 2)
        assert region.is_valid
        cuts = []
        for dado in panel.dados:
            start, end = dado.span_for_panel(panel.width_mm, panel.height_mm)
            if dado.orientation == "vertical":
                u = (
                    panel.width_mm - dado.position_from_edge_mm - dado.width_mm
                    if dado.edge == "right"
                    else dado.position_from_edge_mm
                )
                rect = box(u, start, u + dado.width_mm, end)
            else:
                v = (
                    panel.height_mm - dado.position_from_edge_mm - dado.width_mm
                    if dado.edge == "top"
                    else dado.position_from_edge_mm
                )
                rect = box(start, v, end, v + dado.width_mm)
            cuts.append((rect, dado.depth_mm))
        return cls(panel, placement, region, tuple(cuts))

    def depth_breaks(self) -> set[float]:
        if self.placement.kind == "back":
            y = self.placement.origin[1]
            return {y, y + self.panel.thickness_mm, *[y + depth for _, depth in self.cuts]}
        axis = 1 if self.placement.kind == "horizontal" else 0
        result = set()
        for g in [self.region, *[rect for rect, _ in self.cuts]]:
            if not isinstance(g, Polygon):
                continue
            for p in g.exterior.coords:
                coordinate = self.placement.origin[1] + (-p[axis] if self.placement.reverse else p[axis])
                result.add(round(coordinate, 9))
        return result

    def _project(self, segment, normal_lo, normal_hi):
        x, _, z = self.placement.origin
        b = segment.bounds
        return (
            box(x + b[0], normal_lo, x + b[2], normal_hi)
            if self.placement.kind == "horizontal"
            else box(normal_lo, z + b[1], normal_hi, z + b[3])
        )

    def section(self, depth: float) -> BaseGeometry:
        x, y, z = self.placement.origin
        if self.placement.kind == "back":
            if not y < depth < y + self.panel.thickness_mm:
                return Polygon()
            result = self.region
            for rectangle, cut_depth in self.cuts:
                if depth < y + cut_depth:
                    result = result.difference(rectangle)
            return translate(result, xoff=x, yoff=z)
        local = y - depth if self.placement.reverse else depth - y
        horizontal = self.placement.kind == "horizontal"
        query = (
            LineString([(-1, local), (self.panel.width_mm + 1, local)])
            if horizontal
            else LineString([(local, -1), (local, self.panel.height_mm + 1)])
        )
        normal_start = z if horizontal else x
        result = unary_union(
            [
                self._project(s, normal_start, normal_start + self.panel.thickness_mm)
                for s in _line_intervals(self.region.intersection(query))
            ]
        )
        for rectangle, cut_depth in self.cuts:
            lo = normal_start + self.panel.thickness_mm - cut_depth if self.placement.normal > 0 else normal_start
            hi = normal_start + self.panel.thickness_mm if self.placement.normal > 0 else normal_start + cut_depth
            for segment in _line_intervals(rectangle.intersection(query)):
                result = result.difference(self._project(segment, lo, hi))
        return result


def _assembled_panels(assembly: Assembly) -> dict[str, _SectionPanel]:
    placements = {
        "top": _Placement("horizontal", (0, 300, 582), True, -1),
        "bottom": _Placement("horizontal", (0, 0, 0)),
        "left_side": _Placement("vertical", (0, 0, 0)),
        "right_side": _Placement("vertical", (882, 300, 0), True, -1),
        "shelf_1": _Placement("horizontal", (9, 0, 291)),
        "partition_1": _Placement("vertical", (294, 0, 9)),
        "partition_2": _Placement("vertical", (588, 0, 9)),
        "back": _Placement("back", (9, 270, 9), False, -1),
    }
    return {p.name: _SectionPanel.from_spec(p, placements[p.name]) for p in assembly.resolve()}


def test_no_material_collisions_across_all_assembled_depth_sections():
    panels = _assembled_panels(_organizer())
    depths = {0.0, 300.0}
    for panel in panels.values():
        depths.update(d for d in panel.depth_breaks() if 0 <= d <= 300)
    for low, high in pairwise(sorted(depths)):
        depth = (low + high) / 2
        sections = {name: panel.section(depth) for name, panel in panels.items()}
        for a, b in combinations(sections, 2):
            overlap = sections[a].intersection(sections[b]).area
            assert overlap < 1e-6, f"{a} overlaps {b} by {overlap} mm2 at depth {depth} mm"


@pytest.mark.parametrize(
    "perimeter, cap_width, wall_height, shelf_width, partition_height, shelf_position, partition_positions",
    [
        (Finger(), 900, 600, 882, 582, 291, [294, 588]),
        (Butt(), 864, 600, 882, 582, 291, [276, 570]),
        (Captured(dado_depth_mm=6), 900, 576, 882, 582, 279, [294, 588]),
        (Captured(receiving="b", dado_depth_mm=6), 876, 600, 882, 582, 291, [282, 576]),
        (Captured(dado_depth_mm=6, inset_mm=3), 900, 576, 876, 582, 279, [295, 587]),
        (Captured(receiving="b", dado_depth_mm=6, inset_mm=3), 876, 600, 882, 576, 291, [282, 576]),
    ],
)
def test_perimeter_joint_origins_are_used_for_every_internal_interface(
    perimeter, cap_width, wall_height, shelf_width, partition_height, shelf_position, partition_positions
):
    assembly = cubby(width=900, length=300, height=600, thickness=18, rows=2, cols=3, perimeter_joinery=perimeter)
    assert assembly.panels["top"].width_mm == cap_width
    assert assembly.panels["left_side"].height_mm == wall_height
    assert assembly.panels["shelf_1"].width_mm == shelf_width
    assert assembly.panels["partition_1"].height_mm == partition_height
    assert [
        i.position_along_edge_a_mm
        for i in assembly.interfaces
        if i.type == InterfaceType.INTERNAL and i.panel_a == "left_side"
    ] == [shelf_position]
    assert [
        i.position_along_edge_a_mm
        for i in assembly.interfaces
        if i.type == InterfaceType.INTERNAL and i.panel_a == "top"
    ] == partition_positions
    assembly.resolve()


def test_a_setback_without_a_back_does_not_shorten_members():
    assembly = cubby(width=900, length=300, height=600, thickness=18, rows=2, cols=3, back_inset=12)
    assert assembly.panels["shelf_1"].height_mm == assembly.panels["partition_1"].width_mm == 300


def test_thin_back_without_internal_support_uses_its_actual_stock_and_face():
    assembly = cubby(
        width=900,
        length=300,
        height=600,
        thickness=18,
        rows=2,
        cols=3,
        back=Captured(),
        back_thickness=6,
        back_inset=12,
        back_internal_support=False,
    )
    assert (
        assembly.panels["back"].width_mm,
        assembly.panels["back"].height_mm,
        assembly.panels["back"].thickness_mm,
    ) == (870, 570, 6)
    assert assembly.panels["shelf_1"].height_mm == assembly.panels["partition_1"].width_mm == 282


@pytest.mark.parametrize(
    "changes, error",
    [
        ({"back": Captured(receiving="b")}, "receiving='a'"),
        ({"internal_joinery": Butt()}, "crossings require HalfLap"),
        ({"shelf_joinery": HalfLap()}, "internal/back support fit"),
        ({"shelf_joinery": Captured(dado_depth_mm=3)}, "same front and rear extents"),
        ({"back_thickness": 6}, "fit 6mm receiving stock"),
        ({"back_inset": 282}, "positive interior depth"),
        ({"back_inset": -1}, "back setback"),
    ],
)
def test_unsupported_or_impossible_fits_error_instead_of_changing_the_design(changes, error):
    arguments: dict[str, Any] = {
        "width": 900,
        "length": 300,
        "height": 600,
        "thickness": 18,
        "rows": 2,
        "cols": 3,
        "back": Captured(),
        "back_thickness": 18,
        "back_inset": 12,
    }
    arguments.update(changes)
    with pytest.raises(ValueError, match=error):
        cubby(**arguments)
