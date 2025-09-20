import unittest

from skills.mill_ui.cam.model.material import Material
from skills.mill_ui.cam.model.machine import Machine
from skills.mill_ui.cam.model.stock import Stock
from skills.mill_ui.cam.model.hints import build_cam_hints
from skills.mill_ui.cam.planner.passes import plan_passes


class TestPolylineProfilePasses(unittest.TestCase):
    def setUp(self):
        self.tool_db = [
            {"name": "QuarterFlat", "diameter": 6.35, "kind": "flat", "rpm": 12000, "feed_xy": 800, "feed_z": 280}
        ]
        self.material = Material(name="MDF")
        self.machine = Machine(name="default_grbl")
        self.stock = Stock(width=300.0, height=300.0, thickness=12.0)

    def test_polyline_profile_emits_profile(self):
        # Rectangle-like polyline centered at (100, 120)
        cx, cy = 100.0, 120.0
        w, h = 80.0, 40.0
        pts = [
            (-w/2, -h/2), (w/2, -h/2), (w/2, h/2), (-w/2, h/2), (-w/2, -h/2)
        ]
        items = [{
            "kind": "shape",
            "type": "Polyline",
            "id": "P1",
            "geometry": {"points": pts, "closed": True},
            "placement": {"center_xy_mm": (cx, cy)},
            "feature": {"type": "profile", "depth": "through"}
        }]
        hints = build_cam_hints(items_resolved=items, sheet_thickness=self.stock.thickness, kerf_width_mm=6.35)
        passes, summary = plan_passes(
            hints,
            tool_db=self.tool_db,
            material=self.material,
            machine=self.machine,
            stock=self.stock,
            safe_z=6.0,
        )

        ops = {p["op"] for p in passes}
        self.assertIn("profile", ops)
        prof = next(p for p in passes if p["op"] == "profile")
        self.assertTrue(any(m.get("kind") == "comment" and "profile_outline" in m.get("text", "") for m in prof["moves"]))

