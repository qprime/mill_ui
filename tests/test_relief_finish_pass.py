from __future__ import annotations

import math

import numpy as np
import pytest

from cam.model.machine import Machine
from cam.model.stock import Stock
from cam.moves import CutMove
from cam.planner.passes import PassAccumulator
from cam.planner.passes.relief.finish import _emit_finish_moves
from cam.planner.passes.relief.kernels import compute_center_z_ball, spherical_cap_kernel
from cam.planner.passes.relief.rough import _plan_one_heightfield
from cam.planner.passes.tools import ToolSelection
from cam.planner.planner_input import HeightfieldFeatureInput
from ir.removal_intent import HeightfieldToolAssignment


def _ball_tool(diameter: float = 3.0, name: str | None = None) -> ToolSelection:
    return ToolSelection(
        name=name or f"ball_{diameter}mm",
        diameter=diameter,
        kind="ball",
        rpm=18000.0,
        feed_xy=2000.0,
        feed_z=300.0,
    )


def _flat_tool(diameter: float = 6.0, name: str | None = None) -> ToolSelection:
    return ToolSelection(
        name=name or f"flat_{diameter}mm",
        diameter=diameter,
        kind="flat",
        rpm=18000.0,
        feed_xy=2000.0,
        feed_z=300.0,
    )


def _feature(width_mm: float = 20.0, height_mm: float = 20.0, depth_mm: float = 3.0) -> HeightfieldFeatureInput:
    return HeightfieldFeatureInput(
        id="hf",
        center_xy_mm=(0.0, 0.0),
        width_mm=width_mm,
        height_mm=height_mm,
        depth_mm=depth_mm,
        image_path="unused",
        white_is_high=True,
        tools=(),
        z_top=0.0,
    )


def _flat_surface(shape: tuple[int, int], z: float) -> np.ndarray:
    return np.full(shape, z, dtype=np.float32)


def _sloped_surface(shape: tuple[int, int], z_top: float, z_bottom: float) -> np.ndarray:
    h, w = shape
    col_grad = np.linspace(z_top, z_bottom, w, dtype=np.float32)
    return np.tile(col_grad, (h, 1))


def _gaussian_bump_surface(shape: tuple[int, int], z_base: float, amplitude: float, sigma_px: float) -> np.ndarray:
    ys, xs = np.mgrid[0 : shape[0], 0 : shape[1]]
    cy, cx = shape[0] / 2.0, shape[1] / 2.0
    g = np.exp(-((xs - cx) ** 2 + (ys - cy) ** 2) / (2.0 * sigma_px * sigma_px))
    out: np.ndarray = (z_base + amplitude * g).astype(np.float32)
    return out


def _max_no_gouge_violation(
    moves: list,
    surface: np.ndarray,
    kernel: np.ndarray,
    x_min: float,
    y_min: float,
    width_mm: float,
    height_mm: float,
) -> float:
    r_px = kernel.shape[0] // 2
    h_px, w_px = surface.shape
    max_violation = 0.0
    for m in moves:
        if not isinstance(m, CutMove) or m.x is None or m.y is None or m.z is None:
            continue
        u = (m.x - x_min) / width_mm
        v = (m.y - y_min) / height_mm
        col_c = int(np.clip(round(u * (w_px - 1)), 0, w_px - 1))
        row_c = int(np.clip(round((1.0 - v) * (h_px - 1)), 0, h_px - 1))
        for di in range(-r_px, r_px + 1):
            for dj in range(-r_px, r_px + 1):
                kz = kernel[r_px + di, r_px + dj]
                if not np.isfinite(kz):
                    continue
                r = row_c + di
                c = col_c + dj
                if 0 <= r < h_px and 0 <= c < w_px:
                    required = float(surface[r, c]) + float(kz)
                    if m.z < required:
                        max_violation = max(max_violation, required - m.z)
    return max_violation


