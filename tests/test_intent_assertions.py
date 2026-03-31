from __future__ import annotations

import os

import pytest

from layout_ast.layout import (
    Feature,
    Geometry,
    Item,
    LayoutAST,
    Placement,
    Sheet,
)
from validation.assertions.intent_assertions import (
    IntentAssertion,
    check_assertions,
    derive_assertions,
)
from validation.core import Verdict

RECIPE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "docs",
    "recipes",
)


def make_simple_profile_ast() -> LayoutAST:
    return LayoutAST(
        sheet=Sheet(width_mm=450.0, height_mm=650.0, thickness_mm=19.0, margin_mm=0.0),
        items=(
            Item(
                kind="shape",
                type="Rect",
                geometry=Geometry(data={"w_mm": 200.0, "h_mm": 150.0}),
                placement=Placement(center_xy_mm=(225.0, 325.0)),
                feature=Feature(type="profile", depth_mm=0.0, is_through=True, side="outside"),
                shape_id="part",
            ),
        ),
    )


def make_pocket_ast() -> LayoutAST:
    return LayoutAST(
        sheet=Sheet(width_mm=200.0, height_mm=150.0, thickness_mm=19.0, margin_mm=0.0),
        items=(
            Item(
                kind="shape",
                type="Rect",
                geometry=Geometry(data={"w_mm": 100.0, "h_mm": 80.0}),
                placement=Placement(center_xy_mm=(100.0, 75.0)),
                feature=Feature(type="pocket", depth_mm=6.0),
                shape_id="panel",
            ),
        ),
    )


def make_shaker_door_ast() -> LayoutAST:
    return LayoutAST(
        sheet=Sheet(width_mm=450.0, height_mm=650.0, thickness_mm=19.0, margin_mm=0.0),
        items=(
            Item(
                kind="shape",
                type="Rect",
                geometry=Geometry(data={"w_mm": 300.0, "h_mm": 500.0}),
                placement=Placement(center_xy_mm=(225.0, 325.0)),
                feature=Feature(type="pocket", depth_mm=6.0),
                shape_id="panel",
            ),
            Item(
                kind="shape",
                type="Rect",
                geometry=Geometry(data={"w_mm": 400.0, "h_mm": 600.0}),
                placement=Placement(center_xy_mm=(225.0, 325.0)),
                feature=Feature(type="profile", depth_mm=0.0, is_through=True, side="outside"),
                shape_id="door",
            ),
        ),
    )


def make_hole_ast() -> LayoutAST:
    return LayoutAST(
        sheet=Sheet(width_mm=200.0, height_mm=200.0, thickness_mm=19.0, margin_mm=0.0),
        items=(
            Item(
                kind="shape",
                type="Circle",
                geometry=Geometry(data={"diameter_mm": 10.0}),
                placement=Placement(center_xy_mm=(50.0, 50.0)),
                feature=Feature(type="hole", depth_mm=0.0, is_through=True),
                shape_id="hole_1",
            ),
            Item(
                kind="shape",
                type="Circle",
                geometry=Geometry(data={"diameter_mm": 10.0}),
                placement=Placement(center_xy_mm=(150.0, 150.0)),
                feature=Feature(type="hole", depth_mm=0.0, is_through=True),
                shape_id="hole_2",
            ),
        ),
    )


def test_derive_returns_list():
    ast = make_simple_profile_ast()
    assertions = derive_assertions(ast)
    assert isinstance(assertions, list)
    assert all(isinstance(a, IntentAssertion) for a in assertions)


def test_sheet_dimensions_assertion():
    ast = make_simple_profile_ast()
    assertions = derive_assertions(ast)
    sheet_asserts = [a for a in assertions if a.id == "SHEET_DIMENSIONS"]
    assert len(sheet_asserts) == 1

    sheet_assert = sheet_asserts[0]
    assert sheet_assert.expected["width_mm"] == 450.0
    assert sheet_assert.expected["height_mm"] == 650.0
    assert sheet_assert.expected["thickness_mm"] == 19.0
    assert sheet_assert.source == "ast:sheet"


