
from __future__ import annotations

import re
from typing import Any

from core.constants import DepthMode
from layout_ast.layout import LayoutAST, Sheet, Item, Geometry, Placement, Feature


class PMLParseError(Exception):
    def __init__(self, message: str, line_num: int | None = None):
        if line_num is not None:
            super().__init__(f"Line {line_num}: {message}")
        else:
            super().__init__(message)
        self.line_num = line_num


def parse_pml(text: str) -> LayoutAST:
    parser = _PMLParser(text)
    return parser.parse()


class _PMLParser:

    def __init__(self, text: str):
        self.lines = text.splitlines()
        self.line_num = 0


        self.sheet: Sheet | None = None
        self.items: list[Item] = []
        self.project: str | None = None
        self.kerf_width_mm: float | None = None

    def parse(self) -> LayoutAST:
        for line_num, line in enumerate(self.lines, start=1):
            self.line_num = line_num
            line = line.strip()


            if not line or line.startswith("#"):
                continue


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


        if self.sheet is None:
            raise PMLParseError("Missing required 'sheet' declaration")

        return LayoutAST(
            sheet=self.sheet,
            items=tuple(self.items),
            project=self.project,
            kerf_width_mm=self.kerf_width_mm,
        )

    def _parse_sheet(self, line: str) -> None:
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
        if self.project is not None:
            raise PMLParseError("Duplicate 'project' declaration", self.line_num)

        match = re.match(r"project\s+(.+)", line)
        if not match:
            raise PMLParseError("Invalid project syntax. Expected: project <name>", self.line_num)

        self.project = match.group(1).strip()

    def _parse_kerf(self, line: str) -> None:
        if self.kerf_width_mm is not None:
            raise PMLParseError("Duplicate 'kerf' declaration", self.line_num)

        match = re.match(r"kerf\s+([\d.]+)mm", line)
        if not match:
            raise PMLParseError("Invalid kerf syntax. Expected: kerf <width>mm", self.line_num)

        self.kerf_width_mm = float(match.group(1))

    def _parse_rect(self, line: str) -> None:

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

        match = re.match(
            r"circle\s+(\S+)\s+at\s+([\d.]+)mm,([\d.]+)mm\s+diameter\s+([\d.]+)mm\s+(.+)",
            line
        )
        if match:
            shape_id, x, y, diameter, feature_str = match.groups()
            geometry = Geometry(data={"diameter_mm": float(diameter)})
        else:

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
        raise PMLParseError("Template syntax not yet implemented (Phase 2 feature)", self.line_num)

    def _parse_feature(self, feature_str: str) -> Feature:
        feature_str = feature_str.strip()
        parts = feature_str.split()

        if len(parts) < 2:
            raise PMLParseError(f"Invalid feature syntax: {feature_str}", self.line_num)

        feature_type = parts[0]
        depth_str = parts[1]


        if DepthMode.is_through(depth_str):
            depth = DepthMode.THROUGH
            depth_mm = None
        elif depth_str.endswith("mm"):
            depth_val = float(depth_str[:-2])
            depth = str(depth_val)
            depth_mm = depth_val
        else:
            raise PMLParseError(f"Invalid depth syntax: {depth_str}", self.line_num)


        side = None
        idx = 2
        if feature_type == "profile" and len(parts) >= 3:
            if parts[2] in ("inside", "outside", "on"):
                side = parts[2]
                idx = 3


        corner_cleanup_tool_diameter_mm = None
        if feature_type == "pocket" and idx < len(parts):
            if parts[idx] == "corner_cleanup":
                if idx + 1 >= len(parts) or not parts[idx + 1].endswith("mm"):
                    raise PMLParseError(f"Invalid corner_cleanup diameter. Expected 'corner_cleanup <diameter>mm'", self.line_num)
                corner_cleanup_tool_diameter_mm = float(parts[idx + 1][:-2])
                idx += 2


        tab_count = None
        tab_height_mm = None
        tab_width_mm = None
        if feature_type == "profile" and idx < len(parts):
            if parts[idx] == "tabs":

                if idx + 3 >= len(parts):
                    raise PMLParseError(f"Invalid tabs syntax. Expected 'tabs <count> height <height>mm [width <width>mm]'", self.line_num)


                try:
                    tab_count = int(parts[idx + 1])
                    if tab_count <= 0:
                        raise ValueError()
                except ValueError:
                    raise PMLParseError(f"Invalid tab count: {parts[idx + 1]}. Must be a positive integer", self.line_num)


                if parts[idx + 2] != "height":
                    raise PMLParseError(f"Expected 'height' after tab count, got: {parts[idx + 2]}", self.line_num)


                if not parts[idx + 3].endswith("mm"):
                    raise PMLParseError(f"Invalid tab height: {parts[idx + 3]}. Must end with 'mm'", self.line_num)
                try:
                    tab_height_mm = float(parts[idx + 3][:-2])
                    if tab_height_mm <= 0:
                        raise ValueError()
                except ValueError:
                    raise PMLParseError(f"Invalid tab height: {parts[idx + 3]}. Must be a positive number", self.line_num)

                idx += 4


                if idx < len(parts) and parts[idx] == "width":
                    if idx + 1 >= len(parts) or not parts[idx + 1].endswith("mm"):
                        raise PMLParseError(f"Invalid tab width. Expected 'width <width>mm'", self.line_num)
                    try:
                        tab_width_mm = float(parts[idx + 1][:-2])
                        if tab_width_mm <= 0:
                            raise ValueError()
                    except ValueError:
                        raise PMLParseError(f"Invalid tab width: {parts[idx + 1]}. Must be a positive number", self.line_num)
                    idx += 2


        if feature_type not in ("profile", "pocket", "hole", "engrave"):
            raise PMLParseError(f"Unknown feature type: {feature_type}", self.line_num)

        return Feature(
            type=feature_type,
            depth=depth,
            side=side,
            depth_mm=depth_mm,
            corner_cleanup_tool_diameter_mm=corner_cleanup_tool_diameter_mm,
            tab_count=tab_count,
            tab_height_mm=tab_height_mm,
            tab_width_mm=tab_width_mm,
        )
