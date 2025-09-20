from __future__ import annotations

import unittest


class TestLayoutUtilsValidation(unittest.TestCase):
    def test_skeleton_is_valid(self) -> None:
        from skills.mill_ui.io.layout_utils import skeleton_layout, validate_layout_json
        ok, msg = validate_layout_json(skeleton_layout())
        self.assertTrue(ok, msg)

    def test_invalid_sheet(self) -> None:
        from skills.mill_ui.io.layout_utils import validate_layout_json
        ok, msg = validate_layout_json({"sheet": {"width_mm": "x"}, "items": []})
        self.assertFalse(ok)

