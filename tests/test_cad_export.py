
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


    rect = shapes[0]
    assert rect["type"] == "Rect"
    assert rect["geometry"] == {"w_mm": 400.0, "h_mm": 600.0}
    assert rect["placement"] == {"center_xy_mm": (225.0, 325.0)}
    assert rect["feature"]["type"] == "profile"
    assert rect["feature"]["side"] == "outside"
    assert rect["feature"]["depth"] == "through"
    assert rect["id"] == "door_outer"


    circle = shapes[1]
    assert circle["type"] == "Circle"
    assert circle["geometry"] == {"diameter_mm": 50.0}
    assert circle["placement"] == {"center_xy_mm": (100.0, 100.0)}
    assert circle["feature"]["type"] == "hole"
    assert circle["feature"]["depth"] == "through"
    assert circle["id"] == "hole_1"


def test_items_to_shape_dicts_pocket():
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


    assert len(shapes) == 1
    assert shapes[0]["type"] == "Rect"


def test_items_to_shape_dicts_polyline():
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


def test_stl_export_simple_profile(tmp_path):
    from cad.export.stl import export_stl

    items = (
        Item(
            kind="shape",
            type="Rect",
            geometry=Geometry(data={"w_mm": 400.0, "h_mm": 600.0}),
            placement=Placement(center_xy_mm=(225.0, 325.0)),
            feature=Feature(type="profile", side="outside", depth="through"),
            shape_id="door_outer",
        ),
    )

    shapes = items_to_shape_dicts(items)
    output_path = tmp_path / "simple_profile.stl"

    export_stl(
        shapes=shapes,
        sheet_thickness_mm=19.0,
        output_path=output_path,
    )

    assert output_path.exists()
    assert output_path.stat().st_size > 0


def test_stl_export_with_pocket(tmp_path):
    from cad.export.stl import export_stl

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
            type="Rect",
            geometry=Geometry(data={"w_mm": 300.0, "h_mm": 500.0}),
            placement=Placement(center_xy_mm=(225.0, 325.0)),
            feature=Feature(type="pocket", depth=6.0, depth_mm=6.0),
            shape_id="panel_pocket",
        ),
    )

    shapes = items_to_shape_dicts(items)
    output_path = tmp_path / "with_pocket.stl"

    export_stl(
        shapes=shapes,
        sheet_thickness_mm=19.0,
        output_path=output_path,
    )

    assert output_path.exists()
    assert output_path.stat().st_size > 0


def test_stl_export_with_kerf(tmp_path):
    from cad.export.stl import export_stl

    items = (
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
    output_path = tmp_path / "with_kerf.stl"

    export_stl(
        shapes=shapes,
        sheet_thickness_mm=19.0,
        output_path=output_path,
        kerf_mm=1.5875,
    )

    assert output_path.exists()
    assert output_path.stat().st_size > 0


def test_stl_export_polyline(tmp_path):
    from cad.export.stl import export_stl

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
    output_path = tmp_path / "polyline.stl"

    export_stl(
        shapes=shapes,
        sheet_thickness_mm=19.0,
        output_path=output_path,
    )

    assert output_path.exists()
    assert output_path.stat().st_size > 0


if __name__ == "__main__":

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


    print("\nTesting STL export (simple profile)...")
    test_stl_export_simple_profile(Path(tempfile.mkdtemp()))
    print("✓ Pass")

    print("Testing STL export (with pocket)...")
    test_stl_export_with_pocket(Path(tempfile.mkdtemp()))
    print("✓ Pass")

    print("Testing STL export (with kerf)...")
    test_stl_export_with_kerf(Path(tempfile.mkdtemp()))
    print("✓ Pass")

    print("Testing STL export (polyline)...")
    test_stl_export_polyline(Path(tempfile.mkdtemp()))
    print("✓ Pass")

    print("\n✓ All tests passed!")
