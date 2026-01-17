# tests/test_intent_assertions.py - Tests for intent-derived assertions
#
# Tests the derivation and checking of assertions from LayoutAST.
# See docs/cam_validation_plan.md for Stage 7 scope.

from __future__ import annotations

import os
import sys

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from layout_ast.layout import (
    LayoutAST,
    Sheet,
    Item,
    Geometry,
    Placement,
    Feature,
)
from validation.core import Verdict
from validation.assertions.intent_assertions import (
    derive_assertions,
    check_assertions,
    IntentAssertion,
    ASSERTION_IDS,
)


# Path to recipe outputs
RECIPE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "docs",
    "recipes",
)


# ============================================================================
# Test fixtures (helper functions)
# ============================================================================


def make_simple_profile_ast() -> LayoutAST:
    """AST for a simple profile cut (like recipe 01)."""
    return LayoutAST(
        sheet=Sheet(width_mm=450.0, height_mm=650.0, thickness_mm=19.0),
        items=(
            Item(
                kind="shape",
                type="Rect",
                geometry=Geometry(data={"w_mm": 200.0, "h_mm": 150.0}),
                placement=Placement(center_xy_mm=(225.0, 325.0)),
                feature=Feature(type="profile", depth="through", side="outside"),
                shape_id="part",
            ),
        ),
    )


def make_pocket_ast() -> LayoutAST:
    """AST for a pocket cut (like recipe 02)."""
    return LayoutAST(
        sheet=Sheet(width_mm=200.0, height_mm=150.0, thickness_mm=19.0),
        items=(
            Item(
                kind="shape",
                type="Rect",
                geometry=Geometry(data={"w_mm": 100.0, "h_mm": 80.0}),
                placement=Placement(center_xy_mm=(100.0, 75.0)),
                feature=Feature(type="pocket", depth=6.0, depth_mm=6.0),
                shape_id="panel",
            ),
        ),
    )


def make_shaker_door_ast() -> LayoutAST:
    """AST for a shaker door (like recipe 03)."""
    return LayoutAST(
        sheet=Sheet(width_mm=450.0, height_mm=650.0, thickness_mm=19.0),
        items=(
            Item(
                kind="shape",
                type="Rect",
                geometry=Geometry(data={"w_mm": 300.0, "h_mm": 500.0}),
                placement=Placement(center_xy_mm=(225.0, 325.0)),
                feature=Feature(type="pocket", depth=6.0, depth_mm=6.0),
                shape_id="panel",
            ),
            Item(
                kind="shape",
                type="Rect",
                geometry=Geometry(data={"w_mm": 400.0, "h_mm": 600.0}),
                placement=Placement(center_xy_mm=(225.0, 325.0)),
                feature=Feature(type="profile", depth="through", side="outside"),
                shape_id="door",
            ),
        ),
    )


def make_hole_ast() -> LayoutAST:
    """AST with holes."""
    return LayoutAST(
        sheet=Sheet(width_mm=200.0, height_mm=200.0, thickness_mm=19.0),
        items=(
            Item(
                kind="shape",
                type="Circle",
                geometry=Geometry(data={"diameter_mm": 10.0}),
                placement=Placement(center_xy_mm=(50.0, 50.0)),
                feature=Feature(type="hole", depth="through"),
                shape_id="hole_1",
            ),
            Item(
                kind="shape",
                type="Circle",
                geometry=Geometry(data={"diameter_mm": 10.0}),
                placement=Placement(center_xy_mm=(150.0, 150.0)),
                feature=Feature(type="hole", depth="through"),
                shape_id="hole_2",
            ),
        ),
    )


# ============================================================================
# Test assertion derivation
# ============================================================================


def test_derive_returns_list():
    """derive_assertions returns a list of IntentAssertion."""
    ast = make_simple_profile_ast()
    assertions = derive_assertions(ast)
    assert isinstance(assertions, list)
    assert all(isinstance(a, IntentAssertion) for a in assertions)
    print("PASS: test_derive_returns_list")


def test_sheet_dimensions_assertion():
    """Sheet dimensions assertion is derived."""
    ast = make_simple_profile_ast()
    assertions = derive_assertions(ast)
    sheet_asserts = [a for a in assertions if a.id == "SHEET_DIMENSIONS"]
    assert len(sheet_asserts) == 1

    sheet_assert = sheet_asserts[0]
    assert sheet_assert.expected["width_mm"] == 450.0
    assert sheet_assert.expected["height_mm"] == 650.0
    assert sheet_assert.expected["thickness_mm"] == 19.0
    assert sheet_assert.source == "ast:sheet"
    print("PASS: test_sheet_dimensions_assertion")