def test_item_count_assertion():
    ast = make_simple_profile_ast()
    assertions = derive_assertions(ast)
    count_asserts = [a for a in assertions if a.id == "ITEM_COUNT"]
    assert len(count_asserts) == 1
    assert count_asserts[0].expected["count"] == 1


def test_profile_exists_assertion():
    ast = make_simple_profile_ast()
    assertions = derive_assertions(ast)
    profile_asserts = [a for a in assertions if a.id == "PROFILE_EXISTS"]
    assert len(profile_asserts) == 1
    assert profile_asserts[0].expected["shape_id"] == "part"
    assert profile_asserts[0].expected["feature_type"] == "profile"


def test_profile_side_assertion():
    ast = make_simple_profile_ast()
    assertions = derive_assertions(ast)
    side_asserts = [a for a in assertions if a.id == "PROFILE_SIDE"]
    assert len(side_asserts) == 1
    assert side_asserts[0].expected["side"] == "outside"
    assert side_asserts[0].expected["nominal_width_mm"] == 200.0
    assert side_asserts[0].expected["nominal_height_mm"] == 150.0


def test_through_cut_assertion():
    ast = make_simple_profile_ast()
    assertions = derive_assertions(ast)
    through_asserts = [a for a in assertions if a.id == "THROUGH_CUT"]
    assert len(through_asserts) == 1
    assert through_asserts[0].expected["target_depth_mm"] == -19.0


def test_shaker_door_multiple_assertions():
    ast = make_shaker_door_ast()
    assertions = derive_assertions(ast)

    ids = [a.id for a in assertions]
    assert ids.count("SHEET_DIMENSIONS") == 1
    assert ids.count("ITEM_COUNT") == 1
    assert ids.count("PROFILE_EXISTS") == 1
    assert ids.count("PROFILE_SIDE") == 1
    assert ids.count("THROUGH_CUT") == 1


def test_hole_position_assertion():
    ast = make_hole_ast()
    assertions = derive_assertions(ast)
    pos_asserts = [a for a in assertions if a.id == "HOLE_POSITION"]
    assert len(pos_asserts) == 2

    positions = [(a.expected["center_x_mm"], a.expected["center_y_mm"]) for a in pos_asserts]
    assert (50.0, 50.0) in positions
    assert (150.0, 150.0) in positions


def test_hole_diameter_assertion():
    ast = make_hole_ast()
    assertions = derive_assertions(ast)
    diam_asserts = [a for a in assertions if a.id == "HOLE_DIAMETER"]
    assert len(diam_asserts) == 2
    for a in diam_asserts:
        assert a.expected["diameter_mm"] == 10.0


def test_check_returns_results():
    ast = make_simple_profile_ast()
    assertions = derive_assertions(ast)

    svg_metrics = {
        "layers": {
            "by_layer": {
                "SHEET_OUTLINE": {
                    "element_count": 1,
                    "elements": [
                        {
                            "element_type": "rect",
                            "width": 450.0,
                            "height": 650.0,
                        }
                    ],
                },
            }
        }
    }

    results = check_assertions(assertions, svg_metrics=svg_metrics)
    assert len(results) > 0
    from validation.core import AssertionResult

    assert all(isinstance(r, AssertionResult) for r in results)


def test_sheet_dimensions_pass():
    ast = make_simple_profile_ast()
    assertions = derive_assertions(ast)

    svg_metrics = {
        "layers": {
            "by_layer": {
                "SHEET_OUTLINE": {
                    "element_count": 1,
                    "elements": [
                        {
                            "element_type": "rect",
                            "width": 450.0,
                            "height": 650.0,
                            "center": [225.0, 325.0],
                            "bounds": [0.0, 0.0, 450.0, 650.0],
                        }
                    ],
                },
            }
        }
    }

    results = check_assertions(assertions, svg_metrics=svg_metrics)
    sheet_results = [r for r in results if r.id == "SHEET_DIMENSIONS"]
    assert len(sheet_results) == 1
    assert sheet_results[0].status == Verdict.PASS


