from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from assembly.topology import MatingEdge, FaceSpec
from assembly.notches import NotchSpec, finger_joints_to_notches

JoineryType = Literal["butt", "finger"]


class JoineryStrategy(Protocol):

    @property
    def joinery_type(self) -> JoineryType: ...

    def supports_angle(self, dihedral_deg: float) -> bool: ...

    def compute_notches(
        self,
        edge: MatingEdge,
        faces: dict[str, FaceSpec],
        phase_a: int,
        phase_b: int,
    ) -> tuple[list[NotchSpec], list[NotchSpec]]: ...


@dataclass(frozen=True)
class ButtJoineryStrategy:
    joinery_type: JoineryType = "butt"

    def supports_angle(self, dihedral_deg: float) -> bool:
        return True

    def compute_notches(
        self,
        edge: MatingEdge,
        faces: dict[str, FaceSpec],
        phase_a: int,
        phase_b: int,
    ) -> tuple[list[NotchSpec], list[NotchSpec]]:
        return ([], [])


@dataclass(frozen=True)
class FingerJoineryStrategy:
    finger_width_mm: float | None = None
    finger_count: int | None = None
    clearance_mm: float = 0.12
    joinery_type: JoineryType = "finger"

    def __post_init__(self) -> None:
        if self.finger_width_mm is not None and self.finger_count is not None:
            raise ValueError("Specify at most one of finger_width_mm or finger_count")

    def supports_angle(self, dihedral_deg: float) -> bool:
        return abs(dihedral_deg - 90.0) < 1.0

    def compute_notches(
        self,
        edge: MatingEdge,
        faces: dict[str, FaceSpec],
        phase_a: int,
        phase_b: int,
    ) -> tuple[list[NotchSpec], list[NotchSpec]]:
        face_a = faces[edge.face_a]
        face_b = faces[edge.face_b]
        edge_length = face_a.edge_length(edge.edge_index_a)
        depth = face_a.thickness_mm

        notches_a = finger_joints_to_notches(
            edge_index=edge.edge_index_a,
            edge_length=edge_length,
            depth_mm=depth,
            phase=phase_a,
            width_mm=self.finger_width_mm,
            count=self.finger_count,
            clearance_mm=self.clearance_mm,
        )

        notches_b = finger_joints_to_notches(
            edge_index=edge.edge_index_b,
            edge_length=edge_length,
            depth_mm=depth,
            phase=phase_b,
            width_mm=self.finger_width_mm,
            count=self.finger_count,
            clearance_mm=self.clearance_mm,
        )

        return (notches_a, notches_b)