def test_finish_emits_cut_moves_and_is_deterministic():
    tool = _ball_tool(3.0)
    feature = _feature()
    assignment = HeightfieldToolAssignment(tool_name=tool.name, role="finish", stepover_frac=0.3, angle_deg=0.0)
    pitch_mm = 0.5
    shape = (int(feature.height_mm / pitch_mm) + 1, int(feature.width_mm / pitch_mm) + 1)
    surface = _flat_surface(shape, -2.0)
    safe_surface = compute_center_z_ball(surface, pitch_mm, 0.5 * tool.diameter)
    moves1 = _emit_finish_moves(feature, tool, assignment, safe_surface, safe_z=5.0)
    moves2 = _emit_finish_moves(feature, tool, assignment, safe_surface, safe_z=5.0)
    cuts1 = [m for m in moves1 if isinstance(m, CutMove)]
    assert cuts1, "finish should emit at least one CutMove"
    assert moves1 == moves2


def test_finish_never_gouges_flat_surface():
    tool = _ball_tool(3.0)
    feature = _feature()
    assignment = HeightfieldToolAssignment(tool_name=tool.name, role="finish", stepover_frac=0.3, angle_deg=0.0)
    pitch_mm = 0.5
    shape = (int(feature.height_mm / pitch_mm) + 1, int(feature.width_mm / pitch_mm) + 1)
    surface_z = -2.0
    surface = _flat_surface(shape, surface_z)
    radius = 0.5 * tool.diameter
    safe_surface = compute_center_z_ball(surface, pitch_mm, radius)
    moves = _emit_finish_moves(feature, tool, assignment, safe_surface, safe_z=5.0)
    cuts = [m for m in moves if isinstance(m, CutMove) and m.z is not None]
    for move in cuts:
        assert move.z is not None
        assert move.z >= surface_z + radius - 1e-3


def test_finish_never_gouges_bumpy_surface():
    tool = _ball_tool(3.0)
    feature = _feature(width_mm=30.0, height_mm=30.0, depth_mm=4.0)
    assignment = HeightfieldToolAssignment(tool_name=tool.name, role="finish", stepover_frac=0.2, angle_deg=0.0)
    pitch_mm = 0.5
    shape = (int(feature.height_mm / pitch_mm) + 1, int(feature.width_mm / pitch_mm) + 1)
    surface = _gaussian_bump_surface(shape, z_base=-2.0, amplitude=1.5, sigma_px=5.0)
    radius_mm = 0.5 * tool.diameter
    safe_surface = compute_center_z_ball(surface, pitch_mm, radius_mm)
    moves = _emit_finish_moves(feature, tool, assignment, safe_surface, safe_z=5.0)
    kernel = spherical_cap_kernel(radius_mm, pitch_mm)
    violation = _max_no_gouge_violation(
        moves, surface, kernel, -feature.width_mm / 2, -feature.height_mm / 2, feature.width_mm, feature.height_mm
    )
    assert violation <= 1e-3, f"no-gouge violation: {violation:.6f}mm"


def test_finish_never_gouges_rotated_angle():
    tool = _ball_tool(3.0)
    feature = _feature(width_mm=30.0, height_mm=30.0, depth_mm=4.0)
    assignment = HeightfieldToolAssignment(tool_name=tool.name, role="finish", stepover_frac=0.2, angle_deg=37.0)
    pitch_mm = 0.5
    shape = (int(feature.height_mm / pitch_mm) + 1, int(feature.width_mm / pitch_mm) + 1)
    surface = _gaussian_bump_surface(shape, z_base=-2.0, amplitude=1.5, sigma_px=5.0)
    radius_mm = 0.5 * tool.diameter
    safe_surface = compute_center_z_ball(surface, pitch_mm, radius_mm)
    moves = _emit_finish_moves(feature, tool, assignment, safe_surface, safe_z=5.0)
    kernel = spherical_cap_kernel(radius_mm, pitch_mm)
    violation = _max_no_gouge_violation(
        moves, surface, kernel, -feature.width_mm / 2, -feature.height_mm / 2, feature.width_mm, feature.height_mm
    )
    assert violation <= 1e-3, f"rotated no-gouge violation: {violation:.6f}mm"


