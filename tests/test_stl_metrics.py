# tests/test_stl_metrics.py - Unit tests for STL metric extraction
#
# Tests verify:
# 1. Correct metric extraction from known STL files
# 2. Determinism (same input -> same output)
# 3. JSON serialization
# 4. Topology checks (manifold, watertight)
# 5. Edge cases and error handling

from __future__ import annotations

import json
import os
import sys

import pytest

try:
    import rtree
    RTREE_AVAILABLE = True
except ImportError:
    RTREE_AVAILABLE = False

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from validation.metrics.stl_metrics import (
    STLMetrics,
    extract_stl_metrics,
)
from validation.core import Verdict, CAMValidationResult


# Path to recipe outputs
RECIPE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "docs",
    "recipes",
)


def get_recipe_stl_path(recipe_num: int, recipe_name: str, filename: str = "example.stl") -> str:
    """Get path to a recipe's STL output."""
    return os.path.join(
        RECIPE_DIR,
        f"{recipe_num:02d}_{recipe_name}",
        "output",
        filename,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Test: Basic STL Parsing
# ─────────────────────────────────────────────────────────────────────────────


def test_extract_stl_metrics_simple_profile():
    """Test metric extraction from simple profile recipe."""
    stl_path = get_recipe_stl_path(1, "simple_profile")

    if not os.path.exists(stl_path):
        print(f"SKIP: {stl_path} not found")
        return

    metrics = extract_stl_metrics(stl_path)

    # Mesh should be valid
    assert metrics.mesh.vertex_count > 0, f"Vertices: {metrics.mesh.vertex_count}"
    assert metrics.mesh.face_count > 0, f"Faces: {metrics.mesh.face_count}"
    assert metrics.mesh.is_watertight, "Should be watertight"
    assert metrics.mesh.is_volume, "Should be a valid volume"

    # Volume should be positive
    assert metrics.volume_mm3 > 0, f"Volume: {metrics.volume_mm3}"

    # Surface area should be positive
    assert metrics.surface_area_mm2 > 0, f"Surface area: {metrics.surface_area_mm2}"

    # Z levels should include 0 (bottom) and sheet thickness
    assert 0.0 in metrics.z_statistics.unique_z_levels, "Should have Z=0"
    assert metrics.z_statistics.max_z > 0, "Should have positive Z max"

    print("PASS: test_extract_stl_metrics_simple_profile")


def test_extract_stl_metrics_with_pocket():
    """Test metric extraction from shaker door (has pocket)."""
    stl_path = get_recipe_stl_path(3, "shaker_door_template")

    if not os.path.exists(stl_path):
        print(f"SKIP: {stl_path} not found")
        return

    metrics = extract_stl_metrics(stl_path)

    # Should be valid mesh
    assert metrics.mesh.is_watertight
    assert metrics.mesh.is_volume

    # Shaker door has pocket, so should have intermediate Z level
    # (0 = bottom, pocket_depth, sheet_thickness)
    assert metrics.z_statistics.z_level_count >= 2, f"Z levels: {metrics.z_statistics.unique_z_levels}"

    # Dimensions should match expected (400x600mm door in recipe 03)
    assert metrics.dimensions.width_mm > 300, f"Width: {metrics.dimensions.width_mm}"
    assert metrics.dimensions.height_mm > 500, f"Height: {metrics.dimensions.height_mm}"

    print("PASS: test_extract_stl_metrics_with_pocket")


def test_extract_stl_metrics_multiple_depths():
    """Test STL with multiple pocket depths."""
    stl_path = get_recipe_stl_path(6, "multiple_depths")

    if not os.path.exists(stl_path):
        print(f"SKIP: {stl_path} not found")
        return

    metrics = extract_stl_metrics(stl_path)

    # Should have multiple Z levels for different depths
    assert metrics.z_statistics.z_level_count >= 2, f"Z levels: {metrics.z_statistics.unique_z_levels}"

    print("PASS: test_extract_stl_metrics_multiple_depths")


# ─────────────────────────────────────────────────────────────────────────────
# Test: Determinism
# ─────────────────────────────────────────────────────────────────────────────


def test_stl_metrics_deterministic():
    """Verify same input produces identical metrics."""
    stl_path = get_recipe_stl_path(1, "simple_profile")

    if not os.path.exists(stl_path):
        print(f"SKIP: {stl_path} not found")
        return

    # Extract twice
    metrics1 = extract_stl_metrics(stl_path)
    metrics2 = extract_stl_metrics(stl_path)

    # Convert to dict (excluding timing)
    dict1 = metrics1.to_dict()
    dict2 = metrics2.to_dict()

    # Remove extraction time (will differ)
    dict1["stl"]["extraction_time_ms"] = 0
    dict2["stl"]["extraction_time_ms"] = 0

    # Compare
    assert dict1 == dict2, "Metrics should be deterministic"

    print("PASS: test_stl_metrics_deterministic")


# ─────────────────────────────────────────────────────────────────────────────
# Test: JSON Serialization
# ─────────────────────────────────────────────────────────────────────────────


def test_stl_metrics_json_serializable():
    """Verify metrics can be serialized to JSON."""
    stl_path = get_recipe_stl_path(1, "simple_profile")

    if not os.path.exists(stl_path):
        print(f"SKIP: {stl_path} not found")
        return

    metrics = extract_stl_metrics(stl_path)
    metrics_dict = metrics.to_dict()

    # Should serialize without error
    json_str = json.dumps(metrics_dict, indent=2)
    assert len(json_str) > 0

    # Should deserialize back
    parsed = json.loads(json_str)
    assert "stl" in parsed
    assert "mesh" in parsed["stl"]
    assert "bounds" in parsed["stl"]
    assert "dimensions" in parsed["stl"]
    assert "z_statistics" in parsed["stl"]

    print("PASS: test_stl_metrics_json_serializable")


def test_stl_metrics_schema_compliance():
    """Verify output matches expected schema structure."""
    stl_path = get_recipe_stl_path(3, "shaker_door_template")

    if not os.path.exists(stl_path):
        print(f"SKIP: {stl_path} not found")
        return

    metrics = extract_stl_metrics(stl_path)
    d = metrics.to_dict()

    # Top level
    assert "stl" in d
    stl = d["stl"]

    # Required fields
    assert "version" in stl
    assert "extraction_time_ms" in stl
    assert "mesh" in stl
    assert "bounds" in stl
    assert "dimensions" in stl
    assert "volume_mm3" in stl
    assert "surface_area_mm2" in stl
    assert "z_statistics" in stl

    # Mesh fields
    mesh = stl["mesh"]
    assert "vertex_count" in mesh
    assert "face_count" in mesh
    assert "is_watertight" in mesh
    assert "is_manifold" in mesh
    assert "is_volume" in mesh
    assert "euler_number" in mesh
    assert "connected_components" in mesh

    # Bounds fields
    bounds = stl["bounds"]
    assert "x_min" in bounds
    assert "x_max" in bounds
    assert "y_min" in bounds
    assert "y_max" in bounds
    assert "z_min" in bounds
    assert "z_max" in bounds

    # Dimensions fields
    dims = stl["dimensions"]
    assert "width_mm" in dims
    assert "height_mm" in dims
    assert "thickness_mm" in dims

    # Z statistics fields
    z_stats = stl["z_statistics"]
    assert "unique_z_levels" in z_stats
    assert "z_level_count" in z_stats
    assert "min_z" in z_stats
    assert "max_z" in z_stats

    print("PASS: test_stl_metrics_schema_compliance")


# ─────────────────────────────────────────────────────────────────────────────
# Test: Topology Checks
# ─────────────────────────────────────────────────────────────────────────────


def test_stl_metrics_watertight():
    """Test that recipe STLs are watertight."""
    stl_path = get_recipe_stl_path(1, "simple_profile")

    if not os.path.exists(stl_path):
        print(f"SKIP: {stl_path} not found")
        return

    metrics = extract_stl_metrics(stl_path)
    assert metrics.mesh.is_watertight, "Recipe STLs should be watertight"
    assert metrics.mesh.euler_number == 2, f"Euler number should be 2 for closed surface, got {metrics.mesh.euler_number}"

    print("PASS: test_stl_metrics_watertight")


def test_stl_metrics_single_component():
    """Test that simple recipes have single connected component."""
    stl_path = get_recipe_stl_path(1, "simple_profile")

    if not os.path.exists(stl_path):
        print(f"SKIP: {stl_path} not found")
        return

    metrics = extract_stl_metrics(stl_path)
    assert metrics.mesh.connected_components == 1, f"Should be single component, got {metrics.mesh.connected_components}"

    print("PASS: test_stl_metrics_single_component")


# ─────────────────────────────────────────────────────────────────────────────
# Test: Heightmap Generation
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.skipif(not RTREE_AVAILABLE, reason="rtree package not installed")
def test_stl_metrics_heightmap():
    """Test heightmap generation."""
    stl_path = get_recipe_stl_path(1, "simple_profile")

    if not os.path.exists(stl_path):
        print(f"SKIP: {stl_path} not found")
        return

    metrics = extract_stl_metrics(stl_path, generate_heightmap=True, heightmap_resolution_mm=5.0)

    assert metrics.heightmap is not None, "Heightmap should be generated"
    assert metrics.heightmap.grid_size[0] > 0
    assert metrics.heightmap.grid_size[1] > 0
    assert metrics.heightmap.checksum.startswith("sha256:")
    assert metrics.heightmap.max_height >= metrics.heightmap.min_height

    print("PASS: test_stl_metrics_heightmap")


@pytest.mark.skipif(not RTREE_AVAILABLE, reason="rtree package not installed")
def test_stl_metrics_heightmap_deterministic():
    """Verify heightmap checksum is deterministic."""
    stl_path = get_recipe_stl_path(1, "simple_profile")

    if not os.path.exists(stl_path):
        print(f"SKIP: {stl_path} not found")
        return

    metrics1 = extract_stl_metrics(stl_path, generate_heightmap=True, heightmap_resolution_mm=5.0)
    metrics2 = extract_stl_metrics(stl_path, generate_heightmap=True, heightmap_resolution_mm=5.0)

    assert metrics1.heightmap.checksum == metrics2.heightmap.checksum, "Heightmap checksum should be deterministic"

    print("PASS: test_stl_metrics_heightmap_deterministic")


# ─────────────────────────────────────────────────────────────────────────────
# Test: Edge Cases
# ─────────────────────────────────────────────────────────────────────────────


def test_stl_metrics_invalid_file():
    """Test error handling for invalid STL."""
    try:
        extract_stl_metrics("/nonexistent/file.stl")
        assert False, "Should have raised FileNotFoundError"
    except FileNotFoundError:
        pass

    print("PASS: test_stl_metrics_invalid_file")


def test_stl_metrics_z_bounds_positive():
    """Test that Z bounds are non-negative (no cuts below sheet)."""
    stl_path = get_recipe_stl_path(1, "simple_profile")

    if not os.path.exists(stl_path):
        print(f"SKIP: {stl_path} not found")
        return

    metrics = extract_stl_metrics(stl_path)
    assert metrics.bounds.z_min >= 0, f"Z min should be >= 0, got {metrics.bounds.z_min}"

    print("PASS: test_stl_metrics_z_bounds_positive")


# ─────────────────────────────────────────────────────────────────────────────
# Test: All Recipes (Smoke Test)
# ─────────────────────────────────────────────────────────────────────────────


def test_stl_metrics_all_recipes():
    """Smoke test: extract metrics from all recipe STLs without error."""
    recipes = [
        (1, "simple_profile", "example.stl"),
        (2, "pocket_with_cleanup", "example.stl"),
        (3, "shaker_door_template", "example.stl"),
        (4, "custom_template", "example.stl"),
        (5, "validation_workflow", "example.stl"),
        (6, "multiple_depths", "example.stl"),
        (7, "json_generation", "example.stl"),
        (8, "svg_visualization", "example.stl"),
        (9, "config_tuning", "example.stl"),
        # Recipe 10 (hole_patterns_grid) doesn't have STL output
        (11, "keepout_islands", "example.stl"),
        (12, "edge_treatment_intent", "example.stl"),
        (13, "split_layout_french_door", "example.stl"),
        (14, "corner_cleanup_multi_tool", "example.stl"),
        (15, "profile_with_tabs", "simple_cutout_with_tabs.stl"),
        (16, "sheet_layout_nesting", "example.stl"),
    ]

    passed = 0
    skipped = 0
    failed = 0

    for num, name, filename in recipes:
        stl_path = get_recipe_stl_path(num, name, filename)
        if not os.path.exists(stl_path):
            skipped += 1
            continue

        try:
            metrics = extract_stl_metrics(stl_path)
            # Basic sanity checks
            assert metrics.mesh.vertex_count > 0
            assert metrics.mesh.face_count > 0
            assert metrics.volume_mm3 > 0
            assert metrics.mesh.is_watertight
            passed += 1
        except Exception as e:
            print(f"FAIL: Recipe {num:02d}_{name}: {e}")
            failed += 1

    print(f"PASS: test_stl_metrics_all_recipes ({passed} passed, {skipped} skipped, {failed} failed)")
    assert failed == 0, f"{failed} recipes failed"


# ─────────────────────────────────────────────────────────────────────────────
# Test: Core Types Integration
# ─────────────────────────────────────────────────────────────────────────────


def test_cam_validation_result_with_stl_metrics():
    """Test integration of STL metrics into CAMValidationResult."""
    stl_path = get_recipe_stl_path(1, "simple_profile")

    if not os.path.exists(stl_path):
        print(f"SKIP: {stl_path} not found")
        return

    metrics = extract_stl_metrics(stl_path)

    # Create validation result with metrics
    result = CAMValidationResult(input_file="simple_profile.pml")
    result.metrics["stl"] = metrics.to_dict()["stl"]

    # Should serialize
    json_str = result.to_json()
    assert len(json_str) > 0

    # Parse and verify
    parsed = json.loads(json_str)
    assert "validation_result" in parsed
    assert "metrics" in parsed["validation_result"]
    assert "stl" in parsed["validation_result"]["metrics"]

    print("PASS: test_cam_validation_result_with_stl_metrics")


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────


def run_tests():
    """Run all tests."""
    print("=" * 60)
    print("STL Metrics Tests")
    print("=" * 60)

    tests = [
        test_extract_stl_metrics_simple_profile,
        test_extract_stl_metrics_with_pocket,
        test_extract_stl_metrics_multiple_depths,
        test_stl_metrics_deterministic,
        test_stl_metrics_json_serializable,
        test_stl_metrics_schema_compliance,
        test_stl_metrics_watertight,
        test_stl_metrics_single_component,
        test_stl_metrics_heightmap,
        test_stl_metrics_heightmap_deterministic,
        test_stl_metrics_invalid_file,
        test_stl_metrics_z_bounds_positive,
        test_stl_metrics_all_recipes,
        test_cam_validation_result_with_stl_metrics,
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
            print(f"ERROR: {test.__name__}: {e}")
            failed += 1

    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
