"""
Test suite for F001: Pocket Wall Cleanup Pass

Tests that pocket operations can optionally generate perimeter finish passes
to clean scalloped walls left by raster toolpaths.

Note: These tests mock the native backend to focus on testing the cleanup logic.
"""

from unittest.mock import patch
from cam.path.strategies import pocket_then_finish_profile
from cam.primitives import rectangle
from cam.transforms import Transform2D, place
from cam.model.setup import Setup
from cam.model.tool import Tool
from cam.model.stock import Stock
from cam.model.material import Material
from cam.model.machine import Machine


def _create_test_setup():
    """Create minimal setup for testing."""
    tool = Tool(name="6mm_flat", diameter=6.0, rpm=18000, feed_xy=2000, feed_z=300)
    stock = Stock(width=200.0, height=200.0, thickness=19.0)
    material = Material(name="MDF")
    machine = Machine(name="default_grbl")
    return Setup(stock=stock, tool=tool, material=material, machine=machine, safe_z=5.0)


def _count_comments_with_text(moves: list[dict], text: str) -> int:
    """Count moves that are comments containing the given text."""
    count = 0
    for move in moves:
        if move.get("kind") == "comment" and text in move.get("text", ""):
            count += 1
    return count


def _has_finish_profile_pass(moves: list[dict]) -> bool:
    """Check if moves contain a finish profile pass."""
    return _count_comments_with_text(moves, "finish profile pass") > 0


def _has_rough_pocket_comment(moves: list[dict]) -> bool:
    """Check if moves contain rough pocket comment."""
    return _count_comments_with_text(moves, "rough pocket") > 0


def _has_no_finish_comment(moves: list[dict]) -> bool:
    """Check if moves contain 'no finish' comment."""
    return _count_comments_with_text(moves, "no finish") > 0


@patch('cam.path.strategies.pocket_raster')
@patch('cam.path.strategies.profile_outline')
def test_pocket_cleanup_enabled_by_default(mock_profile, mock_raster):
    """Test that finish_perimeter=True generates finish pass."""
    # Mock native backend calls to return simple move lists
    mock_raster.return_value = [{"kind": "comment", "text": "raster_moves"}]
    mock_profile.return_value = [{"kind": "comment", "text": "profile_moves"}]

    # Create a simple rectangular pocket
    shape = rectangle(100, 100)
    shape = place(shape, Transform2D(tx=50, ty=50))

    # Create setup
    setup = _create_test_setup()

    # Generate moves with finish_perimeter=True (default)
    moves = pocket_then_finish_profile(
        shape,
        setup,
        total_depth_mm=10.0,
        finish_perimeter=True,
    )

    # Should have both rough pocket and finish profile
    assert _has_rough_pocket_comment(moves), "Should have rough pocket comment"
    assert _has_finish_profile_pass(moves), "Should have finish profile pass"
    assert not _has_no_finish_comment(moves), "Should not have 'no finish' comment"

    # Verify both backend functions were called
    assert mock_raster.called, "pocket_raster should be called for rough pass"
    assert mock_profile.called, "profile_outline should be called for finish pass"


@patch('cam.path.strategies.pocket_raster')
@patch('cam.path.strategies.profile_outline')
def test_pocket_cleanup_disabled(mock_profile, mock_raster):
    """Test that finish_perimeter=False skips finish pass."""
    # Mock native backend calls to return simple move lists
    mock_raster.return_value = [{"kind": "comment", "text": "raster_moves"}]
    mock_profile.return_value = [{"kind": "comment", "text": "profile_moves"}]

    # Create a simple rectangular pocket
    shape = rectangle(100, 100)
    shape = place(shape, Transform2D(tx=50, ty=50))

    # Create setup
    setup = _create_test_setup()

    # Generate moves with finish_perimeter=False
    moves = pocket_then_finish_profile(
        shape,
        setup,
        total_depth_mm=10.0,
        finish_perimeter=False,
    )

    # Should have pocket but NOT finish profile
    assert _has_no_finish_comment(moves), "Should have 'no finish' comment"
    assert not _has_finish_profile_pass(moves), "Should NOT have finish profile pass"
    assert not _has_rough_pocket_comment(moves), "Should not have 'rough pocket' comment when no finish"

    # Verify only raster was called, not profile
    assert mock_raster.called, "pocket_raster should be called"
    assert not mock_profile.called, "profile_outline should NOT be called when finish disabled"


