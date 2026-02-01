

from __future__ import annotations

import math
import re
import time
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from validation.core import round_metric


DEFAULT_RAPID_RATE_MM_MIN = 5000.0


@dataclass
class SummaryMetrics:

    total_lines: int = 0
    comment_lines: int = 0
    motion_lines: int = 0
    tool_change_lines: int = 0
    spindle_lines: int = 0
    feed_lines: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_lines": self.total_lines,
            "comment_lines": self.comment_lines,
            "motion_lines": self.motion_lines,
            "tool_change_lines": self.tool_change_lines,
            "spindle_lines": self.spindle_lines,
            "feed_lines": self.feed_lines,
        }


@dataclass
class MotionMetrics:

    g0_count: int = 0
    g1_count: int = 0
    g2_count: int = 0
    g3_count: int = 0
    total_rapid_distance_mm: float = 0.0
    total_feed_distance_mm: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "g0_count": self.g0_count,
            "g1_count": self.g1_count,
            "g2_count": self.g2_count,
            "g3_count": self.g3_count,
            "total_rapid_distance_mm": round_metric(self.total_rapid_distance_mm),
            "total_feed_distance_mm": round_metric(self.total_feed_distance_mm),
        }


@dataclass
class ZProfileMetrics:

    safe_z_mm: float = 0.0
    max_plunge_z_mm: float = 0.0
    unique_cutting_depths: list[float] = field(default_factory=list)
    depth_count: int = 0
    max_single_plunge_mm: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "safe_z_mm": round_metric(self.safe_z_mm),
            "max_plunge_z_mm": round_metric(self.max_plunge_z_mm),
            "unique_cutting_depths": [round_metric(d) for d in self.unique_cutting_depths],
            "depth_count": self.depth_count,
            "max_single_plunge_mm": round_metric(self.max_single_plunge_mm),
        }


@dataclass
class XYBoundsMetrics:

    x_min: float = float("inf")
    x_max: float = float("-inf")
    y_min: float = float("inf")
    y_max: float = float("-inf")

    def to_dict(self) -> dict[str, Any]:

        x_min = self.x_min if self.x_min != float("inf") else 0.0
        x_max = self.x_max if self.x_max != float("-inf") else 0.0
        y_min = self.y_min if self.y_min != float("inf") else 0.0
        y_max = self.y_max if self.y_max != float("-inf") else 0.0
        return {
            "x_min": round_metric(x_min),
            "x_max": round_metric(x_max),
            "y_min": round_metric(y_min),
            "y_max": round_metric(y_max),
        }


@dataclass
class FeedMetrics:

    min_feed_rate: float = float("inf")
    max_feed_rate: float = float("-inf")
    feed_rates_used: list[float] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        min_feed = self.min_feed_rate if self.min_feed_rate != float("inf") else 0.0
        max_feed = self.max_feed_rate if self.max_feed_rate != float("-inf") else 0.0
        return {
            "min_feed_rate": round_metric(min_feed),
            "max_feed_rate": round_metric(max_feed),
            "feed_rates_used": sorted([round_metric(f) for f in self.feed_rates_used]),
        }


@dataclass
class ToolMetrics:

    tool_numbers: list[int] = field(default_factory=list)
    tool_changes: int = 0
    spindle_speeds: list[int] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool_numbers": sorted(self.tool_numbers),
            "tool_changes": self.tool_changes,
            "spindle_speeds": sorted(self.spindle_speeds),
        }


@dataclass
class OperationMetrics:

    profile_passes: int = 0
    pocket_passes: int = 0
    bore_passes: int = 0
    total_passes: int = 0
    operation_names: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile_passes": self.profile_passes,
            "pocket_passes": self.pocket_passes,
            "bore_passes": self.bore_passes,
            "total_passes": self.total_passes,
            "operation_names": self.operation_names,
        }


