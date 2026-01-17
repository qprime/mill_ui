# validation/metrics/stl_metrics.py - STL metric extraction
#
# Extracts deterministic metrics from STL mesh files.
# Uses trimesh for mesh analysis.
#
# See docs/cam_validation_plan.md for schema specification.

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from validation.core import round_metric


@dataclass
class MeshMetrics:
    """Core mesh topology metrics."""

    vertex_count: int = 0
    face_count: int = 0
    is_watertight: bool = False
    is_manifold: bool = False
    is_volume: bool = False
    euler_number: int = 0
    connected_components: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "vertex_count": self.vertex_count,
            "face_count": self.face_count,
            "is_watertight": self.is_watertight,
            "is_manifold": self.is_manifold,
            "is_volume": self.is_volume,
            "euler_number": self.euler_number,
            "connected_components": self.connected_components,
        }


@dataclass
class BoundsMetrics:
    """3D bounding box metrics."""

    x_min: float = 0.0
    x_max: float = 0.0
    y_min: float = 0.0
    y_max: float = 0.0
    z_min: float = 0.0
    z_max: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "x_min": round_metric(self.x_min),
            "x_max": round_metric(self.x_max),
            "y_min": round_metric(self.y_min),
            "y_max": round_metric(self.y_max),
            "z_min": round_metric(self.z_min),
            "z_max": round_metric(self.z_max),
        }


@dataclass
class DimensionMetrics:
    """Overall dimensions of the mesh."""

    width_mm: float = 0.0
    height_mm: float = 0.0
    thickness_mm: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "width_mm": round_metric(self.width_mm),
            "height_mm": round_metric(self.height_mm),
            "thickness_mm": round_metric(self.thickness_mm),
        }


@dataclass
class ZStatistics:
    """Statistics about Z (depth) levels in the mesh."""

    unique_z_levels: list[float] = field(default_factory=list)
    z_level_count: int = 0
    min_z: float = 0.0
    max_z: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "unique_z_levels": [round_metric(z) for z in self.unique_z_levels],
            "z_level_count": self.z_level_count,
            "min_z": round_metric(self.min_z),
            "max_z": round_metric(self.max_z),
        }


@dataclass
class HeightmapMetrics:
    """Metrics for optional heightmap representation."""

    resolution_mm: float = 0.0
    grid_size: tuple[int, int] = (0, 0)
    checksum: str = ""
    min_height: float = 0.0
    max_height: float = 0.0
    mean_height: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "resolution_mm": round_metric(self.resolution_mm),
            "grid_size": list(self.grid_size),
            "checksum": self.checksum,
            "min_height": round_metric(self.min_height),
            "max_height": round_metric(self.max_height),
            "mean_height": round_metric(self.mean_height),
        }


@dataclass
class STLMetrics:
    """Complete metrics for an STL file."""

    version: str = "1.0.0"
    extraction_time_ms: float = 0.0
    mesh: MeshMetrics = field(default_factory=MeshMetrics)
    bounds: BoundsMetrics = field(default_factory=BoundsMetrics)
    dimensions: DimensionMetrics = field(default_factory=DimensionMetrics)
    volume_mm3: float = 0.0
    surface_area_mm2: float = 0.0
    z_statistics: ZStatistics = field(default_factory=ZStatistics)
    heightmap: HeightmapMetrics | None = None

    def to_dict(self) -> dict[str, Any]:
        result = {
            "stl": {
                "version": self.version,
                "extraction_time_ms": round_metric(self.extraction_time_ms),
                "mesh": self.mesh.to_dict(),
                "bounds": self.bounds.to_dict(),
                "dimensions": self.dimensions.to_dict(),
                "volume_mm3": round_metric(self.volume_mm3),
                "surface_area_mm2": round_metric(self.surface_area_mm2),
                "z_statistics": self.z_statistics.to_dict(),
            }
        }
        if self.heightmap is not None:
            result["stl"]["heightmap"] = self.heightmap.to_dict()
        return result


