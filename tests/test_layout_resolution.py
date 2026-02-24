from __future__ import annotations

import sys

from layout_ast.compositional import (
    Cell,
    ComponentDef,
    CompositionalLayoutAST,
    Frame,
    Grid,
    Inset,
    Panel,
    Place,
    ProfileGen,
    Rect,
    RoundedRect,
    UseComponent,
)
from layout_ast.layout import Feature, Sheet
from pml import format_pml
from resolution.layout_resolver import LayoutResolver, ResolutionAssertionError, resolve_layout


def approx_eq(a, b, rel=1e-6):
    """Check if two values are approximately equal."""
    if abs(b) < 1e-9:
        return abs(a - b) < 1e-9
    return abs(a - b) / abs(b) < rel


def test_simple_panel_with_rect():
    print("Running test_simple_panel_with_rect...")
    ast = CompositionalLayoutAST(
        sheet=Sheet(width_mm=400, height_mm=600, thickness_mm=19, margin_mm=0.0),
        root=Panel(
            children=(
                Rect(
                    feature=Feature(type="profile", depth_mm=0.0, is_through=True, side="outside"),
                    id="outer",
                ),
            )
        ),
    )

    flat = resolve_layout(ast)

    assert len(flat.items) == 1
    item = flat.items[0]
    assert item.type == "Rect"
    assert item.geometry.data["w_mm"] == 400.0
    assert item.geometry.data["h_mm"] == 600.0
    assert item.placement.center_xy_mm == (200.0, 300.0)
    assert item.feature.type == "profile"
    print("  PASS")
    return True


def test_panel_with_inset():
    print("Running test_panel_with_inset...")
    ast = CompositionalLayoutAST(
        sheet=Sheet(width_mm=400, height_mm=600, thickness_mm=19, margin_mm=0.0),
        root=Panel(
            children=(
                Inset(
                    amount_mm=25,
                    children=(
                        Rect(
                            feature=Feature(type="pocket", depth_mm=6.0),
                            id="panel",
                        ),
                    ),
                ),
            )
        ),
    )

    flat = resolve_layout(ast)

    assert len(flat.items) == 1
    item = flat.items[0]

    assert item.geometry.data["w_mm"] == 350.0
    assert item.geometry.data["h_mm"] == 550.0

    assert item.placement.center_xy_mm == (200.0, 300.0)
    print("  PASS")
    return True


def test_frame_insets_region_for_children():
    print("Running test_frame_insets_region_for_children...")
    ast = CompositionalLayoutAST(
        sheet=Sheet(width_mm=400, height_mm=600, thickness_mm=19, margin_mm=0.0),
        root=Panel(
            children=(
                Rect(
                    children=(
                        Frame(
                            width_mm=50,
                            children=(
                                Rect(
                                    feature=Feature(type="pocket", depth_mm=6.0),
                                    id="inner",
                                ),
                            ),
                        ),
                    ),
                    feature=Feature(type="profile", depth_mm=0.0, is_through=True, side="outside"),
                    id="outer",
                ),
            )
        ),
    )

    flat = resolve_layout(ast)

    assert len(flat.items) == 2

    outer = flat.items[0]
    assert outer.shape_id == "outer"
    assert outer.geometry.data["w_mm"] == 400.0
    assert outer.geometry.data["h_mm"] == 600.0
    assert outer.feature.type == "profile"

    inner = flat.items[1]
    assert inner.shape_id == "inner"
    assert inner.feature.type == "pocket"
    assert inner.geometry.data["w_mm"] == 300.0
    assert inner.geometry.data["h_mm"] == 500.0
    print("  PASS")
    return True


def test_frame_does_not_emit_profile():
    print("Running test_frame_does_not_emit_profile...")
    ast = CompositionalLayoutAST(
        sheet=Sheet(width_mm=400, height_mm=600, thickness_mm=19, margin_mm=0.0),
        root=Panel(
            children=(
                Rect(
                    children=(
                        Frame(
                            width_mm=50,
                            children=(
                                Rect(
                                    feature=Feature(type="pocket", depth_mm=6.0),
                                ),
                            ),
                        ),
                    ),
                ),
            )
        ),
    )

    flat = resolve_layout(ast)

    profile_items = [item for item in flat.items if item.feature and item.feature.type == "profile"]
    assert len(profile_items) == 0, f"Frame should not emit profile, but found {len(profile_items)}"

    pocket_items = [item for item in flat.items if item.feature and item.feature.type == "pocket"]
    assert len(pocket_items) == 1
    assert pocket_items[0].geometry.data["w_mm"] == 300.0
    assert pocket_items[0].geometry.data["h_mm"] == 500.0
    print("  PASS")
    return True


