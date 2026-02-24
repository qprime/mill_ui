"""Tests for DepthMode (DepthSpec) in core/constants.py.

These tests verify the DepthMode class provides correct depth comparison
and resolution utilities for the "through" and "half" depth modes.
"""

import sys
import traceback


def test_is_through_with_string():
    """Test is_through() correctly identifies 'through' string."""
    print("Running test_is_through_with_string...")

    from core.constants import DepthMode

    assert DepthMode.is_through("through") is True
    assert DepthMode.is_through("Through") is False  # Case-sensitive
    assert DepthMode.is_through("THROUGH") is False  # Case-sensitive
    assert DepthMode.is_through("half") is False
    assert DepthMode.is_through("6.0") is False

    print("  ✓ PASS")
    return True


def test_is_through_with_numeric():
    """Test is_through() returns False for numeric values."""
    print("Running test_is_through_with_numeric...")

    from core.constants import DepthMode

    assert DepthMode.is_through(19.0) is False
    assert DepthMode.is_through(6.0) is False
    assert DepthMode.is_through(0.0) is False
    assert DepthMode.is_through(0) is False

    print("  ✓ PASS")
    return True


def test_is_through_with_none():
    """Test is_through() returns False for None."""
    print("Running test_is_through_with_none...")

    from core.constants import DepthMode

    assert DepthMode.is_through(None) is False

    print("  ✓ PASS")
    return True


def test_is_half():
    """Test is_half() correctly identifies 'half' string."""
    print("Running test_is_half...")

    from core.constants import DepthMode

    assert DepthMode.is_half("half") is True
    assert DepthMode.is_half("Half") is False  # Case-sensitive
    assert DepthMode.is_half("through") is False
    assert DepthMode.is_half(9.5) is False
    assert DepthMode.is_half(None) is False

    print("  ✓ PASS")
    return True


def test_resolve_through():
    """Test resolve() returns sheet thickness for 'through'."""
    print("Running test_resolve_through...")

    from core.constants import DepthMode

    result = DepthMode.resolve("through", sheet_thickness_mm=19.0)
    assert result == 19.0

    result = DepthMode.resolve("through", sheet_thickness_mm=12.5)
    assert result == 12.5

    print("  ✓ PASS")
    return True


def test_resolve_half():
    """Test resolve() returns half sheet thickness for 'half'."""
    print("Running test_resolve_half...")

    from core.constants import DepthMode

    result = DepthMode.resolve("half", sheet_thickness_mm=19.0)
    assert result == 9.5

    result = DepthMode.resolve("half", sheet_thickness_mm=12.0)
    assert result == 6.0

    print("  ✓ PASS")
    return True


def test_resolve_numeric():
    """Test resolve() passes through numeric values."""
    print("Running test_resolve_numeric...")

    from core.constants import DepthMode

    result = DepthMode.resolve(6.0, sheet_thickness_mm=19.0)
    assert result == 6.0

    result = DepthMode.resolve(3.5, sheet_thickness_mm=19.0)
    assert result == 3.5

    # Integer should be converted to float
    result = DepthMode.resolve(6, sheet_thickness_mm=19.0)
    assert result == 6.0

    print("  ✓ PASS")
    return True


def test_resolve_none():
    """Test resolve() returns sheet thickness for None."""
    print("Running test_resolve_none...")

    from core.constants import DepthMode

    result = DepthMode.resolve(None, sheet_thickness_mm=19.0)
    assert result == 19.0

    print("  ✓ PASS")
    return True


def test_resolve_string_number():
    """Test resolve() converts string numbers to float."""
    print("Running test_resolve_string_number...")

    from core.constants import DepthMode

    result = DepthMode.resolve("6.0", sheet_thickness_mm=19.0)
    assert result == 6.0

    result = DepthMode.resolve("3", sheet_thickness_mm=19.0)
    assert result == 3.0

    print("  ✓ PASS")
    return True


def test_depth_mode_constants():
    """Test that DepthMode constants have expected values."""
    print("Running test_depth_mode_constants...")

    from core.constants import DepthMode

    assert DepthMode.THROUGH == "through"
    assert DepthMode.HALF == "half"

    print("  ✓ PASS")
    return True


def test_integration_with_ast_to_removal():
    """Test DepthMode integrates correctly with ast_to_removal depth resolution."""
    print("Running test_integration_with_ast_to_removal...")

    from adapters.ast_to_removal import _resolve_depth
    from layout_ast.layout import Feature

    # Test through mode
    feature = Feature(type="profile", depth_mm=0.0, is_through=True)
    result = _resolve_depth(feature, sheet_thickness_mm=19.0)
    assert result == 19.0

    # Test explicit depth_mm
    feature = Feature(type="pocket", depth_mm=6.0)
    result = _resolve_depth(feature, sheet_thickness_mm=19.0)
    assert result == 6.0

    print("  ✓ PASS")
    return True


def run_tests():
    """Run all DepthMode tests."""
    tests = [
        test_is_through_with_string,
        test_is_through_with_numeric,
        test_is_through_with_none,
        test_is_half,
        test_resolve_through,
        test_resolve_half,
        test_resolve_numeric,
        test_resolve_none,
        test_resolve_string_number,
        test_depth_mode_constants,
        test_integration_with_ast_to_removal,
    ]

    passed = 0
    failed = 0

    for test_fn in tests:
        try:
            test_fn()
            passed += 1
        except AssertionError as e:
            print(f"  ✗ FAIL: {e}")
            traceback.print_exc()
            failed += 1
        except Exception as e:
            print(f"  ✗ ERROR: {e}")
            traceback.print_exc()
            failed += 1

    print(f"\n{'=' * 40}")
    print(f"Results: {passed}/{passed + failed} passed")

    return failed == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
