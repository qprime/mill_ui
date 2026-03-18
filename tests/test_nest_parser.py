import sys

from pml.nest_parser import nest_job_to_api_params
from pml.yaml_parser import NestParseError, parse_nest_yaml


def test_basic_nest_parsing():
    print("Running test_basic_nest_parsing...")

    source = """
Nest:
  algorithm: maxrects

  Sheet:
    width: 1000mm
    height: 2000mm
    thickness: 19mm

  kerf: 6.35mm
  margin: 10mm

  parts:
    - name: panel
      width: 400mm
      height: 600mm
      quantity: 4
"""

    job = parse_nest_yaml(source)

    assert job.algorithm == "maxrects"
    assert job.sheet_width_mm == 1000.0
    assert job.sheet_height_mm == 2000.0
    assert job.sheet_thickness_mm == 19.0
    assert job.kerf_mm == 6.35
    assert job.margin_mm == 10.0
    assert len(job.parts) == 1
    assert job.parts[0].name == "panel"
    assert job.parts[0].width_mm == 400.0
    assert job.parts[0].height_mm == 600.0
    assert job.parts[0].quantity == 4

    print("  PASSED")


def test_guillotine_algorithm():
    print("Running test_guillotine_algorithm...")

    source = """
Nest:
  algorithm: guillotine

  Sheet:
    width: 1200mm
    height: 2400mm
    thickness: 18mm

  parts:
    - name: door
      width: 500mm
      height: 800mm
      quantity: 2
"""

    job = parse_nest_yaml(source)

    assert job.algorithm == "guillotine"
    assert job.sheet_width_mm == 1200.0
    assert job.sheet_height_mm == 2400.0
    assert job.sheet_thickness_mm == 18.0

    assert job.kerf_mm == 6.35
    assert job.margin_mm == 10.0

    print("  PASSED")


def test_multiple_parts():
    print("Running test_multiple_parts...")

    source = """
Nest:
  algorithm: maxrects

  Sheet:
    width: 1232mm
    height: 1245mm
    thickness: 19mm

  kerf: 6.35mm
  margin: 10mm

  parts:
    - name: large_door
      width: 457mm
      height: 597mm
      quantity: 20

    - name: small_door
      width: 305mm
      height: 203mm
      quantity: 15

    - name: tall_door
      width: 457mm
      height: 914mm
      quantity: 2
"""

    job = parse_nest_yaml(source)

    assert len(job.parts) == 3
    assert job.parts[0].name == "large_door"
    assert job.parts[0].quantity == 20
    assert job.parts[1].name == "small_door"
    assert job.parts[1].quantity == 15
    assert job.parts[2].name == "tall_door"
    assert job.parts[2].quantity == 2

    print("  PASSED")


def test_part_with_template():
    print("Running test_part_with_template...")

    source = """
Nest:
  algorithm: maxrects

  Sheet:
    width: 1000mm
    height: 2000mm
    thickness: 19mm

  parts:
    - name: door
      width: 400mm
      height: 600mm
      quantity: 2
      template:
        name: Shaker
        params:
          stile_w: 50mm
          rail_h: 50mm
          panel_recess: 6mm
"""

    job = parse_nest_yaml(source)

    assert len(job.parts) == 1
    part = job.parts[0]
    assert part.name == "door"
    assert part.template == "Shaker"
    assert part.template_params["stile_w"] == 50.0
    assert part.template_params["rail_h"] == 50.0
    assert part.template_params["panel_recess"] == 6.0

    print("  PASSED")


def test_mixed_parts_with_and_without_template():
    print("Running test_mixed_parts_with_and_without_template...")

    source = """
Nest:
  algorithm: maxrects

  Sheet:
    width: 1232mm
    height: 1245mm
    thickness: 19mm

  kerf: 6.35mm
  margin: 10mm

  parts:
    - name: large_door
      width: 457mm
      height: 597mm
      quantity: 20
      template:
        name: Shaker
        params:
          stile_w: 57mm
          rail_h: 57mm
          panel_recess: 6mm

    - name: small_door
      width: 305mm
      height: 203mm
      quantity: 15

    - name: tall_door
      width: 457mm
      height: 914mm
      quantity: 2
      template:
        name: Shaker
        params:
          stile_w: 57mm
          rail_h: 57mm
          panel_recess: 6mm
"""

    job = parse_nest_yaml(source)

    assert len(job.parts) == 3

    assert job.parts[0].name == "large_door"
    assert job.parts[0].template == "Shaker"
    assert job.parts[0].template_params["stile_w"] == 57.0

    assert job.parts[1].name == "small_door"
    assert job.parts[1].template is None
    assert job.parts[1].template_params == {}

    assert job.parts[2].name == "tall_door"
    assert job.parts[2].template == "Shaker"

    print("  PASSED")


def test_quantity_default():
    print("Running test_quantity_default...")

    source = """
Nest:
  algorithm: maxrects

  Sheet:
    width: 1000mm
    height: 2000mm
    thickness: 19mm

  parts:
    - name: panel
      width: 400mm
      height: 600mm
"""

    job = parse_nest_yaml(source)

    assert job.parts[0].quantity == 1

    print("  PASSED")


