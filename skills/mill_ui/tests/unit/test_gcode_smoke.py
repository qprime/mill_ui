import unittest
from skills.mill_ui.cam.post.gcode import write_gcode

class TestGcodeSmoke(unittest.TestCase):
    def test_simple(self):
        moves = [
            {"kind":"comment","text":"hello"},
            {"kind":"set_rpm","rpm":12000},
            {"kind":"set_feed","feed":800},
            {"kind":"rapid","x":0,"y":0,"z":5},
            {"kind":"cut","x":10,"y":0,"z":0},
            {"kind":"retract","z":5},
        ]
        out = write_gcode(moves, safe_z=6.0)
        self.assertIn("M3 S12000", out)
        self.assertIn("F800.0", out)
        self.assertIn("G0 Z6.000", out)  # final safe Z
