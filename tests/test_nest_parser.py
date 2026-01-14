"""Tests for nest PML parser.

Run from repository root: PYTHONPATH=. python3 -m tests.test_nest_parser
"""

import sys
from pml.nest_parser import parse_nest_pml, nest_job_to_api_params, NestParseError


def test_basic_nest_parsing():
    """Parse basic nest PML with all required fields."""
    print("Running test_basic_nest_parsing...")

    source = """
nest maxrects
    sheet 1000mm 2000mm 19mm
    kerf 6.35mm
    margin 10mm

    parts
        panel 400mm 600mm x4
    """

    job = parse_nest_pml(source)

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
    """Parse nest PML with guillotine algorithm."""
    print("Running test_guillotine_algorithm...")

    source = """
nest guillotine
    sheet 1200mm 2400mm 18mm

    parts
        door 500mm 800mm x2
    """

    job = parse_nest_pml(source)

    assert job.algorithm == "guillotine"
    assert job.sheet_width_mm == 1200.0
    assert job.sheet_height_mm == 2400.0
    assert job.sheet_thickness_mm == 18.0
    # Defaults when not specified
    assert job.kerf_mm == 6.35
    assert job.margin_mm == 10.0

    print("  PASSED")


def test_multiple_parts():
    """Parse nest PML with multiple parts."""
    print("Running test_multiple_parts...")

    source = """
nest maxrects
    sheet 1232mm 1245mm 19mm
    kerf 6.35mm
    margin 10mm

    parts
        large_door 457mm 597mm x20
        small_door 305mm 203mm x15
        tall_door 457mm 914mm x2
    """

    job = parse_nest_pml(source)

    assert len(job.parts) == 3
    assert job.parts[0].name == "large_door"
    assert job.parts[0].quantity == 20
    assert job.parts[1].name == "small_door"
    assert job.parts[1].quantity == 15
    assert job.parts[2].name == "tall_door"
    assert job.parts[2].quantity == 2

    print("  PASSED")


def test_part_with_template():
    """Parse nest PML with template specification."""
    print("Running test_part_with_template...")

    source = """
nest maxrects
    sheet 1000mm 2000mm 19mm

    parts
        door 400mm 600mm x2
            template Shaker
                stile_w 50mm
                rail_h 50mm
                panel_recess 6mm
    """

    job = parse_nest_pml(source)

    assert len(job.parts) == 1
    part = job.parts[0]
    assert part.name == "door"
    assert part.template == "Shaker"
    assert part.template_params["stile_w"] == 50.0
    assert part.template_params["rail_h"] == 50.0
    assert part.template_params["panel_recess"] == 6.0

    print("  PASSED")


def test_mixed_parts_with_and_without_template():
    """Parse nest PML with mix of templated and simple parts."""
    print("Running test_mixed_parts_with_and_without_template...")

    source = """
nest maxrects
    sheet 1232mm 1245mm 19mm
    kerf 6.35mm
    margin 10mm

    parts
        large_door 457mm 597mm x20
            template Shaker
                stile_w 57mm
                rail_h 57mm
                panel_recess 6mm

        small_door 305mm 203mm x15

        tall_door 457mm 914mm x2
            template Shaker
                stile_w 57mm
                rail_h 57mm
                panel_recess 6mm
    """

    job = parse_nest_pml(source)

    assert len(job.parts) == 3

    # First part has template
    assert job.parts[0].name == "large_door"
    assert job.parts[0].template == "Shaker"
    assert job.parts[0].template_params["stile_w"] == 57.0

    # Second part has no template
    assert job.parts[1].name == "small_door"
    assert job.parts[1].template is None
    assert job.parts[1].template_params == {}

    # Third part has template
    assert job.parts[2].name == "tall_door"
    assert job.parts[2].template == "Shaker"

    print("  PASSED")


def test_comments_ignored():
    """Comments are ignored in nest PML."""
    print("Running test_comments_ignored...")

    source = """
# This is a comment
nest maxrects
    # Another comment
    sheet 1000mm 2000mm 19mm

    parts
        # Part comment
        panel 400mm 600mm x4
    """

    job = parse_nest_pml(source)

    assert job.algorithm == "maxrects"
    assert len(job.parts) == 1

    print("  PASSED")


def test_quantity_default():
    """Parts without quantity default to 1."""
    print("Running test_quantity_default...")

    source = """
nest maxrects
    sheet 1000mm 2000mm 19mm

    parts
        panel 400mm 600mm
    """

    job = parse_nest_pml(source)

    assert job.parts[0].quantity == 1

    print("  PASSED")


def test_nest_job_to_api_params():
    """Convert NestJob to API params dict."""
    print("Running test_nest_job_to_api_params...")

    source = """
nest maxrects
    sheet 1232mm 1245mm 19mm
    kerf 6.35mm
    margin 10mm

    parts
        door 457mm 597mm x20
            template Shaker
                stile_w 57mm
                rail_h 57mm
                panel_recess 6mm

        panel 305mm 203mm x15
    """

    job = parse_nest_pml(source)
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
    """Error on missing nest directive."""
    print("Running test_error_missing_nest_directive...")

    source = """
    sheet 1000mm 2000mm 19mm

    parts
        panel 400mm 600mm
    """

    try:
        parse_nest_pml(source)
        assert False, "Should have raised NestParseError"
    except NestParseError as e:
        assert "nest" in str(e).lower()

    print("  PASSED")


def test_error_missing_sheet():
    """Error on missing sheet directive."""
    print("Running test_error_missing_sheet...")

    source = """
nest maxrects

    parts
        panel 400mm 600mm
    """

    try:
        parse_nest_pml(source)
        assert False, "Should have raised NestParseError"
    except NestParseError as e:
        assert "sheet" in str(e).lower()

    print("  PASSED")


def test_error_no_parts():
    """Error on empty parts list."""
    print("Running test_error_no_parts...")

    source = """
nest maxrects
    sheet 1000mm 2000mm 19mm

    parts
    """

    try:
        parse_nest_pml(source)
        assert False, "Should have raised NestParseError"
    except NestParseError as e:
        assert "parts" in str(e).lower() or "no parts" in str(e).lower()

    print("  PASSED")


def run_all_tests():
    """Run all tests."""
    print("=" * 60)
    print("Nest PML Parser Tests")
    print("=" * 60)

    tests = [
        test_basic_nest_parsing,
        test_guillotine_algorithm,
        test_multiple_parts,
        test_part_with_template,
        test_mixed_parts_with_and_without_template,
        test_comments_ignored,
        test_quantity_default,
        test_nest_job_to_api_params,
        test_error_missing_nest_directive,
        test_error_missing_sheet,
        test_error_no_parts,
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
