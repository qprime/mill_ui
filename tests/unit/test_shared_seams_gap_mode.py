import unittest

from skills.mill_ui.cad.layout.panel import Panel
from skills.mill_ui.compositions import resolve_templates
from skills.mill_ui.apps.compose_cam import _apply_grid_layout
from skills.mill_ui.cam.model.hints import build_cam_hints
from skills.mill_ui.cam.model.material import Material
from skills.mill_ui.cam.model.machine import Machine
from skills.mill_ui.cam.model.stock import Stock
from skills.mill_ui.cam.planner.passes import plan_passes


class TestGapModeSharedSeams(unittest.TestCase):
    def setUp(self):
        # Match your layout.json sheet setup
        self.panel = Panel(width=1225.55, height=1238.25, thickness=19.6)
        self.kerf = 6.35

        # Minimal tool DB: 1/8" and 1/4" (so the planner can pick closest to kerf)
        self.tool_db = [
            {"name": "SmallFlat", "diameter": 3.175, "kind": "flat", "rpm": 14000, "feed_xy": 900, "feed_z": 300},
            {"name": "BigFlat",   "diameter": 6.35,  "kind": "flat", "rpm": 12000, "feed_xy": 800, "feed_z": 280},
        ]

        self.material = Material(name="MDF")
        self.machine = Machine(name="default_grbl")
        self.stock   = Stock(width=self.panel.width, height=self.panel.height, thickness=self.panel.thickness)

    def _make_doors(self):
        # Shaker params trimmed to essentials; matches your door sizing
        params = {"outer_w": 450.0, "outer_h": 600.0, "stile_w": 60.0, "rail_h": 60.0, "panel_recess": 6.0}
        return [
            {"kind": "template", "type": "Shaker", "id": "door_1", "params": dict(params)},
            {"kind": "template", "type": "Shaker", "id": "door_2", "params": dict(params)},
            {"kind": "template", "type": "Shaker", "id": "door_3", "params": dict(params)},
            {"kind": "template", "type": "Shaker", "id": "door_4", "params": dict(params)},
        ]

    def _compose(self, gap_mode: str, gap_clearance_mm: float | None = None):
        items = self._make_doors()
        layout = {"type": "grid", "cols": 2, "rows": 2, "border_mm": 15, "fit": "tight", "gap_mode": gap_mode}
        if gap_clearance_mm is not None:
            layout["gap_clearance_mm"] = float(gap_clearance_mm)

        # Place items according to gap_mode (this sets centers, not geometry)
        _apply_grid_layout(self.panel.width, self.panel.height, layout, items, kerf_hint=self.kerf)

        # Resolve templates -> concrete shapes, then build hints and plan passes
        resolved = resolve_templates(items, sheet_thickness_mm=self.panel.thickness)
        hints = build_cam_hints(items_resolved=resolved, sheet_thickness=self.panel.thickness, kerf_width_mm=self.kerf)

        passes, summary = plan_passes(
            hints,
            tool_db=self.tool_db,
            material=self.material,
            machine=self.machine,
            stock=self.stock,
            safe_z=6.0,
        )
        return passes, summary, hints

    def test_gap_mode_zero_merges_internal_borders(self):
        """
        Expect 4 merged seams in a 2x2 grid:
          - 2 vertical shared cuts (top row, bottom row)
          - 2 horizontal shared cuts (left column, right column)
        """
        _, summary, _ = self._compose("zero")
        self.assertEqual(
            summary.get("merged_seams"),
            4,
            f"expected 4 merged seams for 2x2 grid with gap_mode='zero', got {summary}",
        )

    def test_gap_mode_kerf_has_no_merged_seams(self):
        """
        With kerf spacing, no edges are coincident → no seam merges.
        """
        _, summary, _ = self._compose("kerf")  # default clearance = 0.10 in _apply_grid_layout
        self.assertEqual(
            summary.get("merged_seams"),
            0,
            f"expected 0 merged seams when gap_mode='kerf', got {summary}",
        )

    def test_outer_profile_ids_are_unique_per_template_instance(self):
        """
        Guards against regressions where child ids like 'door:outer' are reused across different doors.
        Unique ids are required for seam detection to consider them *different* rectangles.
        """
        items = self._make_doors()
        layout = {"type": "grid", "cols": 2, "rows": 2, "border_mm": 15, "fit": "tight", "gap_mode": "zero"}
        _apply_grid_layout(self.panel.width, self.panel.height, layout, items, kerf_hint=self.kerf)

        resolved = resolve_templates(items, sheet_thickness_mm=self.panel.thickness)
        hints = build_cam_hints(items_resolved=resolved, sheet_thickness=self.panel.thickness, kerf_width_mm=self.kerf)
        outer_rect_ids = [rec.get("id") for rec in hints.get("profiles", []) if rec.get("shape") == "Rect"]

        self.assertEqual(len(outer_rect_ids), 4, f"expected 4 outer Rect profiles, got {outer_rect_ids}")
        self.assertEqual(
            len(set(outer_rect_ids)),
            4,
            f"outer Rect profile ids must be unique per door; got {outer_rect_ids}",
        )


if __name__ == "__main__":
    unittest.main()
