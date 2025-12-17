"""PML (Panel Machining Language) parser: PML → LayoutAST.

Parses human-readable PML syntax into canonical LayoutAST.
"""

from __future__ import annotations

import re
from typing import Any

from skills.mill_ui.v2.ast.layout import LayoutAST, Sheet, Item, Geometry, Placement, Feature


class PMLParseError(Exception):
    """Raised when PML syntax is invalid."""
    def __init__(self, message: str, line_num: int | None = None):
        if line_num is not None:
            super().__init__(f"Line {line_num}: {message}")
        else:
            super().__init__(message)
        self.line_num = line_num


def parse_pml(text: str) -> LayoutAST:
    """Parse PML text into LayoutAST.

    Args:
        text: PML source text

    Returns:
        Parsed LayoutAST

    Raises:
        PMLParseError: If syntax is invalid
    """
    parser = _PMLParser(text)
    return parser.parse()


class _PMLParser:
    """Internal PML parser implementation."""

    def __init__(self, text: str):
        self.lines = text.splitlines()
        self.line_num = 0

        # Parsing state
        self.sheet: Sheet | None = None
        self.items: list[Item] = []
        self.project: str | None = None
        self.kerf_width_mm: float | None = None

    def parse(self) -> LayoutAST:
        """Parse all lines into LayoutAST."""
        for line_num, line in enumerate(self.lines, start=1):
            self.line_num = line_num
            line = line.strip()

            # Skip blank lines and comments
            if not line or line.startswith("#"):
                continue

            # Parse line by keyword
            if line.startswith("sheet "):
                self._parse_sheet(line)
            elif line.startswith("project "):
                self._parse_project(line)
            elif line.startswith("kerf "):
                self._parse_kerf(line)
            elif line.startswith("rect "):
                self._parse_rect(line)
            elif line.startswith("circle "):
                self._parse_circle(line)
            elif line.startswith("roundedrect "):
                self._parse_roundedrect(line)
            elif line.startswith("template "):
                self._parse_template(line)
            else:
                raise PMLParseError(f"Unknown declaration: {line.split()[0]}", self.line_num)

        # Validate required fields
        if self.sheet is None:
            raise PMLParseError("Missing required 'sheet' declaration")

        return LayoutAST(
            sheet=self.sheet,
            items=tuple(self.items),
            project=self.project,
            kerf_width_mm=self.kerf_width_mm,
        )

    def _parse_sheet(self, line: str) -> None:
        """Parse: sheet <width>mm <height>mm <thickness>mm"""
        if self.sheet is not None:
            raise PMLParseError("Duplicate 'sheet' declaration", self.line_num)

        match = re.match(r"sheet\s+([\d.]+)mm\s+([\d.]+)mm\s+([\d.]+)mm", line)
        if not match:
            raise PMLParseError("Invalid sheet syntax. Expected: sheet <width>mm <height>mm <thickness>mm", self.line_num)

        width, height, thickness = match.groups()
        self.sheet = Sheet(
            width_mm=float(width),
            height_mm=float(height),
            thickness_mm=float(thickness),
        )

    def _parse_project(self, line: str) -> None:
        """Parse: project <name>"""
        if self.project is not None:
            raise PMLParseError("Duplicate 'project' declaration", self.line_num)

        match = re.match(r"project\s+(.+)", line)
        if not match:
            raise PMLParseError("Invalid project syntax. Expected: project <name>", self.line_num)

        self.project = match.group(1).strip()

    def _parse_kerf(self, line: str) -> None:
        """Parse: kerf <width>mm"""
        if self.kerf_width_mm is not None:
            raise PMLParseError("Duplicate 'kerf' declaration", self.line_num)

        match = re.match(r"kerf\s+([\d.]+)mm", line)
        if not match:
            raise PMLParseError("Invalid kerf syntax. Expected: kerf <width>mm", self.line_num)

        self.kerf_width_mm = float(match.group(1))

    def _parse_rect(self, line: str) -> None:
        """Parse: rect <id> at <x>mm,<y>mm size <w>mm,<h>mm <feature>"""
        # Pattern: rect ID at Xmm,Ymm size Wmm,Hmm FEATURE
        match = re.match(
            r"rect\s+(\S+)\s+at\s+([\d.]+)mm,([\d.]+)mm\s+size\s+([\d.]+)mm,([\d.]+)mm\s+(.+)",
            line
        )
        if not match:
            raise PMLParseError(
                "Invalid rect syntax. Expected: rect <id> at <x>mm,<y>mm size <w>mm,<h>mm <feature>",
                self.line_num
            )

        shape_id, x, y, w, h, feature_str = match.groups()
        feature = self._parse_feature(feature_str)

        self.items.append(Item(
            kind="shape",
            type="Rect",
            geometry=Geometry(data={"w_mm": float(w), "h_mm": float(h)}),
            placement=Placement(center_xy_mm=(float(x), float(y))),
            feature=feature,
            shape_id=shape_id,
        ))

    def _parse_circle(self, line: str) -> None:
        """Parse: circle <id> at <x>mm,<y>mm {diameter|radius} <d>mm <feature>"""
        # Try diameter syntax first
        match = re.match(
            r"circle\s+(\S+)\s+at\s+([\d.]+)mm,([\d.]+)mm\s+diameter\s+([\d.]+)mm\s+(.+)",
            line
        )
        if match:
            shape_id, x, y, diameter, feature_str = match.groups()
            geometry = Geometry(data={"diameter_mm": float(diameter)})
        else:
            # Try radius syntax
            match = re.match(
                r"circle\s+(\S+)\s+at\s+([\d.]+)mm,([\d.]+)mm\s+radius\s+([\d.]+)mm\s+(.+)",
                line
            )
            if not match:
                raise PMLParseError(
                    "Invalid circle syntax. Expected: circle <id> at <x>mm,<y>mm {diameter|radius} <d>mm <feature>",
                    self.line_num
                )
            shape_id, x, y, radius, feature_str = match.groups()
            geometry = Geometry(data={"radius_mm": float(radius)})

        feature = self._parse_feature(feature_str)

        self.items.append(Item(
            kind="shape",
            type="Circle",
            geometry=geometry,
            placement=Placement(center_xy_mm=(float(x), float(y))),
            feature=feature,
            shape_id=shape_id,
        ))

    def _parse_roundedrect(self, line: str) -> None:
        """Parse: roundedrect <id> at <x>mm,<y>mm size <w>mm,<h>mm radius <r>mm <feature>"""
        match = re.match(
            r"roundedrect\s+(\S+)\s+at\s+([\d.]+)mm,([\d.]+)mm\s+size\s+([\d.]+)mm,([\d.]+)mm\s+radius\s+([\d.]+)mm\s+(.+)",
            line
        )
        if not match:
            raise PMLParseError(
                "Invalid roundedrect syntax. Expected: roundedrect <id> at <x>mm,<y>mm size <w>mm,<h>mm radius <r>mm <feature>",
                self.line_num
            )

        shape_id, x, y, w, h, radius, feature_str = match.groups()
        feature = self._parse_feature(feature_str)

        self.items.append(Item(
            kind="shape",
            type="RoundedRect",
            geometry=Geometry(data={
                "w_mm": float(w),
                "h_mm": float(h),
                "corner_radius_mm": float(radius),
            }),
            placement=Placement(center_xy_mm=(float(x), float(y))),
            feature=feature,
            shape_id=shape_id,
        ))

    def _parse_template(self, line: str) -> None:
        """Parse: template <TemplateName> <id> params { ... }

        NOTE: Multi-line template parsing is simplified for Phase 2.
        Currently expects single-line param dict syntax.
        """
        raise PMLParseError("Template syntax not yet implemented (Phase 2 feature)", self.line_num)

    def _parse_feature(self, feature_str: str) -> Feature:
        """Parse feature specification from string.

        Supported formats:
        - profile through [inside|outside|on]
        - profile <depth>mm [inside|outside|on]
        - pocket <depth>mm
        - pocket through
        - hole <depth>mm
        - hole through
        - engrave <depth>mm
        """
        feature_str = feature_str.strip()
        parts = feature_str.split()

        if len(parts) < 2:
            raise PMLParseError(f"Invalid feature syntax: {feature_str}", self.line_num)

        feature_type = parts[0]
        depth_str = parts[1]

        # Parse depth
        if depth_str == "through":
            depth = "through"
            depth_mm = None
        elif depth_str.endswith("mm"):
            depth_val = float(depth_str[:-2])
            depth = str(depth_val)
            depth_mm = depth_val
        else:
            raise PMLParseError(f"Invalid depth syntax: {depth_str}", self.line_num)

        # Parse optional side for profiles
        side = None
        if feature_type == "profile" and len(parts) >= 3:
            side = parts[2]
            if side not in ("inside", "outside", "on"):
                raise PMLParseError(f"Invalid profile side: {side}. Must be inside, outside, or on", self.line_num)

        # Validate feature type
        if feature_type not in ("profile", "pocket", "hole", "engrave"):
            raise PMLParseError(f"Unknown feature type: {feature_type}", self.line_num)

        return Feature(
            type=feature_type,
            depth=depth,
            side=side,
            depth_mm=depth_mm,
        )
