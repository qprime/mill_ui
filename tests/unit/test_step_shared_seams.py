import unittest

from skills.mill_ui.cad.step_export import RectProfileInfo, _find_shared_rect_seams


class TestStepSharedSeams(unittest.TestCase):
    def test_vertical_shared_seam_detected(self):
        rects = {
            "left": RectProfileInfo(id="left", center_x=0.0, center_y=0.0, width=100.0, height=200.0),
            "right": RectProfileInfo(id="right", center_x=100.0, center_y=0.0, width=100.0, height=200.0),
        }

        seams = _find_shared_rect_seams(rects)

        self.assertEqual(len(seams), 1, f"expected one seam, got {seams}")
        seam = seams[0]
        self.assertEqual(seam.orientation, "vertical")
        self.assertEqual(seam.negative_id, "left")
        self.assertEqual(seam.positive_id, "right")
        self.assertAlmostEqual(seam.coord, 50.0)
        self.assertAlmostEqual(seam.span_start, -100.0)
        self.assertAlmostEqual(seam.span_end, 100.0)

    def test_horizontal_shared_seam_detected(self):
        rects = {
            "bottom": RectProfileInfo(id="bottom", center_x=0.0, center_y=0.0, width=200.0, height=100.0),
            "top": RectProfileInfo(id="top", center_x=0.0, center_y=100.0, width=200.0, height=100.0),
        }

        seams = _find_shared_rect_seams(rects)

        self.assertTrue(any(seam.orientation == "horizontal" for seam in seams), f"horizontal seam missing: {seams}")
        horizontal = next(seam for seam in seams if seam.orientation == "horizontal")
        self.assertEqual(horizontal.negative_id, "bottom")
        self.assertEqual(horizontal.positive_id, "top")
        self.assertAlmostEqual(horizontal.coord, 50.0)
        self.assertAlmostEqual(horizontal.span_start, -100.0)
        self.assertAlmostEqual(horizontal.span_end, 100.0)

    def test_gap_prevents_seam_detection(self):
        rects = {
            "left": RectProfileInfo(id="left", center_x=0.0, center_y=0.0, width=100.0, height=200.0),
            "right": RectProfileInfo(id="right", center_x=106.35, center_y=0.0, width=100.0, height=200.0),
        }

        seams = _find_shared_rect_seams(rects)

        self.assertEqual(seams, [], f"no seam expected when explicit gap present, got {seams}")


if __name__ == "__main__":
    unittest.main()
