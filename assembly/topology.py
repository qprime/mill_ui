from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass(frozen=True)
class FaceSpec:
    name: str
    polygon: tuple[tuple[float, float], ...]
    thickness_mm: float

    @property
    def edge_count(self) -> int:
        return len(self.polygon)

    def edge_length(self, edge_index: int) -> float:
        p0 = self.polygon[edge_index]
        p1 = self.polygon[(edge_index + 1) % len(self.polygon)]
        return math.sqrt((p1[0] - p0[0]) ** 2 + (p1[1] - p0[1]) ** 2)

    def edge_vertices(self, edge_index: int) -> tuple[tuple[float, float], tuple[float, float]]:
        p0 = self.polygon[edge_index]
        p1 = self.polygon[(edge_index + 1) % len(self.polygon)]
        return (p0, p1)


@dataclass(frozen=True)
class MatingEdge:
    face_a: str
    edge_index_a: int
    face_b: str
    edge_index_b: int
    dihedral_angle_deg: float = 90.0


@dataclass(frozen=True)
class MatingFeature:
    face: str
    kind: Literal["dado", "pilot_holes", "notch"]
    params: dict[str, Any]
    mates_with: str | None = None


@dataclass(frozen=True)
class AssemblyTopology:
    faces: dict[str, FaceSpec]
    mating_edges: tuple[MatingEdge, ...]
    mating_features: tuple[MatingFeature, ...] = ()

    def validate(self) -> None:
        for edge in self.mating_edges:
            if edge.face_a not in self.faces:
                raise ValueError(f"MatingEdge references unknown face: {edge.face_a}")
            if edge.face_b not in self.faces:
                raise ValueError(f"MatingEdge references unknown face: {edge.face_b}")

            face_a = self.faces[edge.face_a]
            face_b = self.faces[edge.face_b]

            if edge.edge_index_a < 0 or edge.edge_index_a >= face_a.edge_count:
                raise ValueError(
                    f"MatingEdge edge_index_a={edge.edge_index_a} out of range for face {edge.face_a} "
                    f"with {face_a.edge_count} edges"
                )
            if edge.edge_index_b < 0 or edge.edge_index_b >= face_b.edge_count:
                raise ValueError(
                    f"MatingEdge edge_index_b={edge.edge_index_b} out of range for face {edge.face_b} "
                    f"with {face_b.edge_count} edges"
                )

            len_a = face_a.edge_length(edge.edge_index_a)
            len_b = face_b.edge_length(edge.edge_index_b)
            if abs(len_a - len_b) > 0.01:
                raise ValueError(
                    f"MatingEdge length mismatch: {edge.face_a}[{edge.edge_index_a}]={len_a:.2f}mm "
                    f"vs {edge.face_b}[{edge.edge_index_b}]={len_b:.2f}mm"
                )

        for feature in self.mating_features:
            if feature.face not in self.faces:
                raise ValueError(f"MatingFeature references unknown face: {feature.face}")
            if feature.mates_with is not None and feature.mates_with not in self.faces:
                raise ValueError(f"MatingFeature mates_with references unknown face: {feature.mates_with}")

    def compute_phase_assignment(self) -> dict[tuple[str, int], int]:
        edge_to_node: dict[tuple[str, int], int] = {}
        node_counter = 0
        for edge in self.mating_edges:
            key_a = (edge.face_a, edge.edge_index_a)
            key_b = (edge.face_b, edge.edge_index_b)
            if key_a not in edge_to_node:
                edge_to_node[key_a] = node_counter
                node_counter += 1
            if key_b not in edge_to_node:
                edge_to_node[key_b] = node_counter
                node_counter += 1

        adjacency: dict[int, list[int]] = {i: [] for i in range(node_counter)}
        for edge in self.mating_edges:
            node_a = edge_to_node[(edge.face_a, edge.edge_index_a)]
            node_b = edge_to_node[(edge.face_b, edge.edge_index_b)]
            adjacency[node_a].append(node_b)
            adjacency[node_b].append(node_a)

        colors: dict[int, int] = {}

        def bfs_color(start: int) -> bool:
            from collections import deque
            queue = deque([start])
            colors[start] = 0
            while queue:
                node = queue.popleft()
                for neighbor in adjacency[node]:
                    if neighbor not in colors:
                        colors[neighbor] = 1 - colors[node]
                        queue.append(neighbor)
                    elif colors[neighbor] == colors[node]:
                        return False
            return True

        for node in range(node_counter):
            if node not in colors:
                if not bfs_color(node):
                    raise ValueError(
                        "Cannot 2-color mating edge graph (odd cycle detected). "
                        "Finger joints require bipartite topology."
                    )

        result: dict[tuple[str, int], int] = {}
        for key, node in edge_to_node.items():
            result[key] = colors[node]

        return result

    def edges_for_face(self, face_name: str) -> list[MatingEdge]:
        return [
            e for e in self.mating_edges
            if e.face_a == face_name or e.face_b == face_name
        ]

    def features_for_face(self, face_name: str) -> list[MatingFeature]:
        return [f for f in self.mating_features if f.face == face_name]
