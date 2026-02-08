from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Literal, Any

from assembly.panel import PanelSpec


MachiningStage = Literal["segment", "strip"]


class BeamRole(Enum):
    POST = auto()
    RAIL = auto()
    LEG = auto()
    APRON = auto()
    STRETCHER = auto()
    STILE = auto()
    MUNTIN = auto()


@dataclass(frozen=True)
class Cutout:
    start_mm: float
    length_mm: float
    width_mm: float | None = None
    offset_from_edge_mm: float = 0.0

    def __post_init__(self) -> None:
        if self.start_mm < 0:
            raise ValueError(f"Cutout start_mm must be non-negative, got {self.start_mm}")
        if self.length_mm <= 0:
            raise ValueError(f"Cutout length_mm must be positive, got {self.length_mm}")
        if self.width_mm is not None and self.width_mm <= 0:
            raise ValueError(f"Cutout width_mm must be positive, got {self.width_mm}")


@dataclass(frozen=True)
class LayerSpec:
    length_mm: float
    offset_mm: float = 0.0
    cutouts: tuple[Cutout, ...] = ()

    def __post_init__(self) -> None:
        if self.length_mm <= 0:
            raise ValueError(f"LayerSpec length_mm must be positive, got {self.length_mm}")
        for cutout in self.cutouts:
            if cutout.start_mm + cutout.length_mm > self.length_mm:
                raise ValueError(
                    f"Cutout exceeds layer length: {cutout.start_mm} + {cutout.length_mm} > {self.length_mm}"
                )


@dataclass(frozen=True)
class Segment:
    start_mm: float
    end_mm: float
    layer: int
    index: int

    @property
    def length(self) -> float:
        return self.end_mm - self.start_mm


@dataclass(frozen=True)
class DrillHole:
    x_mm: float
    y_mm: float
    diameter_mm: float
    depth_mm: float | None = None
    face: Literal["front", "back"] = "front"
    stage: MachiningStage = "strip"


@dataclass(frozen=True)
class SquareMortise:
    x_mm: float
    y_mm: float
    width_mm: float
    height_mm: float
    depth_mm: float
    face: Literal["front", "back"] = "front"
    stage: MachiningStage = "strip"


@dataclass(frozen=True)
class CarvedDesign:
    x_mm: float
    y_mm: float
    design: str
    depth_mm: float
    face: Literal["front", "back"] = "front"
    stage: MachiningStage = "strip"


@dataclass(frozen=True)
class GeometricPattern:
    x_mm: float
    y_mm: float
    pattern_type: str
    params: dict[str, Any] = field(default_factory=dict)
    depth_mm: float = 1.0
    face: Literal["front", "back"] = "front"
    stage: MachiningStage = "strip"


FaceFeature = DrillHole | SquareMortise | CarvedDesign | GeometricPattern


@dataclass(frozen=True)
class Tenon:
    end: Literal["left", "right"]
    extension_mm: float
    width_mm: float
    height_mm: float
    center_offset_mm: float = 0.0
    layers: Literal["center", "outer", "all"] | tuple[int, ...] = "center"


@dataclass(frozen=True)
class EndCap:
    end: Literal["left", "right"]
    profile: str
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EndProfile:
    end: Literal["left", "right"]
    contour: tuple[tuple[float, float], ...]


EndFeature = Tenon | EndCap | EndProfile


@dataclass(frozen=True)
class Fillet:
    edge: Literal["top", "bottom"]
    radius_mm: float
    start_mm: float = 0.0
    end_mm: float | None = None
    layers: Literal["outer", "all"] = "outer"
    stage: MachiningStage = "strip"


@dataclass(frozen=True)
class Chamfer:
    edge: Literal["top", "bottom"]
    width_mm: float
    angle_deg: float = 45.0
    start_mm: float = 0.0
    end_mm: float | None = None
    layers: Literal["outer", "all"] = "outer"
    stage: MachiningStage = "strip"


@dataclass(frozen=True)
class Rabbet:
    edge: Literal["top", "bottom"]
    width_mm: float
    depth_mm: float
    start_mm: float = 0.0
    end_mm: float | None = None
    layers: Literal["outer", "all"] = "outer"
    stage: MachiningStage = "strip"


