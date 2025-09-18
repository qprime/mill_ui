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

    def test_feed_restored_after_plunge(self):
        moves = [
            {"kind": "set_feed", "feed": 3500.0},
            {"kind": "cut", "z": -3.0, "feed": 600.0},  # plunge at feed_z
            {"kind": "set_feed", "feed": 3500.0},        # planner re-issues XY feed
            {"kind": "cut", "x": 10.0},                  # XY move should use restored feed
        ]
        out = write_gcode(moves, safe_z=6.0, unit="mm", prec=3)
        lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
        self.assertIn("F3500.0", lines)  # initial feed line present
        self.assertIn("G1 Z-3.000 F600.0", lines)  # plunge feed emitted
        self.assertIn("G1 X10.000 F3500.0", lines)  # XY pass runs at restored feed

        first_xy_index = lines.index("F3500.0")
        plunge_index = lines.index("G1 Z-3.000 F600.0")
        self.assertGreater(plunge_index, first_xy_index)

        # Second XY feed should be re-issued after the plunge
        self.assertGreater(lines.count("F3500.0"), 1)
        second_xy_index = lines.index("F3500.0", first_xy_index + 1)
        self.assertGreater(second_xy_index, plunge_index)

if __name__ == "__main__":
    unittest.main()
