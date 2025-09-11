
import unittest
from skills.mill_ui.cam.path.toolpath import move_comment, move_set_feed, move_set_rpm, move_rapid, move_cut, move_retract
from skills.mill_ui.cam.post.gcode import write_gcode
class TestToolpathPost(unittest.TestCase):
    def test_moves_and_post(self):
        moves=[
            move_comment('hello(world)'), move_set_rpm(12000), move_set_feed(800),
            move_rapid(x=0,y=0,z=5), move_cut(x=10,y=0,z=0), move_retract(5),
        ]
        out=write_gcode(moves, safe_z=6.0)
        self.assertIn('G21', out); self.assertIn('(hello[world])', out); self.assertIn('M3 S12000', out)
        self.assertTrue(out.strip().splitlines()[-4].startswith('G0 Z6.000'))
