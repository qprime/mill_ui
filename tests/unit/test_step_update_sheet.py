from __future__ import annotations

import unittest
from pathlib import Path
import shutil

try:  # optional dependency for STEP import
    import cadquery as cq  # type: ignore
except Exception:  # pragma: no cover
    cq = None  # type: ignore


@unittest.skipIf(cq is None, "cadquery is required for STEP update tests")
class TestComposeCamUpdateFromStep(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path("memories/cam_projects/sheet_layouts")
        self.proj = self.root / "__test_update_project__"
        if self.proj.exists():
            shutil.rmtree(self.proj)
        (self.proj / "input").mkdir(parents=True, exist_ok=True)
        (self.proj / "CAM").mkdir(parents=True, exist_ok=True)

        # Create a base layout with an existing item but missing sheet dims
        from skills.mill_ui.io.layout_utils import write_layout
        base_layout = {
            "sheet": {"width_mm": 0.0, "height_mm": 0.0, "thickness_mm": 0.0},
            "items": [
                {
                    "kind": "shape",
                    "type": "Rect",
                    "geometry": {"w_mm": 10.0, "h_mm": 10.0},
                    "feature": {"type": "profile", "depth": "through"},
                    "placement": {"center_xy_mm": [0.0, 0.0]},
                }
            ],
        }
        write_layout(self.proj / "input" / "layout.json", base_layout)

        # Emit a simple STEP plate: 100 x 50 x 12 mm
        plate = cq.Workplane("XY").rect(100.0, 50.0).extrude(-12.0)
        step_path = self.proj / "input" / "plate.step"
        cq.exporters.export(plate.val(), str(step_path))
        self.step_path = step_path
        # Ensure STEP importer is functional in this environment; otherwise skip
        try:
            shape_or_wp = cq.importers.importStep(str(step_path))  # type: ignore[attr-defined]
        except Exception:  # pragma: no cover - environment without STEP importer
            self.skipTest("CadQuery STEP importer not available; skipping update test")

    def tearDown(self) -> None:
        if self.proj.exists():
            shutil.rmtree(self.proj)

    def test_update_sheet_from_step_keeps_items(self) -> None:
        from skills.mill_ui.apps import compose_cam
        from skills.mill_ui.io.layout_utils import load_layout

        code = compose_cam.main([self.proj.name, "--update"])
        self.assertEqual(code, 0)

        data = load_layout(self.proj / "input" / "layout.json")
        # Items should be preserved
        self.assertEqual(len(data.get("items", [])), 1)

        # Sheet should be inferred (with 5mm margin per side -> +10mm)
        sheet = data.get("sheet", {})
        self.assertAlmostEqual(float(sheet.get("width_mm", 0)), 110.0, places=3)
        self.assertAlmostEqual(float(sheet.get("height_mm", 0)), 60.0, places=3)
        self.assertAlmostEqual(float(sheet.get("thickness_mm", 0)), 12.0, places=3)