def test_sheet_dimensions_fail():
    ast = make_simple_profile_ast()
    assertions = derive_assertions(ast)

    svg_metrics = {
        "layers": {
            "by_layer": {
                "SHEET_OUTLINE": {
                    "element_count": 1,
                    "elements": [
                        {
                            "element_type": "rect",
                            "width": 400.0,
                            "height": 650.0,
                            "center": [200.0, 325.0],
                            "bounds": [0.0, 0.0, 400.0, 650.0],
                        }
                    ],
                },
            }
        }
    }

    results = check_assertions(assertions, svg_metrics=svg_metrics)
    sheet_results = [r for r in results if r.id == "SHEET_DIMENSIONS"]
    assert len(sheet_results) == 1
    assert sheet_results[0].status == Verdict.FAIL
    assert "width" in sheet_results[0].message.lower()


def test_sheet_dimensions_warn_no_metrics():
    ast = make_simple_profile_ast()
    assertions = derive_assertions(ast)

    results = check_assertions(assertions, svg_metrics=None)
    sheet_results = [r for r in results if r.id == "SHEET_DIMENSIONS"]
    assert len(sheet_results) == 1
    assert sheet_results[0].status == Verdict.WARN


def test_profile_exists_pass():
    ast = make_simple_profile_ast()
    assertions = derive_assertions(ast)

    svg_metrics = {
        "layers": {
            "by_layer": {
                "PROFILE_CUTS": {
                    "element_count": 1,
                    "rect_count": 1,
                    "elements": [
                        {
                            "element_type": "rect",
                            "bounds": [125.0, 250.0, 325.0, 400.0],
                            "center": [225.0, 325.0],
                            "width": 200.0,
                            "height": 150.0,
                        }
                    ],
                },
            }
        }
    }

    results = check_assertions(assertions, svg_metrics=svg_metrics)
    profile_results = [r for r in results if r.id == "PROFILE_EXISTS"]
    assert len(profile_results) == 1
    assert profile_results[0].status == Verdict.PASS


def test_profile_exists_fail():
    ast = make_simple_profile_ast()
    assertions = derive_assertions(ast)

    svg_metrics = {
        "layers": {
            "by_layer": {
                "PROFILE_CUTS": {"element_count": 0, "rect_count": 0},
            }
        }
    }

    results = check_assertions(assertions, svg_metrics=svg_metrics)
    profile_results = [r for r in results if r.id == "PROFILE_EXISTS"]
    assert len(profile_results) == 1
    assert profile_results[0].status == Verdict.FAIL


def test_through_cut_pass():
    ast = make_simple_profile_ast()
    assertions = derive_assertions(ast)

    gcode_metrics = {
        "z_profile": {
            "max_plunge_z_mm": -19.0,
        },
    }

    results = check_assertions(assertions, gcode_metrics=gcode_metrics)
    through_results = [r for r in results if r.id == "THROUGH_CUT"]
    assert len(through_results) == 1
    assert through_results[0].status == Verdict.PASS


def test_through_cut_fail():
    ast = make_simple_profile_ast()
    assertions = derive_assertions(ast)

    gcode_metrics = {
        "z_profile": {
            "max_plunge_z_mm": -10.0,
        },
    }

    results = check_assertions(assertions, gcode_metrics=gcode_metrics)
    through_results = [r for r in results if r.id == "THROUGH_CUT"]
    assert len(through_results) == 1
    assert through_results[0].status == Verdict.FAIL


def test_outside_profile_side_pass():
    ast = make_simple_profile_ast()
    assertions = derive_assertions(ast)

    gcode_metrics = {
        "xy_bounds": {
            "x_min": 120.0,
            "x_max": 330.0,
            "y_min": 245.0,
            "y_max": 405.0,
        },
    }

    results = check_assertions(assertions, gcode_metrics=gcode_metrics)
    side_results = [r for r in results if r.id == "PROFILE_SIDE"]
    assert len(side_results) == 1
    assert side_results[0].status == Verdict.PASS


