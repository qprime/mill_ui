import unittest

from skills.mill_ui.cam.model.material import Material
from skills.mill_ui.cam.model.machine import Machine
from skills.mill_ui.cam.model.stock import Stock
from skills.mill_ui.cam.model.hints import build_cam_hints
from skills.mill_ui.cam.planner.passes import plan_passes
from skills.mill_ui.core import Config


class TestCircleProfilePasses(unittest.TestCase):
    def setUp(self):
        # Simple 1/4" flat tool (exact values don't matter beyond diameter)
        self.tool_db = [
            {"name": "QuarterFlat", "diameter": 6.35, "kind": "flat", "rpm": 12000, "feed_xy": 800, "feed_z": 280}
        ]
        self.material = Material(name="MDF")
        self.machine = Machine(name="default_grbl")
        self.stock = Stock(width=300.0, height=300.0, thickness=12.0)

    def _hints(self, *, side: str):
        # Circle as a PROFILE (not a hole/pocket); depth through the sheet
        items = [{
            "kind": "shape",
            "type": "Circle",
            "id": "C1",
            "geometry": {"diameter_mm": 150.0},
            "placement": {"center_xy_mm": (150.0, 150.0)},
            "feature": {"type": "profile", "side": side, "depth": "through"}
        }]
        return build_cam_hints(
            items_resolved=items,
            sheet_thickness=self.stock.thickness,
            kerf_width_mm=6.35
        )

    def _run(self, *, side: str):
        hints = self._hints(side=side)
        passes, summary = plan_passes(
            hints,
            config=Config(safe_z_mm=6.0),
            tool_db=self.tool_db,
            material=self.material,
            machine=self.machine,
            stock=self.stock,
            safe_z=6.0,
        )
        return passes, summary

    def test_circle_profile_emits_profile_not_pocket(self):
        passes, _ = self._run(side="inside")

        # Must produce a profile pass (and not a pocket)
        ops = {p["op"] for p in passes}
        self.assertIn("profile", ops, "circle profile must produce a profile pass")
        self.assertNotIn("pocket", ops, "circle profile must NOT produce a pocket pass")

        # The profile pass must contain the profile_outline marker and reach full depth
        prof = next(p for p in passes if p["op"] == "profile")
        moves = prof["moves"]
        self.assertTrue(
            any(m.get("kind") == "comment" and "profile_outline" in m.get("text", "") for m in moves),
            "expected profile_outline comment in profile moves"
        )
        cut_zs = [m.get("z") for m in moves if m.get("kind") == "cut" and m.get("z") is not None]
        self.assertTrue(cut_zs and min(cut_zs) <= -self.stock.thickness + 1e-6, "must reach through depth")

        # And it must not contain the circular pocket marker
        self.assertFalse(any(
            m.get("kind") == "comment" and "pocket_circle_concentric" in m.get("text", "")
            for p in passes for m in p["moves"]
        ), "circle profile should not pocket")

    def test_inside_vs_outside_change_path_length(self):
        # Inside/outside should change the XY cut length (≈ +8.8% for ± tool radius on 150mm)
        _, sum_in = self._run(side="inside")
        _, sum_out = self._run(side="outside")

        L_in = next(s["metrics"]["cut_length_xy_mm"] for s in sum_in["passes"] if s["operation"] == "profile")
        L_out = next(s["metrics"]["cut_length_xy_mm"] for s in sum_out["passes"] if s["operation"] == "profile")

        self.assertGreater(L_out, L_in * 1.05, "outside perimeter should be measurably longer than inside")

if __name__ == "__main__":
    unittest.main()
