import unittest
from skills.mill_ui.cad.layout.panel import Panel
from skills.mill_ui.api.cad import apply_grid_layout, item_size_mm

class TestApplyGridLayout(unittest.TestCase):
    def setUp(self):
        self.panel = Panel(width=300.0, height=200.0, thickness=12.0)

    def test_tight_fit(self):
        # Max item size will be 60x70, which fits:
        # height check: 2*70 + 10 gap = 150 <= available 150 (with border=20)
        items = [
            {"kind":"shape","type":"Rect","geometry":{"w_mm":50,"h_mm":30}},
            {"kind":"shape","type":"Circle","geometry":{"diameter_mm":40}},
            {"kind":"door","params":{"outer_w":60,"outer_h":70}},
        ]
        placements = apply_grid_layout(
            self.panel, items,
            rows=2, cols=2, gap_x=10, gap_y=10, border=20, fit="tight"
        )
        cw = placements[0]["cell_size_mm"][0]
        ch = placements[0]["cell_size_mm"][1]
        self.assertAlmostEqual(cw, 60.0)
        self.assertAlmostEqual(ch, 70.0)
        self.assertAlmostEqual(placements[0]["center_xy_mm"][0], 20 + cw/2)
        self.assertAlmostEqual(placements[0]["center_xy_mm"][1], 20 + ch/2)

    def test_even_fill(self):
        items = [{"kind":"shape","type":"Rect","geometry":{"w_mm":10,"h_mm":10}} for _ in range(6)]
        placements = apply_grid_layout(self.panel, items, rows=2, cols=3, gap_x=10, gap_y=10, border=10, fit="even")
        cw, ch = placements[0]["cell_size_mm"]
        avail_w = self.panel.width - 2*10 - (3-1)*10
        avail_h = self.panel.height - 2*10 - (2-1)*10
        self.assertAlmostEqual(cw, avail_w/3)
        self.assertAlmostEqual(ch, avail_h/2)

    def test_item_size_mm(self):
        self.assertEqual(item_size_mm({"kind":"door","params":{"outer_w":20,"outer_h":30}}), (20.0,30.0))
        self.assertEqual(item_size_mm({"kind":"shape","type":"Rect","geometry":{"w_mm":5,"h_mm":7}}), (5.0,7.0))
        self.assertEqual(item_size_mm({"kind":"shape","type":"Circle","geometry":{"diameter_mm":8}}), (8.0,8.0))

    def test_tight_fit_overflow_raises(self):
        items = [{"kind":"shape","type":"Rect","geometry":{"w_mm":200,"h_mm":200}}]
        with self.assertRaises(ValueError):
            apply_grid_layout(self.panel, items, rows=1, cols=2, gap_x=50, border=20, fit="tight")