@dataclass(frozen=True)
class EdgeDado:
    edge: Literal["top", "bottom"]
    position_mm: float
    width_mm: float
    depth_mm: float
    layers: Literal["outer", "all"] = "all"
    stage: MachiningStage = "strip"


@dataclass(frozen=True)
class EdgeNotch:
    edge: Literal["top", "bottom"]
    position_mm: float
    width_mm: float
    depth_mm: float
    layers: Literal["outer", "all"] = "all"
    stage: MachiningStage = "strip"


@dataclass(frozen=True)
class EdgeContour:
    edge: Literal["top", "bottom"]
    contour: tuple[tuple[float, float], ...]
    layers: Literal["outer", "all"] = "outer"
    stage: MachiningStage = "strip"


EdgeFeature = Fillet | Chamfer | Rabbet | EdgeDado | EdgeNotch | EdgeContour


def compute_segments(
    length: float,
    sheet_size: float,
    layers: int,
    min_segment_length: float | None = None,
) -> list[list[Segment]]:
    if layers < 1:
        raise ValueError(f"layers must be >= 1, got {layers}")
    if length <= 0:
        raise ValueError(f"length must be positive, got {length}")
    if sheet_size <= 0:
        raise ValueError(f"sheet_size must be positive, got {sheet_size}")

    if min_segment_length is None:
        min_segment_length = sheet_size * 0.1

    if length <= sheet_size:
        return [
            [Segment(start_mm=0.0, end_mm=length, layer=layer_idx, index=0)]
            for layer_idx in range(layers)
        ]

    stagger = sheet_size / layers

    result: list[list[Segment]] = []
    for layer_idx in range(layers):
        layer_offset = layer_idx * stagger
        layer_segments: list[Segment] = []
        pos = 0.0
        seg_idx = 0

        while pos < length:
            remaining = length - pos
            if seg_idx == 0:
                seg_len = min(sheet_size - layer_offset, remaining)
            else:
                seg_len = min(sheet_size, remaining)

            next_remaining = remaining - seg_len
            if next_remaining > 0 and next_remaining < min_segment_length:
                seg_len = remaining / 2.0

            layer_segments.append(Segment(
                start_mm=pos,
                end_mm=pos + seg_len,
                layer=layer_idx,
                index=seg_idx,
            ))
            pos += seg_len
            seg_idx += 1

        result.append(layer_segments)

    return result


def _get_butt_positions(segments: list[list[Segment]]) -> list[float]:
    butts: list[float] = []
    for layer_segments in segments:
        for seg in layer_segments[:-1]:
            butts.append(seg.end_mm)
    return butts


def validate_butts_never_align(segments: list[list[Segment]], tolerance: float = 1e-6) -> None:
    butts = _get_butt_positions(segments)
    seen: set[float] = set()
    for butt in butts:
        for existing in seen:
            if abs(butt - existing) < tolerance:
                raise ValueError(f"Butt joints align at position {butt}mm (BM-9 violation)")
        seen.add(butt)


def validate_stagger_minimum(
    segments: list[list[Segment]],
    thickness_mm: float,
    tolerance: float = 1e-6,
) -> None:
    if len(segments) < 2:
        return

    has_splicing = any(len(layer_segs) > 1 for layer_segs in segments)
    if not has_splicing:
        return

    min_stagger = 2 * thickness_mm
    for i in range(len(segments) - 1):
        layer_a = segments[i]
        layer_b = segments[i + 1]
        if len(layer_a) > 1 and len(layer_b) > 1:
            butt_a = layer_a[0].end_mm
            butt_b = layer_b[0].end_mm
            stagger = abs(butt_a - butt_b)
            if stagger < min_stagger - tolerance:
                raise ValueError(
                    f"Stagger {stagger}mm < minimum {min_stagger}mm (BM-10 violation)"
                )


