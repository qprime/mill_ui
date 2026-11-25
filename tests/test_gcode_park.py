from __future__ import annotations

import pytest

from cam.moves import CutMove, Move, RapidMove, RetractMove, SetRpmMove
from cam.post.gcode import ParkingError, ParkingRequest, write_gcode
from config.machine_loader import CNCMachine2D, MachineConfig, MachineDefaults

MOVES: tuple[Move, ...] = (
    SetRpmMove(rpm=12000),
    RapidMove(x=10, y=15, z=6),
    CutMove(x=100, y=None, z=-5, feed=800),
    RetractMove(z=6),
)


def _machine(*, z_min: float | None = -77, park_z: float | None = 18) -> MachineConfig:
    return MachineConfig(
        CNCMachine2D("Test router", 0, 110, 0, 120, envelope_z_min=z_min, envelope_z_max=0),
        defaults=MachineDefaults(park_z_mm=park_z),
    )


def test_default_preserves_programmed_exit_and_shutdown():
    program = write_gcode(MOVES, safe_z=6, machine_config=_machine())
    assert program.splitlines()[-4:] == ["G0 Z6.000", "M5", "M2", "(end)"]
    assert "G0 X0.000 Y0.000" not in program
    assert "G0 Z18.000" not in program


@pytest.mark.parametrize(("override", "height"), [(None, "18.000"), (25, "25.000")], ids=["profile", "override"])
def test_parking_retracts_then_returns_to_work_zero(override: float | None, height: str):
    program = write_gcode(
        MOVES,
        safe_z=6,
        machine_config=_machine(),
        parking=ParkingRequest(work_offset_mm=(5, 10, -30), z_mm=override),
        footer=["M5", "M30", "(done)"],
    )
    lines = program.splitlines()
    assert "G54" in lines
    assert lines[-6:] == ["G0 Z6.000", f"G0 Z{height}", "G0 X0.000 Y0.000", "M5", "M30", "(done)"]


@pytest.mark.parametrize(
    ("parking", "diagnostic"),
    [
        pytest.param(ParkingRequest(), "--work-offset", id="missing_offset"),
        pytest.param(ParkingRequest((0, 0, float("nan"))), "finite", id="nonfinite_offset"),
        pytest.param(ParkingRequest((0, 0, -30), 100), "work Z100 resolves to machine Z70", id="above_travel"),
        pytest.param(ParkingRequest((0, 0, -85), 18), "return start work Z6", id="below_travel_at_exit"),
        pytest.param(ParkingRequest((11, 0, -30), 18), "return start work X100", id="exit_x_outside"),
        pytest.param(ParkingRequest((-1, 0, -30), 18), "target work X0", id="target_x_outside"),
        pytest.param(ParkingRequest((0, 0, -30), 5), "work Z >= 6", id="below_job_safe_height"),
        pytest.param(ParkingRequest((0, 0, -18.0007), 18.0006), "target work Z18.001", id="rounds_above_limit"),
    ],
)
def test_invalid_return_is_rejected(parking: ParkingRequest, diagnostic: str):
    with pytest.raises(ParkingError, match=diagnostic):
        write_gcode(MOVES, safe_z=6, machine_config=_machine(), parking=parking)


def test_return_start_uses_emitted_xy_after_margin_and_y_flip():
    with pytest.raises(ParkingError, match="return start work Y100 resolves to machine Y125"):
        write_gcode(
            MOVES,
            safe_z=6,
            margin_mm=5,
            y_origin="front",
            sheet_height=120,
            machine_config=_machine(),
            parking=ParkingRequest((0, 25, -30)),
        )


@pytest.mark.parametrize(
    ("machine", "diagnostic"),
    [
        pytest.param(_machine(z_min=None), "envelope.z_min and envelope.z_max", id="missing_z_limit"),
        pytest.param(_machine(park_z=None), "defaults.park_z_mm or --park-z", id="missing_park_height"),
    ],
)
def test_parking_requires_explicit_profile_data(machine: MachineConfig, diagnostic: str):
    with pytest.raises(ParkingError, match=diagnostic):
        write_gcode(MOVES, safe_z=6, machine_config=machine, parking=ParkingRequest((0, 0, -30)))