def test_grid_subdivides_region():
    print("Running test_grid_subdivides_region...")
    ast = CompositionalLayoutAST(
        sheet=Sheet(width_mm=400, height_mm=400, thickness_mm=19, margin_mm=0.0),
        root=Panel(
            children=(
                Grid(
                    rows=2,
                    cols=2,
                    gap_mm=10,
                    children=(
                        Cell(
                            children=(
                                Rect(
                                    feature=Feature(type="pocket", depth_mm=5.0),
                                    id="cell_pocket",
                                ),
                            )
                        ),
                    ),
                ),
            )
        ),
    )

    flat = resolve_layout(ast)

    assert len(flat.items) == 4

    for item in flat.items:
        assert item.feature.type == "pocket"
        assert approx_eq(item.geometry.data["w_mm"], 195.0)
        assert approx_eq(item.geometry.data["h_mm"], 195.0)
    print("  PASS")
    return True


def test_component_definition_and_use():
    print("Running test_component_definition_and_use...")

    simple_panel = ComponentDef(
        name="SimplePanel",
        params={"recess_depth": 6.0},
        body=Rect(
            feature=Feature(type="pocket", depth_mm=6.0),
            id="panel",
        ),
    )

    ast = CompositionalLayoutAST(
        sheet=Sheet(width_mm=400, height_mm=600, thickness_mm=19, margin_mm=0.0),
        components={"SimplePanel": simple_panel},
        root=Panel(
            children=(
                UseComponent(
                    component_name="SimplePanel",
                    args={"recess_depth": 8.0},
                ),
            )
        ),
    )

    flat = resolve_layout(ast)

    assert len(flat.items) == 1
    item = flat.items[0]
    assert item.shape_id == "panel"
    print("  PASS")
    return True


def test_place_grid_with_components():
    print("Running test_place_grid_with_components...")

    shaker_panel = ComponentDef(
        name="ShakerPanel",
        params={"frame_width": 50.0, "recess_depth": 6.0},
        body=Rect(
            children=(
                Frame(
                    width_mm=50,
                    children=(
                        Rect(
                            feature=Feature(type="pocket", depth_mm=6.0),
                            id="inner",
                        ),
                    ),
                ),
            ),
            feature=Feature(type="profile", depth_mm=0.0, is_through=True, side="outside"),
            id="outer",
        ),
    )

    ast = CompositionalLayoutAST(
        sheet=Sheet(width_mm=1000, height_mm=1000, thickness_mm=19, margin_mm=0.0),
        components={"ShakerPanel": shaker_panel},
        root=Place(
            layout=Grid(rows=2, cols=2, gap_mm=50),
            children=(
                UseComponent(component_name="ShakerPanel"),
                UseComponent(component_name="ShakerPanel"),
                UseComponent(component_name="ShakerPanel"),
                UseComponent(component_name="ShakerPanel"),
            ),
        ),
    )

    flat = resolve_layout(ast)

    assert len(flat.items) == 8

    first_outer = flat.items[0]
    assert first_outer.shape_id == "outer"
    assert approx_eq(first_outer.geometry.data["w_mm"], 475.0)
    assert approx_eq(first_outer.geometry.data["h_mm"], 475.0)
    print("  PASS")
    return True


def test_acceptance_4_instances_frame_grid_pocket():
    print("Running test_acceptance_4_instances_frame_grid_pocket...")

    grid_panel = ComponentDef(
        name="GridPanel",
        params={},
        body=Rect(
            children=(
                Frame(
                    width_mm=40,
                    children=(
                        Grid(
                            rows=2,
                            cols=2,
                            gap_mm=10,
                            children=(
                                Cell(
                                    children=(
                                        Rect(
                                            feature=Feature(type="pocket", depth_mm=5.0),
                                        ),
                                    )
                                ),
                            ),
                        ),
                    ),
                ),
            ),
            feature=Feature(type="profile", depth_mm=0.0, is_through=True, side="outside"),
            id="panel_outer",
        ),
    )

    ast = CompositionalLayoutAST(
        sheet=Sheet(width_mm=1200, height_mm=1200, thickness_mm=19, margin_mm=0.0),
        components={"GridPanel": grid_panel},
        root=Place(
            layout=Grid(rows=2, cols=2, gap_mm=100),
            children=(
                UseComponent(component_name="GridPanel"),
                UseComponent(component_name="GridPanel"),
                UseComponent(component_name="GridPanel"),
                UseComponent(component_name="GridPanel"),
            ),
        ),
        project="acceptance_test_grid_panels",
    )

    flat = resolve_layout(ast)

    assert len(flat.items) == 20

    assert flat.sheet.width_mm == 1200
    assert flat.sheet.height_mm == 1200
    assert flat.project == "acceptance_test_grid_panels"

    pml_output = format_pml(flat)
    assert "sheet 1200.00mm 1200.00mm 19.00mm" in pml_output
    assert "project acceptance_test_grid_panels" in pml_output
    assert "profile through outside" in pml_output
    assert "pocket 5.00mm" in pml_output

    profile_items = [item for item in flat.items if item.feature and item.feature.type == "profile"]
    pocket_items = [item for item in flat.items if item.feature and item.feature.type == "pocket"]

    assert len(profile_items) == 4

    assert len(pocket_items) == 16

    print("\n=== Acceptance Test FlatPML Output ===")
    print(pml_output[:1000])
    print("  PASS")
    return True


