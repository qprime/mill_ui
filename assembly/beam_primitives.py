from __future__ import annotations

from assembly.beam import (
    BeamSpec,
    BeamRole,
    FaceFeature,
    EndFeature,
    EdgeFeature,
    Chamfer,
    Fillet,
)


def post(
    height: float,
    width: float,
    thickness: float = 19.0,
    layers: int = 3,
    face_features: tuple[FaceFeature, ...] = (),
    end_features: tuple[EndFeature, ...] = (),
    edge_features: tuple[EdgeFeature, ...] = (),
    name: str = "post",
) -> BeamSpec:
    return BeamSpec(
        name=name,
        length_mm=height,
        width_mm=width,
        thickness_mm=thickness,
        layers=layers,
        face_features=face_features,
        end_features=end_features,
        edge_features=edge_features,
        role=BeamRole.POST,
    )


def rail(
    length: float,
    height: float,
    thickness: float = 19.0,
    layers: int = 3,
    face_features: tuple[FaceFeature, ...] = (),
    end_features: tuple[EndFeature, ...] = (),
    edge_features: tuple[EdgeFeature, ...] = (),
    name: str = "rail",
) -> BeamSpec:
    return BeamSpec(
        name=name,
        length_mm=length,
        width_mm=height,
        thickness_mm=thickness,
        layers=layers,
        face_features=face_features,
        end_features=end_features,
        edge_features=edge_features,
        role=BeamRole.RAIL,
    )


def leg(
    height: float,
    width: float,
    thickness: float = 19.0,
    layers: int = 3,
    face_features: tuple[FaceFeature, ...] = (),
    end_features: tuple[EndFeature, ...] = (),
    edge_features: tuple[EdgeFeature, ...] = (),
    name: str = "leg",
) -> BeamSpec:
    return BeamSpec(
        name=name,
        length_mm=height,
        width_mm=width,
        thickness_mm=thickness,
        layers=layers,
        face_features=face_features,
        end_features=end_features,
        edge_features=edge_features,
        role=BeamRole.LEG,
    )


def apron(
    length: float,
    height: float,
    thickness: float = 19.0,
    layers: int = 3,
    face_features: tuple[FaceFeature, ...] = (),
    end_features: tuple[EndFeature, ...] = (),
    edge_features: tuple[EdgeFeature, ...] = (),
    name: str = "apron",
) -> BeamSpec:
    return BeamSpec(
        name=name,
        length_mm=length,
        width_mm=height,
        thickness_mm=thickness,
        layers=layers,
        face_features=face_features,
        end_features=end_features,
        edge_features=edge_features,
        role=BeamRole.APRON,
    )


def chamfered_post(
    height: float,
    width: float,
    chamfer_width: float = 3.0,
    thickness: float = 19.0,
    layers: int = 3,
    name: str = "post",
) -> BeamSpec:
    return post(
        height=height,
        width=width,
        thickness=thickness,
        layers=layers,
        edge_features=(
            Chamfer(edge="top", width_mm=chamfer_width),
            Chamfer(edge="bottom", width_mm=chamfer_width),
        ),
        name=name,
    )


def filleted_leg(
    height: float,
    width: float,
    fillet_radius: float = 6.0,
    thickness: float = 19.0,
    layers: int = 3,
    name: str = "leg",
) -> BeamSpec:
    return leg(
        height=height,
        width=width,
        thickness=thickness,
        layers=layers,
        edge_features=(
            Fillet(edge="top", radius_mm=fillet_radius),
            Fillet(edge="bottom", radius_mm=fillet_radius),
        ),
        name=name,
    )


__all__ = [
    "post",
    "rail",
    "leg",
    "apron",
    "chamfered_post",
    "filleted_leg",
]
