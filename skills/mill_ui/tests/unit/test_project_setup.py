from __future__ import annotations

import unittest
from pathlib import Path
import shutil


class TestComposeCamSetup(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path("memories/cam_projects/sheet_layouts")
        self.proj = self.root / "__test_setup_project__"
        if self.proj.exists():
            shutil.rmtree(self.proj)

    def tearDown(self) -> None:
        if self.proj.exists():
            shutil.rmtree(self.proj)

    def test_setup_creates_structure_and_skeleton(self) -> None:
        from skills.mill_ui.apps import compose_cam
        code = compose_cam.main(["__test_setup_project__", "--setup"])
        self.assertEqual(code, 0)

        in_dir = self.proj / "input"
        cam_dir = self.proj / "CAM"
        layout = in_dir / "layout.json"
        self.assertTrue(in_dir.is_dir(), "input folder should be created")
        self.assertTrue(cam_dir.is_dir(), "CAM folder should be created")
        self.assertTrue(layout.is_file(), "layout.json skeleton should be created")

        # Running setup again should validate and exit cleanly
        code2 = compose_cam.main(["__test_setup_project__", "--setup"])
        self.assertEqual(code2, 0)