def test_item_count_assertion():
    """Item count assertion is derived."""
    ast = make_simple_profile_ast()
    assertions = derive_assertions(ast)
    count_asserts = [a for a in assertions if a.id == "ITEM_COUNT"]
    assert len(count_asserts) == 1
    assert count_asserts[0].expected["count"] == 1
    print("PASS: test_item_count_assertion")


def test_profile_exists_assertion():
    """Profile exists assertion is derived for profile features."""
    ast = make_simple_profile_ast()
    assertions = derive_assertions(ast)
    profile_asserts = [a for a in assertions if a.id == "PROFILE_EXISTS"]
    assert len(profile_asserts) == 1
    assert profile_asserts[0].expected["shape_id"] == "part"
    assert profile_asserts[0].expected["feature_type"] == "profile"
    print("PASS: test_profile_exists_assertion")


def test_profile_side_assertion():
    """Profile side assertion is derived for profile features with side."""
    ast = make_simple_profile_ast()
    assertions = derive_assertions(ast)
    side_asserts = [a for a in assertions if a.id == "PROFILE_SIDE"]
    assert len(side_asserts) == 1
    assert side_asserts[0].expected["side"] == "outside"
    assert side_asserts[0].expected["nominal_width_mm"] == 200.0
    assert side_asserts[0].expected["nominal_height_mm"] == 150.0
    print("PASS: test_profile_side_assertion")


def test_through_cut_assertion():
    """Through cut assertion is derived for through cuts."""
    ast = make_simple_profile_ast()
    assertions = derive_assertions(ast)
    through_asserts = [a for a in assertions if a.id == "THROUGH_CUT"]
    assert len(through_asserts) == 1
    assert through_asserts[0].expected["target_depth_mm"] == -19.0
    print("PASS: test_through_cut_assertion")


def test_pocket_depth_assertion():
    """Pocket depth assertion is derived for pocket features."""
    ast = make_pocket_ast()
    assertions = derive_assertions(ast)
    pocket_asserts = [a for a in assertions if a.id == "POCKET_DEPTH"]
    assert len(pocket_asserts) == 1
    assert pocket_asserts[0].expected["depth_mm"] == 6.0
    print("PASS: test_pocket_depth_assertion")


def test_shaker_door_multiple_assertions():
    """Multiple assertions derived for complex layouts."""
    ast = make_shaker_door_ast()
    assertions = derive_assertions(ast)

    # Should have: 1 sheet, 1 item_count, 1 pocket_depth, 1 profile_exists,
    # 1 profile_side, 1 through_cut
    ids = [a.id for a in assertions]
    assert ids.count("SHEET_DIMENSIONS") == 1
    assert ids.count("ITEM_COUNT") == 1
    assert ids.count("POCKET_DEPTH") == 1
    assert ids.count("PROFILE_EXISTS") == 1
    assert ids.count("PROFILE_SIDE") == 1
    assert ids.count("THROUGH_CUT") == 1
    print("PASS: test_shaker_door_multiple_assertions")


def test_hole_position_assertion():
    """Hole position assertions are derived."""
    ast = make_hole_ast()
    assertions = derive_assertions(ast)
    pos_asserts = [a for a in assertions if a.id == "HOLE_POSITION"]
    assert len(pos_asserts) == 2

    # Check positions
    positions = [(a.expected["center_x_mm"], a.expected["center_y_mm"]) for a in pos_asserts]
    assert (50.0, 50.0) in positions
    assert (150.0, 150.0) in positions
    print("PASS: test_hole_position_assertion")


def test_hole_diameter_assertion():
    """Hole diameter assertions are derived."""
    ast = make_hole_ast()
    assertions = derive_assertions(ast)
    diam_asserts = [a for a in assertions if a.id == "HOLE_DIAMETER"]
    assert len(diam_asserts) == 2
    for a in diam_asserts:
        assert a.expected["diameter_mm"] == 10.0
    print("PASS: test_hole_diameter_assertion")


# ============================================================================
# Test assertion checking with mock metrics
# ============================================================================