def test_grid_with_no_explicit_cell():
    print("Running test_grid_with_no_explicit_cell...")
    ast = CompositionalLayoutAST(
        sheet=Sheet(width_mm=400, height_mm=400, thickness_mm=19, margin_mm=0.0),
        root=Panel(
            children=(
                Grid(
                    rows=2,
                    cols=2,
                    gap_mm=0,
                    children=(
                        Rect(
                            feature=Feature(type="pocket", depth_mm=5.0),
                        ),
                    ),
                ),
            )
        ),
    )

    flat = resolve_layout(ast)

    assert len(flat.items) == 4
    print("  PASS")
    return True


def test_rounded_rect_profile_inherits_geometry():
    """Test that ProfileGen inside RoundedRect produces RoundedRect profile item."""
    print("Running test_rounded_rect_profile_inherits_geometry...")
    ast = CompositionalLayoutAST(
        sheet=Sheet(width_mm=400, height_mm=600, thickness_mm=19, margin_mm=0.0),
        root=Panel(
            children=(
                RoundedRect(
                    radius_mm=25.0,
                    children=(ProfileGen(side="outside", depth="through"),),
                    id="panel",
                ),
            )
        ),
    )

    flat = resolve_layout(ast)

    assert len(flat.items) == 2

    shape_item = flat.items[0]
    assert shape_item.shape_id == "panel"
    assert shape_item.type == "RoundedRect"
    assert shape_item.geometry.data["radius_mm"] == 25.0

    profile_item = flat.items[1]
    assert profile_item.type == "RoundedRect"
    assert profile_item.feature.type == "profile"
    assert profile_item.geometry.data["radius_mm"] == 25.0
    assert profile_item.geometry.data["w_mm"] == 400.0
    assert profile_item.geometry.data["h_mm"] == 600.0

    print("  PASS")
    return True


def test_rounded_rect_selective_corners_profile_inherits():
    """Test that ProfileGen inside RoundedRect with selective corners preserves corner radii."""
    print("Running test_rounded_rect_selective_corners_profile_inherits...")
    ast = CompositionalLayoutAST(
        sheet=Sheet(width_mm=400, height_mm=600, thickness_mm=19, margin_mm=0.0),
        root=Panel(
            children=(
                RoundedRect(
                    radius_mm=25.4,
                    corners=frozenset({"bl", "br"}),
                    children=(ProfileGen(side="outside", depth="through"),),
                    id="panel",
                ),
            )
        ),
    )

    flat = resolve_layout(ast)

    assert len(flat.items) == 2

    shape_item = flat.items[0]
    assert shape_item.type == "RoundedRect"
    assert shape_item.geometry.data["radius_tl_mm"] == 0.0
    assert shape_item.geometry.data["radius_tr_mm"] == 0.0
    assert shape_item.geometry.data["radius_bl_mm"] == 25.4
    assert shape_item.geometry.data["radius_br_mm"] == 25.4

    profile_item = flat.items[1]
    assert profile_item.type == "RoundedRect"
    assert profile_item.feature.type == "profile"
    assert profile_item.geometry.data["radius_tl_mm"] == 0.0
    assert profile_item.geometry.data["radius_tr_mm"] == 0.0
    assert profile_item.geometry.data["radius_bl_mm"] == 25.4
    assert profile_item.geometry.data["radius_br_mm"] == 25.4

    print("  PASS")
    return True