def test_finish_90deg_is_perpendicular_to_0deg():
    tool = _ball_tool(3.0)
    feature = _feature(width_mm=20.0, height_mm=20.0)
    pitch_mm = 0.5
    shape = (41, 41)
    surface = _flat_surface(shape, -2.0)
    safe_surface = compute_center_z_ball(surface, pitch_mm, 0.5 * tool.diameter)

    a0 = HeightfieldToolAssignment(tool_name=tool.name, role="finish", stepover_frac=0.3, angle_deg=0.0)
    a90 = HeightfieldToolAssignment(tool_name=tool.name, role="finish", stepover_frac=0.3, angle_deg=90.0)
    moves0 = _emit_finish_moves(feature, tool, a0, safe_surface, safe_z=5.0)
    moves90 = _emit_finish_moves(feature, tool, a90, safe_surface, safe_z=5.0)

    def scanline_direction(moves: list) -> tuple[float, float]:
        cuts = [m for m in moves if isinstance(m, CutMove) and m.x is not None and m.y is not None]
        assert len(cuts) >= 2
        x0, y0 = cuts[0].x, cuts[0].y
        x1, y1 = cuts[1].x, cuts[1].y
        assert x0 is not None and y0 is not None and x1 is not None and y1 is not None
        dx = x1 - x0
        dy = y1 - y0
        norm = math.hypot(dx, dy)
        return dx / norm, dy / norm

    dx0, dy0 = scanline_direction(moves0)
    dx90, dy90 = scanline_direction(moves90)
    dot = dx0 * dx90 + dy0 * dy90
    assert abs(dot) < 0.1


def test_finish_on_sloped_surface_tracks_slope():
    tool = _ball_tool(3.0)
    feature = _feature(width_mm=20.0, height_mm=20.0)
    pitch_mm = 0.5
    shape = (41, 41)
    surface = _sloped_surface(shape, z_top=0.0, z_bottom=-3.0)
    safe_surface = compute_center_z_ball(surface, pitch_mm, 0.5 * tool.diameter)
    assignment = HeightfieldToolAssignment(tool_name=tool.name, role="finish", stepover_frac=0.3, angle_deg=0.0)
    moves = _emit_finish_moves(feature, tool, assignment, safe_surface, safe_z=5.0)
    cuts = [m for m in moves if isinstance(m, CutMove) and m.z is not None and m.x is not None]
    assert cuts
    z_values = [m.z for m in cuts if m.z is not None]
    assert max(z_values) > min(z_values)


def test_finish_rejects_missing_angle():
    tool = _ball_tool(3.0)
    feature = _feature()
    assignment = HeightfieldToolAssignment.__new__(HeightfieldToolAssignment)
    object.__setattr__(assignment, "tool_name", tool.name)
    object.__setattr__(assignment, "role", "finish")
    object.__setattr__(assignment, "stepover_frac", 0.3)
    object.__setattr__(assignment, "stepdown_mm", None)
    object.__setattr__(assignment, "angle_deg", None)
    surface = _flat_surface((21, 21), -2.0)
    safe_surface = compute_center_z_ball(surface, 0.5, 1.5)
    with pytest.raises(ValueError, match="angle_deg required"):
        _emit_finish_moves(feature, tool, assignment, safe_surface, safe_z=5.0)


def _dispatch_feature(
    feature: HeightfieldFeatureInput, tool_db: list[ToolSelection], safe_z: float = 5.0
) -> PassAccumulator:
    accumulator = PassAccumulator(
        machine=Machine(name="test"),
        stock=Stock(width=100.0, height=100.0, thickness=20.0),
        safe_z=safe_z,
        prime_spindle=False,
    )
    _plan_one_heightfield(feature, accumulator=accumulator, tool_db=tool_db, safe_z=safe_z)
    return accumulator