def test_nest_job_to_api_params():
    print("Running test_nest_job_to_api_params...")

    source = """
Nest:
  algorithm: maxrects

  Sheet:
    width: 1232mm
    height: 1245mm
    thickness: 19mm

  kerf: 6.35mm
  margin: 10mm

  parts:
    - name: door
      width: 457mm
      height: 597mm
      quantity: 20
      template:
        name: Shaker
        params:
          stile_w: 57mm
          rail_h: 57mm
          panel_recess: 6mm

    - name: panel
      width: 305mm
      height: 203mm
      quantity: 15
"""

    job = parse_nest_yaml(source)
    params = nest_job_to_api_params(job)

    assert params["algorithm"] == "maxrects"
    assert params["sheet_width_mm"] == 1232.0
    assert params["sheet_height_mm"] == 1245.0
    assert params["sheet_thickness_mm"] == 19.0
    assert params["kerf_mm"] == 6.35
    assert params["margin_mm"] == 10.0

    assert len(params["parts"]) == 2
    assert params["parts"][0]["name"] == "door"
    assert params["parts"][0]["template"] == "Shaker"
    assert params["parts"][0]["template_params"]["stile_w"] == 57.0
    assert params["parts"][1]["name"] == "panel"
    assert "template" not in params["parts"][1]

    print("  PASSED")


def test_error_missing_nest_directive():
    print("Running test_error_missing_nest_directive...")

    source = """
Sheet:
  width: 1000mm
  height: 2000mm
  thickness: 19mm

parts:
  - name: panel
    width: 400mm
    height: 600mm
"""

    try:
        parse_nest_yaml(source)
        raise AssertionError("Should have raised NestParseError")
    except NestParseError as e:
        assert "nest" in str(e).lower()

    print("  PASSED")


def test_error_missing_sheet():
    print("Running test_error_missing_sheet...")

    source = """
Nest:
  algorithm: maxrects

  parts:
    - name: panel
      width: 400mm
      height: 600mm
"""

    try:
        parse_nest_yaml(source)
        raise AssertionError("Should have raised NestParseError")
    except NestParseError as e:
        assert "sheet" in str(e).lower()

    print("  PASSED")


def test_error_no_parts():
    print("Running test_error_no_parts...")

    source = """
Nest:
  algorithm: maxrects

  Sheet:
    width: 1000mm
    height: 2000mm
    thickness: 19mm

  parts: []
"""

    try:
        parse_nest_yaml(source)
        raise AssertionError("Should have raised NestParseError")
    except NestParseError as e:
        assert "parts" in str(e).lower() or "no parts" in str(e).lower()

    print("  PASSED")


def test_simple_template_reference():
    print("Running test_simple_template_reference...")

    source = """
Nest:
  algorithm: maxrects

  Sheet:
    width: 1000mm
    height: 2000mm
    thickness: 19mm

  parts:
    - name: door
      width: 400mm
      height: 600mm
      quantity: 2
      template: shaker
"""

    job = parse_nest_yaml(source)

    assert len(job.parts) == 1
    part = job.parts[0]
    assert part.name == "door"
    assert part.template == "shaker"
    assert part.template_params == {}

    print("  PASSED")


def test_parse_shape_rounded_rect():
    source = """
Nest:
  algorithm: maxrects
  Sheet:
    width: 1000mm
    height: 2000mm
    thickness: 19mm
  parts:
    - name: coaster
      width: 100mm
      height: 100mm
      quantity: 10
      shape:
        type: RoundedRect
        radius: 10mm
"""
    job = parse_nest_yaml(source)
    part = job.parts[0]
    assert part.shape == "RoundedRect"
    assert part.shape_params["radius_mm"] == 10.0
    assert "corners" not in part.shape_params


def test_parse_shape_rounded_rect_selective_corners():
    source = """
Nest:
  algorithm: maxrects
  Sheet:
    width: 1000mm
    height: 2000mm
    thickness: 19mm
  parts:
    - name: edge_strip
      width: 228.6mm
      height: 863.6mm
      quantity: 2
      shape:
        type: RoundedRect
        radius: 12.7mm
        corners: [tl, bl]
"""
    job = parse_nest_yaml(source)
    part = job.parts[0]
    assert part.shape == "RoundedRect"
    assert part.shape_params["radius_mm"] == 12.7
    assert part.shape_params["corners"] == ("bl", "tl")


def test_parse_shape_circle():
    source = """
Nest:
  algorithm: maxrects
  Sheet:
    width: 1000mm
    height: 2000mm
    thickness: 19mm
  parts:
    - name: disc
      width: 200mm
      height: 200mm
      quantity: 4
      shape:
        type: Circle
"""
    job = parse_nest_yaml(source)
    part = job.parts[0]
    assert part.shape == "Circle"
    assert part.shape_params == {}


