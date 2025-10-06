# path: skills/mill_ui/compositions/cabinets/shaker.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any, List, Optional, Tuple

from skills.mill_ui.compositions.base import TemplateBase, register_template
from skills.mill_ui.compositions.panels.border import make_border_for_frame


def _rect(center: Tuple[float, float], w: float, h: float,
          feature: Dict[str, Any], id_: str) -> Dict[str, Any]:
    cx, cy = float(center[0]), float(center[1])
    return {
        "kind": "shape",
        "type": "Rect",
        "id": id_,
        "geometry": {"w_mm": float(w), "h_mm": float(h)},
        "placement": {"center_xy_mm": (cx, cy)},
        "feature": feature,
    }


def _circle(center: Tuple[float, float], diameter: float,
            feature: Dict[str, Any], id_: str) -> Dict[str, Any]:
    cx, cy = float(center[0]), float(center[1])
    return {
        "kind": "shape",
        "type": "Circle",
        "id": id_,
        "geometry": {"diameter_mm": float(diameter)},
        "placement": {"center_xy_mm": (cx, cy)},
        "feature": feature,
    }


@dataclass(frozen=True)
class Region:
    """Simple centered rectangle helper (used for panel + anchor math)."""

    width: float
    height: float

    @property
    def half_width(self) -> float:
        return float(self.width) * 0.5

    @property
    def half_height(self) -> float:
        return float(self.height) * 0.5

    def anchor_centers(self, offsets: "AnchorOffsets") -> List[Tuple[float, float]]:
        hx, hy = self.half_width, self.half_height
        return [
            (-hx + offsets.left,  +hy - offsets.top),    # top-left
            (+hx - offsets.right, +hy - offsets.top),    # top-right
            (-hx + offsets.left,  -hy + offsets.bottom), # bottom-left
            (+hx - offsets.right, -hy + offsets.bottom), # bottom-right
        ]


@dataclass(frozen=True)
class AnchorOffsets:
    left: float = 0.0
    right: float = 0.0
    top: float = 0.0
    bottom: float = 0.0

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AnchorOffsets":
        return cls(
            left=float(data.get("left", 0.0)),
            right=float(data.get("right", 0.0)),
            top=float(data.get("top", 0.0)),
            bottom=float(data.get("bottom", 0.0)),
        )


@dataclass(frozen=True)
class AnchorRecess:
    diameter_mm: float
    extra_depth_mm: float
    offsets: AnchorOffsets

    @classmethod
    def from_params(cls, data: Optional[Dict[str, Any]]) -> Optional["AnchorRecess"]:
        if not data or not data.get("enabled"):
            return None
        diameter = float(data.get("diameter_mm", 0.0))
        extra_depth = float(data.get("extra_depth_mm", 0.0))
        offsets = AnchorOffsets.from_dict(data.get("offsets_mm") or {})
        if diameter <= 0.0:
            return None
        return cls(diameter_mm=diameter, extra_depth_mm=extra_depth, offsets=offsets)

    def depth_mm(self, panel_recess_mm: float, stock_thickness_mm: float) -> float:
        requested = float(panel_recess_mm) + float(self.extra_depth_mm)
        return min(float(stock_thickness_mm), requested)

    def pockets(self, region: Region, panel_recess: float,
                stock_thickness: float) -> List[Dict[str, Any]]:
        depth = self.depth_mm(panel_recess, stock_thickness)
        feature = {"type": "pocket", "depth_mm": depth}
        return [
            _circle(center, self.diameter_mm, feature, id_=f"door:anchor:{i}")
            for i, center in enumerate(region.anchor_centers(self.offsets), start=1)
        ]


@dataclass(frozen=True)
class ShakerConfig:
    outer: Region
    stile_mm: float
    rail_mm: float
    panel_recess_mm: float
    anchor_recess: Optional[AnchorRecess]

    @classmethod
    def from_params(cls, params: Dict[str, Any]) -> "ShakerConfig":
        # Allow sizing by outer OR inner dimensions. Outer takes precedence when provided.
        outer_w = float(params.get("outer_w", 0.0))
        outer_h = float(params.get("outer_h", 0.0))
        stile_w = float(params.get("stile_w", 0.0))
        rail_h = float(params.get("rail_h", 0.0))

        if outer_w <= 0.0 or outer_h <= 0.0:
            inner_w = float(params.get("inner_w", 0.0))
            inner_h = float(params.get("inner_h", 0.0))
            # Compute missing outer dimensions from inner + stile/rail if available
            if inner_w > 0.0:
                outer_w = max(outer_w, inner_w + 2.0 * max(stile_w, 0.0))
            if inner_h > 0.0:
                outer_h = max(outer_h, inner_h + 2.0 * max(rail_h, 0.0))

        outer = Region(width=float(outer_w), height=float(outer_h))
        return cls(
            outer=outer,
            stile_mm=stile_w,
            rail_mm=rail_h,
            panel_recess_mm=float(params.get("panel_recess", 0.0)),
            anchor_recess=AnchorRecess.from_params(params.get("anchor_recess")),
        )

    def panel_region(self) -> Optional[Region]:
        if self.panel_recess_mm <= 0.0:
            return None
        inner_w = self.outer.width - 2.0 * self.stile_mm
        inner_h = self.outer.height - 2.0 * self.rail_mm
        if inner_w <= 0.0 or inner_h <= 0.0:
            return None
        return Region(width=inner_w, height=inner_h)

    def compose(self, stock_thickness_mm: float) -> List[Dict[str, Any]]:
        shapes: List[Dict[str, Any]] = []

        # 1) Outer perimeter
        shapes.append(
            _rect(
                center=(0.0, 0.0),
                w=self.outer.width,
                h=self.outer.height,
                feature={"type": "profile", "depth": "through", "side": "outside"},
                id_="door:outer",
            )
        )

        # 2) Optional panel recess
        panel = self.panel_region()
        if panel:
            shapes.append(
                _rect(
                    center=(0.0, 0.0),
                    w=panel.width,
                    h=panel.height,
                    feature={"type": "pocket", "depth_mm": self.panel_recess_mm},
                    id_="door:panel",
                )
            )

        # 3) Optional anchor recesses (use panel region if present, otherwise outer)
        if self.anchor_recess:
            reference_region = panel or self.outer
            shapes.extend(
                self.anchor_recess.pockets(
                    region=reference_region,
                    panel_recess=self.panel_recess_mm,
                    stock_thickness=stock_thickness_mm,
                )
            )

        return shapes


@register_template("Shaker")
class Shaker(TemplateBase):
    def expand(self, params: Dict[str, Any], thickness_mm: float) -> List[Dict[str, Any]]:
        cfg = ShakerConfig.from_params(params)
        if cfg.outer.width <= 0.0 or cfg.outer.height <= 0.0:
            return []
        shapes = cfg.compose(stock_thickness_mm=float(thickness_mm))

        border_cfg = params.get("border")
        if isinstance(border_cfg, dict) and border_cfg:
            frame_width_candidates = [v for v in (cfg.stile_mm, cfg.rail_mm) if v > 0.0]
            frame_width = min(frame_width_candidates) if frame_width_candidates else 0.0
            border_shapes = make_border_for_frame(
                outer_w_mm=cfg.outer.width,
                outer_h_mm=cfg.outer.height,
                frame_width_mm=frame_width,
                overrides=border_cfg,
                sheet_thickness_mm=float(thickness_mm),
            )
            shapes.extend(border_shapes)

        return shapes
