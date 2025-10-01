# path: skills/mill_ui/compositions/shop_accessories/clamp_bar.py
"""Composable clamp bar template used by the cnc_clamp_v1 project."""

from __future__ import annotations

from dataclasses import dataclass
from math import floor
from typing import Dict, Any, List
import copy

from skills.mill_ui.compositions.base import (
    TemplateBase,
    register_template,
    rect_shape,
    CenterRegion,
)


@dataclass(frozen=True)
class SlotPattern:
    mode: str
    count: int | None
    pitch_mm: float | None
    margin_mm: float
    min_slots: int
    max_slots: int

    def positions(self, length_mm: float) -> List[float]:
        L = float(length_mm)
        margin = max(0.0, self.margin_mm)
        usable = max(0.0, L - 2.0 * margin)
        left = -L * 0.5 + margin
        right = +L * 0.5 - margin
        if usable <= 0.0:
            return []

        if self.mode == "pitch" and (self.pitch_mm or 0.0) > 0.0:
            pitch = float(self.pitch_mm)
            n = int(floor(usable / pitch)) + 1
            n = max(self.min_slots, min(self.max_slots, n))
            if n <= 1:
                return [0.0]
            span = (n - 1) * pitch
            start = -0.5 * span
            xs = [start + i * pitch for i in range(n)]
            return [max(left, min(right, x)) for x in xs]

        n = self.count if isinstance(self.count, int) and self.count > 0 else None
        if n is None:
            n = self.min_slots
        n = max(self.min_slots, min(self.max_slots, n))
        if n <= 1:
            return [0.0]
        step = usable / float(n - 1)
        return [left + i * step for i in range(n)]


@dataclass(frozen=True)
class SlotSpec:
    length_mm: float
    width_mm: float
    depth: str | float  # "through" or numeric depth

    def feature(self) -> Dict[str, Any]:
        feat: Dict[str, Any] = {"type": "pocket"}
        if self.depth == "through":
            feat["depth"] = "through"
        else:
            feat["depth_mm"] = float(self.depth)
        return feat

@dataclass(frozen=True)
class BarSpec:
    label: str
    region: CenterRegion
    slot_spec: SlotSpec
    slot_pattern: SlotPattern
    band_height_mm: float
    band_depth_mm: float
    band_offset_mm: float
    band_overtravel_mm: float
    lip_height_mm: float
    lip_depth_mm: float
    lip_overtravel_mm: float

    def compose(self) -> List[Dict[str, Any]]:
        shapes: List[Dict[str, Any]] = []
        shapes.append(
            rect_shape(
                (0.0, 0.0),
                width_mm=self.region.width_mm,
                height_mm=self.region.height_mm,
                feature={"type": "profile", "depth": "through", "side": "outside"},
                shape_id=f"{self.label}:outline",
            )
        )
        slot_feature = self.slot_spec.feature()
        for idx, x in enumerate(self.slot_pattern.positions(self.region.width_mm), start=1):
            shapes.append(
                rect_shape(
                    (x, 0.0),
                    width_mm=self.slot_spec.length_mm,
                    height_mm=self.slot_spec.width_mm,
                    feature=copy.deepcopy(slot_feature),
                    shape_id=f"{self.label}:slot:{idx}",
                )
            )
        if self.band_height_mm > 0.0 and self.band_depth_mm > 0.0:
            band_width = self.region.width_mm + 2.0 * max(0.0, self.band_overtravel_mm)
            shapes.append(
                rect_shape(
                    (0.0, self.band_offset_mm),
                    width_mm=band_width,
                    height_mm=self.band_height_mm,
                    feature={"type": "pocket", "depth_mm": self.band_depth_mm},
                    shape_id=f"{self.label}:band",
                )
            )

        if self.lip_height_mm > 0.0 and self.lip_depth_mm > 0.0:
            half = 0.5 * self.region.height_mm
            lip_half = 0.5 * self.lip_height_mm
            lip_feature = {"type": "pocket", "depth_mm": self.lip_depth_mm}
            lip_width = self.region.width_mm + 2.0 * max(0.0, self.lip_overtravel_mm)
            # top lip
            shapes.append(
                rect_shape(
                    (0.0, half - lip_half),
                    width_mm=lip_width,
                    height_mm=self.lip_height_mm,
                    feature=copy.deepcopy(lip_feature),
                    shape_id=f"{self.label}:lip:top",
                )
            )
            # bottom lip
            shapes.append(
                rect_shape(
                    (0.0, -half + lip_half),
                    width_mm=lip_width,
                    height_mm=self.lip_height_mm,
                    feature=copy.deepcopy(lip_feature),
                    shape_id=f"{self.label}:lip:bottom",
                )
            )
        return shapes