@dataclass(frozen=True)
class BeamSpec:
    name: str
    length_mm: float
    width_mm: float
    thickness_mm: float
    layers: int | tuple[LayerSpec, ...]
    face_features: tuple[FaceFeature, ...] = ()
    end_features: tuple[EndFeature, ...] = ()
    edge_features: tuple[EdgeFeature, ...] = ()
    role: BeamRole | None = None

    def __post_init__(self) -> None:
        if self.length_mm <= 0:
            raise ValueError(f"BeamSpec length_mm must be positive, got {self.length_mm}")
        if self.width_mm <= 0:
            raise ValueError(f"BeamSpec width_mm must be positive, got {self.width_mm}")
        if self.thickness_mm <= 0:
            raise ValueError(f"BeamSpec thickness_mm must be positive, got {self.thickness_mm}")
        if isinstance(self.layers, int) and self.layers < 1:
            raise ValueError(f"BeamSpec layers must be >= 1, got {self.layers}")
        if isinstance(self.layers, tuple) and len(self.layers) < 1:
            raise ValueError("BeamSpec layers tuple must have at least one LayerSpec")

    @property
    def layer_count(self) -> int:
        if isinstance(self.layers, int):
            return self.layers
        return len(self.layers)

    @property
    def total_thickness(self) -> float:
        return self.thickness_mm * self.layer_count

    def _is_outer_layer(self, layer_idx: int) -> bool:
        return layer_idx == 0 or layer_idx == self.layer_count - 1

    def _should_apply_edge_feature(self, feature: EdgeFeature, layer_idx: int) -> bool:
        if feature.layers == "all":
            return True
        return self._is_outer_layer(layer_idx)

    def _should_apply_tenon(self, tenon: Tenon, layer_idx: int) -> bool:
        if tenon.layers == "all":
            return True
        if tenon.layers == "center":
            return not self._is_outer_layer(layer_idx)
        if tenon.layers == "outer":
            return self._is_outer_layer(layer_idx)
        return layer_idx in tenon.layers

    def _tenon_extensions_for_layer(self, layer_idx: int) -> float:
        total = 0.0
        for feat in self.end_features:
            if isinstance(feat, Tenon) and self._should_apply_tenon(feat, layer_idx):
                total += feat.extension_mm
        return total

    def expand(self, sheet_size: float) -> list[PanelSpec]:
        if isinstance(self.layers, int):
            segments = compute_segments(self.length_mm, sheet_size, self.layers)
            validate_butts_never_align(segments)
            if self.layer_count > 1:
                validate_stagger_minimum(segments, self.thickness_mm)
        else:
            segments = None

        panels: list[PanelSpec] = []

        for layer_idx in range(self.layer_count):
            if isinstance(self.layers, int):
                layer_length = self.length_mm + self._tenon_extensions_for_layer(layer_idx)
                layer_offset = 0.0
                layer_segments = segments[layer_idx] if segments else None
            else:
                layer_spec = self.layers[layer_idx]
                layer_length = layer_spec.length_mm
                layer_offset = layer_spec.offset_mm
                layer_segments = None

            if layer_segments and len(layer_segments) > 1:
                for seg in layer_segments:
                    panel_name = f"{self.name}_L{layer_idx}_S{seg.index}"
                    panel = PanelSpec(
                        name=panel_name,
                        width_mm=seg.length,
                        height_mm=self.width_mm,
                        thickness_mm=self.thickness_mm,
                    )
                    panels.append(panel)
            else:
                if self.layer_count == 1:
                    panel_name = self.name
                else:
                    panel_name = f"{self.name}_L{layer_idx}"

                panel = PanelSpec(
                    name=panel_name,
                    width_mm=layer_length,
                    height_mm=self.width_mm,
                    thickness_mm=self.thickness_mm,
                )
                panels.append(panel)

        return panels


__all__ = [
    "MachiningStage",
    "BeamRole",
    "Cutout",
    "LayerSpec",
    "Segment",
    "DrillHole",
    "SquareMortise",
    "CarvedDesign",
    "GeometricPattern",
    "FaceFeature",
    "Tenon",
    "EndCap",
    "EndProfile",
    "EndFeature",
    "Fillet",
    "Chamfer",
    "Rabbet",
    "EdgeDado",
    "EdgeNotch",
    "EdgeContour",
    "EdgeFeature",
    "compute_segments",
    "validate_butts_never_align",
    "validate_stagger_minimum",
    "BeamSpec",
]