def extract_stl_metrics(
    stl_path: str | Path,
    generate_heightmap: bool = False,
    heightmap_resolution_mm: float = 1.0,
) -> STLMetrics:
    """Extract metrics from an STL file.

    Args:
        stl_path: Path to the STL file (binary or ASCII)
        generate_heightmap: Whether to generate a heightmap for comparison
        heightmap_resolution_mm: Resolution of the heightmap grid

    Returns:
        STLMetrics object with all extracted metrics

    Raises:
        ValueError: If the file is not a valid STL
        FileNotFoundError: If the file doesn't exist
    """
    import trimesh

    start_time = time.perf_counter()

    stl_path = Path(stl_path)
    if not stl_path.exists():
        raise FileNotFoundError(f"STL file not found: {stl_path}")

    # Load the mesh
    try:
        mesh = trimesh.load(str(stl_path))
    except Exception as e:
        raise ValueError(f"Invalid STL file: {e}") from e

    # Handle case where trimesh returns a Scene instead of Trimesh
    if hasattr(mesh, "geometry"):
        # It's a Scene, concatenate all meshes
        meshes = list(mesh.geometry.values())
        if not meshes:
            raise ValueError("STL file contains no geometry")
        mesh = trimesh.util.concatenate(meshes)

    if not isinstance(mesh, trimesh.Trimesh):
        raise ValueError(f"Unexpected mesh type: {type(mesh)}")

    # Extract mesh topology metrics
    mesh_metrics = _extract_mesh_metrics(mesh)

    # Extract bounds
    bounds_metrics = _extract_bounds_metrics(mesh)

    # Extract dimensions
    dim_metrics = _extract_dimension_metrics(mesh)

    # Extract Z statistics
    z_stats = _extract_z_statistics(mesh)

    # Calculate volume and surface area
    # Always report abs(volume) for regression detection; use is_volume to qualify validity
    volume = abs(mesh.volume)
    surface_area = mesh.area

    # Generate heightmap if requested
    heightmap_metrics = None
    if generate_heightmap:
        heightmap_metrics = _generate_heightmap_metrics(
            mesh, heightmap_resolution_mm
        )

    end_time = time.perf_counter()
    extraction_time_ms = (end_time - start_time) * 1000

    return STLMetrics(
        extraction_time_ms=extraction_time_ms,
        mesh=mesh_metrics,
        bounds=bounds_metrics,
        dimensions=dim_metrics,
        volume_mm3=volume,
        surface_area_mm2=surface_area,
        z_statistics=z_stats,
        heightmap=heightmap_metrics,
    )


def extract_stl_metrics_from_content(
    stl_content: bytes,
    generate_heightmap: bool = False,
    heightmap_resolution_mm: float = 1.0,
) -> STLMetrics:
    """Extract metrics from STL content bytes.

    Args:
        stl_content: STL file content as bytes (binary or ASCII)
        generate_heightmap: Whether to generate a heightmap for comparison
        heightmap_resolution_mm: Resolution of the heightmap grid

    Returns:
        STLMetrics object with all extracted metrics

    Raises:
        ValueError: If the content is not valid STL
    """
    import io
    import trimesh

    start_time = time.perf_counter()

    if not stl_content:
        raise ValueError("STL content is empty")

    # Load the mesh from bytes
    try:
        # trimesh.load expects a file-like object with file_type hint
        mesh = trimesh.load(io.BytesIO(stl_content), file_type="stl")
    except Exception as e:
        raise ValueError(f"Invalid STL content: {e}") from e

    # Handle case where trimesh returns a Scene instead of Trimesh
    if hasattr(mesh, "geometry"):
        # It's a Scene, concatenate all meshes
        meshes = list(mesh.geometry.values())
        if not meshes:
            raise ValueError("STL content contains no geometry")
        mesh = trimesh.util.concatenate(meshes)

    if not isinstance(mesh, trimesh.Trimesh):
        raise ValueError(f"Unexpected mesh type: {type(mesh)}")

    # Extract mesh topology metrics
    mesh_metrics = _extract_mesh_metrics(mesh)

    # Extract bounds
    bounds_metrics = _extract_bounds_metrics(mesh)

    # Extract dimensions
    dim_metrics = _extract_dimension_metrics(mesh)

    # Extract Z statistics
    z_stats = _extract_z_statistics(mesh)

    # Calculate volume and surface area
    volume = abs(mesh.volume)
    surface_area = mesh.area

    # Generate heightmap if requested
    heightmap_metrics = None
    if generate_heightmap:
        heightmap_metrics = _generate_heightmap_metrics(
            mesh, heightmap_resolution_mm
        )

    end_time = time.perf_counter()
    extraction_time_ms = (end_time - start_time) * 1000

    return STLMetrics(
        extraction_time_ms=extraction_time_ms,
        mesh=mesh_metrics,
        bounds=bounds_metrics,
        dimensions=dim_metrics,
        volume_mm3=volume,
        surface_area_mm2=surface_area,
        z_statistics=z_stats,
        heightmap=heightmap_metrics,
    )


