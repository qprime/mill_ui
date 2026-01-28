from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from joints.profiles import JointProfile, FingerJointProfile
from assembly.topology import MatingEdge, FaceSpec

JoineryType = Literal["butt", "finger"]


class JoineryStrategy(Protocol):

    @property
    def joinery_type(self) -> JoineryType: ...

    def supports_angle(self, dihedral_deg: float) -> bool: ...

    def compute_profiles(
        self,
        edge: MatingEdge,
        faces: dict[str, FaceSpec],
        phase_a: int,
        phase_b: int,
    ) -> tuple[JointProfile | None, JointProfile | None]: ...


@dataclass(frozen=True)
class ButtJoineryStrategy:
    joinery_type: JoineryType = "butt"

    def supports_angle(self, dihedral_deg: float) -> bool:
        return True

    def compute_profiles(
        self,
        edge: MatingEdge,
        faces: dict[str, FaceSpec],
        phase_a: int,
        phase_b: int,
    ) -> tuple[JointProfile | None, JointProfile | None]:
        return (None, None)


@dataclass(frozen=True)
class FingerJoineryStrategy:
    finger_width_mm: float | None = None
    finger_count: int | None = None
    clearance_mm: float = 0.1
    joinery_type: JoineryType = "finger"

    def __post_init__(self) -> None:
        if self.finger_width_mm is not None and self.finger_count is not None:
            raise ValueError("Specify at most one of finger_width_mm or finger_count")

    def supports_angle(self, dihedral_deg: float) -> bool:
        return abs(dihedral_deg - 90.0) < 1.0

    def compute_profiles(
        self,
        edge: MatingEdge,
        faces: dict[str, FaceSpec],
        phase_a: int,
        phase_b: int,
    ) -> tuple[JointProfile | None, JointProfile | None]:
        depth = faces[edge.face_a].thickness_mm
        profile_a = FingerJointProfile(
            depth_mm=depth,
            width_mm=self.finger_width_mm,
            count=self.finger_count,
            phase=phase_a,
            clearance_mm=self.clearance_mm,
        )
        profile_b = FingerJointProfile(
            depth_mm=depth,
            width_mm=self.finger_width_mm,
            count=self.finger_count,
            phase=phase_b,
            clearance_mm=self.clearance_mm,
        )
        return (profile_a, profile_b)
