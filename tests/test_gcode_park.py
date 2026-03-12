from __future__ import annotations

import pytest

from cam.moves import CutMove, Move, RapidMove, RetractMove, SetFeedMove, SetRpmMove
from cam.post.gcode import write_gcode
from config.machine_loader import MachineDefaults


class TestGcodeFooterPark:
    def test_gcode_ends_with_park_moves(self):
        moves: list[Move] = [
            SetRpmMove(rpm=12000),
            SetFeedMove(feed=800),
            RapidMove(x=10.0, y=10.0, z=None),
            CutMove(x=100.0, y=10.0, z=-5.0, feed=800),
            RetractMove(z=6.0),
        ]
        gcode = write_gcode(moves, safe_z=6.0)
        lines = gcode.strip().split("\n")

        assert "G0 Z100.000" in lines
        assert "G0 X0.000 Y0.000" in lines

    def test_park_z_configurable(self):
        moves: list[Move] = [
            SetRpmMove(rpm=12000),
            RapidMove(x=10.0, y=10.0, z=None),
            RetractMove(z=6.0),
        ]
        gcode = write_gcode(moves, safe_z=6.0, park_z_mm=50.0)
        lines = gcode.strip().split("\n")

        assert "G0 Z50.000" in lines
        assert "G0 Z100.000" not in lines

    def test_park_before_spindle_stop(self):
        moves: list[Move] = [
            SetRpmMove(rpm=12000),
            RapidMove(x=10.0, y=10.0, z=None),
            RetractMove(z=6.0),
        ]
        gcode = write_gcode(moves, safe_z=6.0)
        lines = gcode.strip().split("\n")

        z_park_idx = lines.index("G0 Z100.000")
        xy_park_idx = lines.index("G0 X0.000 Y0.000")
        m5_idx = lines.index("M5")

        assert z_park_idx < xy_park_idx < m5_idx

    def test_park_z_less_than_safe_z_rejected(self):
        with pytest.raises(ValueError, match=r"park_z_mm.*must be >= safe_z_mm"):
            MachineDefaults(safe_z_mm=10.0, park_z_mm=5.0)

    def test_park_z_equal_to_safe_z_accepted(self):
        defaults = MachineDefaults(safe_z_mm=10.0, park_z_mm=10.0)
        assert defaults.park_z_mm == 10.0

    def test_custom_footer_gets_park_prepended(self):
        moves: list[Move] = [
            SetRpmMove(rpm=12000),
            RapidMove(x=10.0, y=10.0, z=None),
            RetractMove(z=6.0),
        ]
        custom_footer = ["M5", "M30", "(done)"]
        gcode = write_gcode(moves, safe_z=6.0, footer=custom_footer)
        lines = gcode.strip().split("\n")

        z_park_idx = lines.index("G0 Z100.000")
        m30_idx = lines.index("M30")
        assert z_park_idx < m30_idx
        assert "(end)" not in lines
