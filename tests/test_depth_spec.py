"""Tests for DepthMode (DepthSpec) in core/constants.py.

These tests verify the DepthMode class provides correct depth comparison
and resolution utilities for the "through" and "half" depth modes.
"""


def test_is_through_with_string():
    """Test is_through() correctly identifies 'through' string."""
    from core.constants import DepthMode

    assert DepthMode.is_through("through") is True
    assert DepthMode.is_through("Through") is False
    assert DepthMode.is_through("THROUGH") is False
    assert DepthMode.is_through("half") is False
    assert DepthMode.is_through("6.0") is False


def test_is_through_with_numeric():
    """Test is_through() returns False for numeric values."""
    from core.constants import DepthMode

    assert DepthMode.is_through(19.0) is False
    assert DepthMode.is_through(6.0) is False
    assert DepthMode.is_through(0.0) is False
    assert DepthMode.is_through(0) is False


def test_is_through_with_none():
    """Test is_through() returns False for None."""
    from core.constants import DepthMode

    assert DepthMode.is_through(None) is False


def test_is_half():
    """Test is_half() correctly identifies 'half' string."""
    from core.constants import DepthMode

    assert DepthMode.is_half("half") is True
    assert DepthMode.is_half("Half") is False
    assert DepthMode.is_half("through") is False
    assert DepthMode.is_half(9.5) is False
    assert DepthMode.is_half(None) is False


def test_resolve_through():
    """Test resolve() returns sheet thickness for 'through'."""
    from core.constants import DepthMode

    result = DepthMode.resolve("through", sheet_thickness_mm=19.0)
    assert result == 19.0

    result = DepthMode.resolve("through", sheet_thickness_mm=12.5)
    assert result == 12.5


def test_resolve_half():
    """Test resolve() returns half sheet thickness for 'half'."""
    from core.constants import DepthMode

    result = DepthMode.resolve("half", sheet_thickness_mm=19.0)
    assert result == 9.5

    result = DepthMode.resolve("half", sheet_thickness_mm=12.0)
    assert result == 6.0


def test_resolve_numeric():
    """Test resolve() passes through numeric values."""
    from core.constants import DepthMode

    result = DepthMode.resolve(6.0, sheet_thickness_mm=19.0)
    assert result == 6.0

    result = DepthMode.resolve(3.5, sheet_thickness_mm=19.0)
    assert result == 3.5

    result = DepthMode.resolve(6, sheet_thickness_mm=19.0)
    assert result == 6.0


def test_resolve_none():
    """Test resolve() returns sheet thickness for None."""
    from core.constants import DepthMode

    result = DepthMode.resolve(None, sheet_thickness_mm=19.0)
    assert result == 19.0


def test_resolve_string_number():
    """Test resolve() converts string numbers to float."""
    from core.constants import DepthMode

    result = DepthMode.resolve("6.0", sheet_thickness_mm=19.0)
    assert result == 6.0

    result = DepthMode.resolve("3", sheet_thickness_mm=19.0)
    assert result == 3.0


def test_depth_mode_constants():
    """Test that DepthMode constants have expected values."""
    from core.constants import DepthMode

    assert DepthMode.THROUGH == "through"
    assert DepthMode.HALF == "half"


def test_integration_with_ast_to_removal():
    """Test DepthMode integrates correctly with ast_to_removal depth resolution."""
    from adapters.ast_to_removal import _resolve_depth
    from layout_ast.layout import Feature

    feature = Feature(type="profile", depth_mm=0.0, is_through=True)
    result = _resolve_depth(feature, sheet_thickness_mm=19.0)
    assert result == 19.0

    feature = Feature(type="pocket", depth_mm=6.0)
    result = _resolve_depth(feature, sheet_thickness_mm=19.0)
    assert result == 6.0
