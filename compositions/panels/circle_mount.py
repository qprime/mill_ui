# path: skills/mill_ui/compositions/panels/circle_mount.py
"""Circle mount template powering the impeller_mount_base project."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Dict, Any, List

from skills.mill_ui.compositions.base import (
    TemplateBase,
    register_template,
    circle_shape,
)


@dataclass(frozen=True)
class DiskSpec:
    diameter_mm: float

    def to_shape(self) -> Dict[str, Any]:
        return circle_shape(
            (0.0, 0.0),
            diameter_mm=self.diameter_mm,
            feature={"type": "profile", "depth": "through", "side": "outside"},
            shape_id="mount:disk",
        )


@dataclass(frozen=True)
class PortSpec:
    diameter_mm: float

    def to_shape(self) -> Dict[str, Any]:
        return circle_shape(
            (0.0, 0.0),
            diameter_mm=self.diameter_mm,
            feature={"type": "hole", "depth": "through"},
            shape_id="mount:port",
        )


@dataclass(frozen=True)
class BoltCircleSpec:
    diameter_mm: float
    count: int
    through_d_mm: float
    counterbore_d_mm: float
    counterbore_depth_mm: float

    def radial_points(self) -> List[tuple[float, float]]:
        r = 0.5 * self.diameter_mm
        return [
            (r * math.cos(2.0 * math.pi * i / self.count),
             r * math.sin(2.0 * math.pi * i / self.count))
            for i in range(self.count)
        ]

    def to_shapes(self) -> List[Dict[str, Any]]:
        shapes: List[Dict[str, Any]] = []
        for idx, (x, y) in enumerate(self.radial_points(), start=1):
            if self.counterbore_d_mm > 0.0 and self.counterbore_depth_mm > 0.0:
                shapes.append(
                    circle_shape(
                        (x, y),
                        diameter_mm=self.counterbore_d_mm,
                        feature={"type": "pocket", "depth_mm": self.counterbore_depth_mm},
                        shape_id=f"mount:cb:{idx}",
                    )
                )
            shapes.append(
                circle_shape(
                    (x, y),
                    diameter_mm=self.through_d_mm,
                    feature={"type": "hole", "depth": "through"},
                    shape_id=f"mount:hole:{idx}",
                )
            )
        return shapes


@dataclass(frozen=True)
class CircleMountConfig:
    disk: DiskSpec | None
    port: PortSpec | None
    bolt_circle: BoltCircleSpec | None

    @classmethod
    def from_params(cls, params: Dict[str, Any]) -> "CircleMountConfig":
        disk_cfg = params.get("disk") or {}
        disk = None
        if float(disk_cfg.get("diameter_mm", 0.0)) > 0.0:
            disk = DiskSpec(diameter_mm=float(disk_cfg.get("diameter_mm", 0.0)))

        port_cfg = params.get("port") or {}
        port_d = float(port_cfg.get("diameter_mm", port_cfg.get("diameter", 0.0)))
        port = PortSpec(diameter_mm=port_d) if port_d > 0.0 else None

        bc_cfg = params.get("bolt_circle") or {}
        bc = None
        bc_count = int(bc_cfg.get("count", 0))
        bc_d = float(bc_cfg.get("diameter_mm", 0.0))
        thru_d = float(bc_cfg.get("through_d_mm", 0.0))
        if bc_count > 0 and bc_d > 0.0 and thru_d > 0.0:
            bc = BoltCircleSpec(
                diameter_mm=bc_d,
                count=bc_count,
                through_d_mm=thru_d,
                counterbore_d_mm=float(bc_cfg.get("counterbore_d_mm", 0.0)),
                counterbore_depth_mm=float(bc_cfg.get("counterbore_depth_mm", 0.0)),
            )

        return cls(disk=disk, port=port, bolt_circle=bc)

    def compose(self) -> List[Dict[str, Any]]:
        shapes: List[Dict[str, Any]] = []
        if self.disk:
            shapes.append(self.disk.to_shape())
        if self.port:
            shapes.append(self.port.to_shape())
        if self.bolt_circle:
            shapes.extend(self.bolt_circle.to_shapes())
        return shapes


@register_template("CircleMount")
class CircleMount(TemplateBase):
    def expand(self, params: Dict[str, Any], thickness_mm: float) -> List[Dict[str, Any]]:
        cfg = CircleMountConfig.from_params(params)
        return cfg.compose()