@dataclass
class TimeEstimateMetrics:

    rapid_time_s: float = 0.0
    feed_time_s: float = 0.0
    total_time_s: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "rapid_time_s": round_metric(self.rapid_time_s),
            "feed_time_s": round_metric(self.feed_time_s),
            "total_time_s": round_metric(self.total_time_s),
        }


@dataclass
class TabMetrics:

    detected_count: int = 0
    tab_heights_mm: list[float] = field(default_factory=list)
    max_cutting_depth_mm: float = 0.0
    tabs_at_max_depth: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "detected_count": self.detected_count,
            "tab_heights_mm": [round_metric(h) for h in self.tab_heights_mm],
            "max_cutting_depth_mm": round_metric(self.max_cutting_depth_mm),
            "tabs_at_max_depth": self.tabs_at_max_depth,
        }


@dataclass
class GCodeMetrics:

    version: str = "1.0.0"
    extraction_time_ms: float = 0.0
    summary: SummaryMetrics = field(default_factory=SummaryMetrics)
    motion: MotionMetrics = field(default_factory=MotionMetrics)
    z_profile: ZProfileMetrics = field(default_factory=ZProfileMetrics)
    xy_bounds: XYBoundsMetrics = field(default_factory=XYBoundsMetrics)
    feeds: FeedMetrics = field(default_factory=FeedMetrics)
    tools: ToolMetrics = field(default_factory=ToolMetrics)
    operations: OperationMetrics = field(default_factory=OperationMetrics)
    time_estimate: TimeEstimateMetrics = field(default_factory=TimeEstimateMetrics)
    tabs: TabMetrics = field(default_factory=TabMetrics)

    def to_dict(self) -> dict[str, Any]:
        return {
            "gcode": {
                "version": self.version,
                "extraction_time_ms": round_metric(self.extraction_time_ms),
                "summary": self.summary.to_dict(),
                "motion": self.motion.to_dict(),
                "z_profile": self.z_profile.to_dict(),
                "xy_bounds": self.xy_bounds.to_dict(),
                "feeds": self.feeds.to_dict(),
                "tools": self.tools.to_dict(),
                "operations": self.operations.to_dict(),
                "time_estimate": self.time_estimate.to_dict(),
                "tabs": self.tabs.to_dict(),
            }
        }


@dataclass
class GCodeConfig:

    rapid_rate_mm_min: float = DEFAULT_RAPID_RATE_MM_MIN
    z_tolerance: float = 0.001

    @classmethod
    def default(cls) -> GCodeConfig:
        return cls()


COMMENT_PATTERN = re.compile(r"^\s*\(.*\)\s*$")
SEMICOLON_COMMENT_PATTERN = re.compile(r"^\s*;.*$")
G_CODE_PATTERN = re.compile(r"G(\d+)", re.IGNORECASE)
M_CODE_PATTERN = re.compile(r"M(\d+)", re.IGNORECASE)
X_PATTERN = re.compile(r"X([+-]?\d*\.?\d+)", re.IGNORECASE)
Y_PATTERN = re.compile(r"Y([+-]?\d*\.?\d+)", re.IGNORECASE)
Z_PATTERN = re.compile(r"Z([+-]?\d*\.?\d+)", re.IGNORECASE)
F_PATTERN = re.compile(r"F(\d*\.?\d+)", re.IGNORECASE)
S_PATTERN = re.compile(r"S(\d+)", re.IGNORECASE)
I_PATTERN = re.compile(r"I([+-]?\d*\.?\d+)", re.IGNORECASE)
J_PATTERN = re.compile(r"J([+-]?\d*\.?\d+)", re.IGNORECASE)
R_PATTERN = re.compile(r"R([+-]?\d*\.?\d+)", re.IGNORECASE)
T_PATTERN = re.compile(r"T(\d+)", re.IGNORECASE)


