# path: skills/mill_ui/compositions/panels/inset_frame.py
"""Inset frame template used by the cross_stitch_map_frame project."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any, List

from skills.mill_ui.compositions.base import (
    TemplateBase,
    register_template,
    rect_shape,
    CenterRegion,
)


@dataclass(frozen=True)
class PocketLayer:
    width_mm: float
    height_mm: float
    depth_mm: float
    label: str

    def to_shape(self) -> Dict[str, Any]:
        return rect_shape(
            (0.0, 0.0),
            width_mm=self.width_mm,
            height_mm=self.height_mm,
            feature={"type": "pocket", "depth_mm": self.depth_mm},
            shape_id=self.label,
        )


@dataclass(frozen=True)
class InsetFrameConfig:
    outer: CenterRegion
    lip_inset_mm: float
    lip_depth_mm: float
    recess_inset_mm: float
    recess_depth_mm: float

    @classmethod
    def from_params(cls, params: Dict[str, Any]) -> "InsetFrameConfig":
        return cls(
            outer=CenterRegion(
                width_mm=float(params.get("outer_w_mm", 0.0)),
                height_mm=float(params.get("outer_h_mm", 0.0)),
            ),
            lip_inset_mm=float(params.get("lip_inset_mm", 3.0)),
            lip_depth_mm=float(params.get("lip_depth_mm", 4.0)),
            recess_inset_mm=float(params.get("recess_extra_inset_mm", 3.0)),
            recess_depth_mm=float(params.get("recess_depth_mm", 10.0)),
        )

    def compose(self) -> List[Dict[str, Any]]:
        if self.outer.width_mm <= 0.0 or self.outer.height_mm <= 0.0:
            return []

        shapes: List[Dict[str, Any]] = []
        shapes.append(
            rect_shape(
                (0.0, 0.0),
                width_mm=self.outer.width_mm,
                height_mm=self.outer.height_mm,
                feature={"type": "profile", "depth": "through", "side": "outside"},
                shape_id="frame:outer",
            )
        )

        lip_w = self.outer.width_mm - 2.0 * self.lip_inset_mm
        lip_h = self.outer.height_mm - 2.0 * self.lip_inset_mm
        if lip_w <= 0.0 or lip_h <= 0.0:
            return shapes

        shapes.append(
            PocketLayer(
                width_mm=lip_w,
                height_mm=lip_h,
                depth_mm=self.lip_depth_mm,
                label="frame:lip",
            ).to_shape()
        )

        recess_w = lip_w - 2.0 * self.recess_inset_mm
        recess_h = lip_h - 2.0 * self.recess_inset_mm
        if recess_w <= 0.0 or recess_h <= 0.0:
            return shapes

        shapes.append(
            PocketLayer(
                width_mm=recess_w,
                height_mm=recess_h,
                depth_mm=self.recess_depth_mm,
                label="frame:recess",
            ).to_shape()
        )

        return shapes


@register_template("InsetFrame")
class InsetFrame(TemplateBase):
    def expand(self, params: Dict[str, Any], thickness_mm: float) -> List[Dict[str, Any]]:
        cfg = InsetFrameConfig.from_params(params)
        return cfg.compose()
