from __future__ import annotations

from config.machine_loader import MachineConfig, Endmill
from ir.removal_intent import Bounds2D
from layout_ast.layout import LayoutAST
from validation.core import InvariantResult, Verdict


def check_job_fits_machine(
    job_bounds: Bounds2D,
    machine: MachineConfig,
    endmill: Endmill | None = None,
) -> InvariantResult:
    if endmill:
        bit_radius = endmill.radius_mm
        eff_x_min, eff_y_min, eff_x_max, eff_y_max = machine.effective_envelope(bit_radius)
    else:
        eff_x_min = machine.machine.envelope_x_min
        eff_y_min = machine.machine.envelope_y_min
        eff_x_max = machine.machine.envelope_x_max
        eff_y_max = machine.machine.envelope_y_max

    failures = []

    if job_bounds.x_min < eff_x_min:
        failures.append(
            f"Job x_min ({job_bounds.x_min:.1f}) < effective envelope x_min ({eff_x_min:.1f})"
        )
    if job_bounds.x_max > eff_x_max:
        failures.append(
            f"Job x_max ({job_bounds.x_max:.1f}) > effective envelope x_max ({eff_x_max:.1f})"
        )
    if job_bounds.y_min < eff_y_min:
        failures.append(
            f"Job y_min ({job_bounds.y_min:.1f}) < effective envelope y_min ({eff_y_min:.1f})"
        )
    if job_bounds.y_max > eff_y_max:
        failures.append(
            f"Job y_max ({job_bounds.y_max:.1f}) > effective envelope y_max ({eff_y_max:.1f})"
        )

    status = Verdict.PASS if not failures else Verdict.FAIL

    details = {
        "job_bounds": {
            "x_min": job_bounds.x_min,
            "x_max": job_bounds.x_max,
            "y_min": job_bounds.y_min,
            "y_max": job_bounds.y_max,
        },
        "effective_envelope": {
            "x_min": eff_x_min,
            "x_max": eff_x_max,
            "y_min": eff_y_min,
            "y_max": eff_y_max,
        },
        "machine_name": machine.machine.name,
    }
    if endmill:
        details["endmill"] = {
            "name": endmill.name,
            "diameter_mm": endmill.diameter_mm,
        }

    return InvariantResult(
        id="JOB_FITS_MACHINE",
        category="safety",
        artifact="job",
        description="Job sheet bounds fit within machine's effective envelope",
        status=status,
        checked=4,
        passed=4 - len(failures),
        failed=len(failures),
        failures=tuple(failures),
        details=details,
    )


def check_sheet_fits_machine(
    ast: LayoutAST,
    machine: MachineConfig,
    endmill: Endmill | None = None,
) -> InvariantResult:
    sheet = ast.sheet
    margin = sheet.margin_mm

    job_bounds = Bounds2D(
        x_min=margin,
        x_max=sheet.width_mm - margin,
        y_min=margin,
        y_max=sheet.height_mm - margin,
    )

    return check_job_fits_machine(job_bounds, machine, endmill)


def check_mch_envelope_positive(machine: MachineConfig) -> InvariantResult:
    m = machine.machine
    failures = []

    if m.envelope_x_max <= m.envelope_x_min:
        failures.append(
            f"envelope_x_max ({m.envelope_x_max}) <= envelope_x_min ({m.envelope_x_min})"
        )
    if m.envelope_y_max <= m.envelope_y_min:
        failures.append(
            f"envelope_y_max ({m.envelope_y_max}) <= envelope_y_min ({m.envelope_y_min})"
        )

    status = Verdict.PASS if not failures else Verdict.FAIL

    return InvariantResult(
        id="MCH_ENVELOPE_POSITIVE",
        category="structural",
        artifact="machine_config",
        description="envelope_x_max > envelope_x_min, same for Y",
        status=status,
        checked=2,
        passed=2 - len(failures),
        failed=len(failures),
        failures=tuple(failures),
    )


