from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any, List, Tuple, Optional
import math
import random

from skills.mill_ui.compositions.base import (
    TemplateBase,
    register_template,
)

ShapeSpec = Dict[str, Any]
ENGRAVE_TOOL_D_MM = 3.175
POCKET_TOOL_D_MM = 3.175
DEFAULT_TRACK_WIDTH_MM = 3.0
DEFAULT_VEIN_WIDTH_MM = 1.2
_MIN_STEP_MM = 0.25


@dataclass(frozen=True)
class BorderParams:
    outer_w_mm: float
    outer_h_mm: float
    inset_mm: float
    band_mm: float
    mode: str
    track_depth_mm: float
    extras: Dict[str, Any]
    sheet_thickness_mm: float

    @classmethod
    def from_dict(cls, raw: Dict[str, Any], *, sheet_thickness_mm: float) -> "BorderParams":
        outer_w = float(raw.get("outer_w_mm", 0.0))
        outer_h = float(raw.get("outer_h_mm", 0.0))
        inset = max(0.0, float(raw.get("inset_mm", 0.0)))
        band = max(0.0, float(raw.get("band_mm", 0.0)))
        mode = str(raw.get("mode", "vine")).lower()
        track_depth = float(raw.get("track_depth_mm", 0.6))
        track_depth = min(max(track_depth, 0.0), sheet_thickness_mm)
        if outer_w <= 0.0 or outer_h <= 0.0:
            raise ValueError("outer_w_mm and outer_h_mm must be positive")
        if inset <= 0.0:
            raise ValueError("inset_mm must be positive")
        if inset <= band:
            raise ValueError("inset_mm must exceed band_mm")
        if outer_w <= 2.0 * inset or outer_h <= 2.0 * inset:
            raise ValueError("inset_mm too large for outer size")
        extras = {k: v for k, v in raw.items()
                  if k not in {"outer_w_mm", "outer_h_mm", "inset_mm", "band_mm", "mode", "track_depth_mm"}}
        return cls(
            outer_w_mm=outer_w,
            outer_h_mm=outer_h,
            inset_mm=inset,
            band_mm=band,
            mode=mode,
            track_depth_mm=track_depth,
            extras=extras,
            sheet_thickness_mm=sheet_thickness_mm,
        )


@dataclass(frozen=True)
class TrackSegment:
    start: Tuple[float, float]
    tangent: Tuple[float, float]
    normal: Tuple[float, float]
    length: float


class PerimeterTrack:
    def __init__(self, segments: List[TrackSegment]):
        self._segments = segments
        self._cum: List[float] = []
        total = 0.0
        for seg in segments:
            total += seg.length
            self._cum.append(total)
        self.total_length = total

    @property
    def segments(self) -> List[TrackSegment]:
        return self._segments

    def frame_at(self, s: float) -> Tuple[Tuple[float, float], Tuple[float, float], Tuple[float, float], int, float]:
        if not self._segments:
            raise ValueError("empty track")
        total = self.total_length
        if total <= 0.0:
            raise ValueError("track length must be positive")
        s_mod = s % total
        prev = 0.0
        for idx, seg in enumerate(self._segments):
            end = self._cum[idx]
            if s_mod <= end or idx == len(self._segments) - 1:
                offset = s_mod - prev
                px = seg.start[0] + seg.tangent[0] * offset
                py = seg.start[1] + seg.tangent[1] * offset
                return (px, py), seg.tangent, seg.normal, idx, offset
            prev = end
        seg = self._segments[-1]
        return seg.start, seg.tangent, seg.normal, len(self._segments) - 1, 0.0

    def distance_to_corner(self, s: float) -> float:
        _, _, _, idx, offset = self.frame_at(s)
        seg = self._segments[idx]
        return min(offset, seg.length - offset)


