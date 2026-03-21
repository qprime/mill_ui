from __future__ import annotations

import math

from domains import Domain
from layout_ast.compositional import (
    Arch,
    ChamferGen,
    Circle,
    CompositionalLayoutAST,
    Panel,
    PocketGen,
    Polygon,
    ProfileGen,
    Rect,
    RoundedRect,
    RoundoverGen,
    Subtract,
    Triangle,
)
from layout_ast.layout import Sheet
from resolution.layout_resolver import resolve_layout


def _resolve_pml(root, width=400, height=400, thickness=19):
    ast = CompositionalLayoutAST(
        sheet=Sheet(width_mm=width, height_mm=height, thickness_mm=thickness, margin_mm=0.0),
        root=Panel(children=(root,)),
    )
    return resolve_layout(ast)


def _items_by_feature(flat, feature_type):
    return [item for item in flat.items if item.feature and item.feature.type == feature_type]


def _item_dims(item):
    data = item.geometry.data
    if "w_mm" in data:
        return data["w_mm"], data["h_mm"]
    points = data["points"]
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return max(xs) - min(xs), max(ys) - min(ys)


class TestDomainFactories:
    def test_from_circle_basic(self):
        d = Domain.from_circle(100)
        assert len(d.outer_boundary) == 80
        assert abs(d.area_mm2 - math.pi * 50**2) < 50

    def test_from_circle_with_center(self):
        d = Domain.from_circle(100, center=(50, 50))
        cx, cy = d.centroid
        assert abs(cx - 50) < 0.1
        assert abs(cy - 50) < 0.1

    def test_from_rounded_rect_basic(self):
        d = Domain.from_rounded_rect(100, 60, 10)
        assert len(d.outer_boundary) > 4
        assert d.area_mm2 < 100 * 60
        assert d.area_mm2 > 100 * 60 * 0.95

    def test_from_rounded_rect_selective_corners(self):
        d = Domain.from_rounded_rect(100, 60, 10, corners=("tl", "tr"))
        assert len(d.outer_boundary) > 4

    def test_from_rounded_rect_zero_radius(self):
        d = Domain.from_rounded_rect(100, 60, 0)
        assert len(d.outer_boundary) == 4
        assert abs(d.area_mm2 - 6000) < 1


class TestDomainAwareDispatch:
    def test_profile_on_polygon_via_dispatch(self):
        flat = _resolve_pml(
            Polygon(
                points=((100, 100), (300, 100), (200, 300)),
                children=(ProfileGen(side="outside", depth="through"),),
            )
        )
        profiles = _items_by_feature(flat, "profile")
        assert len(profiles) == 1
        assert profiles[0].type == "Polygon"
        assert len(profiles[0].geometry.data["points"]) == 3

    def test_pocket_on_polygon_via_dispatch(self):
        flat = _resolve_pml(
            Polygon(
                points=((100, 100), (300, 100), (200, 300)),
                children=(PocketGen(depth_mm=5),),
            )
        )
        pockets = _items_by_feature(flat, "pocket")
        assert len(pockets) == 1
        assert pockets[0].type == "Polygon"
        assert len(pockets[0].geometry.data["points"]) == 3

    def test_profile_on_triangle_via_dispatch(self):
        flat = _resolve_pml(
            Triangle(
                base_mm=200,
                height_mm=200,
                children=(ProfileGen(side="outside", depth="through"),),
            )
        )
        profiles = _items_by_feature(flat, "profile")
        assert len(profiles) == 1
        assert profiles[0].type == "Polygon"
        assert len(profiles[0].geometry.data["points"]) == 3

    def test_pocket_on_triangle_via_dispatch(self):
        flat = _resolve_pml(
            Triangle(
                base_mm=200,
                height_mm=200,
                children=(PocketGen(depth_mm=5),),
            )
        )
        pockets = _items_by_feature(flat, "pocket")
        assert len(pockets) == 1
        assert pockets[0].type == "Polygon"

    def test_profile_on_arch_via_dispatch(self):
        flat = _resolve_pml(
            Arch(
                width_mm=200,
                height_mm=300,
                radius_mm=100,
                children=(ProfileGen(side="outside", depth="through"),),
            )
        )
        profiles = _items_by_feature(flat, "profile")
        assert len(profiles) == 1
        assert profiles[0].type == "Polygon"
        assert len(profiles[0].geometry.data["points"]) > 4

    def test_profile_on_rounded_rect_via_dispatch(self):
        flat = _resolve_pml(
            RoundedRect(
                radius_mm=25.0,
                children=(ProfileGen(side="outside", depth="through"),),
            )
        )
        profiles = _items_by_feature(flat, "profile")
        assert len(profiles) == 1
        assert profiles[0].type == "Polygon"
        assert len(profiles[0].geometry.data["points"]) > 4

    def test_subtract_pocket_via_dispatch(self):
        flat = _resolve_pml(
            Subtract(
                inner_inset_mm=20,
                children=(PocketGen(depth_mm=5),),
            )
        )
        pockets = _items_by_feature(flat, "pocket")
        assert len(pockets) >= 1
        for p in pockets:
            assert p.type == "Polygon"
            assert "holes" in p.geometry.data

    def test_subtract_chamfer_via_dispatch(self):
        flat = _resolve_pml(
            Subtract(
                inner_inset_mm=20,
                children=(ChamferGen(depth_mm=3, width_mm=5),),
            )
        )
        chamfers = _items_by_feature(flat, "chamfer")
        assert len(chamfers) >= 1
        for c in chamfers:
            assert c.type == "Polygon"

    def test_subtract_roundover_via_dispatch(self):
        flat = _resolve_pml(
            Subtract(
                inner_inset_mm=20,
                children=(RoundoverGen(radius_mm=3),),
            )
        )
        roundovers = _items_by_feature(flat, "roundover")
        assert len(roundovers) >= 1
        for r in roundovers:
            assert r.type == "Polygon"