def test_hole_position_pass():
    ast = make_hole_ast()
    assertions = derive_assertions(ast)

    svg_metrics = {
        "document": {
            "viewbox": [0, 0, 200, 200],
        },
        "layers": {
            "by_layer": {
                "SHEET_OUTLINE": {
                    "element_count": 1,
                    "elements": [
                        {"element_type": "rect", "width": 200.0, "height": 200.0},
                    ],
                },
                "HOLES": {
                    "element_count": 2,
                    "circle_count": 2,
                    "elements": [
                        {
                            "element_type": "circle",
                            "bounds": [45.0, 145.0, 55.0, 155.0],
                            "center": [50.0, 150.0],
                            "radius": 5.0,
                        },
                        {
                            "element_type": "circle",
                            "bounds": [145.0, 45.0, 155.0, 55.0],
                            "center": [150.0, 50.0],
                            "radius": 5.0,
                        },
                    ],
                },
            }
        },
    }

    results = check_assertions(assertions, svg_metrics=svg_metrics)
    pos_results = [r for r in results if r.id == "HOLE_POSITION"]
    assert len(pos_results) == 2
    assert all(r.status == Verdict.PASS for r in pos_results)


def test_hole_diameter_pass():
    ast = make_hole_ast()
    assertions = derive_assertions(ast)

    svg_metrics = {
        "layers": {
            "by_layer": {
                "HOLES": {
                    "element_count": 2,
                    "circle_count": 2,
                    "elements": [
                        {
                            "element_type": "circle",
                            "bounds": [45.0, 45.0, 55.0, 55.0],
                            "center": [50.0, 50.0],
                            "radius": 5.0,
                        },
                        {
                            "element_type": "circle",
                            "bounds": [145.0, 145.0, 155.0, 155.0],
                            "center": [150.0, 150.0],
                            "radius": 5.0,
                        },
                    ],
                },
            }
        },
    }

    results = check_assertions(assertions, svg_metrics=svg_metrics)
    diam_results = [r for r in results if r.id == "HOLE_DIAMETER"]
    assert len(diam_results) == 2
    assert all(r.status == Verdict.PASS for r in diam_results)


def test_simple_profile_recipe():
    recipe_dir = os.path.join(RECIPE_DIR, "01_simple_profile")
    if not os.path.exists(recipe_dir):
        pytest.skip("recipe directory not found")

    from pml import parse_pml

    pml_path = os.path.join(recipe_dir, "example.pml.yml")
    if not os.path.exists(pml_path):
        pytest.skip("PML file not found")

    with open(pml_path) as f:
        ast = parse_pml(f.read())

    output_dir = os.path.join(recipe_dir, "output")
    svg_path = os.path.join(output_dir, "01_simple_profile.svg")
    nc_path = os.path.join(output_dir, "profile-3.17mm.nc")

    svg_metrics = None
    gcode_metrics = None

    if os.path.exists(svg_path):
        from validation.metrics.svg_metrics import extract_svg_metrics_from_file

        svg_metrics = extract_svg_metrics_from_file(svg_path).to_dict()

    if os.path.exists(nc_path):
        from validation.metrics.gcode_metrics import extract_gcode_metrics

        gcode_metrics = extract_gcode_metrics(nc_path).to_dict()

    assertions = derive_assertions(ast)
    results = check_assertions(
        assertions,
        svg_metrics=svg_metrics,
        gcode_metrics=gcode_metrics,
    )

    failures = [r for r in results if r.status == Verdict.FAIL]
    assert all(r.status != Verdict.FAIL for r in results), f"Recipe 01 has {len(failures)} assertion failures"