def test_parse_shape_circle_nonsquare_error():
    source = """
Nest:
  algorithm: maxrects
  Sheet:
    width: 1000mm
    height: 2000mm
    thickness: 19mm
  parts:
    - name: disc
      width: 200mm
      height: 150mm
      shape:
        type: Circle
"""
    try:
        parse_nest_yaml(source)
        raise AssertionError("Should have raised NestParseError")
    except NestParseError as e:
        assert "width == height" in str(e)


def test_parse_shape_omitted():
    source = """
Nest:
  algorithm: maxrects
  Sheet:
    width: 1000mm
    height: 2000mm
    thickness: 19mm
  parts:
    - name: panel
      width: 400mm
      height: 600mm
"""
    job = parse_nest_yaml(source)
    part = job.parts[0]
    assert part.shape is None
    assert part.shape_params == {}


def test_parse_shape_and_template_error():
    source = """
Nest:
  algorithm: maxrects
  Sheet:
    width: 1000mm
    height: 2000mm
    thickness: 19mm
  parts:
    - name: door
      width: 400mm
      height: 600mm
      template: shaker
      shape:
        type: RoundedRect
        radius: 10mm
"""
    try:
        parse_nest_yaml(source)
        raise AssertionError("Should have raised NestParseError")
    except NestParseError as e:
        assert "mutually exclusive" in str(e)


def test_parse_shape_unknown_type():
    source = """
Nest:
  algorithm: maxrects
  Sheet:
    width: 1000mm
    height: 2000mm
    thickness: 19mm
  parts:
    - name: panel
      width: 400mm
      height: 600mm
      shape:
        type: Hexagon
"""
    try:
        parse_nest_yaml(source)
        raise AssertionError("Should have raised NestParseError")
    except NestParseError as e:
        assert "Hexagon" in str(e)


def test_parse_shape_rounded_rect_missing_radius():
    source = """
Nest:
  algorithm: maxrects
  Sheet:
    width: 1000mm
    height: 2000mm
    thickness: 19mm
  parts:
    - name: panel
      width: 400mm
      height: 600mm
      shape:
        type: RoundedRect
"""
    try:
        parse_nest_yaml(source)
        raise AssertionError("Should have raised NestParseError")
    except NestParseError as e:
        assert "radius" in str(e).lower()


def test_parse_shape_polygon_points_exceed_bounds():
    source = """
Nest:
  algorithm: maxrects
  Sheet:
    width: 1000mm
    height: 2000mm
    thickness: 19mm
  parts:
    - name: gusset
      width: 50mm
      height: 50mm
      shape:
        type: Polygon
        points: [[-100, -100], [100, -100], [0, 100]]
"""
    try:
        parse_nest_yaml(source)
        raise AssertionError("Should have raised NestParseError")
    except NestParseError as e:
        assert "exceeds" in str(e).lower()
        assert "bounding box" in str(e).lower()


def test_parse_shape_polygon_points_within_bounds():
    source = """
Nest:
  algorithm: maxrects
  Sheet:
    width: 1000mm
    height: 2000mm
    thickness: 19mm
  parts:
    - name: gusset
      width: 100mm
      height: 100mm
      shape:
        type: Polygon
        points: [[-50, -50], [50, -50], [0, 50]]
"""
    job = parse_nest_yaml(source)
    part = job.parts[0]
    assert part.shape == "Polygon"
    assert len(part.shape_params["points"]) == 3


def test_nest_job_to_api_params_with_shape():
    source = """
Nest:
  algorithm: maxrects
  Sheet:
    width: 1000mm
    height: 2000mm
    thickness: 19mm
  parts:
    - name: coaster
      width: 100mm
      height: 100mm
      quantity: 10
      shape:
        type: RoundedRect
        radius: 10mm
"""
    job = parse_nest_yaml(source)
    params = nest_job_to_api_params(job)
    part_dict = params["parts"][0]
    assert part_dict["shape"] == "RoundedRect"
    assert part_dict["shape_params"]["radius_mm"] == 10.0


def run_all_tests():
    print("=" * 60)
    print("Nest YAML Parser Tests")
    print("=" * 60)

    tests = [
        test_basic_nest_parsing,
        test_guillotine_algorithm,
        test_multiple_parts,
        test_part_with_template,
        test_mixed_parts_with_and_without_template,
        test_quantity_default,
        test_nest_job_to_api_params,
        test_error_missing_nest_directive,
        test_error_missing_sheet,
        test_error_no_parts,
        test_simple_template_reference,
        test_parse_shape_rounded_rect,
        test_parse_shape_rounded_rect_selective_corners,
        test_parse_shape_circle,
        test_parse_shape_circle_nonsquare_error,
        test_parse_shape_omitted,
        test_parse_shape_and_template_error,
        test_parse_shape_unknown_type,
        test_parse_shape_rounded_rect_missing_radius,
        test_parse_shape_polygon_points_exceed_bounds,
        test_parse_shape_polygon_points_within_bounds,
        test_nest_job_to_api_params_with_shape,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"  FAILED: {e}")
            import traceback

            traceback.print_exc()
            failed += 1

    print()
    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
