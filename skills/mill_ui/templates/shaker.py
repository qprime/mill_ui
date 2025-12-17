"""ShakerV2 template: Production-ready Shaker cabinet door using v2 AST.

Rebuilds v1 Shaker template functionality using v2's LayoutAST and RemovalIntent pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from skills.mill_ui.layout_ast.layout import LayoutAST, Sheet, Item, Geometry, Placement, Feature


@dataclass(frozen=True)
class Region:
    """Simple centered rectangle helper for panel and anchor math."""

    width: float
    height: float

    @property
    def half_width(self) -> float:
        return self.width * 0.5

    @property
    def half_height(self) -> float:
        return self.height * 0.5

    def anchor_centers(self, offsets: AnchorOffsets) -> list[tuple[float, float]]:
        """Calculate 4-corner anchor positions with offsets."""
        hx, hy = self.half_width, self.half_height
        return [
            (-hx + offsets.left, +hy - offsets.top),  # top-left
            (+hx - offsets.right, +hy - offsets.top),  # top-right
            (-hx + offsets.left, -hy + offsets.bottom),  # bottom-left
            (+hx - offsets.right, -hy + offsets.bottom),  # bottom-right
        ]


@dataclass(frozen=True)
class AnchorOffsets:
    """Offsets from corners for anchor placement."""

    left: float = 0.0
    right: float = 0.0
    top: float = 0.0
    bottom: float = 0.0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AnchorOffsets:
        return cls(
            left=float(data.get("left", 0.0)),
            right=float(data.get("right", 0.0)),
            top=float(data.get("top", 0.0)),
            bottom=float(data.get("bottom", 0.0)),
        )


@dataclass(frozen=True)
class AnchorRecess:
    """Configuration for anchor screw recesses."""

    diameter_mm: float
    extra_depth_mm: float
    offsets: AnchorOffsets

    @classmethod
    def from_params(cls, data: dict[str, Any] | None) -> AnchorRecess | None:
        if not data or not data.get("enabled"):
            return None
        diameter = float(data.get("diameter_mm", 0.0))
        extra_depth = float(data.get("extra_depth_mm", 0.0))
        offsets = AnchorOffsets.from_dict(data.get("offsets_mm") or {})
        if diameter <= 0.0:
            return None
        return cls(diameter_mm=diameter, extra_depth_mm=extra_depth, offsets=offsets)

    def depth_mm(self, panel_recess_mm: float, stock_thickness_mm: float) -> float:
        """Calculate anchor recess depth."""
        requested = panel_recess_mm + self.extra_depth_mm
        return min(stock_thickness_mm, requested)


@dataclass(frozen=True)
class ShakerConfig:
    """Shaker panel configuration derived from parameters."""

    outer: Region
    stile_mm: float
    rail_mm: float
    panel_recess_mm: float
    anchor_recess: AnchorRecess | None

    @classmethod
    def from_params(cls, params: dict[str, Any]) -> ShakerConfig:
        """Parse Shaker parameters into configuration."""
        # Allow sizing by outer OR inner dimensions
        outer_w = float(params.get("outer_w", 0.0))
        outer_h = float(params.get("outer_h", 0.0))
        stile_w = float(params.get("stile_w", 0.0))
        rail_h = float(params.get("rail_h", 0.0))

        if outer_w <= 0.0 or outer_h <= 0.0:
            inner_w = float(params.get("inner_w", 0.0))
            inner_h = float(params.get("inner_h", 0.0))
            if inner_w > 0.0:
                outer_w = max(outer_w, inner_w + 2.0 * max(stile_w, 0.0))
            if inner_h > 0.0:
                outer_h = max(outer_h, inner_h + 2.0 * max(rail_h, 0.0))

        outer = Region(width=outer_w, height=outer_h)
        return cls(
            outer=outer,
            stile_mm=stile_w,
            rail_mm=rail_h,
            panel_recess_mm=float(params.get("panel_recess", 0.0)),
            anchor_recess=AnchorRecess.from_params(params.get("anchor_recess")),
        )

    def panel_region(self) -> Region | None:
        """Calculate inner panel region dimensions."""
        if self.panel_recess_mm <= 0.0:
            return None
        inner_w = self.outer.width - 2.0 * self.stile_mm
        inner_h = self.outer.height - 2.0 * self.rail_mm
        if inner_w <= 0.0 or inner_h <= 0.0:
            return None
        return Region(width=inner_w, height=inner_h)


class ShakerV2:
    """Shaker cabinet door template using v2 AST pipeline.

    Generates LayoutAST with:
    - Outer perimeter profile (through-cut)
    - Optional panel recess pocket
    - Optional anchor screw recesses (4 corners)
    """

    @staticmethod
    def expand_to_ast(params: dict[str, Any], sheet_thickness_mm: float) -> LayoutAST:
        """Expand Shaker template parameters to LayoutAST.

        Args:
            params: Shaker configuration (outer_w, outer_h, stile_w, rail_h, panel_recess, anchor_recess)
            sheet_thickness_mm: Material thickness

        Returns:
            LayoutAST with Shaker panel shapes
        """
        cfg = ShakerConfig.from_params(params)

        if cfg.outer.width <= 0.0 or cfg.outer.height <= 0.0:
            raise ValueError(f"Invalid Shaker dimensions: {cfg.outer.width} x {cfg.outer.height}")

        # Calculate sheet size (outer dimensions + margin)
        margin = 25.0  # 25mm margin on all sides
        sheet_width = cfg.outer.width + 2 * margin
        sheet_height = cfg.outer.height + 2 * margin

        items: list[Item] = []

        # 1) Outer perimeter profile
        items.append(
            Item(
                kind="shape",
                type="Rect",
                geometry=Geometry(data={"w_mm": cfg.outer.width, "h_mm": cfg.outer.height}),
                placement=Placement(center_xy_mm=(sheet_width / 2, sheet_height / 2)),
                feature=Feature(type="profile", depth="through", side="outside"),
                shape_id="door:outer",
            )
        )

        # 2) Optional panel recess pocket
        panel = cfg.panel_region()
        if panel:
            items.append(
                Item(
                    kind="shape",
                    type="Rect",
                    geometry=Geometry(data={"w_mm": panel.width, "h_mm": panel.height}),
                    placement=Placement(center_xy_mm=(sheet_width / 2, sheet_height / 2)),
                    feature=Feature(type="pocket", depth=str(cfg.panel_recess_mm), depth_mm=cfg.panel_recess_mm),
                    shape_id="door:panel",
                )
            )

        # 3) Optional anchor recesses (4 corners)
        if cfg.anchor_recess:
            reference_region = panel or cfg.outer
            anchor_depth = cfg.anchor_recess.depth_mm(cfg.panel_recess_mm, sheet_thickness_mm)

            # Calculate anchor centers relative to sheet center
            sheet_center_x = sheet_width / 2
            sheet_center_y = sheet_height / 2

            for i, (offset_x, offset_y) in enumerate(reference_region.anchor_centers(cfg.anchor_recess.offsets), start=1):
                items.append(
                    Item(
                        kind="shape",
                        type="Circle",
                        geometry=Geometry(data={"diameter_mm": cfg.anchor_recess.diameter_mm}),
                        placement=Placement(center_xy_mm=(sheet_center_x + offset_x, sheet_center_y + offset_y)),
                        feature=Feature(type="hole", depth=str(anchor_depth), depth_mm=anchor_depth),
                        shape_id=f"door:anchor:{i}",
                    )
                )

        return LayoutAST(
            sheet=Sheet(width_mm=sheet_width, height_mm=sheet_height, thickness_mm=sheet_thickness_mm),
            items=tuple(items),
        )