def _perimeter_track(outer_w_mm: float, outer_h_mm: float, inset_mm: float) -> PerimeterTrack:
    inner_w = outer_w_mm - 2.0 * inset_mm
    inner_h = outer_h_mm - 2.0 * inset_mm
    if inner_w <= 0.0 or inner_h <= 0.0:
        raise ValueError("inset leaves no interior area")
    half_w = inner_w * 0.5
    half_h = inner_h * 0.5
    bottom_left = (-half_w, -half_h)
    bottom_right = (half_w, -half_h)
    top_right = (half_w, half_h)
    top_left = (-half_w, half_h)
    segments = [
        TrackSegment(start=bottom_left, tangent=(1.0, 0.0), normal=(0.0, 1.0), length=inner_w),
        TrackSegment(start=bottom_right, tangent=(0.0, 1.0), normal=(-1.0, 0.0), length=inner_h),
        TrackSegment(start=top_right, tangent=(-1.0, 0.0), normal=(0.0, -1.0), length=inner_w),
        TrackSegment(start=top_left, tangent=(0.0, -1.0), normal=(1.0, 0.0), length=inner_h),
    ]
    return PerimeterTrack(segments)


@dataclass(frozen=True)
class VineParams:
    amp_mm: float
    wavelength_mm: float
    step_mm: float
    depth_mm: float
    seed: int
    leaf_every_mm: Optional[float]
    leaf_offset_mm: Optional[float]
    leaf_base_d_mm: Optional[float]
    leaf_count: int
    leaf_taper_p: float
    leaf_spacing_mm: float
    leaf_depth_mm: Optional[float]
    leaf_vein_depth_mm: float
    track_width_mm: float
    leaf_vein_width_mm: float
    alternate_side: bool

    @classmethod
    def from_extras(cls, extras: Dict[str, Any], *, params: BorderParams) -> "VineParams":
        amp = float(extras.get("amp_mm", 4.0))
        wavelength = max(float(extras.get("wavelength_mm", 80.0)), 20.0)
        step = max(float(extras.get("step_mm", 1.5)), _MIN_STEP_MM)
        depth = float(extras.get("depth_mm", extras.get("track_depth_mm", params.track_depth_mm)))
        seed = int(extras.get("seed", 0))
        leaf_every = extras.get("leaf_every_mm")
        leaf_offset = extras.get("leaf_offset_mm")
        leaf_base = extras.get("leaf_base_d_mm")
        leaf_count = int(extras.get("leaf_count", 5) or 0)
        leaf_taper = float(extras.get("leaf_taper_p", 1.8))
        leaf_spacing = float(extras.get("leaf_spacing_mm", 0.6))
        leaf_depth = extras.get("leaf_depth_mm")
        leaf_vein_depth = float(extras.get("leaf_vein_depth_mm", 0.5))
        track_width = float(extras.get("track_width_mm", extras.get("line_width_mm", DEFAULT_TRACK_WIDTH_MM)))
        leaf_vein_width = float(extras.get("leaf_vein_width_mm", DEFAULT_VEIN_WIDTH_MM))
        alternate = bool(extras.get("alternate_side", False))
        depth = min(max(depth, 0.0), params.sheet_thickness_mm)
        leaf_depth_val = None
        if leaf_depth is not None:
            leaf_depth_val = min(max(float(leaf_depth), 0.0), params.sheet_thickness_mm)
        leaf_every_val = float(leaf_every) if leaf_every not in (None, "") else None
        leaf_offset_val = float(leaf_offset) if leaf_offset not in (None, "") else None
        leaf_base_val = float(leaf_base) if leaf_base not in (None, "") else None
        track_width = max(0.5, min(track_width, params.inset_mm * 1.5))
        leaf_vein_width = max(0.3, min(leaf_vein_width, track_width))

        return cls(
            amp_mm=max(0.0, amp),
            wavelength_mm=wavelength,
            step_mm=step,
            depth_mm=depth,
            seed=seed,
            leaf_every_mm=leaf_every_val,
            leaf_offset_mm=leaf_offset_val,
            leaf_base_d_mm=leaf_base_val,
            leaf_count=max(0, leaf_count),
            leaf_taper_p=max(0.5, leaf_taper),
            leaf_spacing_mm=max(0.05, leaf_spacing),
            leaf_depth_mm=leaf_depth_val,
            leaf_vein_depth_mm=max(0.0, min(leaf_vein_depth, params.sheet_thickness_mm)),
            track_width_mm=track_width,
            leaf_vein_width_mm=leaf_vein_width,
            alternate_side=alternate,
        )


