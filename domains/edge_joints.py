from __future__ import annotations

from typing import TYPE_CHECKING

from domains.domain import Domain, Point2D

if TYPE_CHECKING:
    from joints.profiles import JointProfile


def _distance(p0: Point2D, p1: Point2D) -> float:
    import math
    return math.sqrt((p1[0] - p0[0]) ** 2 + (p1[1] - p0[1]) ** 2)


def apply_edge_joint(
    domain: Domain,
    edge_index: int,
    profile: JointProfile,
) -> Domain:
    """Apply a joint profile to a specific edge of a domain.

    Replaces the straight edge with the joint geometry (e.g., finger pattern).
    The edge is identified by its 0-based index in CCW order from the first vertex.

    For a standard rectangle created with Domain.from_rectangle():
        - Edge 0: bottom (from bottom-left to bottom-right)
        - Edge 1: right (from bottom-right to top-right)
        - Edge 2: top (from top-right to top-left)
        - Edge 3: left (from top-left to bottom-left)

    Args:
        domain: The domain to modify
        edge_index: 0-based index of the edge to modify (CCW order)
        profile: The joint profile defining the edge geometry

    Returns:
        A new Domain with the specified edge replaced by joint geometry

    Raises:
        IndexError: If edge_index is out of range

    Example:
        >>> from joints.profiles import FingerJointProfile
        >>> domain = Domain.from_rectangle(100, 50)
        >>> profile = FingerJointProfile(depth_mm=6.0, count=5)
        >>> jointed = apply_edge_joint(domain, 0, profile)  # fingers on bottom
    """
    boundary = list(domain.outer_boundary)
    n_vertices = len(boundary)

    if edge_index < 0 or edge_index >= n_vertices:
        raise IndexError(
            f"edge_index {edge_index} out of range for domain with {n_vertices} vertices"
        )

    edge_start = boundary[edge_index]
    edge_end = boundary[(edge_index + 1) % n_vertices]

    joint_vertices = profile.compute_edge_geometry(edge_start, edge_end)

    if len(joint_vertices) < 2:
        return domain

    new_boundary: list[Point2D] = []

    for i in range(n_vertices):
        if i == edge_index:
            new_boundary.extend(joint_vertices)
        elif i == (edge_index + 1) % n_vertices:
            pass
        else:
            new_boundary.append(boundary[i])

    return Domain(
        outer_boundary=tuple(new_boundary),
        inner_boundaries=domain.inner_boundaries,
        local_origin=domain.local_origin,
        local_rotation_rad=domain.local_rotation_rad,
    )


def apply_edge_joints(
    domain: Domain,
    edge_joints: dict[int, JointProfile],
) -> Domain:
    """Apply multiple joint profiles to specified edges simultaneously.

    Unlike applying joints one at a time, this function computes all joint
    geometries based on the original edge positions, then assembles them
    into a single boundary. This avoids index shift issues.

    Args:
        domain: The domain to modify
        edge_joints: Mapping of edge_index -> JointProfile (based on original edges)

    Returns:
        A new Domain with all specified edges replaced by joint geometry

    Example:
        >>> from joints.profiles import FingerJointProfile
        >>> domain = Domain.from_rectangle(100, 50)
        >>> finger = FingerJointProfile(depth_mm=6.0, count=5)
        >>> jointed = apply_edge_joints(domain, {0: finger, 2: finger})
    """
    if not edge_joints:
        return domain

    boundary = list(domain.outer_boundary)
    n_vertices = len(boundary)

    for edge_index in edge_joints:
        if edge_index < 0 or edge_index >= n_vertices:
            raise IndexError(
                f"edge_index {edge_index} out of range for domain with {n_vertices} vertices"
            )

    joint_geometries: dict[int, list[Point2D]] = {}
    for edge_index, profile in edge_joints.items():
        edge_start = boundary[edge_index]
        edge_end = boundary[(edge_index + 1) % n_vertices]
        joint_geometries[edge_index] = profile.compute_edge_geometry(edge_start, edge_end)

    new_boundary: list[Point2D] = []

    for i in range(n_vertices):
        if i in joint_geometries:
            geom = joint_geometries[i]
            next_i = (i + 1) % n_vertices
            if next_i in joint_geometries:
                new_boundary.extend(geom[:-1])
            else:
                new_boundary.extend(geom)
        else:
            prev_i = (i - 1) % n_vertices
            if prev_i not in joint_geometries:
                new_boundary.append(boundary[i])

    return Domain(
        outer_boundary=tuple(new_boundary),
        inner_boundaries=domain.inner_boundaries,
        local_origin=domain.local_origin,
        local_rotation_rad=domain.local_rotation_rad,
    )


__all__ = ["apply_edge_joint", "apply_edge_joints"]