class TestNewlyEnabledCombinations:
    def test_chamfer_on_polygon(self):
        flat = _resolve_pml(
            Polygon(
                points=((100, 100), (300, 100), (300, 300), (100, 300)),
                children=(ChamferGen(depth_mm=3, width_mm=5),),
            )
        )
        chamfers = _items_by_feature(flat, "chamfer")
        assert len(chamfers) == 1
        assert chamfers[0].type == "Polygon"

    def test_roundover_on_polygon(self):
        flat = _resolve_pml(
            Polygon(
                points=((100, 100), (300, 100), (300, 300), (100, 300)),
                children=(RoundoverGen(radius_mm=3),),
            )
        )
        roundovers = _items_by_feature(flat, "roundover")
        assert len(roundovers) == 1
        assert roundovers[0].type == "Polygon"

    def test_chamfer_on_triangle(self):
        flat = _resolve_pml(
            Triangle(
                base_mm=200,
                height_mm=200,
                children=(ChamferGen(depth_mm=3, width_mm=5),),
            )
        )
        chamfers = _items_by_feature(flat, "chamfer")
        assert len(chamfers) == 1
        assert chamfers[0].type == "Polygon"
        assert len(chamfers[0].geometry.data["points"]) == 3

    def test_roundover_on_triangle(self):
        flat = _resolve_pml(
            Triangle(
                base_mm=200,
                height_mm=200,
                children=(RoundoverGen(radius_mm=3),),
            )
        )
        roundovers = _items_by_feature(flat, "roundover")
        assert len(roundovers) == 1
        assert roundovers[0].type == "Polygon"

    def test_pocket_on_circle(self):
        flat = _resolve_pml(
            Circle(
                diameter_mm=200,
                children=(PocketGen(depth_mm=5),),
            )
        )
        pockets = _items_by_feature(flat, "pocket")
        assert len(pockets) == 1
        assert pockets[0].type == "Polygon"
        assert len(pockets[0].geometry.data["points"]) == 80

    def test_profile_on_circle(self):
        flat = _resolve_pml(
            Circle(
                diameter_mm=200,
                children=(ProfileGen(side="outside", depth="through"),),
            )
        )
        profiles = _items_by_feature(flat, "profile")
        assert len(profiles) == 1
        assert profiles[0].type == "Polygon"
        assert len(profiles[0].geometry.data["points"]) == 80

    def test_pocket_on_rounded_rect(self):
        flat = _resolve_pml(
            RoundedRect(
                radius_mm=25.0,
                children=(PocketGen(depth_mm=5),),
            )
        )
        pockets = _items_by_feature(flat, "pocket")
        assert len(pockets) == 1
        assert pockets[0].type == "Polygon"
        assert len(pockets[0].geometry.data["points"]) > 4

    def test_chamfer_on_arch(self):
        flat = _resolve_pml(
            Arch(
                width_mm=200,
                height_mm=300,
                radius_mm=100,
                children=(ChamferGen(depth_mm=3, width_mm=5),),
            )
        )
        chamfers = _items_by_feature(flat, "chamfer")
        assert len(chamfers) == 1
        assert chamfers[0].type == "Polygon"
        assert len(chamfers[0].geometry.data["points"]) > 4


