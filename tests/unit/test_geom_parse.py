import unittest
from skills.mill_ui.cad.layout.panel import Panel
from skills.mill_ui.cad.geom_parse import rect_from_variant, circle_from_variant, is_stock_boundary_rect

class TestGeomParse(unittest.TestCase):
    def test_rect_variants(self):
        r1 = rect_from_variant({"min_x":0,"min_y":1,"max_x":10,"max_y":11})
        self.assertEqual((r1["min_x"], r1["max_y"]), (0.0, 11.0))

        r2 = rect_from_variant({"bbox":{"xmin":0,"ymin":1,"xmax":10,"max_y":11}})
        self.assertEqual((r2["min_y"], r2["max_x"]), (1.0, 10.0))

        r3 = rect_from_variant({"points":[[0,1],[10,11]]})
        self.assertEqual((r3["min_x"], r3["max_y"]), (0.0, 11.0))

        r4 = rect_from_variant({"x":0,"y":1,"width":10,"height":10})
        self.assertEqual((r4["max_x"], r4["max_y"]), (10.0, 11.0))

    def test_circle_variants(self):
        c1 = circle_from_variant({"center_x":5,"center_y":6,"radius_mm":2})
        self.assertEqual(c1, (5.0, 6.0, 2.0))
        c2 = circle_from_variant({"center":{"x":5,"y":6},"diameter_mm":8})
        self.assertEqual(c2, (5.0, 6.0, 4.0))

    def test_boundary_check(self):
        panel = Panel(width=300, height=200, thickness=12)
        self.assertTrue(is_stock_boundary_rect({"min_x":0,"min_y":0,"max_x":300,"max_y":200}, panel))
        self.assertFalse(is_stock_boundary_rect({"min_x":1,"min_y":0,"max_x":300,"max_y":200}, panel))
