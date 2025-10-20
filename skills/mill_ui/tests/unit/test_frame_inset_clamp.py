from __future__ import annotations

import unittest

from skills.mill_ui.compositions.panels.frame_inset_clamp import FrameInsetClamp


def _shape_by_id(shapes, shape_id):
    for shape in shapes:
        if shape.get("id") == shape_id:
            return shape
    raise AssertionError(f"shape id {shape_id!r} not found")


class FrameInsetClampTest(unittest.TestCase):
    def test_builds_outer_inner_and_relief(self) -> None:
        params = {
            "aperture_w_mm": 200.0,
            "aperture_h_mm": 120.0,
            "extent_width_mm": 5.0,
            "inset_width_mm": 12.0,
            "indent_mm": 2.0,
        }
        shapes = FrameInsetClamp().expand(params, thickness_mm=18.0)

        outer = _shape_by_id(shapes, "clamp:outer")
        inner = _shape_by_id(shapes, "clamp:inner")
        self.assertAlmostEqual(outer["geometry"]["w_mm"], 200.0 + 2.0 * 12.0)
        self.assertAlmostEqual(outer["geometry"]["h_mm"], 120.0 + 2.0 * 12.0)

        self.assertAlmostEqual(inner["geometry"]["w_mm"], 200.0 - 2.0 * 5.0)
        self.assertAlmostEqual(inner["geometry"]["h_mm"], 120.0 - 2.0 * 5.0)

        rabbet_passes = [s for s in shapes if s.get("id", "").startswith("clamp:rabbet:pass:")]
        self.assertGreaterEqual(len(rabbet_passes), 2)

        depths = {round(s["feature"]["depth_mm"], 6) for s in rabbet_passes}
        self.assertSetEqual(depths, {18.0 - 2.0})
        self.assertTrue(all(s["feature"]["type"] == "profile" for s in rabbet_passes))

        widths = [s["geometry"]["w_mm"] for s in rabbet_passes]
        heights = [s["geometry"]["h_mm"] for s in rabbet_passes]
        self.assertAlmostEqual(min(widths), inner["geometry"]["w_mm"])
        self.assertAlmostEqual(max(widths), 200.0)
        self.assertAlmostEqual(min(heights), inner["geometry"]["h_mm"])
        self.assertAlmostEqual(max(heights), 120.0)

    def test_border_and_clearances(self) -> None:
        params = {
            "aperture_w_mm": 300.0,
            "aperture_h_mm": 180.0,
            "extent_width_mm": 4.0,
            "inset_width_mm": 10.0,
            "indent_mm": 3.0,
            "outer_clearance_mm": 0.5,
            "inner_clearance_mm": 0.25,
            "border": {
                "mode": "double_vine",
                "track_depth_mm": 0.5,
            },
        }
        shapes = FrameInsetClamp().expand(params, thickness_mm=18.0)

        outer = _shape_by_id(shapes, "clamp:outer")
        expected_outer_w = (300.0 + 2.0 * 10.0) - 2.0 * 0.5
        self.assertAlmostEqual(outer["geometry"]["w_mm"], expected_outer_w)
        self.assertTrue(any(s.get("id", "").startswith("border:") for s in shapes))


if __name__ == "__main__":
    unittest.main()