def extract_gcode_metrics(
    gcode_path: str | Path,
    config: GCodeConfig | None = None,
) -> GCodeMetrics:
    start_time = time.perf_counter()

    if config is None:
        config = GCodeConfig.default()

    gcode_path = Path(gcode_path)
    if not gcode_path.exists():
        raise FileNotFoundError(f"G-code file not found: {gcode_path}")

    with open(gcode_path, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()

    if not lines:
        raise ValueError(f"G-code file is empty: {gcode_path}")


    parser = _GCodeParser(config)
    metrics = parser.parse(lines)

    end_time = time.perf_counter()
    metrics.extraction_time_ms = (end_time - start_time) * 1000

    return metrics


def extract_gcode_metrics_from_content(
    gcode_content: str,
    config: GCodeConfig | None = None,
) -> GCodeMetrics:
    start_time = time.perf_counter()

    if config is None:
        config = GCodeConfig.default()

    lines = gcode_content.splitlines(keepends=True)

    if not lines:
        raise ValueError("G-code content is empty")


    parser = _GCodeParser(config)
    metrics = parser.parse(lines)

    end_time = time.perf_counter()
    metrics.extraction_time_ms = (end_time - start_time) * 1000

    return metrics


extract_gcode_metrics_from_file = extract_gcode_metrics


class _GCodeParser:

    def __init__(self, config: GCodeConfig, lines: list[str] | None = None):
        self.config = config
        self.metrics = GCodeMetrics()
        self._lines = lines


        self.current_x: float = 0.0
        self.current_y: float = 0.0
        self.current_z: float = 0.0
        self.current_feed: float = 0.0
        self.current_mode: int = 0
        self.current_plane: int = 17


        self.z_values: set[float] = set()
        self.feed_rates: set[float] = set()
        self.tool_numbers: set[int] = set()
        self.spindle_speeds: set[int] = set()
        self.operation_names: list[str] = []


        self.last_z: float = 0.0
        self.max_plunge: float = 0.0


        self._warned_g20: bool = False
        self._warned_g91: bool = False
        self._warned_plane: bool = False

    def parse(self, lines: list[str]) -> GCodeMetrics:
        self._lines = lines
        for line in lines:
            self._parse_line(line.strip())

        self._finalize_metrics()
        return self.metrics

    def _parse_line(self, line: str) -> None:
        self.metrics.summary.total_lines += 1


        if not line:
            return


        if COMMENT_PATTERN.match(line) or SEMICOLON_COMMENT_PATTERN.match(line):
            self.metrics.summary.comment_lines += 1
            self._parse_comment(line)
            return


        g_match = G_CODE_PATTERN.search(line)
        if g_match:
            g_code = int(g_match.group(1))
            self._handle_g_code(g_code, line)


        m_match = M_CODE_PATTERN.search(line)
        if m_match:
            m_code = int(m_match.group(1))
            self._handle_m_code(m_code, line)


        if "F" in line.upper():
            f_match = F_PATTERN.search(line)
            if f_match:
                new_feed = float(f_match.group(1))

                if not g_match or g_match.group(1) not in ("0",):
                    self.current_feed = new_feed
                    self.feed_rates.add(new_feed)
                    self.metrics.summary.feed_lines += 1


        t_match = T_PATTERN.search(line)
        if t_match:
            tool_num = int(t_match.group(1))
            if tool_num not in self.tool_numbers:
                if self.tool_numbers:
                    self.metrics.tools.tool_changes += 1
                self.tool_numbers.add(tool_num)
            self.metrics.summary.tool_change_lines += 1

    def _parse_comment(self, line: str) -> None:

        content = line.strip()
        if content.startswith("(") and content.endswith(")"):
            content = content[1:-1].strip()
        elif content.startswith(";"):
            content = content[1:].strip()


        if content.lower() in ("begin", "end", ""):
            return


        lower_content = content.lower()
        if any(op in lower_content for op in ("profile", "pocket", "bore", "drill", "contour")):
            self.operation_names.append(content)


            if "profile" in lower_content or "contour" in lower_content:
                self.metrics.operations.profile_passes += 1
            elif "pocket" in lower_content:
                self.metrics.operations.pocket_passes += 1
            elif "bore" in lower_content or "drill" in lower_content:
                self.metrics.operations.bore_passes += 1

    def _handle_g_code(self, g_code: int, line: str) -> None:
        if g_code in (0, 1, 2, 3):
            self._handle_motion(g_code, line)
        elif g_code == 90:
            pass
        elif g_code == 91:

            if not self._warned_g91:
                warnings.warn(
                    "G91 (incremental mode) detected; metrics assume G90 (absolute). "
                    "Distances and bounds may be incorrect.",
                    RuntimeWarning,
                )
                self._warned_g91 = True
        elif g_code == 17:
            self.current_plane = 17
        elif g_code == 18:
            self.current_plane = 18
            if not self._warned_plane:
                warnings.warn(
                    "G18 (XZ plane) detected; arc distance and bounds assume G17 (XY plane). "
                    "Arc metrics will be inaccurate.",
                    RuntimeWarning,
                )
                self._warned_plane = True
        elif g_code == 19:
            self.current_plane = 19
            if not self._warned_plane:
                warnings.warn(
                    "G19 (YZ plane) detected; arc distance and bounds assume G17 (XY plane). "
                    "Arc metrics will be inaccurate.",
                    RuntimeWarning,
                )
                self._warned_plane = True
        elif g_code == 20:

            if not self._warned_g20:
                warnings.warn(
                    "G20 (inch mode) detected; metrics assume G21 (mm). "
                    "All distance and coordinate values will be incorrect.",
                    RuntimeWarning,
                )
                self._warned_g20 = True
        elif g_code == 21:
            pass
        elif g_code == 94:
            pass

    def _handle_motion(self, g_code: int, line: str) -> None:
        self.metrics.summary.motion_lines += 1


        new_x = self.current_x
        new_y = self.current_y
        new_z = self.current_z

        x_match = X_PATTERN.search(line)
        y_match = Y_PATTERN.search(line)
        z_match = Z_PATTERN.search(line)
        f_match = F_PATTERN.search(line)

        if x_match:
            new_x = float(x_match.group(1))
        if y_match:
            new_y = float(y_match.group(1))
        if z_match:
            new_z = float(z_match.group(1))
        if f_match:
            self.current_feed = float(f_match.group(1))
            self.feed_rates.add(self.current_feed)


        if g_code in (0, 1):
            distance = self._linear_distance(
                self.current_x, self.current_y, self.current_z,
                new_x, new_y, new_z
            )

            self._update_bounds_point(new_x, new_y)
        else:

            distance = self._arc_distance(g_code, line, new_x, new_y, new_z)

            self._update_arc_bounds(g_code, line, new_x, new_y)


        if g_code == 0:
            self.metrics.motion.g0_count += 1
            self.metrics.motion.total_rapid_distance_mm += distance
        elif g_code == 1:
            self.metrics.motion.g1_count += 1
            self.metrics.motion.total_feed_distance_mm += distance
        elif g_code == 2:
            self.metrics.motion.g2_count += 1
            self.metrics.motion.total_feed_distance_mm += distance
        elif g_code == 3:
            self.metrics.motion.g3_count += 1
            self.metrics.motion.total_feed_distance_mm += distance


        if z_match:
            self.z_values.add(new_z)
            plunge = self.current_z - new_z
            if plunge > 0:
                self.max_plunge = max(self.max_plunge, plunge)


        self.current_x = new_x
        self.current_y = new_y
        self.current_z = new_z

    def _linear_distance(
        self, x1: float, y1: float, z1: float,
        x2: float, y2: float, z2: float
    ) -> float:
        return math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2 + (z2 - z1) ** 2)

    def _update_bounds_point(self, x: float, y: float) -> None:
        self.metrics.xy_bounds.x_min = min(self.metrics.xy_bounds.x_min, x)
        self.metrics.xy_bounds.x_max = max(self.metrics.xy_bounds.x_max, x)
        self.metrics.xy_bounds.y_min = min(self.metrics.xy_bounds.y_min, y)
        self.metrics.xy_bounds.y_max = max(self.metrics.xy_bounds.y_max, y)

    def _arc_distance(
        self, g_code: int, line: str,
        end_x: float, end_y: float, end_z: float
    ) -> float:

        i_match = I_PATTERN.search(line)
        j_match = J_PATTERN.search(line)
        r_match = R_PATTERN.search(line)

        start_x, start_y = self.current_x, self.current_y
        z_delta = end_z - self.current_z

        if r_match:

            radius = abs(float(r_match.group(1)))

            chord = math.sqrt((end_x - start_x) ** 2 + (end_y - start_y) ** 2)
            if chord > 2 * radius:

                xy_arc_length = chord
            else:

                angle = 2 * math.asin(min(chord / (2 * radius), 1.0))

                if float(r_match.group(1)) < 0:
                    angle = 2 * math.pi - angle
                xy_arc_length = radius * angle

        elif i_match or j_match:

            i_val = float(i_match.group(1)) if i_match else 0.0
            j_val = float(j_match.group(1)) if j_match else 0.0


            radius = math.sqrt(i_val ** 2 + j_val ** 2)


            center_x = start_x + i_val
            center_y = start_y + j_val


            start_angle = math.atan2(start_y - center_y, start_x - center_x)
            end_angle = math.atan2(end_y - center_y, end_x - center_x)


            if g_code == 2:
                sweep = start_angle - end_angle
            else:
                sweep = end_angle - start_angle


            if sweep <= 0:
                sweep += 2 * math.pi

            xy_arc_length = radius * sweep

        else:

            xy_arc_length = math.sqrt((end_x - start_x) ** 2 + (end_y - start_y) ** 2)


        if abs(z_delta) > 1e-9:
            return math.sqrt(xy_arc_length ** 2 + z_delta ** 2)
        return xy_arc_length

    def _update_arc_bounds(
        self, g_code: int, line: str,
        end_x: float, end_y: float
    ) -> None:

        self._update_bounds_point(self.current_x, self.current_y)
        self._update_bounds_point(end_x, end_y)


        if self.current_plane != 17:
            return


        i_match = I_PATTERN.search(line)
        j_match = J_PATTERN.search(line)
        r_match = R_PATTERN.search(line)

        start_x, start_y = self.current_x, self.current_y

        if r_match:

            r_val = float(r_match.group(1))
            radius = abs(r_val)
            chord = math.sqrt((end_x - start_x) ** 2 + (end_y - start_y) ** 2)
            if chord > 2 * radius or chord < 1e-9:
                return


            mid_x = (start_x + end_x) / 2
            mid_y = (start_y + end_y) / 2


            half_chord = chord / 2
            h = math.sqrt(radius ** 2 - half_chord ** 2)


            dx = end_x - start_x
            dy = end_y - start_y
            perp_x = -dy / chord
            perp_y = dx / chord


            if (g_code == 2) != (r_val < 0):
                center_x = mid_x + h * perp_x
                center_y = mid_y + h * perp_y
            else:
                center_x = mid_x - h * perp_x
                center_y = mid_y - h * perp_y

        elif i_match or j_match:

            i_val = float(i_match.group(1)) if i_match else 0.0
            j_val = float(j_match.group(1)) if j_match else 0.0
            center_x = start_x + i_val
            center_y = start_y + j_val
            radius = math.sqrt(i_val ** 2 + j_val ** 2)

        else:

            return


        start_angle = math.atan2(start_y - center_y, start_x - center_x)
        end_angle = math.atan2(end_y - center_y, end_x - center_x)


        if start_angle < 0:
            start_angle += 2 * math.pi
        if end_angle < 0:
            end_angle += 2 * math.pi


        cardinals = [0, math.pi / 2, math.pi, 3 * math.pi / 2]
        extrema = [
            (center_x + radius, center_y),
            (center_x, center_y + radius),
            (center_x - radius, center_y),
            (center_x, center_y - radius),
        ]

        for angle, (ex, ey) in zip(cardinals, extrema):
            if self._angle_in_arc(angle, start_angle, end_angle, g_code):
                self._update_bounds_point(ex, ey)

    def _angle_in_arc(
        self, angle: float, start: float, end: float, g_code: int
    ) -> bool:
        if g_code == 3:
            if start <= end:
                return start <= angle <= end
            else:
                return angle >= start or angle <= end
        else:
            if start >= end:
                return end <= angle <= start
            else:
                return angle <= end or angle >= start

    def _handle_m_code(self, m_code: int, line: str) -> None:
        if m_code in (3, 4, 5):
            self.metrics.summary.spindle_lines += 1
            s_match = S_PATTERN.search(line)
            if s_match:
                speed = int(s_match.group(1))
                self.spindle_speeds.add(speed)
        elif m_code == 6:
            self.metrics.summary.tool_change_lines += 1

    def _finalize_metrics(self) -> None:

        if self.z_values:
            sorted_z = sorted(self.z_values)
            cutting_depths = [z for z in sorted_z if z < 0]
            safe_z_values = [z for z in sorted_z if z > 0]

            self.metrics.z_profile.safe_z_mm = max(safe_z_values) if safe_z_values else 0.0
            self.metrics.z_profile.max_plunge_z_mm = min(sorted_z) if sorted_z else 0.0


            tolerance = self.config.z_tolerance
            unique_depths = []
            for z in cutting_depths:
                rounded = round(z / tolerance) * tolerance
                if not unique_depths or abs(rounded - unique_depths[-1]) > tolerance:
                    unique_depths.append(rounded)

            self.metrics.z_profile.unique_cutting_depths = unique_depths
            self.metrics.z_profile.depth_count = len(unique_depths)
            self.metrics.z_profile.max_single_plunge_mm = self.max_plunge


        if self.feed_rates:
            self.metrics.feeds.feed_rates_used = sorted(self.feed_rates)
            self.metrics.feeds.min_feed_rate = min(self.feed_rates)
            self.metrics.feeds.max_feed_rate = max(self.feed_rates)


        self.metrics.tools.tool_numbers = sorted(self.tool_numbers)
        self.metrics.tools.spindle_speeds = sorted(self.spindle_speeds)


        self.metrics.operations.total_passes = (
            self.metrics.operations.profile_passes +
            self.metrics.operations.pocket_passes +
            self.metrics.operations.bore_passes
        )
        self.metrics.operations.operation_names = self.operation_names


        rapid_rate = self.config.rapid_rate_mm_min
        rapid_distance = self.metrics.motion.total_rapid_distance_mm
        feed_distance = self.metrics.motion.total_feed_distance_mm


        self.metrics.time_estimate.rapid_time_s = (rapid_distance / rapid_rate) * 60 if rapid_rate > 0 else 0.0


        avg_feed = sum(self.feed_rates) / len(self.feed_rates) if self.feed_rates else 1000.0
        self.metrics.time_estimate.feed_time_s = (feed_distance / avg_feed) * 60 if avg_feed > 0 else 0.0

        self.metrics.time_estimate.total_time_s = (
            self.metrics.time_estimate.rapid_time_s +
            self.metrics.time_estimate.feed_time_s
        )

        if self._lines:
            self.metrics.tabs = _detect_tabs_from_lines(
                self._lines, self.config.z_tolerance
            )


