import unittest
from skills.mill_ui.cad.layout.panel import Panel
from skills.mill_ui.api.cad import apply_grid_layout, render_svg_layout

class TestSvgExport(unittest.TestCase):
    def test_svg_basic(self):
        panel = Panel(width=100.0, height=80.0, thickness=12.0)
        items = [
            {"kind":"shape","type":"Rect","geometry":{"w_mm":30,"h_mm":20}},
            {"kind":"shape","type":"Circle","geometry":{"diameter_mm":10}},
        ]
        placements = apply_grid_layout(panel, items, rows=1, cols=2, gap_x=10, border=5, fit="tight")
        svg = render_svg_layout(panel, placements)
        self.assertIn('<svg', svg)
        self.assertIn('class="panel"', svg)
        self.assertIn('class="item"', svg)
        self.assertIn('<circle', svg)
