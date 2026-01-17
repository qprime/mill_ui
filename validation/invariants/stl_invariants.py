# validation/invariants/stl_invariants.py - STL invariant checking
#
# Validates structural and topological invariants for STL mesh files.
# Uses trimesh for mesh analysis.
#
# See docs/cam_validation_plan.md for invariant definitions.

from __future__ import annotations

from pathlib import Path
from typing import Any

from validation.core import InvariantResult, Verdict
from validation.metrics.stl_metrics import STLMetrics, extract_stl_metrics


# All STL invariant IDs
STL_INVARIANT_IDS = [
    "STL_VALID_FILE",  # Renamed from STL_VALID_BINARY (accepts binary and ASCII STL)
    "STL_POSITIVE_VOLUME",
    "STL_IS_MANIFOLD",
    "STL_IS_WATERTIGHT",
    "STL_CONSISTENT_NORMALS",
    "STL_NO_DEGENERATE_FACES",
    "STL_BOUNDS_POSITIVE",
    "STL_Z_WITHIN_SHEET",
    "STL_CONNECTED",
]


def check_stl_invariants(
    stl_path: str | Path,
    metrics: STLMetrics | None = None,
    sheet_thickness_mm: float | None = None,
    expected_components: int = 1,
) -> list[InvariantResult]:
    """Check all STL invariants for a given STL file.

    Args:
        stl_path: Path to the STL file
        metrics: Pre-computed STLMetrics (extracted if not provided)
        sheet_thickness_mm: Expected sheet thickness for Z bounds check.
                           If None, uses max_z from the mesh as the reference.
        expected_components: Expected number of connected components (default 1)

    Returns:
        List of InvariantResult objects, one per invariant
    """
    results = []
    stl_path = Path(stl_path)

    # First check if file is valid - this gates all other checks
    valid_result, mesh = _check_valid_file(stl_path)
    results.append(valid_result)

    if valid_result.status == Verdict.FAIL:
        # Can't check other invariants if file is invalid
        # Use WARN with skipped=True so they don't count as failures in summary stats
        for inv_id in STL_INVARIANT_IDS[1:]:
            results.append(
                InvariantResult(
                    id=inv_id,
                    category="structural",
                    artifact="stl",
                    description=_get_description(inv_id),
                    status=Verdict.WARN,
                    details={"skipped": True, "reason": "Invalid STL file"},
                )
            )
        return results

    # Extract metrics if not provided
    if metrics is None:
        metrics = extract_stl_metrics(stl_path)

    # Check all other invariants
    results.append(_check_positive_volume(metrics))
    results.append(_check_is_manifold(metrics, mesh))
    results.append(_check_is_watertight(metrics))
    results.append(_check_consistent_normals(mesh))
    results.append(_check_no_degenerate_faces(mesh))
    results.append(_check_bounds_positive(metrics))
    results.append(_check_z_within_sheet(metrics, sheet_thickness_mm))
    results.append(_check_connected(metrics, expected_components))

    return results


def check_stl_invariants_from_content(
    stl_content: bytes,
    metrics: STLMetrics | None = None,
    sheet_thickness_mm: float | None = None,
    expected_components: int = 1,
) -> list[InvariantResult]:
    """Check all STL invariants for given STL content.

    Args:
        stl_content: STL content as bytes (binary or ASCII)
        metrics: Pre-computed STLMetrics (extracted if not provided)
        sheet_thickness_mm: Expected sheet thickness for Z bounds check.
                           If None, uses max_z from the mesh as the reference.
        expected_components: Expected number of connected components (default 1)

    Returns:
        List of InvariantResult objects, one per invariant
    """
    results = []

    # First check if content is valid - this gates all other checks
    valid_result, mesh = _check_valid_content(stl_content)
    results.append(valid_result)

    if valid_result.status == Verdict.FAIL:
        # Can't check other invariants if content is invalid
        for inv_id in STL_INVARIANT_IDS[1:]:
            results.append(
                InvariantResult(
                    id=inv_id,
                    category="structural",
                    artifact="stl",
                    description=_get_description(inv_id),
                    status=Verdict.WARN,
                    details={"skipped": True, "reason": "Invalid STL content"},
                )
            )
        return results

    # Extract metrics if not provided
    if metrics is None:
        from validation.metrics.stl_metrics import extract_stl_metrics_from_content
        metrics = extract_stl_metrics_from_content(stl_content)

    # Check all other invariants
    results.append(_check_positive_volume(metrics))
    results.append(_check_is_manifold(metrics, mesh))
    results.append(_check_is_watertight(metrics))
    results.append(_check_consistent_normals(mesh))
    results.append(_check_no_degenerate_faces(mesh))
    results.append(_check_bounds_positive(metrics))
    results.append(_check_z_within_sheet(metrics, sheet_thickness_mm))
    results.append(_check_connected(metrics, expected_components))

    return results