def test_dispatch_rough_then_finish_respects_rough_barrier(tmp_path):
    from pathlib import Path

    from PIL import Image

    path = Path(tmp_path) / "g.png"
    size = 64
    xs = np.linspace(-1.0, 1.0, size)
    ys = np.linspace(-1.0, 1.0, size)
    xx, yy = np.meshgrid(xs, ys)
    heights = np.clip(1.0 - np.sqrt(xx * xx + yy * yy), 0.0, 1.0)
    Image.fromarray((heights * 65535).astype(np.uint16), mode="I;16").save(path, format="PNG")

    feature = HeightfieldFeatureInput(
        id="hf",
        center_xy_mm=(0.0, 0.0),
        width_mm=60.0,
        height_mm=60.0,
        depth_mm=4.0,
        image_path=str(path),
        white_is_high=True,
        tools=(
            HeightfieldToolAssignment(tool_name="rough6", role="rough", stepover_frac=0.6, stepdown_mm=2.0),
            HeightfieldToolAssignment(tool_name="ball3", role="finish", stepover_frac=0.15, angle_deg=0.0),
        ),
        z_top=0.0,
    )
    tool_db = [_flat_tool(6.0, "rough6"), _ball_tool(3.0, "ball3")]
    acc = _dispatch_feature(feature, tool_db)

    rough_records = [r for r in acc.passes() if r.op == "heightfield-rough"]
    finish_records = [r for r in acc.passes() if r.op == "heightfield-finish"]
    assert len(rough_records) == 1
    assert len(finish_records) == 1

    rough_zs = [m.z for m in rough_records[0].moves if isinstance(m, CutMove) and m.z is not None]
    finish_zs = [m.z for m in finish_records[0].moves if isinstance(m, CutMove) and m.z is not None]
    assert rough_zs and finish_zs
    assert min(finish_zs) >= min(rough_zs) - 1e-3, (
        f"finish dropped below finest rough: finish_min={min(finish_zs)}, rough_min={min(rough_zs)}"
    )


def test_dispatch_two_finish_tools_second_respects_first_floor(tmp_path):
    from pathlib import Path

    from PIL import Image

    path = Path(tmp_path) / "g.png"
    size = 64
    xs = np.linspace(-1.0, 1.0, size)
    ys = np.linspace(-1.0, 1.0, size)
    xx, yy = np.meshgrid(xs, ys)
    heights = np.clip(1.0 - np.sqrt(xx * xx + yy * yy), 0.0, 1.0)
    Image.fromarray((heights * 65535).astype(np.uint16), mode="I;16").save(path, format="PNG")

    feature = HeightfieldFeatureInput(
        id="hf",
        center_xy_mm=(0.0, 0.0),
        width_mm=60.0,
        height_mm=60.0,
        depth_mm=4.0,
        image_path=str(path),
        white_is_high=True,
        tools=(
            HeightfieldToolAssignment(tool_name="ball6", role="finish", stepover_frac=0.2, angle_deg=0.0),
            HeightfieldToolAssignment(tool_name="ball2", role="finish", stepover_frac=0.15, angle_deg=90.0),
        ),
        z_top=0.0,
    )
    tool_db = [_ball_tool(6.0, "ball6"), _ball_tool(2.0, "ball2")]
    acc = _dispatch_feature(feature, tool_db)

    records = {r.tool_selection.name: r for r in acc.passes() if r.op == "heightfield-finish"}
    assert set(records.keys()) == {"ball6", "ball2"}

    first_zs = [m.z for m in records["ball6"].moves if isinstance(m, CutMove) and m.z is not None]
    second_zs = [m.z for m in records["ball2"].moves if isinstance(m, CutMove) and m.z is not None]
    assert first_zs and second_zs
    assert min(second_zs) >= min(first_zs) - 1e-3, (
        f"second finish dropped below first's floor: min2={min(second_zs)}, min1={min(first_zs)}"
    )


def test_dispatch_finish_rejects_non_ball_tool(tmp_path):
    from pathlib import Path

    from PIL import Image

    path = Path(tmp_path) / "g.png"
    arr = np.full((32, 32), 32000, dtype=np.uint16)
    Image.fromarray(arr, mode="I;16").save(path, format="PNG")

    feature = HeightfieldFeatureInput(
        id="hf",
        center_xy_mm=(0.0, 0.0),
        width_mm=30.0,
        height_mm=30.0,
        depth_mm=3.0,
        image_path=str(path),
        white_is_high=True,
        tools=(HeightfieldToolAssignment(tool_name="flat3", role="finish", stepover_frac=0.15, angle_deg=0.0),),
        z_top=0.0,
    )
    tool_db = [_flat_tool(3.0, "flat3")]
    with pytest.raises(ValueError, match="finish role requires kind='ball'"):
        _dispatch_feature(feature, tool_db)
