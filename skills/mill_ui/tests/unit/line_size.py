import unittest
from skills.mill_ui.api.cad import item_size_mm

class TestPolylineSize(unittest.TestCase):
    def test_size(self):
        it = {"kind":"shape","type":"Polyline","geometry":{"points":[[0,0],[10,0],[10,5],[0,5]]}}
        self.assertEqual(item_size_mm(it), (10.0, 5.0))