@dataclass(frozen=True)
class ClampBarConfig:
    length_mm: float
    height_a_mm: float
    height_b_mm: float
    gap_mm: float
    slot_spec: SlotSpec
    slot_pattern: SlotPattern
    band_a_mm: float
    band_a_depth: float
    band_a_overtravel_mm: float
    band_b_mm: float
    band_b_depth: float
    band_b_overtravel_mm: float
    band_a_offset_mm: float
    band_b_offset_mm: float
    lip_a_mm: float
    lip_a_depth: float
    lip_b_mm: float
    lip_b_depth: float
    lip_a_overtravel_mm: float
    lip_b_overtravel_mm: float
    include_bar_a: bool
    include_bar_b: bool

    @classmethod
    def from_params(cls, params: Dict[str, Any]) -> "ClampBarConfig":
        slot_depth = params.get("slot_depth", "through")
        slot_spec = SlotSpec(
            length_mm=float(params.get("slot_len_mm", 8.0)),
            width_mm=float(params.get("slot_w_mm", 10.0)),
            depth=slot_depth if slot_depth == "through" else float(slot_depth),
        )
        raw_count = params.get("slot_count")
        count = int(raw_count) if isinstance(raw_count, (int, float)) else None
        raw_pitch = params.get("slot_pitch_mm")
        pitch = float(raw_pitch) if raw_pitch is not None else None
        slot_pattern = SlotPattern(
            mode=str(params.get("slot_mode", "count")).lower(),
            count=count,
            pitch_mm=pitch,
            margin_mm=float(params.get("slot_edge_margin_mm", 20.0)),
            min_slots=int(params.get("slot_min", 2)),
            max_slots=int(params.get("slot_max", 12)),
        )
        return cls(
            length_mm=float(params.get("length_mm", 0.0)),
            height_a_mm=float(params.get("height_a_mm", 0.0)),
            height_b_mm=float(params.get("height_b_mm", 0.0)),
            gap_mm=float(params.get("gap_mm", 10.0)),
            slot_spec=slot_spec,
            slot_pattern=slot_pattern,
            band_a_mm=float(params.get("band_a_h_mm", 0.0) or 0.0),
            band_a_depth=float(params.get("band_a_depth_mm", 0.0) or 0.0),
            band_a_overtravel_mm=float(params.get("band_a_overtravel_mm", 0.0) or 0.0),
            band_a_offset_mm=float(params.get("band_a_offset_mm", 0.0) or 0.0),
            band_b_mm=float(params.get("band_b_h_mm", 0.0) or 0.0),
            band_b_depth=float(params.get("band_b_depth_mm", 0.0) or 0.0),
            band_b_overtravel_mm=float(params.get("band_b_overtravel_mm", 0.0) or 0.0),
            band_b_offset_mm=float(params.get("band_b_offset_mm", 0.0) or 0.0),
            lip_a_mm=float(params.get("lip_a_h_mm", 0.0) or 0.0),
            lip_a_depth=float(params.get("lip_a_depth_mm", 0.0) or 0.0),
            lip_b_mm=float(params.get("lip_b_h_mm", 0.0) or 0.0),
            lip_b_depth=float(params.get("lip_b_depth_mm", 0.0) or 0.0),
            lip_a_overtravel_mm=float(params.get("lip_a_overtravel_mm", 0.0) or 0.0),
            lip_b_overtravel_mm=float(params.get("lip_b_overtravel_mm", 0.0) or 0.0),
            include_bar_a=bool(params.get("include_bar_a", True)),
            include_bar_b=bool(params.get("include_bar_b", True)),
        )

    def compose(self) -> List[Dict[str, Any]]:
        include_a = self.include_bar_a and self.height_a_mm > 0.0
        include_b = self.include_bar_b and self.height_b_mm > 0.0

        if self.length_mm <= 0.0 or (not include_a and not include_b):
            return []

        shapes: List[Dict[str, Any]] = []

        def _bar(label: str, height: float, band_h: float, band_depth: float,
                  band_offset: float, band_overtravel: float, lip_h: float, lip_depth: float,
                  lip_overtravel: float) -> BarSpec:
            return BarSpec(
                label=label,
                region=CenterRegion(width_mm=self.length_mm, height_mm=height),
                slot_spec=self.slot_spec,
                slot_pattern=self.slot_pattern,
                band_height_mm=band_h,
                band_depth_mm=band_depth,
                band_offset_mm=float(band_offset),
                band_overtravel_mm=float(band_overtravel),
                lip_height_mm=lip_h,
                lip_depth_mm=lip_depth,
                lip_overtravel_mm=float(lip_overtravel),
            )

        if include_a and include_b:
            y_a = -0.5 * (self.height_b_mm + self.gap_mm)
            y_b = +0.5 * (self.height_a_mm + self.gap_mm)
            for shape in _bar(
                "A",
                self.height_a_mm,
                self.band_a_mm,
                self.band_a_depth,
                self.band_a_offset_mm,
                self.band_a_overtravel_mm,
                self.lip_a_mm,
                self.lip_a_depth,
                self.lip_a_overtravel_mm,
            ).compose():
                shapes.append(_offset_shape(shape, dy=y_a))
            for shape in _bar(
                "B",
                self.height_b_mm,
                self.band_b_mm,
                self.band_b_depth,
                self.band_b_offset_mm,
                self.band_b_overtravel_mm,
                self.lip_b_mm,
                self.lip_b_depth,
                self.lip_b_overtravel_mm,
            ).compose():
                shapes.append(_offset_shape(shape, dy=y_b))
            return shapes

        if include_a:
            for shape in _bar(
                "A",
                self.height_a_mm,
                self.band_a_mm,
                self.band_a_depth,
                self.band_a_offset_mm,
                self.band_a_overtravel_mm,
                self.lip_a_mm,
                self.lip_a_depth,
                self.lip_a_overtravel_mm,
            ).compose():
                shapes.append(shape)
            return shapes

        # include only B
        for shape in _bar(
            "B",
            self.height_b_mm,
            self.band_b_mm,
            self.band_b_depth,
            self.band_b_offset_mm,
            self.band_b_overtravel_mm,
            self.lip_b_mm,
            self.lip_b_depth,
            self.lip_b_overtravel_mm,
        ).compose():
            shapes.append(shape)
        return shapes


def _offset_shape(shape: Dict[str, Any], *, dy: float) -> Dict[str, Any]:
    clone = copy.deepcopy(shape)
    placement = dict(clone.get("placement", {}))
    cx, cy = placement.get("center_xy_mm", (0.0, 0.0))
    placement["center_xy_mm"] = (float(cx), float(cy) + float(dy))
    clone["placement"] = placement
    return clone


@register_template("ClampBar")
class ClampBar(TemplateBase):
    def expand(self, params: Dict[str, Any], thickness_mm: float) -> List[Dict[str, Any]]:
        cfg = ClampBarConfig.from_params(params)
        return cfg.compose()