def check_mch_wasteboard_fits(machine: MachineConfig) -> InvariantResult:
    if machine.wasteboard is None:
        return InvariantResult(
            id="MCH_WASTEBOARD_FITS",
            category="structural",
            artifact="machine_config",
            description="Wasteboard bounds fall within or equal to envelope",
            status=Verdict.PASS,
            checked=0,
            passed=0,
            failed=0,
            failures=(),
            details={"wasteboard": "none"},
        )

    wb = machine.wasteboard
    m = machine.machine
    failures = []

    if wb.x_min < m.envelope_x_min:
        failures.append(f"wasteboard x_min ({wb.x_min}) < envelope x_min ({m.envelope_x_min})")
    if wb.x_max > m.envelope_x_max:
        failures.append(f"wasteboard x_max ({wb.x_max}) > envelope x_max ({m.envelope_x_max})")
    if wb.y_min < m.envelope_y_min:
        failures.append(f"wasteboard y_min ({wb.y_min}) < envelope y_min ({m.envelope_y_min})")
    if wb.y_max > m.envelope_y_max:
        failures.append(f"wasteboard y_max ({wb.y_max}) > envelope y_max ({m.envelope_y_max})")

    status = Verdict.PASS if not failures else Verdict.FAIL

    return InvariantResult(
        id="MCH_WASTEBOARD_FITS",
        category="structural",
        artifact="machine_config",
        description="Wasteboard bounds fall within or equal to envelope",
        status=status,
        checked=4,
        passed=4 - len(failures),
        failed=len(failures),
        failures=tuple(failures),
    )


def check_mch_effective_envelope_shrinks(
    machine: MachineConfig,
    endmill: Endmill,
) -> InvariantResult:
    m = machine.machine
    bit_radius = endmill.radius_mm
    eff_x_min, eff_y_min, eff_x_max, eff_y_max = machine.effective_envelope(bit_radius)

    failures = []

    if eff_x_min < m.envelope_x_min:
        failures.append(f"effective x_min ({eff_x_min}) < envelope x_min ({m.envelope_x_min})")
    if eff_x_max > m.envelope_x_max:
        failures.append(f"effective x_max ({eff_x_max}) > envelope x_max ({m.envelope_x_max})")
    if eff_y_min < m.envelope_y_min:
        failures.append(f"effective y_min ({eff_y_min}) < envelope y_min ({m.envelope_y_min})")
    if eff_y_max > m.envelope_y_max:
        failures.append(f"effective y_max ({eff_y_max}) > envelope y_max ({m.envelope_y_max})")

    status = Verdict.PASS if not failures else Verdict.FAIL

    return InvariantResult(
        id="MCH_EFFECTIVE_ENVELOPE_SHRINKS",
        category="structural",
        artifact="machine_config",
        description="Effective envelope <= envelope (inset by bit radius)",
        status=status,
        checked=4,
        passed=4 - len(failures),
        failed=len(failures),
        failures=tuple(failures),
        details={
            "bit_radius_mm": bit_radius,
            "effective_envelope": {
                "x_min": eff_x_min,
                "x_max": eff_x_max,
                "y_min": eff_y_min,
                "y_max": eff_y_max,
            },
        },
    )


def check_mch_endmill_positive(endmill: Endmill) -> InvariantResult:
    failures = []

    if endmill.diameter_mm <= 0:
        failures.append(f"diameter_mm ({endmill.diameter_mm}) <= 0")
    if endmill.flute_length_mm <= 0:
        failures.append(f"flute_length_mm ({endmill.flute_length_mm}) <= 0")

    status = Verdict.PASS if not failures else Verdict.FAIL

    return InvariantResult(
        id="MCH_ENDMILL_POSITIVE",
        category="structural",
        artifact="machine_config",
        description="diameter_mm > 0, flute_length_mm > 0",
        status=status,
        checked=2,
        passed=2 - len(failures),
        failed=len(failures),
        failures=tuple(failures),
    )


def validate_machine_config(
    machine: MachineConfig,
    endmill: Endmill | None = None,
) -> list[InvariantResult]:
    results = [
        check_mch_envelope_positive(machine),
        check_mch_wasteboard_fits(machine),
    ]

    if endmill:
        results.append(check_mch_effective_envelope_shrinks(machine, endmill))
        results.append(check_mch_endmill_positive(endmill))

    return results


__all__ = [
    "check_job_fits_machine",
    "check_sheet_fits_machine",
    "check_mch_envelope_positive",
    "check_mch_wasteboard_fits",
    "check_mch_effective_envelope_shrinks",
    "check_mch_endmill_positive",
    "validate_machine_config",
]