@dataclass(frozen=True)
class DotParams:
    diameter_mm: float
    pitch_mm: float

    @classmethod
    def from_extras(cls, extras: Dict[str, Any], *, params: BorderParams) -> "DotParams":
        diam = float(extras.get("dot_d_mm", extras.get("dot_diameter_mm", 6.0)))
        pitch = float(extras.get("dot_pitch_mm", 40.0))
        if diam <= 0.0:
            raise ValueError("dot_d_mm must be positive")
        if pitch <= 0.0:
            raise ValueError("dot_pitch_mm must be positive")
        return cls(diameter_mm=diam, pitch_mm=pitch)


@dataclass(frozen=True)
class DashParams:
    length_mm: float
    gap_mm: float
    width_mm: float

    @classmethod
    def from_extras(cls, extras: Dict[str, Any], *, params: BorderParams) -> "DashParams":
        length = float(extras.get("dash_len_mm", 30.0))
        gap = float(extras.get("dash_gap_mm", 12.0))
        width = float(extras.get("dash_width_mm", 4.0))
        if length <= 0.0:
            raise ValueError("dash_len_mm must be positive")
        if width <= 0.0:
            raise ValueError("dash_width_mm must be positive")
        return cls(length_mm=length, gap_mm=max(0.0, gap), width_mm=width)


class VineWave:
    def __init__(self, track: PerimeterTrack, vine: VineParams, *, params: BorderParams):
        rng = random.Random(vine.seed)
        self.track = track
        safe_amp = max(0.0, params.inset_mm - params.band_mm - 0.5 * vine.track_width_mm - 1.0)
        self.amp = min(vine.amp_mm, safe_amp)
        self.vine = vine
        self.phase_primary = rng.uniform(0.0, 2.0 * math.pi)
        self.phase_secondary = rng.uniform(0.0, 2.0 * math.pi)
        self.phase_tertiary = rng.uniform(0.0, 2.0 * math.pi)
        self.scale_secondary = rng.uniform(0.15, 0.35)
        self.scale_tertiary = rng.uniform(0.10, 0.22)
        self.wavelength_secondary = vine.wavelength_mm * rng.uniform(0.45, 0.65)
        self.wavelength_tertiary = vine.wavelength_mm * rng.uniform(1.6, 2.2)
        self.corner_blend_mm = max(15.0, vine.wavelength_mm * 0.2)

    def offset(self, s: float) -> float:
        if self.amp <= 0.0:
            return 0.0
        w = self.vine.wavelength_mm
        arg = (2.0 * math.pi * s / max(w, 1e-3)) + self.phase_primary
        base = math.sin(arg)
        sec = math.sin((2.0 * math.pi * s / max(self.wavelength_secondary, 1e-3)) + self.phase_secondary)
        ter = math.sin((2.0 * math.pi * s / max(self.wavelength_tertiary, 1e-3)) + self.phase_tertiary)
        mod = base + self.scale_secondary * sec + self.scale_tertiary * ter
        mod /= (1.0 + self.scale_secondary + self.scale_tertiary)
        fade = self._corner_fade(s)
        return self.amp * mod * fade

    def _corner_fade(self, s: float) -> float:
        dist = self.track.distance_to_corner(s)
        if dist >= self.corner_blend_mm:
            return 1.0
        return max(0.0, dist / self.corner_blend_mm) ** 0.7


