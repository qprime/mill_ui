# path: skills/mill_ui/tests/unit/test_cookbook.py
import unittest
from skills.mill_ui.cad.layout.panel import Panel
from skills.mill_ui.recipes.cookbook.examples import (
    example_progressive_hole_grid,
    example_organizer_tray_rect_islands,
    example_counterbored_holes,
)

class TestCookbookExamples(unittest.TestCase):
    def setUp(self):
        self.panel = Panel(width=300, height=200, thickness=12, safe_z=6.0)
        # Simple 1/8 + 1/4 tool DB
        self.tool_db = [
            {"name": "SmallFlat", "diameter": 3.175, "kind": "flat", "rpm": 14000, "feed_xy": 900, "feed_z": 300},
            {"name": "BigFlat",   "diameter": 6.35,  "kind": "flat", "rpm": 12000, "feed_xy": 800, "feed_z": 280},
        ]

    def _comments(self, moves):
        return [m.get("text","") for m in moves if m.get("kind") == "comment"]

    def _depths(self, moves):
        return [m.get("z") for m in moves if m.get("kind") == "cut" and m.get("z") is not None]

    def test_progressive_hole_grid(self):
        moves, gcode = example_progressive_hole_grid(self.panel, tool_db=self.tool_db)
        comments = self._comments(moves)
        # Should include at least one of these, depending on hole sizes selected
        self.assertTrue(any(tag in c for c in comments for tag in ("drill_peck", "bore_helical", "pocket_circle_concentric")))
        self.assertIn("M3 S", gcode)

    def test_organizer_tray_region_rect_islands(self):
        moves, _ = example_organizer_tray_rect_islands(self.panel, tool_db=self.tool_db, depth_mm=5.0)
        comments = self._comments(moves)
        self.assertTrue(any("pocket_region_rect_raster" in c for c in comments))
        zs = set(self._depths(moves))
        self.assertIn(-5.0, zs)  # bottom depth present

    def test_counterbored_holes(self):
        moves, _ = example_counterbored_holes(self.panel, tool_db=self.tool_db, bore_d_mm=20.0)
        comments = self._comments(moves)
        # Expect a pocket of the bore + a hole op
        self.assertTrue(any(("pocket_circle_concentric" in c) or ("pocket_raster" in c) for c in comments))
        self.assertTrue(any("drill_peck" in c or "bore_helical" in c for c in comments))

if __name__ == "__main__":
    unittest.main()
