# path: skills/mill_ui/compositions/panels/frame_inset_clamp.py
"""Frame inset clamp template for covering the aperture edge on the x-stitch frame."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional

from skills.mill_ui.compositions.base import (
    TemplateBase,
    register_template,
    rect_shape,
    CenterRegion,
)
from skills.mill_ui.compositions.panels.border import make_border_for_frame


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


@dataclass(frozen=True)
class FrameInsetClampConfig:
    outer: CenterRegion
    inner: CenterRegion
    aperture: CenterRegion
    relief_outer_w_mm: float
    relief_outer_h_mm: float
    relief_inner_w_mm: float
    relief_inner_h_mm: float
    indent_mm: float
    rabbet_depth_mm: float
    rabbet_step_mm: float
    border_cfg: Optional[Mapping[str, Any]]

    @property
    def frame_width_mm(self) -> float:
        return max(0.0, 0.5 * (self.outer.width_mm - self.inner.width_mm))

    @classmethod
    def from_params(cls, params: Dict[str, Any]) -> "FrameInsetClampConfig":
        frame_band = _as_float(params.get("frame_width_mm"))
        if frame_band > 0.0:
            return cls._from_modern_params(params, frame_band)
        return cls._from_legacy_params(params)

    @classmethod
    def _from_modern_params(cls, params: Dict[str, Any], frame_width_mm: float) -> "FrameInsetClampConfig":
        outer_w_raw = _as_float(params.get("outer_w_mm"))
        outer_h_raw = _as_float(params.get("outer_h_mm"))
        outer_shrink = max(0.0, _as_float(params.get("outer_shrink_mm")))

        aperture_w = _as_float(params.get("aperture_w_mm") or params.get("aperture_width_mm"))
        aperture_h = _as_float(params.get("aperture_h_mm") or params.get("aperture_height_mm"))

        if outer_w_raw <= 0.0 and aperture_w > 0.0:
            outer_w_raw = aperture_w + 2.0 * frame_width_mm
        if outer_h_raw <= 0.0 and aperture_h > 0.0:
            outer_h_raw = aperture_h + 2.0 * frame_width_mm
        if outer_w_raw <= 0.0 or outer_h_raw <= 0.0:
            raise ValueError("FrameInsetClamp requires outer_w_mm and outer_h_mm when using frame_width_mm")

        outer_w = max(0.0, outer_w_raw - 2.0 * outer_shrink)
        outer_h = max(0.0, outer_h_raw - 2.0 * outer_shrink)

        inner_clearance = _as_float(params.get("inner_clearance_mm"))
        inner_w = max(0.0, outer_w - 2.0 * frame_width_mm + 2.0 * inner_clearance)
        inner_h = max(0.0, outer_h - 2.0 * frame_width_mm + 2.0 * inner_clearance)

        inner_w = min(inner_w, max(0.0, outer_w))
        inner_h = min(inner_h, max(0.0, outer_h))

        rabbet_width = _as_float(params.get("rabbet_width_mm"), frame_width_mm)
        rabbet_width = max(0.0, min(frame_width_mm, rabbet_width))

        relief_outer_w = max(inner_w, min(outer_w, inner_w + 2.0 * rabbet_width))
        relief_outer_h = max(inner_h, min(outer_h, inner_h + 2.0 * rabbet_width))
        relief_inner_w = inner_w
        relief_inner_h = inner_h

        rabbet_depth = max(0.0, _as_float(params.get("rabbet_depth_mm")))
        indent_mm = max(0.0, _as_float(params.get("indent_mm") or params.get("indent")))

        tool_diameter = _as_float(
            params.get("rabbet_tool_diameter_mm")
            or params.get("tool_diameter_mm")
            or params.get("kerf_width_mm"),
            6.35,
        )
        default_rabbet_step = max(0.1, 0.5 * tool_diameter)
        rabbet_step_mm = max(0.1, _as_float(params.get("rabbet_step_mm"), default_rabbet_step))

        aperture_region = CenterRegion(
            width_mm=relief_outer_w if aperture_w <= 0.0 else aperture_w,
            height_mm=relief_outer_h if aperture_h <= 0.0 else aperture_h,
        )

        border_cfg = params.get("border") if isinstance(params.get("border"), Mapping) else None

        return cls(
            outer=CenterRegion(width_mm=outer_w, height_mm=outer_h),
            inner=CenterRegion(width_mm=inner_w, height_mm=inner_h),
            aperture=aperture_region,
            relief_outer_w_mm=relief_outer_w,
            relief_outer_h_mm=relief_outer_h,
            relief_inner_w_mm=relief_inner_w,
            relief_inner_h_mm=relief_inner_h,
            indent_mm=indent_mm,
            rabbet_depth_mm=rabbet_depth,
            rabbet_step_mm=rabbet_step_mm,
            border_cfg=border_cfg,
        )

    @classmethod
    def _from_legacy_params(cls, params: Dict[str, Any]) -> "FrameInsetClampConfig":
        aperture_w = _as_float(params.get("aperture_w_mm") or params.get("aperture_width_mm"))
        aperture_h = _as_float(params.get("aperture_h_mm") or params.get("aperture_height_mm"))
        if aperture_w <= 0.0 or aperture_h <= 0.0:
            raise ValueError("FrameInsetClamp requires aperture_w_mm and aperture_h_mm > 0")

        extent_mm = max(0.0, _as_float(params.get("extent_width_mm") or params.get("extent_mm"), 4.0))
        inset_mm = _as_float(params.get("inset_width_mm") or params.get("inset_mm"))

        outer_w = _as_float(params.get("outer_w_mm"))
        outer_h = _as_float(params.get("outer_h_mm"))

        if inset_mm <= 0.0 and (outer_w > 0.0 or outer_h > 0.0):
            if outer_w > 0.0:
                inset_from_w = 0.5 * max(0.0, outer_w - aperture_w)
                inset_mm = max(inset_mm, inset_from_w)
            if outer_h > 0.0:
                inset_from_h = 0.5 * max(0.0, outer_h - aperture_h)
                inset_mm = max(inset_mm, inset_from_h)

        if inset_mm <= 0.0:
            inset_mm = 8.0

        if outer_w <= 0.0:
            outer_w = aperture_w + 2.0 * inset_mm
        if outer_h <= 0.0:
            outer_h = aperture_h + 2.0 * inset_mm

        outer_clearance = _as_float(params.get("outer_clearance_mm") or params.get("clearance_mm"))
        if outer_clearance != 0.0:
            outer_w = max(0.0, outer_w - 2.0 * outer_clearance)
            outer_h = max(0.0, outer_h - 2.0 * outer_clearance)

        inner_clearance = _as_float(params.get("inner_clearance_mm") or params.get("clearance_mm"))
        inner_w = max(0.0, aperture_w - 2.0 * extent_mm + 2.0 * inner_clearance)
        inner_h = max(0.0, aperture_h - 2.0 * extent_mm + 2.0 * inner_clearance)

        min_wall = 0.5
        max_inner_w = max(0.0, outer_w - 2.0 * min_wall)
        max_inner_h = max(0.0, outer_h - 2.0 * min_wall)
        if max_inner_w > 0.0:
            inner_w = min(inner_w, max_inner_w)
        if max_inner_h > 0.0:
            inner_h = min(inner_h, max_inner_h)

        relief_clearance = max(0.0, _as_float(params.get("relief_clearance_mm")))
        relief_outer_w = aperture_w + 2.0 * relief_clearance
        relief_outer_h = aperture_h + 2.0 * relief_clearance
        relief_outer_w = min(outer_w, max(inner_w, relief_outer_w))
        relief_outer_h = min(outer_h, max(inner_h, relief_outer_h))

        min_relief_band = max(0.25, _as_float(params.get("relief_min_band_mm"), 0.25))
        relief_inner_w = max(0.0, min(inner_w, relief_outer_w - 2.0 * min_relief_band))
        relief_inner_h = max(0.0, min(inner_h, relief_outer_h - 2.0 * min_relief_band))

        indent_mm = max(0.0, _as_float(params.get("indent_mm") or params.get("indent")))

        tool_diameter = _as_float(
            params.get("rabbet_tool_diameter_mm")
            or params.get("tool_diameter_mm")
            or params.get("kerf_width_mm"),
            6.35,
        )
        default_rabbet_step = max(0.1, 0.5 * tool_diameter)
        rabbet_step_mm = max(0.1, _as_float(params.get("rabbet_step_mm"), default_rabbet_step))

        border_cfg = params.get("border") if isinstance(params.get("border"), Mapping) else None

        return cls(
            outer=CenterRegion(width_mm=outer_w, height_mm=outer_h),
            inner=CenterRegion(width_mm=inner_w, height_mm=inner_h),
            aperture=CenterRegion(width_mm=aperture_w, height_mm=aperture_h),
            relief_outer_w_mm=relief_outer_w,
            relief_outer_h_mm=relief_outer_h,
            relief_inner_w_mm=relief_inner_w,
            relief_inner_h_mm=relief_inner_h,
            indent_mm=indent_mm,
            rabbet_depth_mm=0.0,
            rabbet_step_mm=rabbet_step_mm,
            border_cfg=border_cfg,
        )

    def compose(self, thickness_mm: float) -> List[Dict[str, Any]]:
        shapes: List[Dict[str, Any]] = []

        if self.outer.width_mm <= 0.0 or self.outer.height_mm <= 0.0:
            return shapes

        shapes.append(
            rect_shape(
                (0.0, 0.0),
                width_mm=self.outer.width_mm,
                height_mm=self.outer.height_mm,
                feature={"type": "profile", "depth": "through", "side": "outside"},
                shape_id="clamp:outer",
            )
        )

        if self.inner.width_mm > 0.0 and self.inner.height_mm > 0.0:
            shapes.append(
                rect_shape(
                    (0.0, 0.0),
                    width_mm=self.inner.width_mm,
                    height_mm=self.inner.height_mm,
                    feature={"type": "profile", "depth": "through", "side": "inside"},
                    shape_id="clamp:inner",
                )
            )

        if self.rabbet_depth_mm > 0.0 or (0.0 < self.indent_mm < thickness_mm):
            shapes.extend(self._compose_rabbet_passes(thickness_mm))

        if self.border_cfg and self.frame_width_mm > 0.0:
            border_shapes = make_border_for_frame(
                outer_w_mm=self.outer.width_mm,
                outer_h_mm=self.outer.height_mm,
                frame_width_mm=self.frame_width_mm,
                overrides=self.border_cfg,
                sheet_thickness_mm=float(thickness_mm),
            )
            shapes.extend(border_shapes)

        return shapes

    def _compose_rabbet_passes(self, thickness_mm: float) -> List[Dict[str, Any]]:
        pocket_depth = max(0.0, min(thickness_mm, self.rabbet_depth_mm))
        if pocket_depth <= 0.0 and 0.0 < self.indent_mm < thickness_mm:
            pocket_depth = max(0.0, thickness_mm - self.indent_mm)
        if pocket_depth <= 0.0:
            return []

        band_w = max(0.0, self.relief_outer_w_mm - self.relief_inner_w_mm)
        band_h = max(0.0, self.relief_outer_h_mm - self.relief_inner_h_mm)
        if band_w <= 0.0 and band_h <= 0.0:
            return []

        max_offset = 0.5 * max(band_w, band_h)
        if max_offset <= 0.0:
            return []

        step = max(0.1, float(self.rabbet_step_mm))
        offsets: List[float] = [0.0]
        current = 0.0
        # March outward until we hit the relief outer bounds.
        while current + 1e-6 < max_offset:
            current = min(current + step, max_offset)
            # Avoid duplicating the same offset due to tiny bands vs large step.
            if not offsets or abs(current - offsets[-1]) > 1e-6:
                offsets.append(current)

        rabbet_shapes: List[Dict[str, Any]] = []
        half_band_w = 0.5 * band_w
        half_band_h = 0.5 * band_h

        for idx, raw_offset in enumerate(offsets, start=1):
            offset_w = min(raw_offset, half_band_w)
            offset_h = min(raw_offset, half_band_h)
            width = min(self.relief_outer_w_mm, self.relief_inner_w_mm + 2.0 * offset_w)
            height = min(self.relief_outer_h_mm, self.relief_inner_h_mm + 2.0 * offset_h)
            if width <= 0.0 or height <= 0.0:
                continue

            feature = {
                "type": "profile",
                "side": "inside",
                "depth_mm": pocket_depth,
                "tabs": False,
            }
            rabbet_shapes.append(
                rect_shape(
                    (0.0, 0.0),
                    width_mm=width,
                    height_mm=height,
                    feature=feature,
                    shape_id=f"clamp:rabbet:pass:{idx}",
                )
            )

        return rabbet_shapes


@register_template("FrameInsetClamp")
class FrameInsetClamp(TemplateBase):
    def expand(self, params: Dict[str, Any], thickness_mm: float) -> List[Dict[str, Any]]:
        cfg = FrameInsetClampConfig.from_params(params)
        return cfg.compose(thickness_mm)
