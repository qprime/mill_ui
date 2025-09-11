import unittest
from skills.mill_ui.cam.path.toolpath import (
    move_comment, move_set_feed, move_set_rpm, move_rapid, move_cut, move_retract
)

class TestToolpathHelpers(unittest.TestCase):
    def test_comment(self):
        m = move_comment("hi")
        self.assertEqual(m["kind"], "comment")
        self.assertEqual(m["text"], "hi")

    def test_setters(self):
        self.assertEqual(move_set_feed(800)["feed"], 800)
        self.assertEqual(move_set_rpm(12000)["rpm"], 12000)

    def test_motion(self):
        r = move_rapid(x=1, y=2, z=3)
        self.assertEqual((r["x"], r["y"], r["z"]), (1, 2, 3))

        c = move_cut(x=4, y=5, z=-1, feed=700)
        self.assertEqual((c["x"], c["y"], c["z"], c["feed"]), (4, 5, -1, 700))

        t = move_retract(6)
        self.assertEqual((t["kind"], t["z"]), ("retract", 6))