def _sample_vine_polyline(track: PerimeterTrack, vine_wave: VineWave, vine_params: VineParams) -> Tuple[List[Tuple[float, float]], List[float], List[Tuple[float, float]]]:
    total = track.total_length
    step = min(vine_params.step_mm, ENGRAVE_TOOL_D_MM * 0.5)
    step = max(_MIN_STEP_MM, step)
    num_steps = max(12, int(math.ceil(total / step)))
    points: List[Tuple[float, float]] = []
    positions: List[float] = []
    tangents: List[Tuple[float, float]] = []
    for i in range(num_steps + 1):
        s = min(total, i * step)
        if i == num_steps:
            s = total
        (px, py), tangent, normal, _, _ = track.frame_at(s)
        offset = vine_wave.offset(s)
        vx = px + normal[0] * offset
        vy = py + normal[1] * offset
        points.append((round(vx, 6), round(vy, 6)))
        positions.append(s)
        tangents.append(tangent)
    if points and (points[-1][0] != points[0][0] or points[-1][1] != points[0][1]):
        points[-1] = points[0]
    return points, positions, tangents


def _emit_dot_mode(track: PerimeterTrack, params: BorderParams, dot: DotParams) -> List[ShapeSpec]:
    total = track.total_length
    pitch = dot.pitch_mm
    depth = min(params.track_depth_mm, params.sheet_thickness_mm)
    if pitch <= 0.0:
        return []
    shapes: List[ShapeSpec] = []
    s = 0.0
    idx = 1
    while s < total:
        (px, py), _, _, _, _ = track.frame_at(s)
        shapes.append({
            "kind": "shape",
            "type": "Circle",
            "id": f"border:dot:{idx}",
            "geometry": {"diameter_mm": dot.diameter_mm},
            "placement": {"center_xy_mm": (round(px, 6), round(py, 6))},
            "feature": {"type": "pocket", "depth_mm": depth},
        })
        idx += 1
        s += pitch
    return shapes


def _emit_dash_mode(track: PerimeterTrack, params: BorderParams, dash: DashParams) -> List[ShapeSpec]:
    shapes: List[ShapeSpec] = []
    depth = min(params.track_depth_mm, params.sheet_thickness_mm)
    seg_ids = ["bottom", "right", "top", "left"]
    dash_index = 1
    for seg_id, segment in zip(seg_ids, track.segments):
        length = segment.length
        if length <= 0.0:
            continue
        spacing = dash.length_mm + dash.gap_mm
        if spacing <= 0.0:
            count = 1
            spacing = dash.length_mm
        else:
            count = max(1, int(math.floor((length + dash.gap_mm) / spacing)))
        occupied = count * dash.length_mm + max(0, count - 1) * dash.gap_mm
        start_offset = max(0.0, 0.5 * (length - occupied))
        for i in range(count):
            center_offset = start_offset + i * (dash.length_mm + dash.gap_mm) + 0.5 * dash.length_mm
            px = segment.start[0] + segment.tangent[0] * center_offset
            py = segment.start[1] + segment.tangent[1] * center_offset
            width = dash.length_mm if abs(segment.tangent[0]) > 0.0 else dash.width_mm
            height = dash.width_mm if abs(segment.tangent[0]) > 0.0 else dash.length_mm
            shapes.append({
                "kind": "shape",
                "type": "Rect",
                "id": f"border:dash:{seg_id}:{dash_index}",
                "geometry": {"w_mm": width, "h_mm": height},
                "placement": {"center_xy_mm": (round(px, 6), round(py, 6))},
                "feature": {"type": "pocket", "depth_mm": depth},
            })
            dash_index += 1
    return shapes