def _get_description(inv_id: str) -> str:
    """Get description for an invariant ID."""
    descriptions = {
        "STL_VALID_FILE": "File is valid STL (binary or ASCII)",
        "STL_POSITIVE_VOLUME": "Mesh volume > 0",
        "STL_IS_MANIFOLD": "Mesh is 2-manifold (each edge shared by exactly 2 faces)",
        "STL_IS_WATERTIGHT": "Mesh has no holes (closed surface)",
        "STL_CONSISTENT_NORMALS": "Face normals point outward consistently",
        "STL_NO_DEGENERATE_FACES": "No zero-area triangles",
        "STL_BOUNDS_POSITIVE": "All bounds dimensions > 0",
        "STL_Z_WITHIN_SHEET": "All Z values within [0, sheet_thickness]",
        "STL_CONNECTED": "Single connected component (or expected count)",
    }
    return descriptions.get(inv_id, "Unknown invariant")


def _check_valid_file(stl_path: Path) -> tuple[InvariantResult, Any]:
    """Check if file is a valid STL (binary or ASCII).

    Returns:
        Tuple of (InvariantResult, mesh object or None)
    """
    import trimesh

    try:
        mesh = trimesh.load(str(stl_path))

        # Handle case where trimesh returns a Scene instead of Trimesh
        if hasattr(mesh, "geometry"):
            meshes = list(mesh.geometry.values())
            if not meshes:
                return (
                    InvariantResult(
                        id="STL_VALID_FILE",
                        category="structural",
                        artifact="stl",
                        description=_get_description("STL_VALID_FILE"),
                        status=Verdict.FAIL,
                        details={
                            "error": "STL file contains no geometry",
                            "file": str(stl_path),
                        },
                    ),
                    None,
                )
            mesh = trimesh.util.concatenate(meshes)

        if not isinstance(mesh, trimesh.Trimesh):
            return (
                InvariantResult(
                    id="STL_VALID_FILE",
                    category="structural",
                    artifact="stl",
                    description=_get_description("STL_VALID_FILE"),
                    status=Verdict.FAIL,
                    details={
                        "error": f"Unexpected mesh type: {type(mesh).__name__}",
                        "file": str(stl_path),
                    },
                ),
                None,
            )

        # Check for minimum mesh requirements
        if len(mesh.vertices) < 3 or len(mesh.faces) < 1:
            return (
                InvariantResult(
                    id="STL_VALID_FILE",
                    category="structural",
                    artifact="stl",
                    description=_get_description("STL_VALID_FILE"),
                    status=Verdict.FAIL,
                    details={
                        "error": "Mesh has insufficient geometry",
                        "vertex_count": len(mesh.vertices),
                        "face_count": len(mesh.faces),
                        "file": str(stl_path),
                    },
                ),
                None,
            )

        return (
            InvariantResult(
                id="STL_VALID_FILE",
                category="structural",
                artifact="stl",
                description=_get_description("STL_VALID_FILE"),
                status=Verdict.PASS,
                details={
                    "vertex_count": len(mesh.vertices),
                    "face_count": len(mesh.faces),
                    "file": str(stl_path),
                },
            ),
            mesh,
        )

    except FileNotFoundError:
        return (
            InvariantResult(
                id="STL_VALID_FILE",
                category="structural",
                artifact="stl",
                description=_get_description("STL_VALID_FILE"),
                status=Verdict.FAIL,
                details={
                    "error": "File not found",
                    "file": str(stl_path),
                },
            ),
            None,
        )
    except Exception as e:
        return (
            InvariantResult(
                id="STL_VALID_FILE",
                category="structural",
                artifact="stl",
                description=_get_description("STL_VALID_FILE"),
                status=Verdict.FAIL,
                details={
                    "error": f"Failed to parse STL: {e}",
                    "file": str(stl_path),
                },
            ),
            None,
        )


