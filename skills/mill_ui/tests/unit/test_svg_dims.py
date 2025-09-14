# path: skills/mill_ui/tests/unit/test_svg_dims.py
import unittest
from skills.mill_ui.cad.export.svg_dims import render_svg_with_dims

class TestSvgDims(unittest.TestCase):
    def test_features_sizes_depths_and_stile_rail(self):
        panel_w, panel_h, panel_t = 300.0, 200.0, 12.0
        placements = [
            {"item": {"kind":"template","type":"Shaker","params":{"outer_w":100,"outer_h":60}},
             "center_xy_mm": (75.0, 100.0)}
        ]
        # Outer profile 100x60; inner pocket (panel) 80x40 → stile=10, rail=10
        hints = {
            "profiles": [
                {"shape":"Rect","geometry":{"w_mm":100,"h_mm":60},"center_xy_mm":(75.0,100.0),"depth_mm":12.0}
            ],
            "pockets": [
                {"shape":"Rect","geometry":{"w_mm":80,"h_mm":40},"center_xy_mm":(75.0,100.0),"depth_mm":6.0},
                {"shape":"Circle","geometry":{"diameter_mm":25},"center_xy_mm":(60.0,115.0),"depth_mm":9.0},
            ],
            "holes": [
                {"shape":"Circle","geometry":{"diameter_mm":5},"center_xy_mm":(90.0,85.0),"depth_mm":12.0}
            ]
        }
        svg = render_svg_with_dims(panel_w, panel_h, panel_t, placements, hints, tol_mm=0.25, circle_label_threshold=99)
        # Feature classes present
        self.assertIn('class="feature-profile"', svg)
        self.assertIn('class="feature-pocket"', svg)
        self.assertIn('class="feature-anchor"', svg)
        self.assertIn('class="feature-hole"', svg)
        # Size labels (W=…, H=…)
        self.assertIn('W=100.0mm', svg)
        self.assertIn('H=60.0mm', svg)
        self.assertIn('W=80.0mm', svg)
        self.assertIn('H=40.0mm', svg)
        # Circle diameter labels
        self.assertIn('⌀=25.0mm', svg)
        self.assertIn('⌀=5.0mm', svg)
        # Depth labels present
        self.assertIn('d=6.0mm', svg)
        self.assertIn('d=9.0mm', svg)
        # Stile/Rail
        self.assertIn('Stile=10.0mm', svg)
        self.assertIn('Rail=10.0mm', svg)
        # Legend is a single block (no duplicates); check key phrases
        self.assertIn('Sheet 12.0 mm', svg)
        self.assertIn('Pocket depths:', svg)

if __name__ == "__main__":
    unittest.main()
