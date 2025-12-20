"""Tests for STL export adapter layer (AST → shape dicts).

Tests the conversion from LayoutAST Items to shape dicts for CAD export.
End-to-end STL export tests will be added when trimesh implementation is complete.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from layout_ast.layout import (
    LayoutAST,
    Sheet,
    Item,
    Geometry,
    Placement,
    Feature,
)
from adapters.ast_to_cad import items_to_shape_dicts


def test_items_to_shape_dicts_basic():
    """Test basic conversion of Items to shape dicts."""
    items = (
        Item(
            kind="shape",
            type="Rect",
            geometry=Geometry(data={"w_mm": 400.0, "h_mm": 600.0}),
            placement=Placement(center_xy_mm=(225.0, 325.0)),
            feature=Feature(type="profile", side="outside", depth="through"),
            shape_id="door_outer",
        ),
        Item(
            kind="shape",
            type="Circle",
            geometry=Geometry(data={"diameter_mm": 50.0}),
            placement=Placement(center_xy_mm=(100.0, 100.0)),
            feature=Feature(type="hole", depth="through"),
            shape_id="hole_1",
        ),
    )

    shapes = items_to_shape_dicts(items)

    assert len(shapes) == 2

    # Check rect shape
    rect = shapes[0]
    assert rect["type"] == "Rect"
    assert rect["geometry"] == {"w_mm": 400.0, "h_mm": 600.0}
    assert rect["placement"] == {"center_xy_mm": (225.0, 325.0)}
    assert rect["feature"]["type"] == "profile"
    assert rect["feature"]["side"] == "outside"
    assert rect["feature"]["depth"] == "through"
    assert rect["id"] == "door_outer"

    # Check circle shape
    circle = shapes[1]
    assert circle["type"] == "Circle"
    assert circle["geometry"] == {"diameter_mm": 50.0}
    assert circle["placement"] == {"center_xy_mm": (100.0, 100.0)}
    assert circle["feature"]["type"] == "hole"
    assert circle["feature"]["depth"] == "through"
    assert circle["id"] == "hole_1"


def test_items_to_shape_dicts_pocket():
    """Test conversion with pocket feature."""
    items = (
        Item(
            kind="shape",
            type="Rect",
            geometry=Geometry(data={"w_mm": 300.0, "h_mm": 500.0}),
            placement=Placement(center_xy_mm=(225.0, 325.0)),
            feature=Feature(type="pocket", depth=6.0, depth_mm=6.0),
            shape_id="panel_pocket",
        ),
    )

    shapes = items_to_shape_dicts(items)

    assert len(shapes) == 1
    shape = shapes[0]
    assert shape["type"] == "Rect"
    assert shape["feature"]["type"] == "pocket"
    assert shape["feature"]["depth_mm"] == 6.0


def test_items_to_shape_dicts_skips_templates():
    """Test that template items are skipped."""
    items = (
        Item(
            kind="shape",
            type="Rect",
            geometry=Geometry(data={"w_mm": 100.0, "h_mm": 200.0}),
            placement=Placement(center_xy_mm=(50.0, 100.0)),
            feature=Feature(type="profile", side="outside", depth="through"),
        ),
        Item(
            kind="template",
            type="Shaker",
            params={"outer_w": 400.0, "outer_h": 600.0},
            id="door_1",
        ),
    )

    shapes = items_to_shape_dicts(items)

    # Should only return the shape, not the template
    assert len(shapes) == 1
    assert shapes[0]["type"] == "Rect"


def test_items_to_shape_dicts_polyline():
    """Test conversion with polyline geometry."""
    items = (
        Item(
            kind="shape",
            type="Polyline",
            geometry=Geometry(
                data={
                    "points": [
                        (0.0, 0.0),
                        (100.0, 0.0),
                        (100.0, 100.0),
                        (0.0, 100.0),
                    ]
                }
            ),
            placement=Placement(center_xy_mm=(50.0, 50.0)),
            feature=Feature(type="engrave", depth=1.0, depth_mm=1.0),
            shape_id="decorative_line",
        ),
    )

    shapes = items_to_shape_dicts(items)

    assert len(shapes) == 1
    shape = shapes[0]
    assert shape["type"] == "Polyline"
    assert "points" in shape["geometry"]
    assert len(shape["geometry"]["points"]) == 4
    assert shape["feature"]["type"] == "engrave"


# End-to-end STL export tests will be added when trimesh implementation is complete
# The tests below would test:
# - test_stl_export_simple_profile(tmp_path)
# - test_stl_export_with_pocket(tmp_path)
# - test_stl_export_with_kerf(tmp_path)
# - test_stl_export_polyline(tmp_path)


if __name__ == "__main__":
    # Run basic adapter tests (no backend required)
    print("Testing items_to_shape_dicts (basic)...")
    test_items_to_shape_dicts_basic()
    print("✓ Pass")

    print("Testing items_to_shape_dicts (pocket)...")
    test_items_to_shape_dicts_pocket()
    print("✓ Pass")

    print("Testing items_to_shape_dicts (skips templates)...")
    test_items_to_shape_dicts_skips_templates()
    print("✓ Pass")

    print("Testing items_to_shape_dicts (polyline)...")
    test_items_to_shape_dicts_polyline()
    print("✓ Pass")

    print("\n✓ All adapter tests passed!")
    print("Note: STL export end-to-end tests pending (F003 - trimesh implementation)")