def _check_valid_content(stl_content: bytes) -> tuple[InvariantResult, Any]:
    """Check if content is valid STL (binary or ASCII).

    Returns:
        Tuple of (InvariantResult, mesh object or None)
    """
    import io
    import trimesh

    try:
        if not stl_content:
            return (
                InvariantResult(
                    id="STL_VALID_FILE",
                    category="structural",
                    artifact="stl",
                    description=_get_description("STL_VALID_FILE"),
                    status=Verdict.FAIL,
                    details={"error": "STL content is empty"},
                ),
                None,
            )

        mesh = trimesh.load(io.BytesIO(stl_content), file_type="stl")

        # Handle case where trimesh returns a Scene instead of Trimesh
        if hasattr(mesh, "geometry"):
            meshes = list(mesh.geometry.values())
            if not meshes:
                return (
                    InvariantResult(
                        id="STL_VALID_FILE",
                        category="structural",
                        artifact="stl",
                        description=_get_description("STL_VALID_FILE"),
                        status=Verdict.FAIL,
                        details={"error": "STL content contains no geometry"},
                    ),
                    None,
                )
            mesh = trimesh.util.concatenate(meshes)

        if not isinstance(mesh, trimesh.Trimesh):
            return (
                InvariantResult(
                    id="STL_VALID_FILE",
                    category="structural",
                    artifact="stl",
                    description=_get_description("STL_VALID_FILE"),
                    status=Verdict.FAIL,
                    details={"error": f"Unexpected mesh type: {type(mesh).__name__}"},
                ),
                None,
            )

        # Check for minimum mesh requirements
        if len(mesh.vertices) < 3 or len(mesh.faces) < 1:
            return (
                InvariantResult(
                    id="STL_VALID_FILE",
                    category="structural",
                    artifact="stl",
                    description=_get_description("STL_VALID_FILE"),
                    status=Verdict.FAIL,
                    details={
                        "error": "Mesh has insufficient geometry",
                        "vertex_count": len(mesh.vertices),
                        "face_count": len(mesh.faces),
                    },
                ),
                None,
            )

        return (
            InvariantResult(
                id="STL_VALID_FILE",
                category="structural",
                artifact="stl",
                description=_get_description("STL_VALID_FILE"),
                status=Verdict.PASS,
                details={
                    "vertex_count": len(mesh.vertices),
                    "face_count": len(mesh.faces),
                },
            ),
            mesh,
        )

    except Exception as e:
        return (
            InvariantResult(
                id="STL_VALID_FILE",
                category="structural",
                artifact="stl",
                description=_get_description("STL_VALID_FILE"),
                status=Verdict.FAIL,
                details={"error": f"Failed to parse STL content: {e}"},
            ),
            None,
        )


def _check_positive_volume(metrics: STLMetrics) -> InvariantResult:
    """Check that mesh has positive volume."""
    volume = metrics.volume_mm3

    if volume > 0:
        return InvariantResult(
            id="STL_POSITIVE_VOLUME",
            category="structural",
            artifact="stl",
            description=_get_description("STL_POSITIVE_VOLUME"),
            status=Verdict.PASS,
            details={"volume_mm3": volume},
        )
    else:
        return InvariantResult(
            id="STL_POSITIVE_VOLUME",
            category="structural",
            artifact="stl",
            description=_get_description("STL_POSITIVE_VOLUME"),
            status=Verdict.FAIL,
            details={
                "volume_mm3": volume,
                "message": "Mesh has zero or negative volume (degenerate mesh)",
            },
        )


def _check_is_manifold(metrics: STLMetrics, mesh: Any) -> InvariantResult:
    """Check that mesh is 2-manifold.

    A 2-manifold mesh has each edge shared by exactly 2 faces.

    Note: We compute this directly from edge adjacency rather than relying
    on metrics.mesh.is_manifold which is a proxy (watertight && winding_consistent)
    that may pass non-manifold meshes.
    """
    import numpy as np

    try:
        # Compute manifold status directly from edge adjacency
        # Each edge in a 2-manifold mesh is shared by exactly 2 faces
        if hasattr(mesh, "edges_unique_inverse"):
            edge_counts = np.bincount(mesh.edges_unique_inverse)
            non_manifold_edge_count = int(np.sum(edge_counts != 2))
            is_manifold = non_manifold_edge_count == 0
        else:
            # Fallback to proxy if edges_unique_inverse not available
            is_manifold = mesh.is_watertight and mesh.is_winding_consistent
            non_manifold_edge_count = None

        if is_manifold:
            details: dict[str, Any] = {"is_manifold": True}
            if non_manifold_edge_count is not None:
                details["non_manifold_edge_count"] = 0
            return InvariantResult(
                id="STL_IS_MANIFOLD",
                category="topology",
                artifact="stl",
                description=_get_description("STL_IS_MANIFOLD"),
                status=Verdict.PASS,
                details=details,
            )
        else:
            details = {"is_manifold": False}
            if non_manifold_edge_count is not None:
                details["non_manifold_edge_count"] = non_manifold_edge_count
            details["message"] = "Mesh has non-manifold edges (edges not shared by exactly 2 faces)"

            return InvariantResult(
                id="STL_IS_MANIFOLD",
                category="topology",
                artifact="stl",
                description=_get_description("STL_IS_MANIFOLD"),
                status=Verdict.FAIL,
                details=details,
            )

    except Exception as e:
        # If we can't compute edge adjacency, fall back to proxy with warning
        is_manifold = metrics.mesh.is_manifold

        return InvariantResult(
            id="STL_IS_MANIFOLD",
            category="topology",
            artifact="stl",
            description=_get_description("STL_IS_MANIFOLD"),
            status=Verdict.PASS if is_manifold else Verdict.FAIL,
            details={
                "is_manifold": is_manifold,
                "note": f"Used proxy check (watertight && winding_consistent): {e}",
            },
        )