def test_check_returns_results():
    """check_assertions returns AssertionResult objects."""
    ast = make_simple_profile_ast()
    assertions = derive_assertions(ast)

    # Mock metrics that would pass
    stl_metrics = {
        "dimensions": {
            "width_mm": 450.0,
            "height_mm": 650.0,
            "thickness_mm": 19.0,
        },
    }

    results = check_assertions(assertions, stl_metrics=stl_metrics)
    assert len(results) > 0
    from validation.core import AssertionResult
    assert all(isinstance(r, AssertionResult) for r in results)
    print("PASS: test_check_returns_results")


def test_sheet_dimensions_pass():
    """Sheet dimensions assertion passes with matching metrics."""
    ast = make_simple_profile_ast()
    assertions = derive_assertions(ast)

    # Use SVG SHEET_OUTLINE for sheet dimensions (preferred source)
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
    # Also provide STL for thickness validation
    stl_metrics = {
        "dimensions": {
            "width_mm": 200.0,  # STL has item dimensions, not sheet
            "height_mm": 150.0,
            "thickness_mm": 19.0,
        },
    }

    results = check_assertions(assertions, svg_metrics=svg_metrics, stl_metrics=stl_metrics)
    sheet_results = [r for r in results if r.id == "SHEET_DIMENSIONS"]
    assert len(sheet_results) == 1
    assert sheet_results[0].status == Verdict.PASS
    print("PASS: test_sheet_dimensions_pass")


def test_sheet_dimensions_fail():
    """Sheet dimensions assertion fails with mismatched metrics."""
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
                            "width": 400.0,  # Wrong width
                            "height": 650.0,
                            "center": [200.0, 325.0],
                            "bounds": [0.0, 0.0, 400.0, 650.0],
                        }
                    ],
                },
            }
        }
    }
    stl_metrics = {
        "dimensions": {"thickness_mm": 19.0},
    }

    results = check_assertions(assertions, svg_metrics=svg_metrics, stl_metrics=stl_metrics)
    sheet_results = [r for r in results if r.id == "SHEET_DIMENSIONS"]
    assert len(sheet_results) == 1
    assert sheet_results[0].status == Verdict.FAIL
    assert "width" in sheet_results[0].message.lower()
    print("PASS: test_sheet_dimensions_fail")


def test_sheet_dimensions_warn_no_metrics():
    """Sheet dimensions assertion warns when metrics not available."""
    ast = make_simple_profile_ast()
    assertions = derive_assertions(ast)

    results = check_assertions(assertions, stl_metrics=None)
    sheet_results = [r for r in results if r.id == "SHEET_DIMENSIONS"]
    assert len(sheet_results) == 1
    assert sheet_results[0].status == Verdict.WARN
    print("PASS: test_sheet_dimensions_warn_no_metrics")


def test_profile_exists_pass():
    """Profile exists assertion passes when layer has matching geometry."""
    ast = make_simple_profile_ast()
    assertions = derive_assertions(ast)

    # Mock metrics with per-element geometry matching AST item
    # AST item: 200x150 centered at (225, 325)
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
    print("PASS: test_profile_exists_pass")


def test_profile_exists_fail():
    """Profile exists assertion fails when layer is empty."""
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
    print("PASS: test_profile_exists_fail")


def test_pocket_depth_pass():
    """Pocket depth assertion passes when Z level exists."""
    ast = make_pocket_ast()
    assertions = derive_assertions(ast)

    # For 6mm pocket in 19mm sheet: Z = 19 - 6 = 13mm
    stl_metrics = {
        "dimensions": {"thickness_mm": 19.0, "width_mm": 200.0, "height_mm": 150.0},
        "z_statistics": {
            "unique_z_levels": [0.0, 13.0, 19.0],  # bottom, pocket floor, top
        },
    }

    results = check_assertions(assertions, stl_metrics=stl_metrics)
    pocket_results = [r for r in results if r.id == "POCKET_DEPTH"]
    assert len(pocket_results) == 1
    assert pocket_results[0].status == Verdict.PASS
    print("PASS: test_pocket_depth_pass")


def test_pocket_depth_fail():
    """Pocket depth assertion fails when Z level doesn't exist."""
    ast = make_pocket_ast()
    assertions = derive_assertions(ast)

    stl_metrics = {
        "dimensions": {"thickness_mm": 19.0, "width_mm": 200.0, "height_mm": 150.0},
        "z_statistics": {
            "unique_z_levels": [0.0, 19.0],  # No pocket floor
        },
    }

    results = check_assertions(assertions, stl_metrics=stl_metrics)
    pocket_results = [r for r in results if r.id == "POCKET_DEPTH"]
    assert len(pocket_results) == 1
    assert pocket_results[0].status == Verdict.FAIL
    print("PASS: test_pocket_depth_fail")


