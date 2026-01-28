from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from joints.profiles import JointProfile
from assembly.topology import AssemblyTopology, MatingFeature
from assembly.joinery import JoineryStrategy


@dataclass(frozen=True)
class DadoSpec:
    position_from_edge_mm: float
    width_mm: float
    depth_mm: float
    edge: Literal["top", "bottom"]


@dataclass(frozen=True)
class PanelSpec:
    name: str
    polygon: tuple[tuple[float, float], ...]
    thickness_mm: float
    edge_joints: dict[int, JointProfile]
    dados: tuple[DadoSpec, ...] = ()


@dataclass(frozen=True)
class AssemblyParams:
    topology: AssemblyTopology
    joinery_strategy: JoineryStrategy
    edge_overrides: dict[tuple[str, int], JoineryStrategy] = field(default_factory=dict)


def generate_assembly_panels(params: AssemblyParams) -> list[PanelSpec]:
    params.topology.validate()

    phases = params.topology.compute_phase_assignment()

    face_edge_joints: dict[str, dict[int, JointProfile]] = {
        face_name: {} for face_name in params.topology.faces
    }

    for mating_edge in params.topology.mating_edges:
        strategy = params.edge_overrides.get(
            (mating_edge.face_a, mating_edge.edge_index_a),
            params.edge_overrides.get(
                (mating_edge.face_b, mating_edge.edge_index_b),
                params.joinery_strategy
            )
        )

        if not strategy.supports_angle(mating_edge.dihedral_angle_deg):
            strategy = params.edge_overrides.get(
                (mating_edge.face_a, mating_edge.edge_index_a),
                params.edge_overrides.get(
                    (mating_edge.face_b, mating_edge.edge_index_b),
                    None
                )
            )
            if strategy is None:
                from assembly.joinery import ButtJoineryStrategy
                strategy = ButtJoineryStrategy()

        phase_a = phases.get((mating_edge.face_a, mating_edge.edge_index_a), 0)
        phase_b = phases.get((mating_edge.face_b, mating_edge.edge_index_b), 1)

        profile_a, profile_b = strategy.compute_profiles(
            mating_edge,
            params.topology.faces,
            phase_a,
            phase_b,
        )

        if profile_a is not None:
            face_edge_joints[mating_edge.face_a][mating_edge.edge_index_a] = profile_a
        if profile_b is not None:
            face_edge_joints[mating_edge.face_b][mating_edge.edge_index_b] = profile_b

    face_dados: dict[str, list[DadoSpec]] = {
        face_name: [] for face_name in params.topology.faces
    }

    for feature in params.topology.mating_features:
        if feature.kind == "dado":
            dado = DadoSpec(
                position_from_edge_mm=feature.params.get("position_from_edge_mm", 0.0),
                width_mm=feature.params.get("width_mm", 0.0),
                depth_mm=feature.params.get("depth_mm", 0.0),
                edge=feature.params.get("edge", "bottom"),
            )
            face_dados[feature.face].append(dado)

    panels: list[PanelSpec] = []
    for face_name, face_spec in params.topology.faces.items():
        panel = PanelSpec(
            name=face_name,
            polygon=face_spec.polygon,
            thickness_mm=face_spec.thickness_mm,
            edge_joints=face_edge_joints[face_name],
            dados=tuple(face_dados[face_name]),
        )
        panels.append(panel)

    return panels