def _check_is_watertight(metrics: STLMetrics) -> InvariantResult:
    """Check that mesh is watertight (closed surface with no holes)."""
    is_watertight = metrics.mesh.is_watertight

    if is_watertight:
        return InvariantResult(
            id="STL_IS_WATERTIGHT",
            category="topology",
            artifact="stl",
            description=_get_description("STL_IS_WATERTIGHT"),
            status=Verdict.PASS,
            details={"is_watertight": True},
        )
    else:
        return InvariantResult(
            id="STL_IS_WATERTIGHT",
            category="topology",
            artifact="stl",
            description=_get_description("STL_IS_WATERTIGHT"),
            status=Verdict.FAIL,
            details={
                "is_watertight": False,
                "message": "Mesh has holes or open edges",
            },
        )


def _check_consistent_normals(mesh: Any) -> InvariantResult:
    """Check that face normals are consistent (all point outward).

    Uses trimesh's is_winding_consistent property which checks if all
    face normals point in a consistent direction.
    """
    try:
        is_consistent = mesh.is_winding_consistent
    except Exception:
        is_consistent = False

    if is_consistent:
        return InvariantResult(
            id="STL_CONSISTENT_NORMALS",
            category="topology",
            artifact="stl",
            description=_get_description("STL_CONSISTENT_NORMALS"),
            status=Verdict.PASS,
            details={"is_winding_consistent": True},
        )
    else:
        return InvariantResult(
            id="STL_CONSISTENT_NORMALS",
            category="topology",
            artifact="stl",
            description=_get_description("STL_CONSISTENT_NORMALS"),
            status=Verdict.FAIL,
            details={
                "is_winding_consistent": False,
                "message": "Face normals are not consistently oriented",
            },
        )


def _check_no_degenerate_faces(mesh: Any) -> InvariantResult:
    """Check that mesh has no degenerate (zero-area) triangles."""
    import numpy as np

    try:
        # Get face areas
        areas = mesh.area_faces

        # Find degenerate faces (area essentially zero)
        tolerance = 1e-10  # mm² - extremely small area threshold
        degenerate_mask = areas < tolerance
        degenerate_count = int(np.sum(degenerate_mask))

        if degenerate_count == 0:
            return InvariantResult(
                id="STL_NO_DEGENERATE_FACES",
                category="structural",
                artifact="stl",
                description=_get_description("STL_NO_DEGENERATE_FACES"),
                status=Verdict.PASS,
                details={
                    "degenerate_count": 0,
                    "total_faces": len(areas),
                },
            )
        else:
            # Get indices of degenerate faces (limit to first 10)
            degenerate_indices = np.where(degenerate_mask)[0][:10].tolist()

            return InvariantResult(
                id="STL_NO_DEGENERATE_FACES",
                category="structural",
                artifact="stl",
                description=_get_description("STL_NO_DEGENERATE_FACES"),
                status=Verdict.FAIL,
                details={
                    "degenerate_count": degenerate_count,
                    "total_faces": len(areas),
                    "degenerate_face_indices": degenerate_indices,
                    "message": f"Mesh has {degenerate_count} zero-area triangles",
                },
            )

    except Exception as e:
        return InvariantResult(
            id="STL_NO_DEGENERATE_FACES",
            category="structural",
            artifact="stl",
            description=_get_description("STL_NO_DEGENERATE_FACES"),
            status=Verdict.WARN,
            details={
                "error": f"Could not check for degenerate faces: {e}",
            },
        )


