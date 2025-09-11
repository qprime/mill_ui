# path: skills/mill_ui/tests/unit/test_strategies.py
import unittest
from skills.mill_ui.api.cad import rectangle
from skills.mill_ui.cam.model.tool import Tool
from skills.mill_ui.cam.model.material import Material
from skills.mill_ui.cam.model.machine import Machine
from skills.mill_ui.cam.model.stock import Stock
from skills.mill_ui.cam.model.setup import Setup
from skills.mill_ui.cam.path.strategies import (
    onion_skin_then_finish,
    profile_outline_with_tabs,
    pocket_then_onion_skin_profile,
)

class TestStrategies(unittest.TestCase):
    def setUp(self):
        tool = Tool(name="1/4in", diameter=6.35)
        self.setup = Setup(
            stock=Stock(100,100,12.7),
            tool=tool,
            material=Material(),
            machine=Machine(),
            safe_z=6.0,
        )
        self.shape = rectangle(20, 10)

    def test_onion_skin_then_finish(self):
        moves = onion_skin_then_finish(self.shape, self.setup, total_depth_mm=6.0, skin_mm=0.5, spring_pass=True)
        zs = [m.get("z") for m in moves if m.get("kind") == "cut" and m.get("z") is not None]
        self.assertIn(-5.5, zs)               # rough to 6.0-0.5
        self.assertGreaterEqual(zs.count(-6.0), 2)  # finish + spring pass

    def test_profile_with_tabs(self):
        moves = profile_outline_with_tabs(self.shape, self.setup, depth_mm=6.0, tab_count=2, tab_height_mm=2.0)
        zs = [m.get("z") for m in moves if m.get("kind") == "cut" and m.get("z") is not None]
        self.assertIn(-6.0, zs)
        self.assertTrue(any(z > -6.0 for z in zs))  # tab lift present

    def test_pocket_then_onion_skin_profile(self):
        moves = pocket_then_onion_skin_profile(self.shape, self.setup, total_depth_mm=6.0, skin_mm=0.5, spring_pass=True)
        # Comments prove both stages were emitted
        comments = [m.get("text","") for m in moves if m.get("kind") == "comment"]
        self.assertTrue(any("pocket_raster" in c for c in comments))
        self.assertTrue(any("onion_skin_then_finish" in c for c in comments))
        # Depths: pocket reaches bottom; onion-skin rough is at total-skin; finish at bottom
        zs = sorted({m.get("z") for m in moves if m.get("kind") == "cut" and m.get("z") is not None})
        self.assertIn(-5.5, zs)   # onion-skin rough (6.0 - 0.5)
        self.assertIn(-6.0, zs)   # pocket & finish bottom