class TestDomainNotSet:
    def test_profile_without_domain_falls_back_to_rect(self):
        flat = _resolve_pml(
            Rect(
                children=(ProfileGen(side="outside", depth="through"),),
            )
        )
        profiles = _items_by_feature(flat, "profile")
        assert len(profiles) == 1
        assert profiles[0].type == "Polygon"
        assert len(profiles[0].geometry.data["points"]) == 4

    def test_pocket_without_domain_falls_back_to_rect(self):
        from layout_ast.compositional import Frame

        flat = _resolve_pml(
            Rect(
                children=(
                    Frame(
                        width_mm=50,
                        children=(PocketGen(depth_mm=5),),
                    ),
                ),
            )
        )
        pockets = _items_by_feature(flat, "pocket")
        assert len(pockets) == 1
        assert pockets[0].type == "Rect"
        assert "w_mm" in pockets[0].geometry.data


class TestCoordinateCorrectness:
    def test_triangle_profile_points_reconstruct_to_absolute(self):
        flat = _resolve_pml(
            Triangle(
                base_mm=200,
                height_mm=200,
                children=(ProfileGen(side="outside", depth="through"),),
            ),
            width=400,
            height=400,
        )
        profile = _items_by_feature(flat, "profile")[0]
        cx, cy = profile.placement.center_xy_mm
        points = profile.geometry.data["points"]
        abs_points = [(p[0] + cx, p[1] + cy) for p in points]

        expected = [
            (cx - 100, cy - 100),
            (cx + 100, cy - 100),
            (cx, cy + 100),
        ]
        for actual, exp in zip(sorted(abs_points), sorted(expected), strict=True):
            assert abs(actual[0] - exp[0]) < 0.01
            assert abs(actual[1] - exp[1]) < 0.01

    def test_polygon_pocket_points_reconstruct_to_absolute(self):
        poly_pts = ((50, 50), (350, 50), (350, 350), (50, 350))
        flat = _resolve_pml(
            Polygon(
                points=poly_pts,
                children=(PocketGen(depth_mm=5),),
            )
        )
        pocket = _items_by_feature(flat, "pocket")[0]
        cx, cy = pocket.placement.center_xy_mm
        points = pocket.geometry.data["points"]
        abs_points = sorted([(p[0] + cx, p[1] + cy) for p in points])
        expected = sorted(poly_pts)
        for actual, exp in zip(abs_points, expected, strict=True):
            assert abs(actual[0] - exp[0]) < 0.01
            assert abs(actual[1] - exp[1]) < 0.01

    def test_subtract_ring_has_correct_holes(self):
        flat = _resolve_pml(
            Subtract(
                inner_inset_mm=50,
                children=(PocketGen(depth_mm=5),),
            ),
            width=400,
            height=400,
        )
        pocket = _items_by_feature(flat, "pocket")[0]
        assert pocket.type == "Polygon"
        holes = pocket.geometry.data["holes"]
        assert len(holes) == 1
        cx, cy = pocket.placement.center_xy_mm
        outer_pts = [(p[0] + cx, p[1] + cy) for p in pocket.geometry.data["points"]]
        inner_pts = [(p[0] + cx, p[1] + cy) for p in holes[0]]
        outer_xs = [p[0] for p in outer_pts]
        inner_xs = [p[0] for p in inner_pts]
        assert (max(outer_xs) - min(outer_xs)) > (max(inner_xs) - min(inner_xs))

    def test_circle_profile_points_form_circle(self):
        flat = _resolve_pml(
            Circle(
                diameter_mm=200,
                children=(ProfileGen(side="outside", depth="through"),),
            ),
            width=400,
            height=400,
        )
        profile = _items_by_feature(flat, "profile")[0]
        points = profile.geometry.data["points"]
        for p in points:
            dist = math.sqrt(p[0] ** 2 + p[1] ** 2)
            assert abs(dist - 100) < 1.0

    def test_arch_frame_non_raised_panel_child_gets_no_domain(self):
        from layout_ast.compositional import Frame

        flat = _resolve_pml(
            Arch(
                width_mm=200,
                height_mm=300,
                radius_mm=80,
                children=(
                    Frame(
                        width_mm=20,
                        children=(PocketGen(depth_mm=5),),
                    ),
                ),
            )
        )
        pockets = _items_by_feature(flat, "pocket")
        assert len(pockets) == 1
        assert pockets[0].type == "Rect"
        assert "w_mm" in pockets[0].geometry.data