# Alias for consistency with other modules
extract_stl_metrics_from_file = extract_stl_metrics


def _extract_mesh_metrics(mesh) -> MeshMetrics:
    """Extract topology metrics from a trimesh mesh."""
    import warnings

    # Count connected components
    try:
        components = mesh.split()
        component_count = len(components)
    except ImportError:
        # scipy not available for graph operations
        warnings.warn(
            "scipy not available for connected component detection; "
            "assuming single component. Install scipy for accurate results.",
            RuntimeWarning,
        )
        component_count = 1  # Assume single component

    return MeshMetrics(
        vertex_count=len(mesh.vertices),
        face_count=len(mesh.faces),
        is_watertight=mesh.is_watertight,
        is_manifold=_is_manifold(mesh),
        is_volume=mesh.is_volume,
        euler_number=mesh.euler_number,
        connected_components=component_count,
    )


def _is_manifold(mesh) -> bool:
    """Check if mesh is 2-manifold (each edge shared by exactly 2 faces).

    A manifold mesh has:
    - Each edge shared by exactly 2 faces
    - Consistent vertex neighborhoods

    Note: This is a proxy check using watertight + consistent winding.
    It may misclassify some edge cases (e.g., meshes with non-manifold
    edges that happen to be watertight). For precise manifold detection,
    edge-based analysis would be needed.
    """
    # trimesh doesn't have a direct is_manifold property
    # Use watertight + consistent winding as proxy
    try:
        return mesh.is_watertight and mesh.is_winding_consistent
    except Exception:
        return False


def _extract_bounds_metrics(mesh) -> BoundsMetrics:
    """Extract 3D bounding box from mesh."""
    bounds = mesh.bounds
    return BoundsMetrics(
        x_min=float(bounds[0][0]),
        x_max=float(bounds[1][0]),
        y_min=float(bounds[0][1]),
        y_max=float(bounds[1][1]),
        z_min=float(bounds[0][2]),
        z_max=float(bounds[1][2]),
    )


def _extract_dimension_metrics(mesh) -> DimensionMetrics:
    """Extract overall dimensions from mesh."""
    bounds = mesh.bounds
    extents = bounds[1] - bounds[0]
    return DimensionMetrics(
        width_mm=float(extents[0]),
        height_mm=float(extents[1]),
        thickness_mm=float(extents[2]),
    )


