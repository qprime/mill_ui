from __future__ import annotations

import pytest

from config.machine_loader import CNCMachine2D, Endmill, MachineConfig, Spoilboard2D
from ir.removal_intent import Bounds2D
from layout_ast.layout import LayoutAST, Sheet
from validation.core import Verdict
from validation.machine_checks import (
    check_job_fits_machine,
    check_mch_effective_envelope_shrinks,
    check_mch_endmill_positive,
    check_mch_envelope_positive,
    check_mch_spoilboard_fits,
    check_sheet_fits_machine,
    validate_machine_config,
)


def _machine(
    x_min: float = 0.0,
    x_max: float = 1000.0,
    y_min: float = 0.0,
    y_max: float = 1000.0,
) -> MachineConfig:
    return MachineConfig(
        machine=CNCMachine2D(
            name="test",
            envelope_x_min=x_min,
            envelope_x_max=x_max,
            envelope_y_min=y_min,
            envelope_y_max=y_max,
        )
    )


def _endmill(diameter: float = 6.35, flute_length: float = 25.0) -> Endmill:
    return Endmill(
        name="test_endmill",
        diameter_mm=diameter,
        flute_length_mm=flute_length,
        shank_diameter_mm=diameter,
        flutes=2,
        type="flat",
    )


class TestCheckJobFitsMachine:
    def test_job_inside_envelope(self):
        mc = _machine()
        bounds = Bounds2D(x_min=10, x_max=500, y_min=10, y_max=500)
        result = check_job_fits_machine(bounds, mc)
        assert result.status == Verdict.PASS
        assert result.failed == 0

    def test_job_exceeds_x_max(self):
        mc = _machine()
        bounds = Bounds2D(x_min=10, x_max=1100, y_min=10, y_max=500)
        result = check_job_fits_machine(bounds, mc)
        assert result.status == Verdict.FAIL
        assert result.failed == 1
        assert "x_max" in result.failures[0]

    def test_job_exceeds_x_min(self):
        mc = _machine()
        bounds = Bounds2D(x_min=-5, x_max=500, y_min=10, y_max=500)
        result = check_job_fits_machine(bounds, mc)
        assert result.status == Verdict.FAIL
        assert any("x_min" in f for f in result.failures)

    def test_job_exceeds_y_max(self):
        mc = _machine()
        bounds = Bounds2D(x_min=10, x_max=500, y_min=10, y_max=1100)
        result = check_job_fits_machine(bounds, mc)
        assert result.status == Verdict.FAIL
        assert any("y_max" in f for f in result.failures)

    def test_job_exceeds_y_min(self):
        mc = _machine()
        bounds = Bounds2D(x_min=10, x_max=500, y_min=-5, y_max=500)
        result = check_job_fits_machine(bounds, mc)
        assert result.status == Verdict.FAIL
        assert any("y_min" in f for f in result.failures)

    def test_job_exceeds_all_sides(self):
        mc = _machine()
        bounds = Bounds2D(x_min=-10, x_max=1100, y_min=-10, y_max=1100)
        result = check_job_fits_machine(bounds, mc)
        assert result.status == Verdict.FAIL
        assert result.failed == 4

    def test_job_at_envelope_boundary(self):
        mc = _machine()
        bounds = Bounds2D(x_min=0, x_max=1000, y_min=0, y_max=1000)
        result = check_job_fits_machine(bounds, mc)
        assert result.status == Verdict.PASS

    def test_with_endmill_effective_envelope(self):
        mc = _machine()
        endmill = _endmill(diameter=10.0)
        bounds = Bounds2D(x_min=0, x_max=1000, y_min=0, y_max=1000)
        result = check_job_fits_machine(bounds, mc, endmill)
        assert result.status == Verdict.FAIL
        assert "endmill" in result.details

    def test_with_endmill_inside_effective(self):
        mc = _machine()
        endmill = _endmill(diameter=10.0)
        bounds = Bounds2D(x_min=10, x_max=990, y_min=10, y_max=990)
        result = check_job_fits_machine(bounds, mc, endmill)
        assert result.status == Verdict.PASS