def _check_bounds_positive(metrics: STLMetrics) -> InvariantResult:
    """Check that all bounding box dimensions are positive."""
    dims = metrics.dimensions
    width = dims.width_mm
    height = dims.height_mm
    thickness = dims.thickness_mm

    if width > 0 and height > 0 and thickness > 0:
        return InvariantResult(
            id="STL_BOUNDS_POSITIVE",
            category="structural",
            artifact="stl",
            description=_get_description("STL_BOUNDS_POSITIVE"),
            status=Verdict.PASS,
            details={
                "width_mm": width,
                "height_mm": height,
                "thickness_mm": thickness,
            },
        )
    else:
        issues = []
        if width <= 0:
            issues.append(f"width={width}")
        if height <= 0:
            issues.append(f"height={height}")
        if thickness <= 0:
            issues.append(f"thickness={thickness}")

        return InvariantResult(
            id="STL_BOUNDS_POSITIVE",
            category="structural",
            artifact="stl",
            description=_get_description("STL_BOUNDS_POSITIVE"),
            status=Verdict.FAIL,
            details={
                "width_mm": width,
                "height_mm": height,
                "thickness_mm": thickness,
                "issues": issues,
                "message": f"Flat or inverted bounds: {', '.join(issues)}",
            },
        )


def _check_z_within_sheet(
    metrics: STLMetrics, sheet_thickness_mm: float | None
) -> InvariantResult:
    """Check that all Z values are within [0, sheet_thickness].

    Args:
        metrics: STL metrics
        sheet_thickness_mm: Expected sheet thickness. If None, uses max_z as reference.
    """
    z_stats = metrics.z_statistics
    min_z = z_stats.min_z
    max_z = z_stats.max_z

    # Determine the expected thickness
    if sheet_thickness_mm is None:
        # Use max_z from the mesh as reference
        sheet_thickness_mm = max_z

    tolerance = 0.01  # mm tolerance for floating point comparison

    z_min_ok = min_z >= -tolerance
    z_max_ok = max_z <= sheet_thickness_mm + tolerance

    if z_min_ok and z_max_ok:
        return InvariantResult(
            id="STL_Z_WITHIN_SHEET",
            category="structural",
            artifact="stl",
            description=_get_description("STL_Z_WITHIN_SHEET"),
            status=Verdict.PASS,
            details={
                "min_z": min_z,
                "max_z": max_z,
                "sheet_thickness_mm": sheet_thickness_mm,
            },
        )
    else:
        issues = []
        if not z_min_ok:
            issues.append(f"min_z={min_z} < 0")
        if not z_max_ok:
            issues.append(f"max_z={max_z} > sheet_thickness={sheet_thickness_mm}")

        return InvariantResult(
            id="STL_Z_WITHIN_SHEET",
            category="structural",
            artifact="stl",
            description=_get_description("STL_Z_WITHIN_SHEET"),
            status=Verdict.FAIL,
            details={
                "min_z": min_z,
                "max_z": max_z,
                "sheet_thickness_mm": sheet_thickness_mm,
                "issues": issues,
                "message": f"Z values outside sheet bounds: {', '.join(issues)}",
            },
        )


def _check_connected(metrics: STLMetrics, expected_components: int) -> InvariantResult:
    """Check that mesh has expected number of connected components.

    Args:
        metrics: STL metrics
        expected_components: Expected number of connected components (default 1)
    """
    actual = metrics.mesh.connected_components

    if actual == expected_components:
        return InvariantResult(
            id="STL_CONNECTED",
            category="topology",
            artifact="stl",
            description=_get_description("STL_CONNECTED"),
            status=Verdict.PASS,
            details={
                "connected_components": actual,
                "expected": expected_components,
            },
        )
    else:
        # Determine severity - more components than expected is usually less severe
        # (might be intentional separate pieces) than fewer (mesh is broken)
        if actual > expected_components:
            verdict = Verdict.WARN
            message = f"Mesh has {actual} components, expected {expected_components}"
        else:
            verdict = Verdict.FAIL
            message = f"Mesh has only {actual} components, expected {expected_components}"

        return InvariantResult(
            id="STL_CONNECTED",
            category="topology",
            artifact="stl",
            description=_get_description("STL_CONNECTED"),
            status=verdict,
            details={
                "connected_components": actual,
                "expected": expected_components,
                "message": message,
            },
        )