def _emit_leaves_along_vine(track: PerimeterTrack,
                            params: BorderParams,
                            vine: VineParams,
                            vine_wave: VineWave) -> List[ShapeSpec]:
    leaf_every = vine.leaf_every_mm
    leaf_offset = vine.leaf_offset_mm
    leaf_base = vine.leaf_base_d_mm
    leaf_depth = vine.leaf_depth_mm if vine.leaf_depth_mm is not None else params.track_depth_mm
    leaf_depth = min(leaf_depth, params.sheet_thickness_mm)
    if not leaf_every or not leaf_offset or not leaf_base or vine.leaf_count <= 0:
        return []
    max_radius = max(leaf_base * 0.5, 0.0)
    safe_offset = params.inset_mm - params.band_mm - max_radius - (POCKET_TOOL_D_MM * 0.5) - 0.5
    safe_offset = max(0.0, safe_offset)
    offset_val = min(leaf_offset, safe_offset)
    if offset_val <= 0.0:
        return []
    min_corner_clear = max(offset_val + max_radius + 4.0, 18.0)
    shapes: List[ShapeSpec] = []
    total = track.total_length
    s = leaf_every * 0.5
    side_sign = 1.0
    leaf_idx = 1
    min_overlap = POCKET_TOOL_D_MM / 3.0
    while s < total:
        if track.distance_to_corner(s) < min_corner_clear:
            s += leaf_every
            continue
        (base_px, base_py), tangent, normal, _, _ = track.frame_at(s)
        offset = vine_wave.offset(s)
        anchor_x = base_px + normal[0] * offset
        anchor_y = base_py + normal[1] * offset
        n_hat = (normal[0] * side_sign, normal[1] * side_sign)
        t_hat = tangent
        base_center = (anchor_x + n_hat[0] * offset_val, anchor_y + n_hat[1] * offset_val)
        circles, vein = _make_leaf_teardrop(
            base_center,
            t_hat,
            n_hat,
            vine,
            leaf_depth,
            min_overlap,
            params.sheet_thickness_mm,
            leaf_idx,
        )
        if circles:
            shapes.extend(circles)
            if vein:
                shapes.append(vein)
            leaf_idx += 1
            if vine.alternate_side:
                side_sign *= -1.0
        s += leaf_every
    return shapes


def _make_leaf_teardrop(base_center: Tuple[float, float],
                        tangent: Tuple[float, float],
                        normal: Tuple[float, float],
                        vine: VineParams,
                        depth_mm: float,
                        min_overlap_mm: float,
                        sheet_thickness_mm: float,
                        leaf_index: int) -> Tuple[List[ShapeSpec], Optional[ShapeSpec]]:
    count = max(vine.leaf_count, 0)
    if count <= 1:
        return [], None
    base_d = vine.leaf_base_d_mm or 0.0
    if base_d <= 0.0:
        return [], None
    base_radius = base_d * 0.5
    taper = vine.leaf_taper_p
    spacing_nominal = vine.leaf_spacing_mm
    tang_len = math.hypot(*tangent)
    if tang_len == 0.0:
        return [], None
    t_hat = (tangent[0] / tang_len, tangent[1] / tang_len)
    norm_len = math.hypot(*normal)
    if norm_len == 0.0:
        return [], None
    n_hat = (normal[0] / norm_len, normal[1] / norm_len)
    centers: List[Tuple[float, float]] = []
    diameters: List[float] = []
    cumulative = 0.0
    prev_radius = base_radius
    for i in range(count):
        ratio = i / (count - 1)
        radius = base_radius * (1.0 - (ratio ** taper))
        radius = max(radius, base_radius * 0.15)
        if i == 0:
            cumulative = 0.0
        else:
            desired = spacing_nominal
            max_step = max(0.0, (prev_radius + radius) - min_overlap_mm)
            step = min(desired, max_step) if max_step > 0.0 else desired * 0.5
            cumulative += max(step, spacing_nominal * 0.3)
        cx = base_center[0] + t_hat[0] * cumulative
        cy = base_center[1] + t_hat[1] * cumulative
        centers.append((cx, cy))
        diameters.append(radius * 2.0)
        prev_radius = radius
    shapes: List[ShapeSpec] = []
    for idx, (center, diameter) in enumerate(zip(centers, diameters), start=1):
        if diameter <= 0.1:
            continue
        shapes.append({
            "kind": "shape",
            "type": "Circle",
            "id": f"border:leaf:{leaf_index}:seg:{idx}",
            "geometry": {"diameter_mm": round(diameter, 4)},
            "placement": {"center_xy_mm": (round(center[0], 6), round(center[1], 6))},
            "feature": {"type": "pocket", "depth_mm": depth_mm},
        })
    vein_shape: Optional[ShapeSpec] = None
    if vine.leaf_vein_depth_mm > 0.0 and len(centers) >= 2:
        vein_depth = min(vine.leaf_vein_depth_mm, sheet_thickness_mm)
        vein_shape = {
            "kind": "shape",
            "type": "Polyline",
            "id": f"border:leaf:{leaf_index}:vein",
            "geometry": {"points": [
                (round(centers[0][0], 6), round(centers[0][1], 6)),
                (round(centers[-1][0], 6), round(centers[-1][1], 6)),
            ]},
            "placement": {"center_xy_mm": (0.0, 0.0)},
            "feature": {
                "type": "engrave",
                "depth_mm": vein_depth,
                "line_width_mm": vine.leaf_vein_width_mm,
            },
        }
    return shapes, vein_shape


