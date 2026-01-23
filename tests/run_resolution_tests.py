
import sys
from pathlib import Path

from layout_ast.compositional import (
    Panel,
    Inset,
    Frame,
    Grid,
    Cell,
    ComponentDef,
    UseComponent,
    Place,
    Rect,
    CompositionalLayoutAST,
)
from layout_ast.layout import Sheet, Feature
from resolution.layout_resolver import resolve_layout
from pml import format_pml


def approx_equal(a: float, b: float, tolerance: float = 0.01) -> bool:
    return abs(a - b) < tolerance


def test_simple_panel_with_rect():
    print("Running test_simple_panel_with_rect...")

    ast = CompositionalLayoutAST(
        sheet=Sheet(width_mm=400, height_mm=600, thickness_mm=19),
        root=Panel(
            children=(
                Rect(
                    feature=Feature(type="profile", depth="through", side="outside"),
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

    print("  ✓ PASS")
    return True


def test_panel_with_inset():
    print("Running test_panel_with_inset...")

    ast = CompositionalLayoutAST(
        sheet=Sheet(width_mm=400, height_mm=600, thickness_mm=19),
        root=Panel(
            children=(
                Inset(
                    amount_mm=25,
                    children=(
                        Rect(
                            feature=Feature(type="pocket", depth="6.0", depth_mm=6.0),
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

    print("  ✓ PASS")
    return True


def test_frame_insets_region_for_children():
    print("Running test_frame_insets_region_for_children...")

    ast = CompositionalLayoutAST(
        sheet=Sheet(width_mm=400, height_mm=600, thickness_mm=19),
        root=Panel(
            children=(
                Rect(
                    children=(
                        Frame(
                            width_mm=50,
                            children=(
                                Rect(
                                    feature=Feature(type="pocket", depth="6.0", depth_mm=6.0),
                                    id="inner",
                                ),
                            ),
                        ),
                    ),
                    feature=Feature(type="profile", depth="through", side="outside"),
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

    print("  ✓ PASS")
    return True


def test_frame_does_not_emit_profile():
    print("Running test_frame_does_not_emit_profile...")

    ast = CompositionalLayoutAST(
        sheet=Sheet(width_mm=400, height_mm=600, thickness_mm=19),
        root=Panel(
            children=(
                Rect(
                    children=(
                        Frame(
                            width_mm=50,
                            children=(
                                Rect(
                                    feature=Feature(type="pocket", depth="6.0", depth_mm=6.0),
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

    print("  ✓ PASS")
    return True


def test_grid_subdivides_region():
    print("Running test_grid_subdivides_region...")

    ast = CompositionalLayoutAST(
        sheet=Sheet(width_mm=400, height_mm=400, thickness_mm=19),
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
                                    feature=Feature(type="pocket", depth="5.0", depth_mm=5.0),
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
        assert approx_equal(item.geometry.data["w_mm"], 195.0)
        assert approx_equal(item.geometry.data["h_mm"], 195.0)

    print("  ✓ PASS")
    return True


def test_component_definition_and_use():
    print("Running test_component_definition_and_use...")

    simple_panel = ComponentDef(
        name="SimplePanel",
        params={"recess_depth": 6.0},
        body=Rect(
            feature=Feature(type="pocket", depth="6.0", depth_mm=6.0),
            id="panel",
        ),
    )

    ast = CompositionalLayoutAST(
        sheet=Sheet(width_mm=400, height_mm=600, thickness_mm=19),
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

    print("  ✓ PASS")
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
                            feature=Feature(type="pocket", depth="6.0", depth_mm=6.0),
                            id="inner",
                        ),
                    ),
                ),
            ),
            feature=Feature(type="profile", depth="through", side="outside"),
            id="outer",
        ),
    )

    ast = CompositionalLayoutAST(
        sheet=Sheet(width_mm=1000, height_mm=1000, thickness_mm=19),
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

    assert len(flat.items) == 12

    first_outer = flat.items[0]
    assert first_outer.shape_id == "outer"
    assert approx_equal(first_outer.geometry.data["w_mm"], 475.0)
    assert approx_equal(first_outer.geometry.data["h_mm"], 475.0)

    print("  ✓ PASS")
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
                                            feature=Feature(type="pocket", depth="5.0", depth_mm=5.0),
                                        ),
                                    )
                                ),
                            ),
                        ),
                    ),
                ),
            ),
            feature=Feature(type="profile", depth="through", side="outside"),
            id="panel_outer",
        ),
    )

    ast = CompositionalLayoutAST(
        sheet=Sheet(width_mm=1200, height_mm=1200, thickness_mm=19),
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

    assert len(flat.items) == 24
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

    assert len(profile_items) == 8
    assert len(pocket_items) == 16

    print("\n=== Acceptance Test FlatPML Output (first 1000 chars) ===")
    print(pml_output[:1000])

    print("\n  ✓ PASS")
    return True


def test_grid_with_no_explicit_cell():
    print("Running test_grid_with_no_explicit_cell...")

    ast = CompositionalLayoutAST(
        sheet=Sheet(width_mm=400, height_mm=400, thickness_mm=19),
        root=Panel(
            children=(
                Grid(
                    rows=2,
                    cols=2,
                    gap_mm=0,
                    children=(
                        Rect(
                            feature=Feature(type="pocket", depth="5.0", depth_mm=5.0),
                        ),
                    ),
                ),
            )
        ),
    )

    flat = resolve_layout(ast)

    assert len(flat.items) == 4

    print("  ✓ PASS")
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
    ]

    results = []
    for test in tests:
        try:
            results.append(test())
        except Exception as e:
            print(f"  ✗ FAIL: {e}")
            import traceback
            traceback.print_exc()
            results.append(False)

    passed = sum(1 for r in results if r)
    total = len(results)
    print(f"\n{passed}/{total} layout resolution tests passed")

    sys.exit(0 if all(results) else 1)
