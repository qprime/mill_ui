
import unittest
from skills.mill_ui.api.cad import rectangle
from skills.mill_ui.cam.model.tool import Tool
from skills.mill_ui.cam.model.material import Material
from skills.mill_ui.cam.model.machine import Machine
from skills.mill_ui.cam.model.stock import Stock
from skills.mill_ui.cam.model.setup import Setup
from skills.mill_ui.cam.ops.profile import profile_outline
from skills.mill_ui.cam.ops.pocket import pocket_raster
from skills.mill_ui.cam.ops.drill import drill_peck
from skills.mill_ui.cam.ops.face import face_zigzag
from skills.mill_ui.cam.ops.engrave import engrave_lines
class TestModelsOps(unittest.TestCase):
    def setUp(self):
        self.tool=Tool(name='1/4in flat', diameter=6.35)
        self.setup=Setup(stock=Stock(100,100,12.7), tool=self.tool, material=Material(), machine=Machine())
    def test_profile(self):
        shp=rectangle(20,10); moves=profile_outline(shp, self.setup, depth=6.0, step_down=3.0)
        self.assertTrue(any(m.get('kind')=='cut' and m.get('z')==-3.0 for m in moves))
        self.assertTrue(any(m.get('kind')=='cut' and m.get('z')==-6.0 for m in moves))
    def test_pocket(self):
        shp=rectangle(20,10); moves=pocket_raster(shp, self.setup, depth=3.0, stepover=5.0)
        self.assertTrue(any(m.get('kind')=='cut' and m.get('z')==-3.0 for m in moves))
    def test_drill(self):
        moves=drill_peck([(0,0),(10,10)], self.setup, depth=5.0, peck=2.0)
        self.assertTrue(any(m.get('kind')=='retract' for m in moves))
    def test_face(self):
        moves=face_zigzag(30,20,self.setup,step=10.0,depth=0.5)
        self.assertTrue(any(m.get('kind')=='cut' and m.get('z')==-0.5 for m in moves))
    def test_engrave(self):
        lines=[[(0,0),(10,0),(10,10)]]; moves=engrave_lines(lines, self.setup, z=-0.3)
        self.assertTrue(any(m.get('kind')=='cut' and m.get('z')==-0.3 for m in moves))