class TestCheckSheetFitsMachine:
    def test_sheet_fits(self):
        mc = _machine()
        ast = LayoutAST(
            sheet=Sheet(width_mm=800, height_mm=800, thickness_mm=19, margin_mm=10),
            items=(),
        )
        result = check_sheet_fits_machine(ast, mc)
        assert result.status == Verdict.PASS

    def test_sheet_too_large(self):
        mc = _machine(x_max=500, y_max=500)
        ast = LayoutAST(
            sheet=Sheet(width_mm=800, height_mm=800, thickness_mm=19, margin_mm=10),
            items=(),
        )
        result = check_sheet_fits_machine(ast, mc)
        assert result.status == Verdict.FAIL


class TestCheckMchEnvelopePositive:
    def test_valid_envelope(self):
        mc = _machine()
        result = check_mch_envelope_positive(mc)
        assert result.status == Verdict.PASS
        assert result.failed == 0

    def test_x_degenerate(self):
        mc = _machine(x_min=500, x_max=500.001)
        result = check_mch_envelope_positive(mc)
        assert result.status == Verdict.PASS

    def test_non_zero_origin(self):
        mc = _machine(x_min=100, x_max=900, y_min=50, y_max=850)
        result = check_mch_envelope_positive(mc)
        assert result.status == Verdict.PASS


class TestCheckMchSpoilboardFits:
    def test_no_spoilboard(self):
        mc = _machine()
        result = check_mch_spoilboard_fits(mc)
        assert result.status == Verdict.PASS
        assert result.checked == 0

    def test_spoilboard_inside(self):
        mc = MachineConfig(
            machine=CNCMachine2D(
                name="test",
                envelope_x_min=0,
                envelope_x_max=1000,
                envelope_y_min=0,
                envelope_y_max=1000,
            ),
            spoilboard=Spoilboard2D(
                width_mm=800,
                height_mm=800,
                offset_x=100,
                offset_y=100,
            ),
        )
        result = check_mch_spoilboard_fits(mc)
        assert result.status == Verdict.PASS
        assert result.failed == 0

    def test_spoilboard_at_envelope(self):
        mc = MachineConfig(
            machine=CNCMachine2D(
                name="test",
                envelope_x_min=0,
                envelope_x_max=1000,
                envelope_y_min=0,
                envelope_y_max=1000,
            ),
            spoilboard=Spoilboard2D(
                width_mm=1000,
                height_mm=1000,
                offset_x=0,
                offset_y=0,
            ),
        )
        result = check_mch_spoilboard_fits(mc)
        assert result.status == Verdict.PASS


class TestCheckMchEffectiveEnvelopeShrinks:
    def test_shrinks_with_endmill(self):
        mc = _machine()
        endmill = _endmill(diameter=6.35)
        result = check_mch_effective_envelope_shrinks(mc, endmill)
        assert result.status == Verdict.PASS
        assert result.failed == 0
        assert result.details["bit_radius_mm"] == pytest.approx(3.175)

    def test_zero_radius_no_change(self):
        mc = _machine()
        endmill = _endmill(diameter=0.001)
        result = check_mch_effective_envelope_shrinks(mc, endmill)
        assert result.status == Verdict.PASS


class TestCheckMchEndmillPositive:
    def test_valid_endmill(self):
        endmill = _endmill()
        result = check_mch_endmill_positive(endmill)
        assert result.status == Verdict.PASS
        assert result.failed == 0


class TestValidateMachineConfig:
    def test_basic_config(self):
        mc = _machine()
        results = validate_machine_config(mc)
        assert len(results) == 2
        assert all(r.status == Verdict.PASS for r in results)

    def test_with_endmill(self):
        mc = _machine()
        endmill = _endmill()
        results = validate_machine_config(mc, endmill)
        assert len(results) == 4
        assert all(r.status == Verdict.PASS for r in results)

    def test_with_spoilboard(self):
        mc = MachineConfig(
            machine=CNCMachine2D(
                name="test",
                envelope_x_min=0,
                envelope_x_max=1000,
                envelope_y_min=0,
                envelope_y_max=1000,
            ),
            spoilboard=Spoilboard2D(
                width_mm=800,
                height_mm=800,
                offset_x=100,
                offset_y=100,
            ),
        )
        results = validate_machine_config(mc)
        assert len(results) == 2
        assert all(r.status == Verdict.PASS for r in results)