extract_gcode_metrics_from_file = extract_gcode_metrics


def detect_tabs_from_content(
    gcode_content: str,
    z_tolerance: float = 0.01,
) -> TabMetrics:
    lines = gcode_content.splitlines()
    return _detect_tabs_from_lines(lines, z_tolerance)


def detect_tabs_from_file(
    gcode_path: str | Path,
    z_tolerance: float = 0.01,
) -> TabMetrics:
    gcode_path = Path(gcode_path)
    if not gcode_path.exists():
        return TabMetrics()

    with open(gcode_path, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()

    return _detect_tabs_from_lines(lines, z_tolerance)


def _detect_tabs_from_lines(lines: list[str], z_tolerance: float) -> TabMetrics:
    moves = _parse_moves(lines)
    if not moves:
        return TabMetrics()

    cutting_depths = [m["z"] for m in moves if m["z"] < 0 and m["type"] == "feed"]
    if not cutting_depths:
        return TabMetrics()

    max_cutting_depth = min(cutting_depths)

    depth_threshold = max_cutting_depth + z_tolerance

    tabs: list[dict] = []
    tab_heights: list[float] = []
    tabs_not_at_max = False

    i = 0
    while i < len(moves) - 2:
        m0 = moves[i]
        m1 = moves[i + 1]
        m2 = moves[i + 2]

        if m0["type"] != "feed" or m0["z"] > depth_threshold:
            i += 1
            continue

        cutting_z = m0["z"]

        is_lift = (
            m1["type"] == "feed" and
            m1["z"] > cutting_z + z_tolerance and
            m1["z"] < 0
        )

        if not is_lift:
            i += 1
            continue

        lifted_z = m1["z"]

        j = i + 2
        while j < len(moves):
            mj = moves[j]
            if mj["type"] != "feed":
                break
            if abs(mj["z"] - lifted_z) > z_tolerance:
                break
            j += 1

        if j >= len(moves):
            i += 1
            continue

        plunge_move = moves[j] if j < len(moves) else None
        if plunge_move is None:
            i += 1
            continue

        is_plunge = (
            plunge_move["type"] == "feed" and
            plunge_move["z"] < lifted_z - z_tolerance and
            plunge_move["z"] <= cutting_z + z_tolerance
        )

        if is_plunge:
            tab_height = lifted_z - cutting_z
            tabs.append({
                "cutting_z": cutting_z,
                "lifted_z": lifted_z,
                "tab_height": tab_height,
                "line": m0.get("line", 0),
            })
            tab_heights.append(tab_height)

            if cutting_z > max_cutting_depth + z_tolerance:
                tabs_not_at_max = True

            i = j + 1
        else:
            i += 1

    return TabMetrics(
        detected_count=len(tabs),
        tab_heights_mm=tab_heights,
        max_cutting_depth_mm=max_cutting_depth,
        tabs_at_max_depth=not tabs_not_at_max,
    )


def _parse_moves(lines: list[str]) -> list[dict]:
    moves: list[dict] = []
    current_x = 0.0
    current_y = 0.0
    current_z = 0.0
    current_mode = 0

    for line_num, line in enumerate(lines, 1):
        line = line.strip()
        if not line or line.startswith("(") or line.startswith(";"):
            continue

        g_match = G_CODE_PATTERN.search(line)
        if g_match:
            g_code = int(g_match.group(1))
            if g_code in (0, 1, 2, 3):
                current_mode = g_code

        x_match = X_PATTERN.search(line)
        y_match = Y_PATTERN.search(line)
        z_match = Z_PATTERN.search(line)

        has_motion = x_match or y_match or z_match
        if not has_motion:
            continue

        new_x = float(x_match.group(1)) if x_match else current_x
        new_y = float(y_match.group(1)) if y_match else current_y
        new_z = float(z_match.group(1)) if z_match else current_z

        move_type = "rapid" if current_mode == 0 else "feed"

        moves.append({
            "type": move_type,
            "x": new_x,
            "y": new_y,
            "z": new_z,
            "line": line_num,
        })

        current_x = new_x
        current_y = new_y
        current_z = new_z

    return moves