@patch('cam.path.strategies.pocket_raster')
@patch('cam.path.strategies.profile_outline')
def test_pocket_cleanup_with_custom_offset(mock_profile, mock_raster):
    """Test that cleanup_offset_mm parameter works with finish pass."""
    # Mock native backend calls to return simple move lists
    mock_raster.return_value = [{"kind": "comment", "text": "raster_moves"}]
    mock_profile.return_value = [{"kind": "comment", "text": "profile_moves"}]

    # Create a simple rectangular pocket
    shape = rectangle(100, 100)
    shape = place(shape, Transform2D(tx=50, ty=50))

    # Create setup
    setup = _create_test_setup()

    # Generate moves with custom cleanup offset
    moves = pocket_then_finish_profile(
        shape,
        setup,
        total_depth_mm=10.0,
        cleanup_offset_mm=0.5,
        finish_perimeter=True,
    )

    # Should have both rough pocket and finish profile
    assert _has_rough_pocket_comment(moves), "Should have rough pocket comment"
    assert _has_finish_profile_pass(moves), "Should have finish profile pass"

    # Check that cleanup offset is mentioned in comment
    found_offset = False
    for move in moves:
        if move.get("kind") == "comment" and "cleanup=0.5" in move.get("text", ""):
            found_offset = True
            break
    assert found_offset, "Should mention cleanup offset in comment"


@patch('cam.path.strategies.pocket_raster')
@patch('cam.path.strategies.profile_outline')
def test_pocket_cleanup_produces_moves(mock_profile, mock_raster):
    """Test that finish pass actually produces additional moves."""
    # Mock native backend calls to return simple move lists with different lengths
    mock_raster.return_value = [
        {"kind": "comment", "text": "raster"},
        {"kind": "cut", "x": 10, "y": 10}
    ]
    mock_profile.return_value = [
        {"kind": "comment", "text": "profile"},
        {"kind": "cut", "x": 20, "y": 20},
        {"kind": "cut", "x": 30, "y": 30}
    ]

    # Create a simple rectangular pocket
    shape = rectangle(100, 100)
    shape = place(shape, Transform2D(tx=50, ty=50))

    # Create setup
    setup = _create_test_setup()

    # Generate moves with finish enabled
    moves_with_finish = pocket_then_finish_profile(
        shape,
        setup,
        total_depth_mm=10.0,
        finish_perimeter=True,
    )

    # Reset mocks
    mock_raster.reset_mock()
    mock_profile.reset_mock()

    # Generate moves without finish
    moves_without_finish = pocket_then_finish_profile(
        shape,
        setup,
        total_depth_mm=10.0,
        finish_perimeter=False,
    )

    # With finish should produce more moves than without
    assert len(moves_with_finish) > len(moves_without_finish), \
        f"Finish pass should add moves: {len(moves_with_finish)} vs {len(moves_without_finish)}"


if __name__ == "__main__":
    # Run tests
    test_pocket_cleanup_enabled_by_default()
    print("✓ test_pocket_cleanup_enabled_by_default")

    test_pocket_cleanup_disabled()
    print("✓ test_pocket_cleanup_disabled")

    test_pocket_cleanup_with_custom_offset()
    print("✓ test_pocket_cleanup_with_custom_offset")

    test_pocket_cleanup_produces_moves()
    print("✓ test_pocket_cleanup_produces_moves")

    print("\nAll pocket cleanup tests passed!")