def build_border(params: BorderParams) -> List[ShapeSpec]:
    track = _perimeter_track(params.outer_w_mm, params.outer_h_mm, params.inset_mm)
    mode = params.mode
    if mode == "vine" or mode == "double_vine":
        vine_params = VineParams.from_extras(params.extras, params=params)
        vine_wave = VineWave(track, vine_params, params=params)
        points, _, _ = _sample_vine_polyline(track, vine_wave, vine_params)
        vine_shape = {
            "kind": "shape",
            "type": "Polyline",
            "id": "border:vine",
            "geometry": {"points": points},
            "placement": {"center_xy_mm": (0.0, 0.0)},
            "feature": {
                "type": "engrave",
                "depth_mm": vine_params.depth_mm,
                "line_width_mm": vine_params.track_width_mm,
            },
        }
        shapes: List[ShapeSpec] = [vine_shape]
        if mode == "double_vine":
            phase_shift = VineParams.from_extras({
                "amp_mm": params.extras.get("amp_mm", vine_params.amp_mm),
                "wavelength_mm": vine_params.wavelength_mm,
                "step_mm": vine_params.step_mm,
                "depth_mm": vine_params.depth_mm,
                "seed": vine_params.seed + 17,
                "track_width_mm": vine_params.track_width_mm,
            }, params=params)
            secondary_wave = VineWave(track, phase_shift, params=params)
            shifted_points, _, _ = _sample_vine_polyline(track, secondary_wave, phase_shift)
            shapes.append({
                "kind": "shape",
                "type": "Polyline",
                "id": "border:vine:secondary",
                "geometry": {"points": shifted_points},
                "placement": {"center_xy_mm": (0.0, 0.0)},
                "feature": {
                    "type": "engrave",
                    "depth_mm": phase_shift.depth_mm,
                    "line_width_mm": phase_shift.track_width_mm,
                },
            })
        leaf_shapes = _emit_leaves_along_vine(track, params, vine_params, vine_wave)
        shapes.extend(leaf_shapes)
        return shapes
    if mode == "dot":
        dot_params = DotParams.from_extras(params.extras, params=params)
        return _emit_dot_mode(track, params, dot_params)
    if mode == "dash":
        dash_params = DashParams.from_extras(params.extras, params=params)
        return _emit_dash_mode(track, params, dash_params)
    raise ValueError(f"Unsupported border mode: {mode}")


def make(raw_params: Dict[str, Any], *, sheet_thickness_mm: float) -> List[ShapeSpec]:
    params = BorderParams.from_dict(raw_params, sheet_thickness_mm=sheet_thickness_mm)
    return build_border(params)


@register_template("Border")
class BorderTemplate(TemplateBase):
    def expand(self, params: Dict[str, Any], thickness_mm: float) -> List[ShapeSpec]:
        return make(params, sheet_thickness_mm=thickness_mm)
