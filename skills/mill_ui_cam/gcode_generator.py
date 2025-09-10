#!/usr/bin/env python3
"""G-code generator (circle-first, Z-safe, single-root paths).

- Projects live under one root: PROJECTS_ROOT
- STEP is resolved strictly from <project>/output/<part-or-final.step>
- Z moves are referenced to STOCK TOP (material sits above XY)
- Profile op:
    * If JSON provides a circle (center + radius/diameter), use it.
    * Else, detect the primary XY circle from the STEP and cut that.
    * No bbox rectangle fallback.

Tunable heights:
  SAFE_Z_OFFSET_MM, CLEARANCE_Z_OFFSET_MM
"""

from __future__ import annotations
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import json
import math

# ---- Single place to define project directory pattern ------------------------
PROJECTS_ROOT: Path = Path("memories") / "cam_projects" / "sheet_layouts"

# ---- Easy-to-tune Z offsets (relative to STOCK TOP) -------------------------
SAFE_Z_OFFSET_MM: float = 5.0       # Rapids/retracts at (stock_top + SAFE_Z_OFFSET_MM)
CLEARANCE_Z_OFFSET_MM: float = 1.0  # Links at (stock_top + CLEARANCE_Z_OFFSET_MM)


class GCodeGenerator:
    """G-code generator for CNC operations on flat stock."""

    def __init__(self, decimals: int = 3) -> None:
        self.decimals = decimals
        self._stock_top_z: Optional[float] = None
        self._stock_bottom_z: Optional[float] = None
        self.safe_z_offset: float = SAFE_Z_OFFSET_MM
        self.clearance_z_offset: float = CLEARANCE_Z_OFFSET_MM
        self._active_step_path: Optional[Path] = None

    # -------------------- Public API --------------------

    def process_project(self, project: str) -> List[Path]:
        """
        Layout under PROJECTS_ROOT / <project>:
          - CAM/<project>_operations.json (preferred) or CAM/operations.json
          - output/<part-or-final.step>
        """
        proj_dir = PROJECTS_ROOT / project
        cam_dir = proj_dir / "CAM"

        ops_path = self._resolve_operations_file(cam_dir, project)
        if not ops_path.exists():
            raise FileNotFoundError(f"Operations not found: {ops_path}")

        with ops_path.open("r", encoding="utf-8") as f:
            ops_doc = json.load(f)

        # Resolve STEP strictly from project/output/
        step_path = self._resolve_step_path(ops_doc, proj_dir)
        if not step_path.exists():
            raise FileNotFoundError(
                f"STEP not found: {step_path}\n"
                "Expected the STEP in the project's 'output/' folder."
            )
        self._active_step_path = step_path

        # Configure stock Z from STEP bounds (material sits above XY)
        self._configure_stock_from_step(step_path)

        # Emit program
        program_name = ops_doc.get("program_name", project)
        gcode_out = cam_dir / f"{program_name}.nc"
        gcode_out.parent.mkdir(parents=True, exist_ok=True)

        lines: List[str] = []
        lines.extend(self._program_preamble(program_name))

        for op in ops_doc.get("operations", []):
            lines.extend(self._generate_operation(op))

        lines.extend(self._program_postamble())

        with gcode_out.open("w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

        return [gcode_out]

    # -------------------- Resolve files --------------------

    def _resolve_operations_file(self, cam_dir: Path, project: str) -> Path:
        preferred = cam_dir / f"{project}_operations.json"
        fallback = cam_dir / "operations.json"
        return preferred if preferred.exists() else fallback

    def _resolve_step_path(self, ops_doc: Dict[str, Any], proj_dir: Path) -> Path:
        """
        Strict resolver: STEP must live under <project>/output/<name>.
        <name> from first op's 'part' (basename only), else 'final.step'.
        """
        step_name = "final.step"
        for op in ops_doc.get("operations", []):
            part = (op.get("part") or "").strip()
            if part:
                step_name = Path(part).name  # ignore any directories; enforce output/
                break
        return proj_dir / "output" / step_name

    # -------------------- Stock config (from STEP bounds) --------------------

    def _configure_stock_from_step(self, step_path: Path) -> None:
        from skills.mill_ui_cam.step_geometry_extractor import get_step_bounds
        (min_x, min_y, min_z), (max_x, max_y, max_z) = get_step_bounds(step_path)
        
        # Fix: Interpret the STEP as if it needs to be flipped up
        thickness = abs(max_z - min_z)
        self._stock_top_z = thickness  # Now +19
        self._stock_bottom_z = 0.0      # Now 0

    # -------------------- Z helpers (always reference STOCK TOP) --------------------

    def z_top(self) -> float:
        assert self._stock_top_z is not None, "Stock not configured"
        return self._stock_top_z

    def z_bottom(self) -> float:
        assert self._stock_bottom_z is not None, "Stock not configured"
        return self._stock_bottom_z

    def z_safe(self) -> float:
        return self.z_top() + self.safe_z_offset

    def z_clear(self) -> float:
        return self.z_top() + self.clearance_z_offset

    def clamp_to_bottom(self, target_z: float) -> float:
        return max(self.z_bottom(), target_z)

    def fmt(self, v: float) -> str:
        return f"{v:.{self.decimals}f}"

    # -------------------- Program wrapper --------------------

    def _program_preamble(self, name: str) -> List[str]:
        return [
            f"(Program: {name})",
            "(Units: mm, Absolute positioning, XY plane)",
            "(All Z heights referenced to STOCK TOP)",
            "G90 G17 G21",
            f"G0 Z{self.fmt(self.z_safe())}",
        ]

    def _program_postamble(self) -> List[str]:
        return [
            f"G0 Z{self.fmt(self.z_safe())}",
            "G0 X0 Y0",
            "M5",
            "M30",
        ]

    # -------------------- Operation generation --------------------

    def _generate_operation(self, op: Dict[str, Any]) -> List[str]:
        kind = (op.get("type") or op.get("strategy") or "").strip().lower()
        if kind in ("profile", "profile_cutting"):
            return self._generate_profile(op)
        if kind in ("drill", "helical_boring"):
            return self._generate_drill(op)
        if kind == "pocket":
            return self._generate_pocket(op)
        return [f"(Unknown op type/strategy: {kind})"]

    # ---- Common motion helpers ----

    def _rapid_xy(self, x: float, y: float) -> List[str]:
        return [f"G0 Z{self.fmt(self.z_safe())}", f"G0 X{self.fmt(x)} Y{self.fmt(y)}"]

    def _link_clear(self) -> List[str]:
        return [f"G1 Z{self.fmt(self.z_clear())}"]

    def _touch_top(self, plunge_mm_min: float) -> List[str]:
        return [f"G1 Z{self.fmt(self.z_top())} F{self.fmt(plunge_mm_min)}"]

    def _stepdown_to(self, target_bottom: float, stepdown: float, plunge_mm_min: float) -> List[str]:
        lines: List[str] = []
        current = self.z_top()
        bottom = self.clamp_to_bottom(target_bottom)
        while current > bottom + 1e-6:
            next_z = max(bottom, current - stepdown)
            lines.append(f"G1 Z{self.fmt(next_z)} F{self.fmt(plunge_mm_min)}")
            current = next_z
        return lines

    # -------------------- Circle-first profile --------------------

    def _generate_profile(self, op: Dict[str, Any]) -> List[str]:
        """
        Profile priority:
          1) Explicit circle in op (center + radius/diameter)
          2) Detect primary XY circle from STEP
          3) If neither available -> error (no bbox fallback)
        """
        p = op.get("parameters", {}) or {}
        plunge = float(p.get("plunge_rate_mm_min", 200))
        feed   = float(p.get("feed_rate_mm_min", 600))
        stepdown = float(p.get("depth_per_pass_mm", p.get("stepdown_mm", 1.5)))
        depth   = float(p.get("depth_mm", 0.0))
        target_bottom = self.z_top() - depth if depth > 0 else self.z_bottom()

        # 1) Try explicit circle fields
        circle = op.get("circle", {}) or {}
        cx = circle.get("center_x")
        cy = circle.get("center_y")
        r  = circle.get("radius_mm")
        d  = circle.get("diameter_mm")
        if (cx is not None and cy is not None) and (r is not None or d is not None):
            radius = float(r) if r is not None else float(d) / 2.0
            return self._emit_circle_profile(float(cx), float(cy), radius, feed, plunge, stepdown, target_bottom)

        # 2) Detect from STEP
        assert self._active_step_path is not None, "STEP not set"
        from .step_geometry_extractor import find_circles_xy
        circles = find_circles_xy(self._active_step_path)
        if circles:
            # choose the largest XY circle (common case: outer/primary feature)
            c = max(circles, key=lambda c_: c_["radius_mm"])
            return self._emit_circle_profile(c["center_x"], c["center_y"], c["radius_mm"], feed, plunge, stepdown, target_bottom)

        # 3) Nothing to cut
        return ["(Profile: no circle in JSON and none found in STEP)"]

    def _emit_circle_profile(
        self,
        cx: float,
        cy: float,
        radius: float,
        feed: float,
        plunge: float,
        stepdown: float,
        target_bottom: float,
    ) -> List[str]:
        """Emit a circular profile using two G2 arcs per level (full 360°)."""
        sx = cx + radius
        sy = cy
        lines: List[str] = [f"(Profile: circle cx={self.fmt(cx)} cy={self.fmt(cy)} r={self.fmt(radius)})"]

        # Go to start at clearance, touch top
        lines.extend(self._rapid_xy(sx, sy))
        lines.extend(self._link_clear())
        lines.extend(self._touch_top(plunge))

        # Stepdowns
        current = self.z_top()
        bottom = self.clamp_to_bottom(target_bottom)
        while current > bottom + 1e-6:
            next_z = max(bottom, current - stepdown)
            # Plunge to depth for this pass
            lines.append(f"G1 Z{self.fmt(next_z)} F{self.fmt(plunge)}")
            # Two half-circle CW arcs (G2) to make a full circle
            # First half: to leftmost point
            lines.append(
                f"G2 X{self.fmt(cx - radius)} Y{self.fmt(cy)} "
                f"I{self.fmt(-radius)} J{self.fmt(0.0)} F{self.fmt(feed)}"
            )
            # Second half: back to start
            lines.append(
                f"G2 X{self.fmt(cx + radius)} Y{self.fmt(cy)} "
                f"I{self.fmt(radius)} J{self.fmt(0.0)} F{self.fmt(feed)}"
            )
            current = next_z

        lines.extend(self._link_clear())
        return lines

    # -------------------- Other ops (kept minimal) --------------------

    def _generate_drill(self, op: Dict[str, Any]) -> List[str]:
        p = op.get("parameters", {}) or {}
        holes = op.get("positions", [])  # optional; may be empty
        plunge = float(p.get("plunge_rate_mm_min", 200))
        stepdown = float(p.get("depth_per_pass_mm", p.get("stepdown_mm", 2.0)))
        depth = float(p.get("depth_mm", 0.0))  # >0 => absolute depth from top; else bottom
        target_bottom = self.z_top() - depth if depth > 0 else self.z_bottom()

        lines: List[str] = [f"(Drilling: {len(holes)} holes)"]
        for h in holes:
            x = float(h["x"]); y = float(h["y"])
            lines.extend(self._rapid_xy(x, y))
            lines.extend(self._link_clear())
            lines.extend(self._touch_top(plunge))
            lines.extend(self._stepdown_to(target_bottom, stepdown, plunge))
            lines.extend(self._link_clear())
        return lines

    def _generate_pocket(self, op: Dict[str, Any]) -> List[str]:
        p = op.get("parameters", {}) or {}
        center = op.get("center", {"x": 0, "y": 0})
        plunge = float(p.get("plunge_rate_mm_min", 200))
        stepdown = float(p.get("depth_per_pass_mm", p.get("stepdown_mm", 1.0)))
        depth = float(p.get("depth_mm", 2.0))
        target_bottom = self.z_top() - depth if depth > 0 else self.z_bottom()

        cx = float(center["x"]); cy = float(center["y"])

        lines: List[str] = ["(Pocket)"]
        lines.extend(self._rapid_xy(cx, cy))
        lines.extend(self._link_clear())
        lines.extend(self._touch_top(plunge))
        lines.extend(self._stepdown_to(target_bottom, stepdown, plunge))
        lines.extend(self._link_clear())
        return lines