def test_through_cut_pass():
    """Through cut assertion passes when max plunge reaches target."""
    ast = make_simple_profile_ast()
    assertions = derive_assertions(ast)

    gcode_metrics = {
        "z_profile": {
            "max_plunge_z_mm": -19.0,  # Full depth
        },
    }

    results = check_assertions(assertions, gcode_metrics=gcode_metrics)
    through_results = [r for r in results if r.id == "THROUGH_CUT"]
    assert len(through_results) == 1
    assert through_results[0].status == Verdict.PASS
    print("PASS: test_through_cut_pass")


def test_through_cut_fail():
    """Through cut assertion fails when max plunge doesn't reach target."""
    ast = make_simple_profile_ast()
    assertions = derive_assertions(ast)

    gcode_metrics = {
        "z_profile": {
            "max_plunge_z_mm": -10.0,  # Not full depth
        },
    }

    results = check_assertions(assertions, gcode_metrics=gcode_metrics)
    through_results = [r for r in results if r.id == "THROUGH_CUT"]
    assert len(through_results) == 1
    assert through_results[0].status == Verdict.FAIL
    print("PASS: test_through_cut_fail")


def test_outside_profile_side_pass():
    """Outside profile side passes when toolpath bounds include shape."""
    ast = make_simple_profile_ast()
    assertions = derive_assertions(ast)

    # Shape is 200x150 centered at (225, 325)
    # Bounds: x=[125,325], y=[250,400]
    # Outside profile should cut at or outside these bounds
    gcode_metrics = {
        "xy_bounds": {
            "x_min": 120.0,  # Outside shape bounds
            "x_max": 330.0,
            "y_min": 245.0,
            "y_max": 405.0,
        },
    }

    results = check_assertions(assertions, gcode_metrics=gcode_metrics)
    side_results = [r for r in results if r.id == "PROFILE_SIDE"]
    assert len(side_results) == 1
    assert side_results[0].status == Verdict.PASS
    print("PASS: test_outside_profile_side_pass")


def test_hole_position_pass():
    """Hole position passes when circles exist at expected positions in HOLES layer."""
    ast = make_hole_ast()
    assertions = derive_assertions(ast)

    # Mock metrics with per-element geometry matching AST holes
    # AST holes: 10mm diameter at (50, 50) and (150, 150)
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
    pos_results = [r for r in results if r.id == "HOLE_POSITION"]
    assert len(pos_results) == 2
    assert all(r.status == Verdict.PASS for r in pos_results)
    print("PASS: test_hole_position_pass")