def test_rect_profile_stays_rect():
    """Test that ProfileGen inside Rect still produces Rect profile item (backward compatibility)."""
    print("Running test_rect_profile_stays_rect...")
    ast = CompositionalLayoutAST(
        sheet=Sheet(width_mm=400, height_mm=600, thickness_mm=19, margin_mm=0.0),
        root=Panel(
            children=(
                Rect(
                    children=(ProfileGen(side="outside", depth="through"),),
                    id="panel",
                ),
            )
        ),
    )

    flat = resolve_layout(ast)

    assert len(flat.items) == 2

    shape_item = flat.items[0]
    assert shape_item.shape_id == "panel"
    assert shape_item.type == "Rect"

    profile_item = flat.items[1]
    assert profile_item.type == "Rect"
    assert profile_item.feature.type == "profile"
    assert "radius_mm" not in profile_item.geometry.data

    print("  PASS")
    return True


def test_validation_mode_passes_for_correct_resolution():
    """Test that validation mode passes when resolution is correct."""
    print("Running test_validation_mode_passes_for_correct_resolution...")
    ast = CompositionalLayoutAST(
        sheet=Sheet(width_mm=400, height_mm=600, thickness_mm=19, margin_mm=0.0),
        root=Panel(
            children=(
                RoundedRect(
                    radius_mm=25.0,
                    corners=frozenset({"bl", "br"}),
                    children=(ProfileGen(side="outside", depth="through"),),
                    id="panel",
                ),
            )
        ),
    )

    flat = resolve_layout(ast, validate=True)

    assert len(flat.items) == 2
    assert flat.items[1].type == "RoundedRect"
    print("  PASS")
    return True


def test_validation_assertion_catches_type_mismatch():
    """Test that validation assertions catch shape context type mismatches."""
    print("Running test_validation_assertion_catches_type_mismatch...")
    from layout_ast.layout import Geometry, Item, Placement

    ast = CompositionalLayoutAST(
        sheet=Sheet(width_mm=400, height_mm=600, thickness_mm=19, margin_mm=0.0),
        root=Panel(children=()),
    )
    resolver = LayoutResolver(ast, validate=True)

    bad_item = Item(
        kind="shape",
        type="Rect",
        geometry=Geometry(data={"w_mm": 400, "h_mm": 600}),
        placement=Placement(center_xy_mm=(200, 300)),
        feature=Feature(type="profile", depth_mm=0.0, is_through=True, side="outside"),
        shape_id="test",
    )

    try:
        resolver._assert_shape_context("RoundedRect", bad_item, "test")
        raise AssertionError("Should have raised ResolutionAssertionError")
    except ResolutionAssertionError as e:
        assert "RoundedRect" in str(e)
        assert "Rect" in str(e)

    print("  PASS")
    return True


def test_validation_assertion_catches_geometry_mismatch():
    """Test that validation assertions catch geometry mismatches."""
    print("Running test_validation_assertion_catches_geometry_mismatch...")

    ast = CompositionalLayoutAST(
        sheet=Sheet(width_mm=400, height_mm=600, thickness_mm=19, margin_mm=0.0),
        root=Panel(children=()),
    )
    resolver = LayoutResolver(ast, validate=True)

    parent_geom = {"radius_bl_mm": 25.4, "radius_br_mm": 25.4}
    child_geom = {"radius_bl_mm": 0.0, "radius_br_mm": 25.4}

    try:
        resolver._assert_geometry_preserved(parent_geom, child_geom, ["radius_bl_mm", "radius_br_mm"], "test")
        raise AssertionError("Should have raised ResolutionAssertionError")
    except ResolutionAssertionError as e:
        assert "radius_bl_mm" in str(e)
        assert "25.4" in str(e)
        assert "0.0" in str(e)

    print("  PASS")
    return True


if __name__ == "__main__":
    tests = [
        test_simple_panel_with_rect,
        test_panel_with_inset,
        test_frame_insets_region_for_children,
        test_frame_does_not_emit_profile,
        test_grid_subdivides_region,
        test_component_definition_and_use,
        test_place_grid_with_components,
        test_acceptance_4_instances_frame_grid_pocket,
        test_grid_with_no_explicit_cell,
        test_rounded_rect_profile_inherits_geometry,
        test_rounded_rect_selective_corners_profile_inherits,
        test_rect_profile_stays_rect,
        test_validation_mode_passes_for_correct_resolution,
        test_validation_assertion_catches_type_mismatch,
        test_validation_assertion_catches_geometry_mismatch,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"  FAIL: {e}")
            failed += 1

    print(f"\n{passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)
