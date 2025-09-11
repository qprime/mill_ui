# path: skills/mill_ui/tests/unit/test_planner_pipeline.py
import unittest
from skills.mill_ui.api.cam import write_gcode
from skills.mill_ui.cam.model.material import Material
from skills.mill_ui.cam.model.machine import Machine
from skills.mill_ui.cam.model.stock import Stock
from skills.mill_ui.cam.planner.pipeline import hints_to_moves

class TestPlannerPipeline(unittest.TestCase):
    def test_hints_to_moves_end_to_end(self):
        # Tool DB: 1/8" (3.175mm) and 1/4" (6.35mm)
        tool_db = [
            {"name": "SmallFlat", "diameter": 3.175, "kind": "flat", "rpm": 14000, "feed_xy": 900, "feed_z": 300},
            {"name": "BigFlat",   "diameter": 6.35,  "kind": "flat", "rpm": 12000, "feed_xy": 800, "feed_z": 280},
        ]
        material = Material(name="MDF")
        machine = Machine(name="default_grbl")
        stock = Stock(width=300, height=200, thickness=12)

        hints = {
            "units": "mm",
            "min_channel_width_mm": 6.0,
            "pockets": [
                {"shape": "Rect", "geometry": {"w_mm": 40, "h_mm": 30}, "center_xy_mm": (50, 60), "depth_mm": 3.0}
            ],
            "holes": [
                {"shape": "Circle", "geometry": {"diameter_mm": 5.0}, "center_xy_mm": (100, 50), "depth_mm": 12.0}
            ],
            "profiles": [
                {"shape": "Rect", "geometry": {"w_mm": 60, "h_mm": 40}, "center_xy_mm": (150, 80), "depth_mm": 12.0}
            ],
            "engraves": []
        }

        moves = hints_to_moves(
            hints,
            tool_db=tool_db,
            material=material,
            machine=machine,
            stock=stock,
            safe_z=6.0,
        )
        self.assertTrue(len(moves) > 0)

        gcode = write_gcode(moves, safe_z=6.0)
        # Basic sanity checks
        self.assertIn("G21", gcode)         # mm
        self.assertIn("M3 S", gcode)        # spindle on with rpm at least once
        self.assertTrue(gcode.strip().endswith("(end)"))  # our post footer

if __name__ == "__main__":
    unittest.main()