def test_pocket_recipe():
    recipe_dir = os.path.join(RECIPE_DIR, "02_pocket_with_cleanup")
    if not os.path.exists(recipe_dir):
        pytest.skip("recipe directory not found")

    from pml import parse_pml

    pml_path = os.path.join(recipe_dir, "example.pml.yml")
    if not os.path.exists(pml_path):
        pytest.skip("PML file not found")

    with open(pml_path) as f:
        ast = parse_pml(f.read())

    output_dir = os.path.join(recipe_dir, "output")
    svg_path = os.path.join(output_dir, "02_pocket_with_cleanup.svg")
    nc_path = os.path.join(output_dir, "pocket-9.53mm.nc")

    svg_metrics = None
    gcode_metrics = None

    if os.path.exists(svg_path):
        from validation.metrics.svg_metrics import extract_svg_metrics_from_file

        svg_metrics = extract_svg_metrics_from_file(svg_path).to_dict()

    if os.path.exists(nc_path):
        from validation.metrics.gcode_metrics import extract_gcode_metrics

        gcode_metrics = extract_gcode_metrics(nc_path).to_dict()

    assertions = derive_assertions(ast)
    results = check_assertions(
        assertions,
        svg_metrics=svg_metrics,
        gcode_metrics=gcode_metrics,
    )

    failures = [r for r in results if r.status == Verdict.FAIL]
    assert all(r.status != Verdict.FAIL for r in results), f"Recipe 02 has {len(failures)} assertion failures"


def test_shaker_door_recipe():
    import glob

    recipe_dir = os.path.join(RECIPE_DIR, "03_shaker_door_template")
    if not os.path.exists(recipe_dir):
        pytest.skip("recipe directory not found")

    from pml import parse_pml

    pml_path = os.path.join(recipe_dir, "example.pml.yml")
    if not os.path.exists(pml_path):
        pytest.skip("PML file not found")

    with open(pml_path) as f:
        ast = parse_pml(f.read())

    output_dir = os.path.join(recipe_dir, "output")
    svg_path = os.path.join(output_dir, "03_shaker_door_template.svg")

    svg_metrics = None
    gcode_metrics = None

    if os.path.exists(svg_path):
        from validation.metrics.svg_metrics import extract_svg_metrics_from_file

        svg_metrics = extract_svg_metrics_from_file(svg_path).to_dict()

    nc_files = sorted(glob.glob(os.path.join(output_dir, "*.nc")))
    if nc_files:
        from validation.metrics.gcode_metrics import extract_gcode_metrics

        merged_metrics = None
        for nc_path in nc_files:
            metrics = extract_gcode_metrics(nc_path).to_dict()
            if merged_metrics is None:
                merged_metrics = metrics
            else:
                gcode = merged_metrics.get("gcode", merged_metrics)
                new_gcode = metrics.get("gcode", metrics)

                gcode["xy_bounds"]["x_min"] = min(gcode["xy_bounds"]["x_min"], new_gcode["xy_bounds"]["x_min"])
                gcode["xy_bounds"]["x_max"] = max(gcode["xy_bounds"]["x_max"], new_gcode["xy_bounds"]["x_max"])
                gcode["xy_bounds"]["y_min"] = min(gcode["xy_bounds"]["y_min"], new_gcode["xy_bounds"]["y_min"])
                gcode["xy_bounds"]["y_max"] = max(gcode["xy_bounds"]["y_max"], new_gcode["xy_bounds"]["y_max"])

                gcode["z_profile"]["max_plunge_z_mm"] = min(
                    gcode["z_profile"]["max_plunge_z_mm"], new_gcode["z_profile"]["max_plunge_z_mm"]
                )

        gcode_metrics = merged_metrics

    assertions = derive_assertions(ast)
    results = check_assertions(
        assertions,
        svg_metrics=svg_metrics,
        gcode_metrics=gcode_metrics,
    )

    failures = [r for r in results if r.status == Verdict.FAIL]
    assert all(r.status != Verdict.FAIL for r in results), f"Recipe 03 has {len(failures)} assertion failures"