def test_hole_diameter_pass():
    """Hole diameter passes when matching radius exists in HOLES layer."""
    ast = make_hole_ast()
    assertions = derive_assertions(ast)

    # Mock metrics with per-element geometry in HOLES layer
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
                            "radius": 5.0,  # 10mm diameter
                        },
                        {
                            "element_type": "circle",
                            "bounds": [145.0, 145.0, 155.0, 155.0],
                            "center": [150.0, 150.0],
                            "radius": 5.0,  # 10mm diameter
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
    print("PASS: test_hole_diameter_pass")


# ============================================================================
# Test with actual recipe outputs (integration tests)
# ============================================================================


def test_simple_profile_recipe():
    """Test assertions against recipe 01 outputs."""
    recipe_dir = os.path.join(RECIPE_DIR, "01_simple_profile")
    if not os.path.exists(recipe_dir):
        print("SKIP: test_simple_profile_recipe (recipe directory not found)")
        return

    # Parse PML to get AST
    from pml.parser import parse_pml
    pml_path = os.path.join(recipe_dir, "example.pml")
    if not os.path.exists(pml_path):
        print("SKIP: test_simple_profile_recipe (PML file not found)")
        return

    with open(pml_path) as f:
        ast = parse_pml(f.read())

    # Extract metrics from outputs (using actual filenames)
    output_dir = os.path.join(recipe_dir, "output")
    svg_path = os.path.join(output_dir, "01_simple_profile.svg")
    stl_path = os.path.join(output_dir, "example.stl")
    nc_path = os.path.join(output_dir, "profile-3.17mm.nc")

    svg_metrics = None
    stl_metrics = None
    gcode_metrics = None

    if os.path.exists(svg_path):
        from validation.metrics.svg_metrics import extract_svg_metrics_from_file
        svg_metrics = extract_svg_metrics_from_file(svg_path).to_dict()

    if os.path.exists(stl_path):
        from validation.metrics.stl_metrics import extract_stl_metrics
        stl_metrics = extract_stl_metrics(stl_path).to_dict()

    if os.path.exists(nc_path):
        from validation.metrics.gcode_metrics import extract_gcode_metrics
        gcode_metrics = extract_gcode_metrics(nc_path).to_dict()

    # Derive and check assertions
    assertions = derive_assertions(ast)
    results = check_assertions(
        assertions,
        svg_metrics=svg_metrics,
        stl_metrics=stl_metrics,
        gcode_metrics=gcode_metrics,
    )

    # Report any failures
    failures = [r for r in results if r.status == Verdict.FAIL]
    if failures:
        for f in failures:
            print(f"  FAIL: {f.id} - {f.message}")
            print(f"    Expected: {f.expected}")
            print(f"    Actual: {f.actual}")

    # All assertions should pass (excluding WARN for missing metrics)
    assert all(r.status != Verdict.FAIL for r in results), \
        f"Recipe 01 has {len(failures)} assertion failures"
    print(f"PASS: test_simple_profile_recipe ({len(results)} assertions, {len(failures)} failures)")


def test_pocket_recipe():
    """Test assertions against recipe 02 outputs."""
    recipe_dir = os.path.join(RECIPE_DIR, "02_pocket_with_cleanup")
    if not os.path.exists(recipe_dir):
        print("SKIP: test_pocket_recipe (recipe directory not found)")
        return

    from pml.parser import parse_pml
    pml_path = os.path.join(recipe_dir, "example.pml")
    if not os.path.exists(pml_path):
        print("SKIP: test_pocket_recipe (PML file not found)")
        return

    with open(pml_path) as f:
        ast = parse_pml(f.read())

    output_dir = os.path.join(recipe_dir, "output")
    svg_path = os.path.join(output_dir, "02_pocket_with_cleanup.svg")
    stl_path = os.path.join(output_dir, "example.stl")
    nc_path = os.path.join(output_dir, "pocket-9.53mm.nc")

    svg_metrics = None
    stl_metrics = None
    gcode_metrics = None

    if os.path.exists(svg_path):
        from validation.metrics.svg_metrics import extract_svg_metrics_from_file
        svg_metrics = extract_svg_metrics_from_file(svg_path).to_dict()

    if os.path.exists(stl_path):
        from validation.metrics.stl_metrics import extract_stl_metrics
        stl_metrics = extract_stl_metrics(stl_path).to_dict()

    if os.path.exists(nc_path):
        from validation.metrics.gcode_metrics import extract_gcode_metrics
        gcode_metrics = extract_gcode_metrics(nc_path).to_dict()

    assertions = derive_assertions(ast)
    results = check_assertions(
        assertions,
        svg_metrics=svg_metrics,
        stl_metrics=stl_metrics,
        gcode_metrics=gcode_metrics,
    )

    failures = [r for r in results if r.status == Verdict.FAIL]
    if failures:
        for f in failures:
            print(f"  FAIL: {f.id} - {f.message}")
            print(f"    Expected: {f.expected}")
            print(f"    Actual: {f.actual}")

    assert all(r.status != Verdict.FAIL for r in results), \
        f"Recipe 02 has {len(failures)} assertion failures"
    print(f"PASS: test_pocket_recipe ({len(results)} assertions, {len(failures)} failures)")


def test_shaker_door_recipe():
    """Test assertions against recipe 03 outputs.

    Recipe 03 (shaker door) has both pocket and profile operations in separate NC files.
    We merge G-code metrics from all NC files to get complete coverage.
    """
    import glob

    recipe_dir = os.path.join(RECIPE_DIR, "03_shaker_door_template")
    if not os.path.exists(recipe_dir):
        print("SKIP: test_shaker_door_recipe (recipe directory not found)")
        return

    from pml.parser import parse_pml
    pml_path = os.path.join(recipe_dir, "example.pml")
    if not os.path.exists(pml_path):
        print("SKIP: test_shaker_door_recipe (PML file not found)")
        return

    with open(pml_path) as f:
        ast = parse_pml(f.read())

    output_dir = os.path.join(recipe_dir, "output")
    svg_path = os.path.join(output_dir, "03_shaker_door_template.svg")
    stl_path = os.path.join(output_dir, "example.stl")

    svg_metrics = None
    stl_metrics = None
    gcode_metrics = None

    if os.path.exists(svg_path):
        from validation.metrics.svg_metrics import extract_svg_metrics_from_file
        svg_metrics = extract_svg_metrics_from_file(svg_path).to_dict()

    if os.path.exists(stl_path):
        from validation.metrics.stl_metrics import extract_stl_metrics
        stl_metrics = extract_stl_metrics(stl_path).to_dict()

    # Merge G-code metrics from all NC files in the output directory
    # This handles multi-tool recipes where different operations are in separate files
    nc_files = sorted(glob.glob(os.path.join(output_dir, "*.nc")))
    if nc_files:
        from validation.metrics.gcode_metrics import extract_gcode_metrics
        merged_metrics = None
        for nc_path in nc_files:
            metrics = extract_gcode_metrics(nc_path).to_dict()
            if merged_metrics is None:
                merged_metrics = metrics
            else:
                # Merge relevant fields: take min/max bounds, deepest Z, etc.
                gcode = merged_metrics.get("gcode", merged_metrics)
                new_gcode = metrics.get("gcode", metrics)

                # Merge xy_bounds (take combined extent)
                gcode["xy_bounds"]["x_min"] = min(
                    gcode["xy_bounds"]["x_min"], new_gcode["xy_bounds"]["x_min"]
                )
                gcode["xy_bounds"]["x_max"] = max(
                    gcode["xy_bounds"]["x_max"], new_gcode["xy_bounds"]["x_max"]
                )
                gcode["xy_bounds"]["y_min"] = min(
                    gcode["xy_bounds"]["y_min"], new_gcode["xy_bounds"]["y_min"]
                )
                gcode["xy_bounds"]["y_max"] = max(
                    gcode["xy_bounds"]["y_max"], new_gcode["xy_bounds"]["y_max"]
                )

                # Merge z_profile (take deepest plunge)
                gcode["z_profile"]["max_plunge_z_mm"] = min(
                    gcode["z_profile"]["max_plunge_z_mm"],
                    new_gcode["z_profile"]["max_plunge_z_mm"]
                )

        gcode_metrics = merged_metrics

    assertions = derive_assertions(ast)
    results = check_assertions(
        assertions,
        svg_metrics=svg_metrics,
        stl_metrics=stl_metrics,
        gcode_metrics=gcode_metrics,
    )

    failures = [r for r in results if r.status == Verdict.FAIL]
    if failures:
        for f in failures:
            print(f"  FAIL: {f.id} - {f.message}")
            print(f"    Expected: {f.expected}")
            print(f"    Actual: {f.actual}")

    assert all(r.status != Verdict.FAIL for r in results), \
        f"Recipe 03 has {len(failures)} assertion failures"
    print(f"PASS: test_shaker_door_recipe ({len(results)} assertions, {len(failures)} failures)")


# ============================================================================
# Main
# ============================================================================


def run_tests():
    """Run all tests."""
    print("=" * 60)
    print("Intent Assertions Tests")
    print("=" * 60)

    tests = [
        # Assertion derivation tests
        test_derive_returns_list,
        test_sheet_dimensions_assertion,
        test_item_count_assertion,
        test_profile_exists_assertion,
        test_profile_side_assertion,
        test_through_cut_assertion,
        test_pocket_depth_assertion,
        test_shaker_door_multiple_assertions,
        test_hole_position_assertion,
        test_hole_diameter_assertion,
        # Assertion checking tests
        test_check_returns_results,
        test_sheet_dimensions_pass,
        test_sheet_dimensions_fail,
        test_sheet_dimensions_warn_no_metrics,
        test_profile_exists_pass,
        test_profile_exists_fail,
        test_pocket_depth_pass,
        test_pocket_depth_fail,
        test_through_cut_pass,
        test_through_cut_fail,
        test_outside_profile_side_pass,
        test_hole_position_pass,
        test_hole_diameter_pass,
        # Integration tests
        test_simple_profile_recipe,
        test_pocket_recipe,
        test_shaker_door_recipe,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"FAIL: {test.__name__}: {e}")
            failed += 1
        except Exception as e:
            import traceback
            print(f"ERROR: {test.__name__}: {e}")
            traceback.print_exc()
            failed += 1

    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
