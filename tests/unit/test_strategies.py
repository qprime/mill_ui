# path: skills/mill_ui/tests/unit/test_strategies.py
from __future__ import annotations
import unittest

from skills.mill_ui.cad.primitives import rectangle
from skills.mill_ui.cad.transforms import Transform2D, place
from skills.mill_ui.cam.model.tool import Tool
from skills.mill_ui.cam.model.material import Material
from skills.mill_ui.cam.model.machine import Machine
from skills.mill_ui.cam.model.stock import Stock
from skills.mill_ui.cam.model.setup import Setup
from skills.mill_ui.cam.path.strategies import (
    onion_skin_then_finish,
    profile_outline_with_tabs,
    pocket_then_finish_profile,
)

class TestStrategies(unittest.TestCase):
    def setUp(self):
        # a 100x60 rect centered at (0,0)
        self.shape = place(rectangle(100.0, 60.0), Transform2D(tx=-50.0, ty=-30.0))
        self.tool = Tool(name="test-1/4", diameter=6.35, kind="flat", rpm=12000, feed_xy=1500, feed_z=300)
        self.material = Material(name="MDF")
        self.machine = Machine(name="test-router")
        self.stock = Stock(width=400.0, height=300.0, thickness=19.0)
        self.setup = Setup(stock=self.stock, tool=self.tool, material=self.material, machine=self.machine, safe_z=6.0)

    def test_onion_skin_then_finish(self):
        moves = onion_skin_then_finish(self.shape, self.setup, total_depth_mm=6.0, skin_mm=0.5, step_down_mm=3.0, spring_pass=True)
        zs = [m.get("z") for m in moves if m.get("kind") == "cut" and m.get("z") is not None]
        self.assertIn(-5.5, zs)               # rough to 6.0 - 0.5
        self.assertGreaterEqual(zs.count(-6.0), 2)  # finish + spring pass

    def test_profile_with_tabs(self):
        moves = profile_outline_with_tabs(self.shape, self.setup, depth_mm=6.0, step_down_mm=3.0, tab_count=2, tab_height_mm=2.0)
        zs = [m.get("z") for m in moves if m.get("kind") == "cut" and m.get("z") is not None]
        self.assertIn(-6.0, zs)                         # bottom reached
        self.assertTrue(any(z > -6.0 for z in zs))      # tab lift present

    def test_pocket_then_finish_profile(self):
        moves = pocket_then_finish_profile(
            self.shape,
            self.setup,
            total_depth_mm=6.0,
            stepover_mm=2.5,
            step_down_mm=3.0,
            cleanup_offset_mm=0.25,
        )
        self.assertTrue(moves, "strategy should produce moves")
        comments = [m.get("text","") for m in moves if m.get("kind") == "comment"]
        self.assertTrue(any("rough pocket" in c for c in comments))
        self.assertTrue(any("finish profile pass" in c for c in comments))
        zs = [m.get("z") for m in moves if m.get("kind") == "cut" and m.get("z") is not None]
        self.assertIn(-6.0, zs)  # bottom depth present

if __name__ == "__main__":
    unittest.main()