def _extract_z_statistics(mesh, tolerance: float = 0.001) -> ZStatistics:
    """Extract Z-level statistics from mesh vertices.

    Args:
        mesh: trimesh mesh object
        tolerance: Tolerance for rounding Z values (mm)

    Returns:
        ZStatistics with unique Z levels and counts
    """
    # Round Z values to avoid floating-point noise
    z_values = mesh.vertices[:, 2]
    rounded_z = np.round(z_values / tolerance) * tolerance
    unique_z = sorted(set(rounded_z))

    return ZStatistics(
        unique_z_levels=[float(z) for z in unique_z],
        z_level_count=len(unique_z),
        min_z=float(min(unique_z)) if unique_z else 0.0,
        max_z=float(max(unique_z)) if unique_z else 0.0,
    )


def _generate_heightmap_metrics(
    mesh, resolution_mm: float
) -> HeightmapMetrics:
    """Generate heightmap metrics for mesh comparison.

    Creates a 2D grid and samples the Z height at each point.
    Uses ray casting from above to find surface height.

    Args:
        mesh: trimesh mesh object
        resolution_mm: Grid cell size in mm (exact spacing between samples)

    Returns:
        HeightmapMetrics with grid statistics and checksum
    """
    bounds = mesh.bounds
    x_min, y_min = bounds[0][0], bounds[0][1]
    x_max, y_max = bounds[1][0], bounds[1][1]

    # Calculate grid dimensions
    # Use floor + 1 to ensure grid_x points with spacing = resolution_mm
    # This guarantees: actual_spacing = width / (grid_x - 1) ≈ resolution_mm
    width = x_max - x_min
    height = y_max - y_min
    grid_x = max(2, int(np.floor(width / resolution_mm)) + 1)
    grid_y = max(2, int(np.floor(height / resolution_mm)) + 1)

    # Create sample points with exact spacing
    # Using linspace with grid_x points gives spacing of width/(grid_x-1)
    x_coords = np.linspace(x_min, x_max, grid_x)
    y_coords = np.linspace(y_min, y_max, grid_y)

    # Calculate actual spacing for reporting
    actual_spacing_x = width / (grid_x - 1) if grid_x > 1 else resolution_mm
    actual_spacing_y = height / (grid_y - 1) if grid_y > 1 else resolution_mm
    actual_resolution = (actual_spacing_x + actual_spacing_y) / 2

    # Create ray origins (above the mesh)
    z_above = bounds[1][2] + 10.0
    heightmap = np.zeros((grid_y, grid_x), dtype=np.float32)

    # Sentinel value for "no intersection" (used instead of NaN for portable hashing)
    NO_INTERSECTION_SENTINEL = -1e9

    # Sample heights using ray casting
    for i, y in enumerate(y_coords):
        for j, x in enumerate(x_coords):
            origin = np.array([[x, y, z_above]])
            direction = np.array([[0, 0, -1]])
            locations, _, _ = mesh.ray.intersects_location(
                ray_origins=origin, ray_directions=direction
            )
            if len(locations) > 0:
                # Take highest intersection (surface from above)
                heightmap[i, j] = float(np.max(locations[:, 2]))
            else:
                heightmap[i, j] = NO_INTERSECTION_SENTINEL

    # Calculate statistics (excluding sentinel values)
    valid_mask = heightmap > NO_INTERSECTION_SENTINEL + 1
    valid_heights = heightmap[valid_mask]
    if len(valid_heights) > 0:
        min_height = float(np.min(valid_heights))
        max_height = float(np.max(valid_heights))
        mean_height = float(np.mean(valid_heights))
    else:
        min_height = max_height = mean_height = 0.0

    # Generate checksum from heightmap data
    # Round to microns for stability, sentinel values hash consistently
    rounded = np.round(heightmap * 1000).astype(np.int32)
    checksum = hashlib.sha256(rounded.tobytes()).hexdigest()[:16]

    return HeightmapMetrics(
        resolution_mm=actual_resolution,
        grid_size=(grid_x, grid_y),
        checksum=f"sha256:{checksum}",
        min_height=min_height,
        max_height=max_height,
        mean_height=mean_height,
    )


# Convenience function for file-based extraction
extract_stl_metrics_from_file = extract_stl_metrics
