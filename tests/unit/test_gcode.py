import unittest
from skills.mill_ui.cam.post.gcode import write_gcode

class TestGcodeWriter(unittest.TestCase):
    def test_mm_units_and_safe_end(self):
        moves = [
            {"kind":"comment","text":"hello(world)"},
            {"kind":"set_rpm","rpm":12000},
            {"kind":"set_feed","feed":800},
            {"kind":"rapid","x":0,"y":0,"z":5},
            {"kind":"cut","x":10,"y":0,"z":0},
            {"kind":"retract","z":5},
        ]
        out = write_gcode(moves, safe_z=6.0, unit="mm", prec=3)
        self.assertIn("(hello[world])", out)  # comment sanitized
        self.assertIn("G21", out)             # mm
        self.assertIn("M3 S12000", out)       # rpm
        self.assertIn("F800.0", out)          # feed
        # final safe Z must be 6.000 (not the prior retract at 5.000)
        self.assertTrue(out.strip().splitlines()[-4].startswith("G0 Z6.000"))

    def test_inch_units(self):
        out = write_gcode([{"kind":"rapid","x":1,"y":2,"z":3}], unit="inch", prec=3)
        self.assertIn("G20", out)  # inch

    def test_unhandled_kind_is_commented(self):
        out = write_gcode([{"kind":"teleport","x":1}], unit="mm")
        self.assertIn("(unhandled move kind: teleport)", out)

    def test_trailing_newline(self):
        out = write_gcode([], unit="mm")
        self.assertTrue(out.endswith("\n"))

if __name__ == "__main__":
    unittest.main()
